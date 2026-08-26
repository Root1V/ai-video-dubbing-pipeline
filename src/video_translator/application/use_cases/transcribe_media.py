"""Caso de uso: TranscribeMediaUseCase.

Transcripcion standalone: solo transcribe audio/video en su idioma original,
sin traduccion ni doblaje. Reusa los mismos ports (`MediaProcessor`,
`Transcriber`, `SubtitleWriter`) que `TranslateVideoUseCase`, sin tocarlo ni a
`application/interfaces.py` -- es simplemente un flujo mas corto sobre la
misma arquitectura hexagonal.

A diferencia de `TranslateVideoUseCase`, acepta archivos de audio puro
(.mp3/.wav/.m4a/.flac) ademas de video: `MediaProcessor.extract_audio` invoca
ffmpeg con `-vn` (descarta video si lo hay), que funciona igual de bien sobre
un archivo que ya es solo audio.
"""

from __future__ import annotations

import time

from video_translator.application.interfaces import (
    MediaProcessor,
    SubtitleWriter,
    Summarizer,
    Transcriber,
)
from video_translator.domain.exceptions import InvalidVideoFileError, VideoTranslatorError
from video_translator.domain.models import (
    TranscribeMediaRequest,
    TranscribeMediaResult,
    TranslatedSegment,
)
from video_translator.utils.logging_config import get_logger
from video_translator.utils.timing import PipelineTimings

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm",
    ".mp3", ".wav", ".m4a", ".flac",
}

# Presupuesto de caracteres por llamada al LLM al resumir -- lo bastante chico
# para caber comodo en la ventana de contexto de modelos locales tipicos
# (8k-32k tokens), sin depender de contar tokens con precision (no hace falta
# para un chunking aproximado, a diferencia del batching de traduccion que si
# necesita alinear N->N lineas exactas).
_SUMMARY_CHUNK_CHARS = 8000


def _chunk_text(text: str, max_chars: int) -> list[str]:
    """Parte texto libre en fragmentos de hasta `max_chars`, cortando por
    palabra (no hace falta respetar oraciones: es solo para no exceder la
    ventana de contexto del LLM al resumir, a diferencia del batching de
    traduccion que si necesita alinear segmentos exactos)."""
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        current.append(word)
        current_len += len(word) + 1
        if current_len >= max_chars:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
    if current:
        chunks.append(" ".join(current))
    return chunks or [""]


def _summarize_transcript(
    summarizer: Summarizer, text: str, chunk_chars: int | None = None
) -> str:
    """Resume texto largo tipo map-reduce: si entra en un solo llamado al LLM
    se resume directo; si no, se resume cada fragmento por separado y luego
    se resumen esos resumenes parciales en uno final -- para que un video
    largo no termine resumido solo por sus primeros minutos.

    `chunk_chars` se resuelve en tiempo de llamada (no como valor por
    defecto del parametro) para que los tests puedan parchear
    `_SUMMARY_CHUNK_CHARS` a nivel de modulo y afectar corridas que no pasan
    el argumento explicitamente."""
    chunks = _chunk_text(text, chunk_chars or _SUMMARY_CHUNK_CHARS)
    if len(chunks) == 1:
        return summarizer.summarize(chunks[0])
    partial_summaries = [summarizer.summarize(chunk) for chunk in chunks]
    return summarizer.summarize("\n\n".join(partial_summaries))


class TranscribeMediaUseCase:
    def __init__(
        self,
        media_processor: MediaProcessor,
        transcriber: Transcriber,
        subtitle_writer: SubtitleWriter,
        summarizer: Summarizer | None = None,
        effective_config: dict | None = None,
    ) -> None:
        self._media = media_processor
        self._transcriber = transcriber
        self._subtitles = subtitle_writer
        self._summarizer = summarizer
        self._effective_config = dict(effective_config) if effective_config else {}

    def execute(self, request: TranscribeMediaRequest) -> TranscribeMediaResult:
        self._validate_request(request)
        request.output_dir.mkdir(parents=True, exist_ok=True)
        workdir = request.output_dir / "_work"
        workdir.mkdir(parents=True, exist_ok=True)

        report_path = request.output_dir / "pipeline_timings.json"
        timings = PipelineTimings(report_path=report_path)
        if self._effective_config:
            timings.set_effective_config(**self._effective_config)
        log = logger.bind(input=str(request.input_media), run_id=timings.run_id)
        log.info("transcribe.start")

        duration = self._media.get_duration_seconds(request.input_media)
        timings.set_input(request.input_media, duration)
        log.info("transcribe.duration_detected", seconds=round(duration, 1))

        audio_wav = workdir / "audio_16k_mono.wav"
        with timings.stage("audio_extraction"):
            self._media.extract_audio(request.input_media, audio_wav)
        log.info("transcribe.audio_extracted", path=str(audio_wav))

        start = time.monotonic()
        segments = list(
            self._transcriber.transcribe(audio_wav, language_hint=request.source_lang_hint)
        )
        timings.record("transcription", time.monotonic() - start, num_segments=len(segments))
        if not segments:
            raise VideoTranslatorError("La transcripcion no produjo ningun segmento de texto.")
        log.info("transcribe.transcription_done", num_segments=len(segments))

        transcript_srt = request.output_dir / "transcript.srt"
        transcript_text = request.output_dir / "transcript.txt"
        with timings.stage("transcript_writing"):
            # SubtitleWriter espera TranslatedSegment: se envuelve cada
            # TranscriptSegment con source_text == translated_text (no hay
            # traduccion en este flujo) para reusar el mismo escritor SRT sin
            # introducir un port nuevo solo para este caso.
            as_translated = [
                TranslatedSegment(
                    id=s.id, start=s.start, end=s.end,
                    source_text=s.text, translated_text=s.text, speaker_id=s.speaker_id,
                )
                for s in segments
            ]
            self._subtitles.write(as_translated, transcript_srt, use_translation=True)
            transcript_text.write_text(
                "\n".join(s.text for s in segments), encoding="utf-8"
            )
        log.info("transcribe.transcript_written", srt=str(transcript_srt), text=str(transcript_text))

        summary_text: str | None = None
        output_bytes = {
            "transcript_srt_bytes": transcript_srt.stat().st_size,
            "transcript_text_bytes": transcript_text.stat().st_size,
        }
        if request.include_summary:
            if self._summarizer is None:
                raise VideoTranslatorError(
                    "include_summary=True pero no se configuro un summarizer "
                    "(ver build_transcribe_media_use_case en container.py)."
                )
            with timings.stage("summarization"):
                summary_text = _summarize_transcript(
                    self._summarizer, "\n".join(s.text for s in segments)
                )
                summary_text_path = request.output_dir / "summary.txt"
                summary_text_path.write_text(summary_text, encoding="utf-8")
            log.info("transcribe.summary_written", path=str(summary_text_path))
            output_bytes["summary_text_bytes"] = summary_text_path.stat().st_size

        timings.set_outputs(**output_bytes)
        timings.write_report(report_path, final=True)
        log.info(
            "transcribe.finished",
            total_seconds=round(timings.total_seconds, 1),
            timings_report=str(report_path),
        )

        return TranscribeMediaResult(
            transcript_srt_path=transcript_srt,
            transcript_text_path=transcript_text,
            segments=segments,
            duration_seconds=duration,
            timings=timings.as_dict(),
            summary_text=summary_text,
        )

    @staticmethod
    def _validate_request(request: TranscribeMediaRequest) -> None:
        if not request.input_media.exists():
            raise InvalidVideoFileError(f"No existe el archivo: {request.input_media}")
        if request.input_media.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise InvalidVideoFileError(
                f"Extension no soportada '{request.input_media.suffix}'. "
                f"Soportadas: {sorted(SUPPORTED_EXTENSIONS)}"
            )
