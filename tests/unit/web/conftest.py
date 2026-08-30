"""Fixtures compartidas de los tests del dashboard web: engine SQLite en
memoria + TestClient de FastAPI con la sesion de BD inyectada."""

from __future__ import annotations

from collections.abc import Callable, Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from video_translator.web.config import WebSettings
from video_translator.web.db.base import Base
from video_translator.web.db.models import MusicCategory, MusicTrack, User, UserRole
from video_translator.web.deps import get_db_session
from video_translator.web.main import app
from video_translator.web.routers.projects import get_web_settings
from video_translator.web.security import hash_password


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    # StaticPool: la app corre los endpoints sincronos en un thread pool
    # (FastAPI/Starlette), asi que sin un pool que comparta UNA sola conexion
    # entre threads, cada thread nuevo veria una base ":memory:" distinta y
    # vacia (SQLite crea una base nueva por conexion).
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session: Session, tmp_path: Path) -> Generator[TestClient, None, None]:
    def _override_get_db_session() -> Generator[Session, None, None]:
        yield db_session

    def _override_get_web_settings() -> WebSettings:
        return WebSettings(storage_root=str(tmp_path / "storage"))

    app.dependency_overrides[get_db_session] = _override_get_db_session
    app.dependency_overrides[get_web_settings] = _override_get_web_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def make_user(db_session: Session) -> Callable[..., User]:
    def _make_user(email: str = "user@example.com", password: str = "secret123", **kwargs: object) -> User:
        user = User(
            email=email,
            hashed_password=hash_password(password),
            name=kwargs.get("name", "Test User"),
            role=kwargs.get("role", UserRole.MEMBER),
            is_active=kwargs.get("is_active", True),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make_user


@pytest.fixture()
def make_music_track(db_session: Session) -> Callable[..., MusicTrack]:
    def _make_music_track(
        title: str = "Test Track",
        category: MusicCategory = MusicCategory.ENERGY_POP,
        file_path: str = "",
        **kwargs: object,
    ) -> MusicTrack:
        track = MusicTrack(title=title, category=category, file_path=file_path, **kwargs)
        db_session.add(track)
        db_session.commit()
        db_session.refresh(track)
        return track

    return _make_music_track
