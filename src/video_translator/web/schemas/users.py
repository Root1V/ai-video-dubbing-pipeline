"""Esquemas de administracion de usuarios (listado, cambio de rol/estado)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from video_translator.web.schemas.auth import UserOut


class UserListOut(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


class UserCreateIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str
    role: Literal["admin", "member"] = "member"


class UserUpdateIn(BaseModel):
    role: Literal["admin", "member"] | None = None
    is_active: bool | None = None
