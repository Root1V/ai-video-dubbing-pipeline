"""Esquemas de previsualizacion/busqueda de media externo (import por URL)."""

from __future__ import annotations

from pydantic import BaseModel


class MediaPreviewOut(BaseModel):
    title: str
    thumbnail_url: str | None
    duration_seconds: float | None
    source_url: str
    is_youtube: bool
    youtube_video_id: str | None


class MediaSearchOut(BaseModel):
    items: list[MediaPreviewOut]
