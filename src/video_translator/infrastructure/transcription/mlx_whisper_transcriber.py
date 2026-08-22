"""Implementacion de Transcriber usando mlx-whisper (framework MLX de Apple).

Alternativa a faster-whisper para transcribir en la GPU de Apple Silicon via
Metal. CTranslate2 (el motor de faster-whisper) no soporta Metal/MPS: en Mac
esta limitado a CPU sin importar la configuracion. mlx-whisper si corre en
GPU, y en chips M-series suele ser varias veces mas rapido que CTranslate2 en
CPU para el mismo modelo (large-v3).

Solo disponible en macOS con Apple Silicon (extra "transcription-mlx").
Instalacion: pip install "video-translator[transcription-mlx]"
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from pathlib import Path

from video_translator.domain.exceptions import TranscriptionError
from video_translator.domain.models import TranscriptSegment
from video_translator.utils.logging_config import get_logger
from video_translator.utils.warning_collector import note_stat

logger = get_logger(__name__)


class MlxWhisperTranscriber:
    def __init__(self, model_repo: str = "mlx-community/whisper-large-v3-mlx") -> None:
        self._model_repo = model_repo

    def transcribe(
        self, audio_path: Path, language_hint: str | None = None
    ) -> Iterable[TranscriptSegment]:
        try:
            import mlx_whisper
        except ImportError as exc:  # pragma: no cover
            raise TranscriptionError(
                "mlx-whisper no esta instalado. Ejecuta: "
                'pip install "video-translator[transcription-mlx]" (solo macOS/Apple Silicon).'
            ) from exc

        logger.info("mlx_whisper.loading_model", model_repo=self._model_repo)
        t0 = time.monotonic()
        try:
            result = mlx_whisper.transcribe(
                str(audio_path),
                path_or_hf_repo=self._model_repo,
                language=language_hint,
                condition_on_previous_text=True,
            )
        except Exception as exc:  # reempaquetamos cualquier fallo del motor
            raise TranscriptionError(f"Fallo transcribiendo '{audio_path}': {exc}") from exc
        # mlx-whisper no separa carga de modelo e inferencia (transcribe()
        # hace ambas en una sola llamada): se reporta el tiempo combinado.
        note_stat("transcription.model_load_and_inference_seconds", round(time.monotonic() - t0, 2))

        language = result.get("language", language_hint or "en")
        logger.info("mlx_whisper.detected_language", language=language)
        note_stat("transcription.detected_language", language)

        for i, seg in enumerate(result.get("segments", [])):
            text = seg["text"].strip()
            if not text:
                continue
            yield TranscriptSegment(
                id=i,
                start=seg["start"],
                end=seg["end"],
                text=text,
                language=language,
            )
