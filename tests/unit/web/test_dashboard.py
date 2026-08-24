"""Tests de /api/dashboard/stats: agregados sobre Project + ProjectMetrics,
aislados por usuario."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from video_translator.web.db.models import (
    Project,
    ProjectMetrics,
    ProjectStatus,
    ServiceType,
    SourceType,
    User,
)


def _auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_project(db_session: Session, user: User, **overrides: object) -> Project:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "user_id": user.id,
        "name": "Proyecto",
        "service_type": ServiceType.DUBBING,
        "source_type": SourceType.UPLOAD,
        "input_video_path": "/tmp/input.mp4",
        "output_dir": "/tmp/output",
        "output_mode": "dubbed",
        "config": {"source_lang": "en", "target_lang": "es"},
        "status": ProjectStatus.COMPLETED,
    }
    defaults.update(overrides)
    project = Project(**defaults)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def _make_metrics(db_session: Session, project: Project, **overrides: object) -> ProjectMetrics:
    defaults: dict[str, object] = {
        "project_id": project.id,
        "user_id": project.user_id,
        "project_name": project.name,
        "service_type": project.service_type.value,
        "status": "completed",
        "total_seconds": 10.0,
        "input_duration_seconds": 20.0,
        "realtime_factor": 0.5,
    }
    defaults.update(overrides)
    metrics = ProjectMetrics(**defaults)
    db_session.add(metrics)
    db_session.commit()
    return metrics


def test_dashboard_stats_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/dashboard/stats")
    assert resp.status_code == 401


def test_dashboard_stats_empty_for_new_user(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    resp = client.get("/api/dashboard/stats", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "total_projects": 0,
        "total_seconds_processed": 0.0,
        "distinct_languages": 0,
        "saved_voices": 0,
    }


def test_dashboard_stats_counts_projects_and_distinct_languages(
    client: TestClient, make_user: Callable[..., User], db_session: Session
) -> None:
    user = make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    _make_project(db_session, user, config={"source_lang": "en", "target_lang": "es"})
    _make_project(db_session, user, config={"source_lang": "en", "target_lang": "fr"})

    resp = client.get("/api/dashboard/stats", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_projects"] == 2
    assert body["distinct_languages"] == 3  # en, es, fr


def test_dashboard_stats_sums_processed_seconds_from_metrics(
    client: TestClient, make_user: Callable[..., User], db_session: Session
) -> None:
    user = make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    project = _make_project(db_session, user)
    _make_metrics(db_session, project, input_duration_seconds=30.0)
    _make_metrics(db_session, project, input_duration_seconds=15.5)

    resp = client.get("/api/dashboard/stats", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["total_seconds_processed"] == 45.5


def test_dashboard_stats_survives_project_deletion(
    client: TestClient, make_user: Callable[..., User], db_session: Session
) -> None:
    user = make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    project = _make_project(db_session, user)
    _make_metrics(db_session, project, input_duration_seconds=42.0)

    db_session.delete(project)
    db_session.commit()

    resp = client.get("/api/dashboard/stats", headers=headers)

    assert resp.status_code == 200
    # La fila de metricas sobrevive al borrado del proyecto (project_id
    # queda NULL via ondelete="SET NULL"), asi que sigue sumando.
    assert resp.json()["total_seconds_processed"] == 42.0
    assert resp.json()["total_projects"] == 0


def test_dashboard_stats_only_counts_current_user_projects(
    client: TestClient, make_user: Callable[..., User], db_session: Session
) -> None:
    alice = make_user(email="alice@example.com", password="hunter2")
    make_user(email="bob@example.com", password="secret456")
    _make_project(db_session, alice)

    bob_headers = _auth_headers(client, "bob@example.com", "secret456")
    resp = client.get("/api/dashboard/stats", headers=bob_headers)

    assert resp.status_code == 200
    assert resp.json()["total_projects"] == 0
