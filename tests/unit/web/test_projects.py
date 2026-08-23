"""Tests de /api/projects: creacion (multipart), listado, detalle, status, borrado,
y aislamiento por usuario (ownership)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from video_translator.web.db.models import User
from video_translator.web.tasks.run_project import run_stub_project


@dataclass
class _FakeAsyncResult:
    id: str = "fake-task-id"


@pytest.fixture(autouse=True)
def _stub_celery_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_stub_project, "delay", lambda *args, **kwargs: _FakeAsyncResult())


def _auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_project(client: TestClient, headers: dict[str, str], **overrides: Any) -> Any:
    data = {
        "name": "My dubbing project",
        "service_type": "dubbing",
        "output_mode": "dubbed",
        "context_prompt": "",
        "source_lang": "en",
        "target_lang": "es",
        "diarize": "false",
        **overrides,
    }
    files = {"file": ("clip.mp4", b"fake-video-bytes", "video/mp4")}
    return client.post("/api/projects", data=data, files=files, headers=headers)


def test_create_project_success(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    resp = _create_project(client, headers)

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My dubbing project"
    assert body["service_type"] == "dubbing"
    assert body["output_mode"] == "dubbed"
    assert body["status"] == "queued"
    assert body["celery_task_id"] == "fake-task-id"
    assert body["input_video_path"]
    assert body["output_dir"]


def test_create_project_requires_auth(client: TestClient) -> None:
    resp = _create_project(client, headers={})
    assert resp.status_code == 401


def test_create_project_rejects_invalid_glossary_json(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    resp = _create_project(client, headers, glossary="not-json")

    assert resp.status_code == 422


def test_get_project_and_list(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")
    created = _create_project(client, headers).json()

    get_resp = client.get(f"/api/projects/{created['id']}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == created["id"]

    list_resp = client.get("/api/projects", headers=headers)
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == created["id"]


def test_get_project_status(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")
    created = _create_project(client, headers).json()

    resp = client.get(f"/api/projects/{created['id']}/status", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["db_status"] == "queued"
    assert body["stages"] is None


def test_project_not_found(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    resp = client.get("/api/projects/00000000-0000-0000-0000-000000000000", headers=headers)

    assert resp.status_code == 404


def test_ownership_isolation_returns_404_not_403(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    make_user(email="bob@example.com", password="secret456")
    alice_headers = _auth_headers(client, "alice@example.com", "hunter2")
    bob_headers = _auth_headers(client, "bob@example.com", "secret456")

    created = _create_project(client, alice_headers).json()

    # Bob no puede ver el proyecto de Alice: 404 (no 403), para no filtrar
    # que el proyecto existe.
    get_resp = client.get(f"/api/projects/{created['id']}", headers=bob_headers)
    assert get_resp.status_code == 404

    status_resp = client.get(f"/api/projects/{created['id']}/status", headers=bob_headers)
    assert status_resp.status_code == 404

    delete_resp = client.delete(f"/api/projects/{created['id']}", headers=bob_headers)
    assert delete_resp.status_code == 404

    # Bob no ve el proyecto de Alice en su listado.
    list_resp = client.get("/api/projects", headers=bob_headers)
    assert list_resp.json()["total"] == 0


def test_delete_project(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")
    created = _create_project(client, headers).json()

    upload_dir = Path(created["input_video_path"]).parent
    assert upload_dir.is_dir()

    delete_resp = client.delete(f"/api/projects/{created['id']}", headers=headers)
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/api/projects/{created['id']}", headers=headers)
    assert get_resp.status_code == 404

    # No debe quedar el directorio de subida vacio huerfano en disco.
    assert not upload_dir.exists()
