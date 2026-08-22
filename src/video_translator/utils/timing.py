"""Medicion de tiempo por etapa del pipeline: observabilidad/trazabilidad.

Envuelve cada fase (extraccion de audio, transcripcion, diarizacion,
traduccion, sintesis, mezcla...) con un cronometro, deja un log estructurado
de inicio/fin de cada una, y al terminar produce un resumen (tabla en CLI +
reporte JSON persistido en el directorio de salida) para poder comparar
rendimiento entre corridas — sin esto, "por que tardo tanto" es una pregunta
sin respuesta accionable.
"""

from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from video_translator.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class StageTiming:
    name: str
    seconds: float
    metadata: dict = field(default_factory=dict)


class PipelineTimings:
    """Acumula la duracion de cada etapa durante UNA ejecucion del pipeline."""

    def __init__(self, run_id: str | None = None) -> None:
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self._stages: list[StageTiming] = []
        self._concurrent_groups: list[list[str]] = []
        self._run_start = time.monotonic()

    @contextmanager
    def stage(self, name: str, **metadata):
        """Cronometra un bloque de codigo como una etapa nombrada.

        Uso:
            with timings.stage("transcription"):
                ... trabajo real ...

        Cualquier ``metadata`` extra (p.ej. ``num_segments=39``) se loguea y
        se incluye en el reporte final, util para correlacionar duracion con
        volumen de trabajo entre corridas distintas.
        """
        log = logger.bind(run_id=self.run_id, stage=name, **metadata)
        log.info("pipeline.stage_started")
        start = time.monotonic()
        try:
            yield
        finally:
            elapsed = time.monotonic() - start
            self._stages.append(StageTiming(name=name, seconds=elapsed, metadata=metadata))
            log.info("pipeline.stage_finished", seconds=round(elapsed, 2))

    def record(self, name: str, seconds: float, **metadata) -> None:
        """Registra una duracion ya medida externamente (p.ej. una etapa que
        corrio en un hilo aparte, cronometrada a mano)."""
        self._stages.append(StageTiming(name=name, seconds=seconds, metadata=metadata))
        logger.bind(run_id=self.run_id, stage=name, **metadata).info(
            "pipeline.stage_finished", seconds=round(seconds, 2)
        )

    def mark_concurrent(self, stage_names: list[str]) -> None:
        """Anota que estas etapas corrieron EN PARALELO (mismo tramo de
        tiempo real), para que el reporte final no de a entender que sus
        duraciones se suman al tiempo total — se solapan."""
        self._concurrent_groups.append(list(stage_names))

    @property
    def total_seconds(self) -> float:
        return time.monotonic() - self._run_start

    def as_dict(self) -> dict:
        total = self.total_seconds
        return {
            "run_id": self.run_id,
            "total_seconds": round(total, 2),
            "concurrent_stage_groups": self._concurrent_groups,
            "stages": [
                {
                    "name": s.name,
                    "seconds": round(s.seconds, 2),
                    "percent_of_total": round(100 * s.seconds / total, 1) if total > 0 else 0.0,
                    **s.metadata,
                }
                for s in self._stages
            ],
        }

    def write_report(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return output_path
