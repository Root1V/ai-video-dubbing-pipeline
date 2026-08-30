"""Tests de /api/samples: preview de voces publicas (empaquetadas con la app)
y de musica de fondo (catalogo en BD, ver RM-26)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from video_translator.web.db.models import MusicTrack, User


def _auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_voice_sample_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/samples/voices/public_female")
    assert resp.status_code == 401


def test_get_voice_sample_serves_public_female(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    resp = client.get("/api/samples/voices/public_female", headers=headers)

    assert resp.status_code == 200
    assert resp.headers["content-type"] in ("audio/wav", "audio/x-wav")


def test_get_voice_sample_unknown_id_returns_404(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    resp = client.get("/api/samples/voices/does-not-exist", headers=headers)

    assert resp.status_code == 404


_BACKBEAT_MP3 = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "video_translator"
    / "assets"
    / "background_music"
    / "backbeat.mp3"
)


def test_get_music_sample_serves_known_track(
    client: TestClient, make_user: Callable[..., User], make_music_track: Callable[..., MusicTrack]
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")
    track = make_music_track(title="Backbeat", file_path=str(_BACKBEAT_MP3))

    resp = client.get(f"/api/samples/music/{track.id}", headers=headers)

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"


def test_get_music_sample_unknown_id_returns_404(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    resp = client.get("/api/samples/music/does-not-exist", headers=headers)

    assert resp.status_code == 404
