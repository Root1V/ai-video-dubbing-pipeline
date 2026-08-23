"""Esquemas de proyectos."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    service_type: str
    source_type: str
    source_url: str | None
    input_video_path: str
    output_dir: str
    output_mode: str
    config: dict[str, Any]
    status: str
    celery_task_id: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None


class ProjectListOut(BaseModel):
    items: list[ProjectOut]
    total: int
    page: int
    page_size: int


class ProjectStatusOut(BaseModel):
    db_status: str
    run_id: str | None
    completed: bool | None
    current_stage: dict[str, Any] | None
    stages: list[Any] | None
    total_seconds: float | None
    realtime_factor: float | None
    warnings: list[Any] | None
