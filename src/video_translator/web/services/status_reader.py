"""Lee el progreso de un proyecto: primero intenta `pipeline_timings.json` en
disco (escrito incrementalmente por `PipelineTimings`, ver `utils/timing.py`),
y si no existe o esta corrupto/a medio escribir, cae al `status` de la fila
en base de datos.

En M1 la tarea Celery es un stub que nunca escribe ese archivo, asi que esta
funcion siempre cae al fallback de BD -- pero la logica de lectura de disco ya
esta completa para que M2 (tarea Celery real) no necesite tocar este archivo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from video_translator.web.db.models import Project, ProjectStatus


def read_project_status(project: Project) -> dict[str, Any]:
    timings_path = Path(project.output_dir) / "pipeline_timings.json"
    timings = _read_timings_file(timings_path)
    if timings is not None:
        return {
            "db_status": project.status,
            "run_id": timings.get("run_id"),
            "completed": bool(timings.get("completed")),
            "current_stage": timings.get("current_stage"),
            "stages": timings.get("stages"),
            "total_seconds": timings.get("total_seconds"),
            "realtime_factor": timings.get("realtime_factor"),
            "warnings": timings.get("warnings"),
        }

    return {
        "db_status": project.status,
        "run_id": None,
        "completed": project.status == ProjectStatus.COMPLETED or None,
        "current_stage": None,
        "stages": None,
        "total_seconds": None,
        "realtime_factor": None,
        "warnings": None,
    }


def read_full_timings_report(project: Project) -> dict[str, Any] | None:
    """Lee `pipeline_timings.json` completo, sin descartar `effective_config`/
    `stats`/`outputs` como hace `read_project_status` (que solo expone lo
    necesario para el polling de progreso en vivo). Usado por
    `web/tasks/run_project.py` al finalizar una corrida para persistir una
    foto de metricas de negocio (ver `db/models.py::ProjectMetrics`). None si
    el archivo no existe o esta corrupto -- p.ej. una corrida que fallo antes
    de escribir ninguna etapa."""
    timings_path = Path(project.output_dir) / "pipeline_timings.json"
    return _read_timings_file(timings_path)


def _read_timings_file(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data
