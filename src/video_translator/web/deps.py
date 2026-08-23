"""Dependencias FastAPI: sesion de BD, usuario autenticado, guard de admin."""

from __future__ import annotations

import uuid
from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from video_translator.web.db.models import User, UserRole
from video_translator.web.db.session import SessionLocal
from video_translator.web.security import decode_access_token

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_current_user(
    token: str = Depends(_oauth2_scheme),
    db: Session = Depends(get_db_session),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_error
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise credentials_error from None
    user = db.get(User, user_uuid)
    if user is None or not user.is_active:
        raise credentials_error
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere rol admin.")
    return user
