"""Esquemas del catalogo de musica de fondo (RM-26)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

MusicCategoryLiteral = Literal[
    "calm_meditation",
    "commercials_professional",
    "energy_pop",
    "happy_romantic",
    "social_network",
]


class MusicTrackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    category: MusicCategoryLiteral
    created_at: datetime


class MusicTrackListOut(BaseModel):
    items: list[MusicTrackOut]
