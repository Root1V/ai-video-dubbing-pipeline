"""Tarea Celery que procesa un proyecto.

STUB de M1: no llama al pipeline real todavia (eso es M2), solo simula una
corrida con un sleep para validar el plumbing DB/API/storage de punta a punta.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from celery import Task

from video_translator.web.db.models import Project, ProjectStatus
from video_translator.web.db.session import SessionLocal
from video_translator.web.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="video_translator.web.run_project")
def run_stub_project(self: Task, project_id: str) -> None:
    session = SessionLocal()
    try:
        project = session.get(Project, uuid.UUID(project_id))
        if project is None:
            return
        try:
            project.status = ProjectStatus.RUNNING
            project.started_at = datetime.now(timezone.utc)
            session.commit()

            time.sleep(5)

            project.status = ProjectStatus.COMPLETED
            project.completed_at = datetime.now(timezone.utc)
            session.commit()
        except Exception as exc:
            project.status = ProjectStatus.FAILED
            project.error_message = str(exc)
            session.commit()
            raise
    finally:
        session.close()
