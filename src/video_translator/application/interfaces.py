"""Puertos (interfaces) de la capa de aplicacion.

Siguiendo el principio de inversion de dependencias (Arquitectura Hexagonal / Clean
Architecture), la capa de aplicacion depende solo de estos Protocols, nunca de
implementaciones concretas (faster-whisper, ffmpeg, ollama, etc.). Esto permite:
  - Sustituir cualquier motor de IA sin tocar la logica de negocio.
  - Testear el caso de uso con dobles de prueba (mocks/fakes) triviales.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Protocol

from video_translator.domain.models import (
    DiarizationSegment,
    TranscriptSegment,
    TranslatedSegment,
    TranslationContext,
)


class MediaProcessor(Protocol):
    """Operaciones sobre el contenedor de video/audio (implementado con ffmpeg)."""

    def get_duration_seconds(self, media_path: Path) -> float: ...

    def extract_audio(self, video_path: Path, output_wav: Path) -> Path:
        """Extrae la pista de audio a WAV mono PCM, listo para el modelo de STT."""
        ...

    def extract_audio_clip(self, audio_path: Path, start: float, end: float, output_path: Path) -> Path:
        """Recorta un fragmento del audio (usado para armar clips de referencia por hablante)."""
        ...

    def burn_subtitles(self, video_path: Path, srt_path: Path, output_path: Path) -> Path:
        """Incrusta (quema) subtitulos en el video, no seleccionables/desactivables."""
        ...

    def attach_soft_subtitles(
        self, video_path: Path, srt_path: Path, output_path: Path, lang_code: str = "spa"
    ) -> Path:
        """Adjunta subtitulos como pista independiente y seleccionable."""
        ...

    def replace_audio_track(
        self,
        video_path: Path,
        new_audio_path: Path,
        output_path: Path,
        keep_original_as_secondary: bool = True,
    ) -> Path:
        """Reemplaza (o agrega como segunda pista) el audio del video con el doblaje."""
        ...


class Transcriber(Protocol):
    """Motor de Speech-to-Text (implementado con faster-whisper)."""

    def transcribe(
        self, audio_path: Path, language_hint: str | None = None
    ) -> Iterable[TranscriptSegment]:
        """Transcribe el audio devolviendo segmentos con timestamps."""
        ...


class Translator(Protocol):
    """Motor de traduccion asistido por LLM, sensible a contexto."""

    def translate_batch(
        self,
        segments: list[TranscriptSegment],
        context: TranslationContext,
        rolling_history: list[str],
    ) -> list[str]:
        """Traduce un lote de segmentos manteniendo coherencia con el historial reciente.

        Debe devolver exactamente ``len(segments)`` traducciones, en el mismo orden.
        """
        ...


class SpeechSynthesizer(Protocol):
    """Motor de Text-to-Speech para generar el doblaje (implementado con Coqui TTS)."""

    def synthesize_segment(
        self,
        text: str,
        output_path: Path,
        target_duration_seconds: float,
        speaker_reference_wav: Path | None = None,
        language: str = "es",
    ) -> Path:
        """Sintetiza voz para un segmento, ajustando el ritmo para encajar en el timing."""
        ...

    def concatenate_segments(
        self,
        segment_audio_paths: list[tuple[float, Path, float]],
        total_duration: float,
        output_path: Path,
    ) -> Path:
        """Compone la pista de audio final ubicando cada segmento en su timestamp.

        Cada tupla es ``(start_seconds, path, max_duration_seconds)``: la
        implementacion debe recortar cada clip a ``max_duration_seconds`` (el
        hueco real hasta el siguiente segmento) antes de mezclar, para
        garantizar que dos voces nunca se superponen en la pista final.
        """
        ...


class SubtitleWriter(Protocol):
    """Escritor de subtitulos (formato SRT)."""

    def write(self, segments: list[TranslatedSegment], output_path: Path, use_translation: bool) -> Path: ...


class SpeakerDiarizer(Protocol):
    """Deteccion de hablantes: quien habla y en que intervalos (implementado con pyannote.audio)."""

    def diarize(
        self, audio_path: Path, min_speakers: int | None = None, max_speakers: int | None = None
    ) -> list[DiarizationSegment]: ...


class GenderClassifier(Protocol):
    """Estima el genero de un hablante a partir de un clip de audio de referencia."""

    def classify(self, wav_path: Path) -> str:
        """Devuelve 'male', 'female' o 'unknown'."""
        ...
