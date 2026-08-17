"""Caso de uso: TranslateVideoUseCase.

Orquesta el pipeline completo:
  1. Validar entrada
  2. Extraer audio (MediaProcessor)
  3. Transcribir (Transcriber)
  4. (Opcional) Diarizar hablantes (SpeakerDiarizer) + estimar genero (GenderClassifier)
     y construir un perfil por hablante (clip de referencia de voz)
  5. Traducir por lotes con contexto, historial e info de hablante/genero (Translator)
  6. Generar subtitulos SRT (SubtitleWriter)
  7. (Opcional) Sintetizar doblaje por hablante (SpeechSynthesizer) y mezclar con el video
  8. (Opcional) Incrustar/adjuntar subtitulos al video final (MediaProcessor)

Esta clase depende exclusivamente de los Protocols definidos en
``application.interfaces``, nunca de implementaciones concretas: se le inyectan
por constructor (Dependency Injection), lo que la hace facilmente testeable y
permite intercambiar motores de IA sin modificar esta logica de negocio.
"""

from __future__ import annotations

from pathlib import Path

from video_translator.application.interfaces import (
    GenderClassifier,
    MediaProcessor,
    SpeakerDiarizer,
    SpeechSynthesizer,
    SubtitleWriter,
    Transcriber,
    Translator,
)
from video_translator.domain.exceptions import InvalidVideoFileError, VideoTranslatorError
from video_translator.domain.models import (
    OutputMode,
    SpeakerProfile,
    TranscriptSegment,
    TranslatedSegment,
    TranslateVideoRequest,
    TranslateVideoResult,
)
from video_translator.utils.diarization_alignment import (
    assign_speakers,
    select_reference_windows,
    unique_speaker_labels,
)
from video_translator.utils.logging_config import get_logger
from video_translator.utils.text_batching import batch_segments

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}


class TranslateVideoUseCase:
    def __init__(
        self,
        media_processor: MediaProcessor,
        transcriber: Transcriber,
        translator: Translator,
        subtitle_writer: SubtitleWriter,
        speech_synthesizer: SpeechSynthesizer | None = None,
        speaker_diarizer: SpeakerDiarizer | None = None,
        gender_classifier: GenderClassifier | None = None,
        translation_batch_max_chars: int = 1800,
        context_window_segments: int = 6,
    ) -> None:
        self._media = media_processor
        self._transcriber = transcriber
        self._translator = translator
        self._subtitles = subtitle_writer
        self._synthesizer = speech_synthesizer
        self._diarizer = speaker_diarizer
        self._gender_classifier = gender_classifier
        self._batch_max_chars = translation_batch_max_chars
        self._context_window = context_window_segments

    def execute(self, request: TranslateVideoRequest) -> TranslateVideoResult:
        self._validate_request(request)
        request.output_dir.mkdir(parents=True, exist_ok=True)
        workdir = request.output_dir / "_work"
        workdir.mkdir(parents=True, exist_ok=True)

        log = logger.bind(input=str(request.input_video))
        log.info("pipeline.start")

        duration = self._media.get_duration_seconds(request.input_video)
        log.info("pipeline.duration_detected", seconds=round(duration, 1))

        # 1. Extraccion de audio
        audio_wav = workdir / "audio_16k_mono.wav"
        self._media.extract_audio(request.input_video, audio_wav)
        log.info("pipeline.audio_extracted", path=str(audio_wav))

        # 2. Transcripcion (maneja internamente audios largos via VAD/streaming)
        segments = list(
            self._transcriber.transcribe(audio_wav, language_hint=request.source_lang_hint)
        )
        if not segments:
            raise VideoTranslatorError("La transcripcion no produjo ningun segmento de texto.")
        log.info("pipeline.transcription_done", num_segments=len(segments))

        # 3. Diarizacion opcional: quien habla cuando, y perfil (voz + genero) por hablante
        speaker_profiles: list[SpeakerProfile] = []
        if request.diarize:
            segments, speaker_profiles = self._diarize_and_build_profiles(
                request, segments, audio_wav, workdir, log
            )
            request.context.speaker_genders = {
                p.speaker_id: p.gender for p in speaker_profiles if p.gender
            }

        # 4. Traduccion por lotes, con contexto de usuario + historial rodante
        translated_segments: list[TranslatedSegment] = []
        rolling_history: list[str] = []
        batches = batch_segments(segments, max_chars=self._batch_max_chars)
        log.info("pipeline.translation_batches", num_batches=len(batches))

        for i, batch in enumerate(batches, start=1):
            translations = self._translator.translate_batch(
                segments=batch,
                context=request.context,
                rolling_history=rolling_history[-self._context_window :],
            )
            if len(translations) != len(batch):
                raise VideoTranslatorError(
                    f"El traductor devolvio {len(translations)} lineas para un lote de "
                    f"{len(batch)} segmentos (lote {i}/{len(batches)})."
                )
            for seg, text in zip(batch, translations):
                translated_segments.append(
                    TranslatedSegment(
                        id=seg.id,
                        start=seg.start,
                        end=seg.end,
                        source_text=seg.text,
                        translated_text=text,
                        speaker_id=seg.speaker_id,
                    )
                )
                rolling_history.append(text)
            log.info("pipeline.batch_translated", batch=i, of=len(batches))

        # 5. Subtitulos
        srt_es = request.output_dir / "subtitles.es.srt"
        srt_en = request.output_dir / "subtitles.en.srt"
        self._subtitles.write(translated_segments, srt_es, use_translation=True)
        self._subtitles.write(translated_segments, srt_en, use_translation=False)
        log.info("pipeline.subtitles_written", es=str(srt_es), en=str(srt_en))

        output_video: Path | None = None

        if request.output_mode == OutputMode.BURN_SUBTITLES:
            output_video = request.output_dir / "video.dubbed_subs.mp4"
            self._media.burn_subtitles(request.input_video, srt_es, output_video)

        elif request.output_mode == OutputMode.SOFT_SUBTITLES:
            output_video = request.output_dir / "video.soft_subs.mp4"
            self._media.attach_soft_subtitles(request.input_video, srt_es, output_video)

        elif request.output_mode == OutputMode.DUBBED:
            if self._synthesizer is None:
                raise VideoTranslatorError(
                    "OutputMode.DUBBED requiere un SpeechSynthesizer configurado "
                    "(instala un extra de doblaje y configura TTS_BACKEND)."
                )
            output_video = self._render_dubbed_video(
                request, translated_segments, speaker_profiles, duration, workdir, log
            )

        # OutputMode.SUBTITLES_ONLY -> no se genera video, solo los .srt

        log.info("pipeline.finished", output_video=str(output_video) if output_video else None)

        return TranslateVideoResult(
            output_video=output_video,
            subtitles_source_path=srt_en,
            subtitles_target_path=srt_es,
            segments=translated_segments,
            duration_seconds=duration,
            speakers=speaker_profiles,
        )

    def _diarize_and_build_profiles(
        self,
        request: TranslateVideoRequest,
        segments: list[TranscriptSegment],
        audio_wav: Path,
        workdir: Path,
        log,
    ) -> tuple[list[TranscriptSegment], list[SpeakerProfile]]:
        assert self._diarizer is not None, (
            "request.diarize=True requiere un SpeakerDiarizer configurado "
            "(instala 'diarization' y define HF_TOKEN)."
        )
        diarization_segments = self._diarizer.diarize(
            audio_wav, min_speakers=request.min_speakers, max_speakers=request.max_speakers
        )
        labels = unique_speaker_labels(diarization_segments)
        log.info("pipeline.diarization_done", num_speakers=len(labels), speakers=labels)

        segments_with_speakers = assign_speakers(segments, diarization_segments)

        # Clip de referencia de voz por hablante (para clonacion en doblaje) + genero estimado.
        reference_dir = workdir / "speaker_references"
        reference_dir.mkdir(parents=True, exist_ok=True)
        windows = select_reference_windows(diarization_segments)

        profiles: list[SpeakerProfile] = []
        for label in labels:
            window = windows.get(label)
            reference_wav: Path | None = None
            gender: str | None = None
            if window is not None:
                start, end = window
                reference_wav = reference_dir / f"{label}.wav"
                self._media.extract_audio_clip(audio_wav, start, end, reference_wav)
                if self._gender_classifier is not None:
                    gender = self._gender_classifier.classify(reference_wav)
            else:
                log.warning("pipeline.speaker_reference_too_short", speaker=label)
            profiles.append(SpeakerProfile(speaker_id=label, gender=gender, reference_wav=reference_wav))

        log.info(
            "pipeline.speaker_profiles_built",
            profiles=[(p.speaker_id, p.gender, bool(p.reference_wav)) for p in profiles],
        )
        return segments_with_speakers, profiles

    def _render_dubbed_video(
        self,
        request: TranslateVideoRequest,
        translated_segments: list[TranslatedSegment],
        speaker_profiles: list[SpeakerProfile],
        duration: float,
        workdir: Path,
        log,
    ) -> Path:
        assert self._synthesizer is not None
        segment_dir = workdir / "tts_segments"
        segment_dir.mkdir(parents=True, exist_ok=True)

        reference_by_speaker: dict[str, Path] = {
            p.speaker_id: p.reference_wav for p in speaker_profiles if p.reference_wav is not None
        }

        rendered: list[tuple[float, Path, float]] = []
        for i, seg in enumerate(translated_segments):
            seg_path = segment_dir / f"seg_{seg.id:06d}.wav"
            # Si el segmento tiene hablante identificado y su clip de referencia
            # esta disponible, se clona su voz individual; si no, se cae al
            # --speaker-wav unico provisto (o None, voz generica del modelo).
            speaker_wav = (
                reference_by_speaker.get(seg.speaker_id) if seg.speaker_id else None
            ) or request.speaker_reference_wav

            # Hueco real disponible hasta que empiece el SIGUIENTE segmento (o
            # hasta el final del video, para el ultimo). Se calcula ANTES de
            # sintetizar y se usa como objetivo de duracion del propio TTS
            # (no la duracion original de la transcripcion): asi el control
            # nativo de duracion del modelo, y el ajuste fino de velocidad
            # despues, apuntan desde el principio al limite real, en vez de
            # enterarse recien al mezclar que el clip no entraba. El recorte
            # duro en concatenate_segments queda como ultimo recurso, no como
            # el mecanismo principal.
            next_start = translated_segments[i + 1].start if i + 1 < len(translated_segments) else duration
            max_duration = max(0.05, next_start - seg.start)

            self._synthesizer.synthesize_segment(
                text=seg.translated_text,
                output_path=seg_path,
                target_duration_seconds=max_duration,
                speaker_reference_wav=speaker_wav,
                language=request.context.target_lang,
            )
            rendered.append((seg.start, seg_path, max_duration))
        log.info("pipeline.tts_done", num_segments=len(rendered))

        dubbed_audio = workdir / "dubbed_audio.wav"
        self._synthesizer.concatenate_segments(rendered, duration, dubbed_audio)

        output_video = request.output_dir / "video.dubbed.mp4"
        self._media.replace_audio_track(
            request.input_video,
            dubbed_audio,
            output_video,
            keep_original_as_secondary=request.keep_original_audio_track,
        )
        return output_video

    @staticmethod
    def _validate_request(request: TranslateVideoRequest) -> None:
        if not request.input_video.exists():
            raise InvalidVideoFileError(f"No existe el archivo: {request.input_video}")
        if request.input_video.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise InvalidVideoFileError(
                f"Extension no soportada '{request.input_video.suffix}'. "
                f"Soportadas: {sorted(SUPPORTED_EXTENSIONS)}"
            )
