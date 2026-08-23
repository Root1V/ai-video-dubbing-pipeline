"""Tarea Celery que procesa un proyecto llamando al pipeline real.

Replica el flujo de `cli.py::translate`: construye `Settings`/
`TranslateVideoRequest` via `project_mapper`, llama
`TranslateVideoUseCase.execute()`, y refleja el resultado en el estado del
proyecto. El progreso en vivo NO pasa por aqui -- lo lee
`services.status_reader` directamente de `pipeline_timings.json`, que
`PipelineTimings` ya escribe de forma incremental (ver `utils/timing.py`);
esta tarea solo necesita marcar running/completed/failed en la fila de BD.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from celery import Task

from video_translator.domain.exceptions import VideoTranslatorError
from video_translator.web.db.models import Project, ProjectStatus
from video_translator.web.db.session import SessionLocal
from video_translator.web.services.project_mapper import build_use_case_and_request
from video_translator.web.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="video_translator.web.run_project")
def run_dubbing_project(self: Task, project_id: str, resume: bool = False) -> None:
    session = SessionLocal()
    try:
        project = session.get(Project, uuid.UUID(project_id))
        if project is None:
            return
        try:
            project.status = ProjectStatus.RUNNING
            project.started_at = datetime.now(timezone.utc)
            project.error_message = None
            session.commit()

            use_case, request = build_use_case_and_request(project, resume=resume)
            use_case.execute(request)

            project.status = ProjectStatus.COMPLETED
            project.completed_at = datetime.now(timezone.utc)
            session.commit()
        except VideoTranslatorError as exc:
            project.status = ProjectStatus.FAILED
            project.error_message = str(exc)
            project.completed_at = datetime.now(timezone.utc)
            session.commit()
            raise
        except Exception as exc:
            project.status = ProjectStatus.FAILED
            project.error_message = f"Error inesperado: {exc}"
            project.completed_at = datetime.now(timezone.utc)
            session.commit()
            raise
    finally:
        session.close()
