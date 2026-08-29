"""Caso de uso: GenerateMicroVideoUseCase.

Genera un micro-video vertical para redes sociales a partir de una imagen y
un texto: la imagen queda de fondo con un efecto Ken Burns (zoom lento), el
texto se narra con TTS (mismo `SpeechSynthesizer`/particionado en fragmentos
que `SynthesizeTextUseCase`) y se incrusta como captions sincronizados con la
narracion. No usa ningun modelo de generacion de imagen/video -- toda la
composicion es ffmpeg (`MediaProcessor`), ver RM-14 en docs/roadmap.md para
la alternativa con video generado por IA (RM-22).
"""

from __future__ import annotations

from pathlib import Path

from video_translator.application.interfaces import (
    MediaProcessor,
    SpeechSynthesizer,
    SubtitleWriter,
)
from video_translator.application.use_cases.text_chunking import split_into_chunks
from video_translator.domain.exceptions import InvalidVideoFileError, VideoTranslatorError
from video_translator.domain.models import (
    GenerateMicroVideoRequest,
    GenerateMicroVideoResult,
    TranslatedSegment,
)
from video_translator.utils.logging_config import get_logger
from video_translator.utils.timing import PipelineTimings

logger = get_logger(__name__)

DEFAULT_MAX_CHUNK_CHARS = 500
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920


class GenerateMicroVideoUseCase:
    def __init__(
        self,
        speech_synthesizer: SpeechSynthesizer,
        media_processor: MediaProcessor,
        subtitle_writer: SubtitleWriter,
        default_speaker_reference_wav: Path,
        max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
        effective_config: dict | None = None,
    ) -> None:
        self._synthesizer = speech_synthesizer
        self._media = media_processor
        self._subtitles = subtitle_writer
        self._default_speaker_wav = default_speaker_reference_wav
        self._max_chunk_chars = max_chunk_chars
        self._effective_config = dict(effective_config) if effective_config else {}

    def execute(self, request: GenerateMicroVideoRequest) -> GenerateMicroVideoResult:
        self._validate_request(request)
        request.output_dir.mkdir(parents=True, exist_ok=True)
        workdir = request.output_dir / "_work"
        chunk_dir = workdir / "tts_chunks"
        chunk_dir.mkdir(parents=True, exist_ok=True)

        report_path = request.output_dir / "pipeline_timings.json"
        timings = PipelineTimings(report_path=report_path)
        if self._effective_config:
            timings.set_effective_config(**self._effective_config)
        log = logger.bind(run_id=timings.run_id)
        log.info("generate_micro_video.start", chars=len(request.text))

        speaker_wav = request.speaker_reference_wav or self._default_speaker_wav

        chunks = split_into_chunks(request.text, self._max_chunk_chars)
        segments: list[tuple[float, Path, float]] = []
        cursor = 0.0
        with timings.stage("text_to_speech", num_chunks=len(chunks)):
            for i, chunk_text in enumerate(chunks):
                chunk_path = chunk_dir / f"chunk_{i:03d}.wav"
                self._synthesizer.synthesize_segment(
                    text=chunk_text,
                    output_path=chunk_path,
                    target_duration_seconds=0.0,
                    speaker_reference_wav=speaker_wav,
                    language=request.language,
                )
                chunk_duration = self._media.get_duration_seconds(chunk_path)
                segments.append((cursor, chunk_path, chunk_duration))
                cursor += chunk_duration
        log.info("generate_micro_video.narration_done", num_chunks=len(chunks))

        narration_path = workdir / "narration.wav"
        with timings.stage("audio_concatenation"):
            self._synthesizer.concatenate_segments(segments, cursor, narration_path)

        caption_segments = [
            TranslatedSegment(
                id=i,
                start=start,
                end=start + duration,
                source_text=chunk_text,
                translated_text=chunk_text,
            )
            for i, (chunk_text, (start, _path, duration)) in enumerate(zip(chunks, segments))
        ]
        captions_path = workdir / "captions.srt"
        with timings.stage("caption_writing"):
            self._subtitles.write(caption_segments, captions_path, use_translation=True)

        background_path = workdir / "background.mp4"
        with timings.stage("image_to_video"):
            self._media.render_image_video(
                request.image_path,
                narration_path,
                background_path,
                duration_seconds=cursor,
                width=VIDEO_WIDTH,
                height=VIDEO_HEIGHT,
            )

        output_video = request.output_dir / "micro_video.mp4"
        with timings.stage("caption_burn"):
            self._media.burn_subtitles(background_path, captions_path, output_video)

        timings.set_outputs(video_bytes=output_video.stat().st_size)
        timings.write_report(report_path, final=True)
        log.info(
            "generate_micro_video.finished",
            total_seconds=round(timings.total_seconds, 1),
            timings_report=str(report_path),
        )

        return GenerateMicroVideoResult(
            output_video=output_video,
            duration_seconds=cursor,
            timings=timings.as_dict(),
        )

    @staticmethod
    def _validate_request(request: GenerateMicroVideoRequest) -> None:
        if not request.text.strip():
            raise VideoTranslatorError("El texto a narrar esta vacio.")
        if not request.image_path.exists():
            raise InvalidVideoFileError(f"No existe el archivo: {request.image_path}")
        if request.image_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            raise InvalidVideoFileError(
                f"Extension de imagen no soportada '{request.image_path.suffix}'. "
                f"Soportadas: {sorted(SUPPORTED_IMAGE_EXTENSIONS)}"
            )
