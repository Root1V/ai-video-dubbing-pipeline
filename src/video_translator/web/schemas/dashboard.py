"""Esquemas de analitica de negocio (dashboard/stats)."""

from __future__ import annotations

from pydantic import BaseModel


class DashboardStatsOut(BaseModel):
    total_projects: int
    # Suma de la duracion de entrada de las corridas completadas/fallidas del
    # usuario (ver ProjectMetrics.input_duration_seconds) -- no cubre TTS
    # standalone, que no tiene un "input" de duracion (texto, no audio/video).
    total_seconds_processed: float
    distinct_languages: int
    # Fijo en 0 hasta que exista la libreria de voces (P1.5).
    saved_voices: int
