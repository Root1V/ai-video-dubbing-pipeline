"""Modelos ORM (SQLAlchemy 2.0, estilo Mapped/mapped_column) del dashboard web.

Los valores de los enums de dominio (`service_type`, `output_mode`, etc.) son
strings compatibles con `video_translator.domain.models.OutputMode` y con el
resto del pipeline, para que mapear un `Project` a un `TranslateVideoRequest`
(M2) sea directo.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import JSON, ForeignKey, Uuid
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from video_translator.web.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _str_enum(enum_cls: type[Enum]) -> SqlEnum:
    """`Enum` de SQLAlchemy que persiste `.value` (p.ej. "subtitles_only"), no
    `.name` (el default de SQLAlchemy para enums de Python es `.name`) -- los
    valores deben coincidir exactamente con el contrato de la API y con
    `video_translator.domain.models.OutputMode`."""
    return SqlEnum(enum_cls, values_callable=lambda cls: [e.value for e in cls])


class UserRole(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"


class ServiceType(str, Enum):
    DUBBING = "dubbing"
    SUBTITLES = "subtitles"
    TRANSCRIPTION = "transcription"


class SourceType(str, Enum):
    UPLOAD = "upload"
    YOUTUBE = "youtube"


class OutputModeValue(str, Enum):
    SUBTITLES_ONLY = "subtitles_only"
    BURN_SUBTITLES = "burn_subtitles"
    SOFT_SUBTITLES = "soft_subtitles"
    DUBBED = "dubbed"


class ProjectStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    role: Mapped[UserRole] = mapped_column(_str_enum(UserRole), nullable=False, default=UserRole.MEMBER)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)

    projects: Mapped[list[Project]] = relationship(back_populates="user")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    service_type: Mapped[ServiceType] = mapped_column(_str_enum(ServiceType), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        _str_enum(SourceType), nullable=False, default=SourceType.UPLOAD
    )
    source_url: Mapped[str | None] = mapped_column(default=None)
    input_video_path: Mapped[str] = mapped_column(nullable=False)
    output_dir: Mapped[str] = mapped_column(nullable=False)
    output_mode: Mapped[OutputModeValue] = mapped_column(_str_enum(OutputModeValue), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[ProjectStatus] = mapped_column(
        _str_enum(ProjectStatus), nullable=False, default=ProjectStatus.QUEUED
    )
    celery_task_id: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    error_message: Mapped[str | None] = mapped_column(default=None)

    user: Mapped[User] = relationship(back_populates="projects")
