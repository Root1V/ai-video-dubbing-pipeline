"""Router de analitica de negocio: agregados sobre Project + ProjectMetrics.

Alcance de negocio, no de progreso en vivo: `services/status_reader.py` sigue
siendo la fuente para el detalle de un proyecto individual (polling de
`/projects/{id}/status`); este router responde "cuanto ha procesado este
usuario en total", para el home del dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from video_translator.web.db.models import Project, ProjectMetrics, User
from video_translator.web.deps import get_current_user, get_db_session
from video_translator.web.schemas.dashboard import DashboardStatsOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_LANGUAGE_CONFIG_KEYS = ("source_lang", "target_lang")


@router.get("/stats", response_model=DashboardStatsOut)
def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> DashboardStatsOut:
    total_projects = db.execute(
        select(func.count()).select_from(Project).where(Project.user_id == current_user.id)
    ).scalar_one()

    total_seconds_processed = db.execute(
        select(func.coalesce(func.sum(ProjectMetrics.input_duration_seconds), 0.0)).where(
            ProjectMetrics.user_id == current_user.id
        )
    ).scalar_one()

    configs = db.execute(select(Project.config).where(Project.user_id == current_user.id)).scalars().all()
    languages = {
        config[key]
        for config in configs
        for key in _LANGUAGE_CONFIG_KEYS
        if config and config.get(key)
    }

    return DashboardStatsOut(
        total_projects=total_projects,
        total_seconds_processed=float(total_seconds_processed or 0.0),
        distinct_languages=len(languages),
        saved_voices=0,
    )
