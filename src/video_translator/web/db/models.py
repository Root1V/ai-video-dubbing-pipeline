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
    TTS = "tts"
    MICRO_VIDEO = "micro_video"


class SourceType(str, Enum):
    UPLOAD = "upload"
    YOUTUBE = "youtube"
    URL = "url"


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


class ProjectMetrics(Base):
    """Foto de las metricas de una corrida al finalizar (exito o falla),
    tomada por `web/tasks/run_project.py` desde `pipeline_timings.json` (ver
    `services/status_reader.py::read_full_timings_report`).

    Existe SEPARADA de `Project` a proposito: `project_id` es nullable con
    `ondelete="SET NULL"` para que las metricas de negocio (duracion
    procesada, backend usado, etc.) sobrevivan aunque el usuario borre el
    proyecto y sus archivos (`routers/projects.py::delete_project`) -- sin
    esto, las tendencias historicas del dashboard se degradarian con el
    tiempo a medida que se acumulan proyectos borrados.
    """

    __tablename__ = "project_metrics"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    # Copiado al momento de la foto (no una FK a Project.name) para que el
    # dato siga siendo legible aunque el proyecto ya no exista.
    project_name: Mapped[str] = mapped_column(nullable=False)
    # Strings planos (no el enum `ServiceType`/`ProjectStatus`): esta tabla es
    # un registro historico/analitico, no debe acoplarse a que esos enums
    # nunca cambien de valores validos.
    service_type: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    total_seconds: Mapped[float | None] = mapped_column(default=None)
    input_duration_seconds: Mapped[float | None] = mapped_column(default=None)
    realtime_factor: Mapped[float | None] = mapped_column(default=None)
    effective_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    stats: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    outputs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    warnings_count: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)


class MusicCategory(str, Enum):
    CALM_MEDITATION = "calm_meditation"
    COMMERCIALS_PROFESSIONAL = "commercials_professional"
    ENERGY_POP = "energy_pop"
    HAPPY_ROMANTIC = "happy_romantic"
    SOCIAL_NETWORK = "social_network"


class MusicTrack(Base):
    """Catalogo de musica de fondo para micro-video (ver RM-26), organizado
    por categoria. `file_path` ya apunta al WAV limpio (silencio inicial
    recortado) -- ver `web/services/music_tracks.py::add_music_track`."""

    __tablename__ = "music_tracks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(nullable=False)
    category: Mapped[MusicCategory] = mapped_column(_str_enum(MusicCategory), nullable=False)
    file_path: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)
