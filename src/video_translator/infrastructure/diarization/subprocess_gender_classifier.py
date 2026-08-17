"""Implementacion de GenderClassifier que delega en el mismo proceso aislado
usado para diarizacion (ver subprocess_diarizer.py y diarization_worker.py).

librosa en si no choca con IndexTTS-2.5, pero como solo se usa junto con
diarizacion (para estimar el genero de cada hablante detectado), vive en el
mismo entorno aislado por simplicidad: un unico venv extra para toda la
funcionalidad de "quien habla y que genero estimado tiene", en vez de dos.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from video_translator.domain.exceptions import DiarizationError
from video_translator.utils.logging_config import get_logger

logger = get_logger(__name__)


class SubprocessGenderClassifier:
    def __init__(
        self,
        python_bin: str = ".venv-diarization/bin/python",
        worker_script: str = "scripts/diarization_worker.py",
    ) -> None:
        self._python_bin = python_bin
        self._worker_script = worker_script

    def classify(self, wav_path: Path) -> str:
        if not Path(self._python_bin).exists():
            raise DiarizationError(
                f"No se encontro el entorno aislado de diarizacion ('{self._python_bin}'). "
                "Ejecuta: ./scripts/setup_diarization_env.sh"
            )
        cmd = [self._python_bin, self._worker_script, "gender", str(wav_path)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as exc:
            logger.warning("gender_classifier.subprocess_failed", error=exc.stderr)
            return "unknown"
        except FileNotFoundError:
            return "unknown"

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return "unknown"
        return data.get("gender", "unknown")
