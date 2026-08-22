"""Implementacion de Transcriber usando faster-whisper (CTranslate2).

faster-whisper es una reimplementacion open source de OpenAI Whisper sobre el
runtime CTranslate2: hasta 4x mas rapido y con menor uso de memoria que el
Whisper original, soportando de forma nativa audios largos mediante deteccion
de voz (VAD) interna, lo que evita tener que trocear manualmente el audio.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterable

from video_translator.domain.exceptions import TranscriptionError
from video_translator.domain.models import TranscriptSegment
from video_translator.utils.logging_config import get_logger
from video_translator.utils.warning_collector import note_stat

logger = get_logger(__name__)


class FasterWhisperTranscriber:
    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "float16",
        beam_size: int = 5,
        vad_filter: bool = True,
        cpu_threads: int = 0,
        num_workers: int = 1,
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._beam_size = beam_size
        self._vad_filter = vad_filter
        # 0 = usar todos los nucleos disponibles (CTranslate2 interpreta 0
        # como "auto"). En CPU (p.ej. Mac sin CUDA) esto es el ajuste de
        # rendimiento de mayor impacto para la transcripcion: por defecto
        # CTranslate2 no siempre satura todos los nucleos de la maquina.
        self._cpu_threads = cpu_threads if cpu_threads > 0 else (os.cpu_count() or 4)
        self._num_workers = num_workers
        self._model = None  # carga perezosa: evita cargar pesos si no se usa

    def _load_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:  # pragma: no cover
                raise TranscriptionError(
                    "faster-whisper no esta instalado. Ejecuta: pip install faster-whisper"
                ) from exc
            logger.info(
                "whisper.loading_model",
                model_size=self._model_size,
                device=self._device,
                compute_type=self._compute_type,
                cpu_threads=self._cpu_threads,
                num_workers=self._num_workers,
            )
            t0 = time.monotonic()
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
                cpu_threads=self._cpu_threads,
                num_workers=self._num_workers,
            )
            # Coste de infraestructura vs inferencia: en corridas cortas puede
            # ser una fraccion relevante de la etapa de transcripcion.
            note_stat("transcription.model_load_seconds", round(time.monotonic() - t0, 2))
        return self._model

    def transcribe(
        self, audio_path: Path, language_hint: str | None = None
    ) -> Iterable[TranscriptSegment]:
        model = self._load_model()
        try:
            segments_iter, info = model.transcribe(
                str(audio_path),
                language=language_hint,
                beam_size=self._beam_size,
                vad_filter=self._vad_filter,
                vad_parameters={"min_silence_duration_ms": 500},
                condition_on_previous_text=True,
            )
        except Exception as exc:  # noqa: BLE001 - reempaquetamos cualquier fallo del motor
            raise TranscriptionError(f"Fallo transcribiendo '{audio_path}': {exc}") from exc

        logger.info(
            "whisper.detected_language",
            language=info.language,
            probability=round(info.language_probability, 3),
        )
        note_stat("transcription.detected_language", info.language)
        note_stat("transcription.language_probability", round(info.language_probability, 3))

        for i, seg in enumerate(segments_iter):
            text = seg.text.strip()
            if not text:
                continue
            yield TranscriptSegment(
                id=i,
                start=seg.start,
                end=seg.end,
                text=text,
                language=info.language,
            )
