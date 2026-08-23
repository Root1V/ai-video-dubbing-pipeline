"""Tests de hashing de passwords y JWT."""

from __future__ import annotations

from video_translator.web.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_roundtrip() -> None:
    hashed = hash_password("my-secret")
    assert hashed != "my-secret"
    assert verify_password("my-secret", hashed)
    assert not verify_password("wrong-secret", hashed)


def test_create_and_decode_access_token_roundtrip() -> None:
    token = create_access_token(subject="user-123", expires_minutes=5)
    subject = decode_access_token(token)
    assert subject == "user-123"


def test_decode_access_token_rejects_garbage() -> None:
    assert decode_access_token("not-a-valid-jwt") is None


def test_decode_access_token_rejects_expired_token() -> None:
    # expires_minutes negativo -> "exp" ya quedo en el pasado al codificarlo.
    token = create_access_token(subject="user-123", expires_minutes=-1)
    assert decode_access_token(token) is None
