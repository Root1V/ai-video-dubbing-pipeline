"""Tests de /api/auth/login y /api/auth/me."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from video_translator.web.db.models import User


def test_login_success(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="alice@example.com", password="hunter2")

    resp = client.post(
        "/api/auth/login", data={"username": "alice@example.com", "password": "hunter2"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="alice@example.com", password="hunter2")

    resp = client.post(
        "/api/auth/login", data={"username": "alice@example.com", "password": "wrong"}
    )

    assert resp.status_code == 401


def test_login_unknown_email(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login", data={"username": "nobody@example.com", "password": "whatever"}
    )

    assert resp.status_code == 401


def test_login_inactive_user(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="inactive@example.com", password="hunter2", is_active=False)

    resp = client.post(
        "/api/auth/login", data={"username": "inactive@example.com", "password": "hunter2"}
    )

    assert resp.status_code == 401


def test_me_with_valid_token(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="alice@example.com", password="hunter2")
    login_resp = client.post(
        "/api/auth/login", data={"username": "alice@example.com", "password": "hunter2"}
    )
    token = login_resp.json()["access_token"]

    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert body["role"] == "member"


def test_me_without_token(client: TestClient) -> None:
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_invalid_token(client: TestClient) -> None:
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
