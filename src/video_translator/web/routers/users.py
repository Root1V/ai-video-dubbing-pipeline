"""Router de administracion de usuarios: crear, listar, cambiar rol, activar/desactivar.

Solo accesible para admins (`Depends(require_admin)`). Crear un usuario aca
es equivalente a `scripts/create_admin.py` pero desde la UI -- sigue sin
haber auto-registro ni invitaciones por email (alguien con acceso admin
sigue siendo el unico que puede dar de alta una cuenta).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from video_translator.web.db.models import User, UserRole
from video_translator.web.deps import get_db_session, require_admin
from video_translator.web.schemas.auth import UserOut
from video_translator.web.schemas.users import UserCreateIn, UserListOut, UserUpdateIn
from video_translator.web.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserListOut)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> UserListOut:
    total = db.execute(select(func.count()).select_from(User)).scalar_one()
    stmt = (
        select(User)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return UserListOut(
        items=[UserOut.model_validate(u) for u in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateIn,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> UserOut:
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese email.",
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        name=payload.name,
        role=UserRole(payload.role),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateIn,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    is_self = user.id == current_user.id
    if is_self and payload.role is not None and payload.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes quitarte tu propio rol de admin.",
        )
    if is_self and payload.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivar tu propia cuenta.",
        )

    if payload.role is not None:
        user.role = UserRole(payload.role)
    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
