"""Tests de /api/users: crear, listar, cambio de rol/estado -- solo admin."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from video_translator.web.db.models import User, UserRole


def _auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_user_requires_admin(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="member@example.com", password="hunter2", role=UserRole.MEMBER)
    headers = _auth_headers(client, "member@example.com", "hunter2")

    resp = client.post(
        "/api/users",
        json={"email": "new@example.com", "password": "hunter2222", "name": "New User"},
        headers=headers,
    )

    assert resp.status_code == 403


def test_create_user_success(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="admin@example.com", password="hunter2", role=UserRole.ADMIN)
    headers = _auth_headers(client, "admin@example.com", "hunter2")

    resp = client.post(
        "/api/users",
        json={
            "email": "new@example.com",
            "password": "hunter2222",
            "name": "New User",
            "role": "member",
        },
        headers=headers,
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@example.com"
    assert body["role"] == "member"
    assert body["is_active"] is True

    # La contraseña recien creada debe servir para loguearse.
    login_resp = client.post(
        "/api/auth/login", data={"username": "new@example.com", "password": "hunter2222"}
    )
    assert login_resp.status_code == 200


def test_create_user_defaults_to_member_role(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="admin@example.com", password="hunter2", role=UserRole.ADMIN)
    headers = _auth_headers(client, "admin@example.com", "hunter2")

    resp = client.post(
        "/api/users",
        json={"email": "new@example.com", "password": "hunter2222", "name": "New User"},
        headers=headers,
    )

    assert resp.status_code == 201
    assert resp.json()["role"] == "member"


def test_create_user_rejects_duplicate_email(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="admin@example.com", password="hunter2", role=UserRole.ADMIN)
    make_user(email="taken@example.com", password="hunter2")
    headers = _auth_headers(client, "admin@example.com", "hunter2")

    resp = client.post(
        "/api/users",
        json={"email": "taken@example.com", "password": "hunter2222", "name": "New User"},
        headers=headers,
    )

    assert resp.status_code == 409


def test_create_user_rejects_short_password(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="admin@example.com", password="hunter2", role=UserRole.ADMIN)
    headers = _auth_headers(client, "admin@example.com", "hunter2")

    resp = client.post(
        "/api/users",
        json={"email": "new@example.com", "password": "short", "name": "New User"},
        headers=headers,
    )

    assert resp.status_code == 422


def test_list_users_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/users")
    assert resp.status_code == 401


def test_list_users_requires_admin(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="member@example.com", password="hunter2", role=UserRole.MEMBER)
    headers = _auth_headers(client, "member@example.com", "hunter2")

    resp = client.get("/api/users", headers=headers)

    assert resp.status_code == 403


def test_list_users_success(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="admin@example.com", password="hunter2", role=UserRole.ADMIN)
    make_user(email="bob@example.com", password="hunter2", role=UserRole.MEMBER)
    headers = _auth_headers(client, "admin@example.com", "hunter2")

    resp = client.get("/api/users", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    emails = {item["email"] for item in body["items"]}
    assert emails == {"admin@example.com", "bob@example.com"}


def test_update_user_requires_admin(client: TestClient, make_user: Callable[..., User]) -> None:
    member = make_user(email="member@example.com", password="hunter2", role=UserRole.MEMBER)
    headers = _auth_headers(client, "member@example.com", "hunter2")

    resp = client.patch(f"/api/users/{member.id}", json={"role": "admin"}, headers=headers)

    assert resp.status_code == 403


def test_update_user_changes_role(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="admin@example.com", password="hunter2", role=UserRole.ADMIN)
    bob = make_user(email="bob@example.com", password="hunter2", role=UserRole.MEMBER)
    headers = _auth_headers(client, "admin@example.com", "hunter2")

    resp = client.patch(f"/api/users/{bob.id}", json={"role": "admin"}, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_update_user_changes_active_state(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="admin@example.com", password="hunter2", role=UserRole.ADMIN)
    bob = make_user(email="bob@example.com", password="hunter2", role=UserRole.MEMBER)
    headers = _auth_headers(client, "admin@example.com", "hunter2")

    resp = client.patch(f"/api/users/{bob.id}", json={"is_active": False}, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_update_user_not_found(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="admin@example.com", password="hunter2", role=UserRole.ADMIN)
    headers = _auth_headers(client, "admin@example.com", "hunter2")

    resp = client.patch(
        "/api/users/00000000-0000-0000-0000-000000000000",
        json={"is_active": False},
        headers=headers,
    )

    assert resp.status_code == 404


def test_update_user_cannot_demote_self(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    admin = make_user(email="admin@example.com", password="hunter2", role=UserRole.ADMIN)
    headers = _auth_headers(client, "admin@example.com", "hunter2")

    resp = client.patch(f"/api/users/{admin.id}", json={"role": "member"}, headers=headers)

    assert resp.status_code == 400


def test_update_user_cannot_deactivate_self(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    admin = make_user(email="admin@example.com", password="hunter2", role=UserRole.ADMIN)
    headers = _auth_headers(client, "admin@example.com", "hunter2")

    resp = client.patch(f"/api/users/{admin.id}", json={"is_active": False}, headers=headers)

    assert resp.status_code == 400
