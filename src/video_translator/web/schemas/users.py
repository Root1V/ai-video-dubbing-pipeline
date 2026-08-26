"""Esquemas de administracion de usuarios (listado, cambio de rol/estado)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from video_translator.web.schemas.auth import UserOut


class UserListOut(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


class UserUpdateIn(BaseModel):
    role: Literal["admin", "member"] | None = None
    is_active: bool | None = None
