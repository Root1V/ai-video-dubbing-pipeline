"""Tests de /api/projects: creacion (multipart), listado, detalle, status, borrado,
y aislamiento por usuario (ownership)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from video_translator.web.db.models import Project, ProjectStatus, User
from video_translator.web.tasks.run_project import run_dubbing_project


@dataclass
class _FakeAsyncResult:
    id: str = "fake-task-id"


@pytest.fixture(autouse=True)
def _stub_celery_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    # Los tests de este router no deben depender de un broker Redis real: se
    # reemplaza el despacho de la tarea (no la tarea en si, que se prueba
    # aparte en test_run_project.py) por un doble que solo devuelve un id.
    monkeypatch.setattr(run_dubbing_project, "delay", lambda *args, **kwargs: _FakeAsyncResult())


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


def test_list_and_get_include_total_seconds_and_run_id(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")
    created = _create_project(client, headers).json()

    output_dir = Path(created["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "pipeline_timings.json").write_text(
        json.dumps({"run_id": "abc123def456", "total_seconds": 305.76, "completed": True})
    )

    get_resp = client.get(f"/api/projects/{created['id']}", headers=headers)
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["run_id"] == "abc123def456"
    assert body["total_seconds"] == 305.76

    list_resp = client.get("/api/projects", headers=headers)
    assert list_resp.status_code == 200
    item = list_resp.json()["items"][0]
    assert item["run_id"] == "abc123def456"
    assert item["total_seconds"] == 305.76


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


def test_resume_requires_failed_status(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")
    created = _create_project(client, headers).json()

    # Recien creado esta "queued", no "failed": reintentar debe rechazarse.
    resp = client.post(f"/api/projects/{created['id']}/resume", headers=headers)
    assert resp.status_code == 409


def test_resume_failed_project_reenqueues(
    client: TestClient, make_user: Callable[..., User], db_session: Session
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")
    created = _create_project(client, headers).json()

    project = db_session.get(Project, uuid.UUID(created["id"]))
    assert project is not None
    project.status = ProjectStatus.FAILED
    project.error_message = "algo salio mal"
    db_session.commit()

    resp = client.post(f"/api/projects/{created['id']}/resume", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert body["error_message"] is None
    assert body["celery_task_id"] == "fake-task-id"


def test_download_artifact_not_ready_returns_404(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")
    created = _create_project(client, headers).json()

    resp = client.get(f"/api/projects/{created['id']}/download/video", headers=headers)
    assert resp.status_code == 404


def test_download_artifact_unknown_kind_returns_400(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")
    created = _create_project(client, headers).json()

    resp = client.get(f"/api/projects/{created['id']}/download/nonsense", headers=headers)
    assert resp.status_code == 400


def test_download_artifact_serves_existing_file(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")
    created = _create_project(client, headers).json()

    output_dir = Path(created["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "subtitles.es.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHola\n")

    resp = client.get(f"/api/projects/{created['id']}/download/srt_target", headers=headers)

    assert resp.status_code == 200
    assert resp.content == b"1\n00:00:00,000 --> 00:00:01,000\nHola\n"


def test_create_tts_project_without_voice_file_succeeds(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    resp = client.post(
        "/api/projects",
        data={
            "name": "Mi audio",
            "service_type": "tts",
            "output_mode": "subtitles_only",
            "text": "Hola, esto es una prueba.",
            "target_lang": "es",
        },
        headers=headers,
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["service_type"] == "tts"
    assert body["input_video_path"].endswith("input.txt")
    assert "speaker_reference_wav" not in body["config"]


def test_create_tts_project_requires_text(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    resp = client.post(
        "/api/projects",
        data={"name": "Mi audio", "service_type": "tts", "output_mode": "subtitles_only", "text": "   "},
        headers=headers,
    )

    assert resp.status_code == 422


def test_create_tts_project_with_voice_file_saves_speaker_reference(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    resp = client.post(
        "/api/projects",
        data={
            "name": "Mi audio",
            "service_type": "tts",
            "output_mode": "subtitles_only",
            "text": "Hola.",
            "voice_option": "own",
        },
        files={"file": ("voice.wav", b"fake-wav-bytes", "audio/wav")},
        headers=headers,
    )

    assert resp.status_code == 201
    assert resp.json()["config"]["speaker_reference_wav"].endswith("voice.wav")


def test_create_tts_project_requires_file_when_voice_option_is_own(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    resp = client.post(
        "/api/projects",
        data={
            "name": "Mi audio",
            "service_type": "tts",
            "output_mode": "subtitles_only",
            "text": "Hola.",
            "voice_option": "own",
        },
        headers=headers,
    )

    assert resp.status_code == 422


def test_create_tts_project_defaults_voice_option_to_public_female(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    resp = client.post(
        "/api/projects",
        data={"name": "Mi audio", "service_type": "tts", "output_mode": "subtitles_only", "text": "Hola."},
        headers=headers,
    )

    assert resp.status_code == 201
    assert resp.json()["config"]["voice_option"] == "public_female"


def test_create_project_without_file_rejects_for_non_tts_service(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    resp = client.post(
        "/api/projects",
        data={"name": "Sin archivo", "service_type": "dubbing", "output_mode": "dubbed"},
        headers=headers,
    )

    assert resp.status_code == 422


def test_download_speech_audio_artifact_serves_existing_file(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")
    created = client.post(
        "/api/projects",
        data={"name": "Mi audio", "service_type": "tts", "output_mode": "subtitles_only", "text": "Hola."},
        headers=headers,
    ).json()

    output_dir = Path(created["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "speech.wav").write_bytes(b"fake-speech-audio")

    resp = client.get(f"/api/projects/{created['id']}/download/speech_audio", headers=headers)

    assert resp.status_code == 200
    assert resp.content == b"fake-speech-audio"


def test_download_transcript_artifacts_serves_existing_files(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")
    created = _create_project(client, headers, service_type="transcription").json()

    output_dir = Path(created["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "transcript.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
    (output_dir / "transcript.txt").write_text("Hello")

    srt_resp = client.get(f"/api/projects/{created['id']}/download/transcript_srt", headers=headers)
    text_resp = client.get(f"/api/projects/{created['id']}/download/transcript_text", headers=headers)

    assert srt_resp.status_code == 200
    assert srt_resp.content == b"1\n00:00:00,000 --> 00:00:01,000\nHello\n"
    assert text_resp.status_code == 200
    assert text_resp.content == b"Hello"
