"""App Celery del dashboard web."""

from __future__ import annotations

from celery import Celery

from video_translator.web.config import load_web_settings

_settings = load_web_settings()

celery_app = Celery(
    "prosodia_web",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
)

# Import explicito (en vez de autodiscover_tasks, pensado para layouts tipo
# Django) para que el modulo quede registrado en este app de Celery.
import video_translator.web.tasks.run_project  # noqa: F401
