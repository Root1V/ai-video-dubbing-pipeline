"""Implementacion de SpeakerDiarizer que delega en un proceso aislado.

En vez de importar pyannote.audio en el mismo proceso/venv que el resto de
video-translator, invoca scripts/diarization_worker.py con el interprete de
un venv separado (ver scripts/setup_diarization_env.sh) y parsea su salida
JSON. Esto evita un conflicto real de dependencias entre pyannote.audio
(protobuf>=5.0 via pyannoteai-sdk) e IndexTTS-2.5 (protobuf<3.20 via
descript-audiotools) que no tiene solucion posible dentro de un solo entorno.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from video_translator.domain.exceptions import DiarizationError
from video_translator.domain.models import DiarizationSegment
from video_translator.utils.logging_config import get_logger

logger = get_logger(__name__)


class SubprocessDiarizer:
    def __init__(
        self,
        python_bin: str = ".venv-diarization/bin/python",
        worker_script: str = "scripts/diarization_worker.py",
        model_name: str = "pyannote/speaker-diarization-community-1",
        hf_token: str | None = None,
        device: str = "cpu",
        dyld_library_path: str | None = None,
    ) -> None:
        self._python_bin = python_bin
        self._worker_script = worker_script
        self._model_name = model_name
        self._hf_token = hf_token
        self._device = device
        self._dyld_library_path = dyld_library_path

    def diarize(
        self, audio_path: Path, min_speakers: int | None = None, max_speakers: int | None = None
    ) -> list[DiarizationSegment]:
        self._check_worker_available()
        if not self._hf_token:
            raise DiarizationError(
                "Se requiere HF_TOKEN para descargar el modelo de diarizacion "
                "(acepta los terminos en https://hf.co/"
                f"{self._model_name} y crea un token en hf.co/settings/tokens)."
            )

        cmd = [
            self._python_bin, self._worker_script, "diarize", str(audio_path),
            "--model", self._model_name,
            "--device", self._device,
        ]
        if min_speakers is not None:
            cmd += ["--min-speakers", str(min_speakers)]
        if max_speakers is not None:
            cmd += ["--max-speakers", str(max_speakers)]

        env = self._build_subprocess_env()

        logger.info("diarization.subprocess_start", model=self._model_name)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, check=True)
        except subprocess.CalledProcessError as exc:
            raise DiarizationError(
                f"El proceso de diarizacion aislado fallo: {exc.stderr or exc.stdout}"
            ) from exc
        except FileNotFoundError as exc:
            raise DiarizationError(
                f"No se encontro el interprete '{self._python_bin}'. Ejecuta: "
                "./scripts/setup_diarization_env.sh"
            ) from exc

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise DiarizationError(
                f"Salida invalida del proceso de diarizacion: {result.stdout[:500]!r}"
            ) from exc

        if "error" in data:
            raise DiarizationError(f"Fallo en el proceso de diarizacion: {data['error']}")

        segments = [
            DiarizationSegment(start=s["start"], end=s["end"], speaker_label=s["speaker_label"])
            for s in data.get("segments", [])
        ]
        num_speakers = len({s.speaker_label for s in segments})
        logger.info("diarization.done", num_turns=len(segments), num_speakers=num_speakers)
        return segments

    def _build_subprocess_env(self) -> dict[str, str]:
        """Construye el entorno SOLO para el subprocess del worker de diarizacion.

        DYLD_LIBRARY_PATH (macOS, fix del bug de torchcodec/Homebrew, ver
        README) se agrega unicamente aqui — nunca se modifica os.environ del
        proceso principal, porque esa variable afecta a CUALQUIER binario que
        la herede, incluido el ffmpeg/ffprobe de Homebrew que usa el resto del
        proyecto. Si se exportara globalmente en la terminal, rompe el ffmpeg
        del proceso principal (ha pasado: error 'Symbol not found: _iconv').
        """
        env = dict(os.environ)
        env["HF_TOKEN"] = self._hf_token
        env["HUGGING_FACE_HUB_TOKEN"] = self._hf_token
        if self._dyld_library_path:
            existing = env.get("DYLD_LIBRARY_PATH", "")
            env["DYLD_LIBRARY_PATH"] = (
                f"{self._dyld_library_path}:{existing}" if existing else self._dyld_library_path
            )
        return env

    def _check_worker_available(self) -> None:
        if not Path(self._python_bin).exists():
            raise DiarizationError(
                f"No se encontro el entorno aislado de diarizacion ('{self._python_bin}'). "
                "Ejecuta: ./scripts/setup_diarization_env.sh"
            )
