"""Tests de /api/music-tracks: catalogo de musica de fondo por categoria
(RM-26) -- listado (cualquier usuario autenticado), alta/baja (solo admin).

`clean_music_track` (ffmpeg real) se mockea aca: lo que se verifica es el
mapeo HTTP/BD, no el procesamiento de audio en si (sin test dedicado,
igual que el resto de FFmpegMediaProcessor -- se valida manualmente contra
el binario real, ver docs/roadmap.md RM-26)."""

from __future__ import annotations

import io
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from video_translator.web.db.models import MusicTrack, User, UserRole
from video_translator.web.routers import music_tracks as music_tracks_router


def _auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class _FakeMediaProcessor:
    def clean_music_track(self, input_path: Path, output_wav: Path) -> Path:
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        output_wav.write_bytes(b"fake-clean-wav")
        return output_wav


@pytest.fixture(autouse=True)
def _fake_media_processor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        music_tracks_router,
        "build_music_track_media_processor",
        lambda settings: _FakeMediaProcessor(),
    )


def test_list_music_tracks_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/music-tracks")
    assert resp.status_code == 401


def test_list_music_tracks_returns_all_categories(
    client: TestClient, make_user: Callable[..., User], make_music_track: Callable[..., MusicTrack]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")
    make_music_track(title="Calm One", category="calm_meditation")
    make_music_track(title="Pop One", category="energy_pop")

    resp = client.get("/api/music-tracks", headers=headers)

    assert resp.status_code == 200
    titles = {t["title"] for t in resp.json()["items"]}
    assert titles == {"Calm One", "Pop One"}


def test_list_music_tracks_filters_by_category(
    client: TestClient, make_user: Callable[..., User], make_music_track: Callable[..., MusicTrack]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")
    make_music_track(title="Calm One", category="calm_meditation")
    make_music_track(title="Pop One", category="energy_pop")

    resp = client.get(
        "/api/music-tracks", params={"category": "calm_meditation"}, headers=headers
    )

    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()["items"]]
    assert titles == ["Calm One"]


def test_list_music_tracks_rejects_invalid_category(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    resp = client.get(
        "/api/music-tracks", params={"category": "not-a-category"}, headers=headers
    )

    assert resp.status_code == 422


def test_create_music_track_requires_admin(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="member@example.com", password="hunter2", role=UserRole.MEMBER)
    headers = _auth_headers(client, "member@example.com", "hunter2")

    resp = client.post(
        "/api/music-tracks",
        headers=headers,
        data={"title": "New Track", "category": "happy_romantic"},
        files={"file": ("track.mp3", io.BytesIO(b"fake-mp3-bytes"), "audio/mpeg")},
    )

    assert resp.status_code == 403


def test_create_music_track_admin_cleans_and_stores(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="admin@example.com", password="hunter2", role=UserRole.ADMIN)
    headers = _auth_headers(client, "admin@example.com", "hunter2")

    resp = client.post(
        "/api/music-tracks",
        headers=headers,
        data={"title": "New Track", "category": "happy_romantic"},
        files={"file": ("track.mp3", io.BytesIO(b"fake-mp3-bytes"), "audio/mpeg")},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "New Track"
    assert body["category"] == "happy_romantic"

    list_resp = client.get("/api/music-tracks", headers=headers)
    assert [t["title"] for t in list_resp.json()["items"]] == ["New Track"]


def test_delete_music_track_requires_admin(
    client: TestClient, make_user: Callable[..., User], make_music_track: Callable[..., MusicTrack]
) -> None:
    make_user(email="member@example.com", password="hunter2", role=UserRole.MEMBER)
    headers = _auth_headers(client, "member@example.com", "hunter2")
    track = make_music_track()

    resp = client.delete(f"/api/music-tracks/{track.id}", headers=headers)

    assert resp.status_code == 403


def test_delete_music_track_admin_removes_file_and_row(
    client: TestClient,
    make_user: Callable[..., User],
    make_music_track: Callable[..., MusicTrack],
    tmp_path: Path,
) -> None:
    make_user(email="admin@example.com", password="hunter2", role=UserRole.ADMIN)
    headers = _auth_headers(client, "admin@example.com", "hunter2")
    file_path = tmp_path / "track.wav"
    file_path.write_bytes(b"data")
    track = make_music_track(file_path=str(file_path))

    resp = client.delete(f"/api/music-tracks/{track.id}", headers=headers)

    assert resp.status_code == 204
    assert not file_path.exists()

    list_resp = client.get("/api/music-tracks", headers=headers)
    assert list_resp.json()["items"] == []


def test_delete_music_track_unknown_id_returns_404(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="admin@example.com", password="hunter2", role=UserRole.ADMIN)
    headers = _auth_headers(client, "admin@example.com", "hunter2")

    resp = client.delete(f"/api/music-tracks/{uuid.uuid4()}", headers=headers)

    assert resp.status_code == 404
