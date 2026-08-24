"""Tests de la tarea Celery run_dubbing_project: transiciones de estado en BD
segun el resultado de `build_use_case_and_request`/`execute()`. Se mockea el
mapper para no requerir el pipeline real (GPU/modelos)."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from video_translator.domain.exceptions import SynthesisError
from video_translator.web.db.base import Base
from video_translator.web.db.models import Project, ProjectStatus, ServiceType, SourceType
from video_translator.web.tasks import run_project as run_project_module


@pytest.fixture()
def db_session_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(run_project_module, "SessionLocal", factory)
    return factory


def _make_project(tmp_path: Path) -> Project:
    return Project(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Proyecto",
        service_type=ServiceType.DUBBING,
        source_type=SourceType.UPLOAD,
        input_video_path=str(tmp_path / "input.mp4"),
        output_dir=str(tmp_path / "output"),
        output_mode="dubbed",
        config={},
        status=ProjectStatus.QUEUED,
    )


def test_run_dubbing_project_success(
    db_session_factory: sessionmaker[Session], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = db_session_factory()
    project = _make_project(tmp_path)
    session.add(project)
    session.commit()
    project_id = str(project.id)
    session.close()

    fake_use_case = MagicMock()
    monkeypatch.setattr(
        run_project_module,
        "build_use_case_and_request",
        lambda proj, resume=False: (fake_use_case, MagicMock()),
    )

    run_project_module.run_dubbing_project.run(project_id)

    verify_session = db_session_factory()
    refreshed = verify_session.get(Project, uuid.UUID(project_id))
    assert refreshed is not None
    assert refreshed.status == ProjectStatus.COMPLETED
    assert refreshed.completed_at is not None
    assert refreshed.error_message is None
    fake_use_case.execute.assert_called_once()


def test_run_dubbing_project_pipeline_error_marks_failed(
    db_session_factory: sessionmaker[Session], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = db_session_factory()
    project = _make_project(tmp_path)
    session.add(project)
    session.commit()
    project_id = str(project.id)
    session.close()

    fake_use_case = MagicMock()
    fake_use_case.execute.side_effect = SynthesisError("el motor de TTS fallo")
    monkeypatch.setattr(
        run_project_module,
        "build_use_case_and_request",
        lambda proj, resume=False: (fake_use_case, MagicMock()),
    )

    with pytest.raises(SynthesisError):
        run_project_module.run_dubbing_project.run(project_id)

    verify_session = db_session_factory()
    refreshed = verify_session.get(Project, uuid.UUID(project_id))
    assert refreshed is not None
    assert refreshed.status == ProjectStatus.FAILED
    assert refreshed.error_message == "el motor de TTS fallo"
    assert refreshed.completed_at is not None


def test_run_dubbing_project_unexpected_error_marks_failed(
    db_session_factory: sessionmaker[Session], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = db_session_factory()
    project = _make_project(tmp_path)
    session.add(project)
    session.commit()
    project_id = str(project.id)
    session.close()

    def _boom(proj: Project, resume: bool = False) -> tuple[MagicMock, MagicMock]:
        raise RuntimeError("algo totalmente inesperado")

    monkeypatch.setattr(run_project_module, "build_use_case_and_request", _boom)

    with pytest.raises(RuntimeError):
        run_project_module.run_dubbing_project.run(project_id)

    verify_session = db_session_factory()
    refreshed = verify_session.get(Project, uuid.UUID(project_id))
    assert refreshed is not None
    assert refreshed.status == ProjectStatus.FAILED
    assert "algo totalmente inesperado" in (refreshed.error_message or "")


def test_run_dubbing_project_missing_project_is_a_noop(
    db_session_factory: sessionmaker[Session],
) -> None:
    # No debe lanzar si el proyecto fue borrado antes de que el worker lo tome.
    run_project_module.run_dubbing_project.run(str(uuid.uuid4()))


def _make_transcription_project(tmp_path: Path) -> Project:
    return Project(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Proyecto de transcripcion",
        service_type=ServiceType.TRANSCRIPTION,
        source_type=SourceType.UPLOAD,
        input_video_path=str(tmp_path / "input.mp3"),
        output_dir=str(tmp_path / "output"),
        output_mode="subtitles_only",
        config={},
        status=ProjectStatus.QUEUED,
    )


def test_run_dubbing_project_dispatches_transcription_service_type(
    db_session_factory: sessionmaker[Session], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = db_session_factory()
    project = _make_transcription_project(tmp_path)
    session.add(project)
    session.commit()
    project_id = str(project.id)
    session.close()

    fake_use_case = MagicMock()
    transcribe_mock = MagicMock(return_value=(fake_use_case, MagicMock()))
    monkeypatch.setattr(run_project_module, "build_transcribe_use_case_and_request", transcribe_mock)
    dubbing_mock = MagicMock()
    monkeypatch.setattr(run_project_module, "build_use_case_and_request", dubbing_mock)

    run_project_module.run_dubbing_project.run(project_id)

    transcribe_mock.assert_called_once()
    dubbing_mock.assert_not_called()
    fake_use_case.execute.assert_called_once()

    verify_session = db_session_factory()
    refreshed = verify_session.get(Project, uuid.UUID(project_id))
    assert refreshed is not None
    assert refreshed.status == ProjectStatus.COMPLETED
