"""Tests de /api/media: preview y search. Mockea web.services.media_import
(no se hacen llamadas de red reales / no se invoca yt-dlp)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from video_translator.web.db.models import User
from video_translator.web.routers import media as media_router_module
from video_translator.web.services.media_import import (
    InvalidUrlError,
    MediaImportError,
    MediaPreview,
)


def _auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_preview_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/media/preview", params={"url": "https://example.com/video.mp4"})
    assert resp.status_code == 401


def test_preview_success(
    client: TestClient, make_user: Callable[..., User], monkeypatch: pytest.MonkeyPatch
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    fake_preview = MediaPreview(
        title="Un video",
        thumbnail_url="https://img.example/thumb.jpg",
        duration_seconds=90.0,
        source_url="https://www.youtube.com/watch?v=abc",
        is_youtube=True,
        youtube_video_id="abc",
    )
    monkeypatch.setattr(media_router_module, "fetch_preview", lambda url: fake_preview)

    resp = client.get(
        "/api/media/preview", params={"url": "https://www.youtube.com/watch?v=abc"}, headers=headers
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Un video"
    assert body["is_youtube"] is True
    assert body["youtube_video_id"] == "abc"


def test_preview_invalid_url_is_422(
    client: TestClient, make_user: Callable[..., User], monkeypatch: pytest.MonkeyPatch
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    def _boom(url: str) -> None:
        raise InvalidUrlError("URL bloqueada")

    monkeypatch.setattr(media_router_module, "fetch_preview", _boom)

    resp = client.get(
        "/api/media/preview", params={"url": "http://127.0.0.1/x"}, headers=headers
    )
    assert resp.status_code == 422


def test_preview_lookup_failure_is_502(
    client: TestClient, make_user: Callable[..., User], monkeypatch: pytest.MonkeyPatch
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    def _boom(url: str) -> None:
        raise MediaImportError("no se pudo extraer")

    monkeypatch.setattr(media_router_module, "fetch_preview", _boom)

    resp = client.get(
        "/api/media/preview", params={"url": "https://example.com/gone.mp4"}, headers=headers
    )
    assert resp.status_code == 502


def test_search_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/media/search", params={"q": "gatos"})
    assert resp.status_code == 401


def test_search_success(
    client: TestClient, make_user: Callable[..., User], monkeypatch: pytest.MonkeyPatch
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    fake_results = [
        MediaPreview(
            title="Resultado 1",
            thumbnail_url=None,
            duration_seconds=30.0,
            source_url="https://www.youtube.com/watch?v=r1",
            is_youtube=True,
            youtube_video_id="r1",
        )
    ]
    monkeypatch.setattr(
        media_router_module, "search_youtube", lambda q, limit=12: fake_results
    )

    resp = client.get("/api/media/search", params={"q": "gatos"}, headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Resultado 1"


def test_search_failure_is_502(
    client: TestClient, make_user: Callable[..., User], monkeypatch: pytest.MonkeyPatch
) -> None:
    make_user(email="alice@example.com", password="hunter2")
    headers = _auth_headers(client, "alice@example.com", "hunter2")

    def _boom(q: str, limit: int = 12) -> list[MediaPreview]:
        raise MediaImportError("busqueda fallo")

    monkeypatch.setattr(media_router_module, "search_youtube", _boom)

    resp = client.get("/api/media/search", params={"q": "gatos"}, headers=headers)
    assert resp.status_code == 502
