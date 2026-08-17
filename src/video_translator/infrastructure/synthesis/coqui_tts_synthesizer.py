"""Implementacion alternativa de SpeechSynthesizer usando Coqui TTS (modelo XTTS v2).

Se mantiene como opcion mas liviana/facil de instalar frente a IndexTTS-2.5
(pip install directo, sin clonar repos ni descargar checkpoints manualmente).
XTTS v2 tambien hace clonacion de voz zero-shot multilingue, pero no tiene
control nativo de duracion: aqui el ajuste de ritmo se hace enteramente con
ffmpeg (atempo) despues de generar, via el modulo compartido ``audio_mixing``.
Para doblaje con mejor sincronizacion y calidad, preferir IndexTTS-2.5.

Requiere Python < 3.12 (ver pyproject.toml, extra "dubbing").
"""

from __future__ import annotations

from pathlib import Path

from video_translator.domain.exceptions import SynthesisError
from video_translator.infrastructure.synthesis.audio_mixing import (
    concatenate_segments,
    fit_to_duration,
)
from video_translator.utils.logging_config import get_logger

logger = get_logger(__name__)


class CoquiTTSSynthesizer:
    def __init__(
        self,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        device: str = "cuda",
        ffmpeg_binary: str = "ffmpeg",
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._ffmpeg = ffmpeg_binary
        self._tts = None  # carga perezosa

    def _load(self):
        if self._tts is None:
            try:
                from TTS.api import TTS
            except ImportError as exc:  # pragma: no cover
                raise SynthesisError(
                    "Coqui TTS no esta instalado. Ejecuta: pip install 'video-translator[dubbing]' "
                    "(requiere Python < 3.12)."
                ) from exc
            logger.info("tts.loading_model", model=self._model_name, device=self._device)
            self._tts = TTS(self._model_name).to(self._device)
        return self._tts

    def synthesize_segment(
        self,
        text: str,
        output_path: Path,
        target_duration_seconds: float,
        speaker_reference_wav: Path | None = None,
        language: str = "es",
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tts = self._load()
        try:
            tts.tts_to_file(
                text=text,
                file_path=str(output_path),
                speaker_wav=str(speaker_reference_wav) if speaker_reference_wav else None,
                language=language,
            )
        except Exception as exc:  # noqa: BLE001
            raise SynthesisError(f"Fallo sintetizando segmento: {exc}") from exc

        fit_to_duration(output_path, target_duration_seconds, ffmpeg_binary=self._ffmpeg)
        return output_path

    def concatenate_segments(
        self, segment_audio_paths: list[tuple[float, Path, float]], total_duration: float, output_path: Path
    ) -> Path:
        return concatenate_segments(
            segment_audio_paths, total_duration, output_path, ffmpeg_binary=self._ffmpeg
        )
