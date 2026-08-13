from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status

from app.core.config import settings


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return f"pbkdf2_sha256$260000${_b64url_encode(salt)}${_b64url_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            _b64url_decode(salt),
            int(iterations),
        )
        return hmac.compare_digest(_b64url_encode(digest), expected)
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": subject, "exp": int(expires_at.timestamp())}
    signing_input = ".".join(
        [
            _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录状态无效或已过期，请重新登录。",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        header_b64, payload_b64, signature_b64 = token.split(".", 2)
        signing_input = f"{header_b64}.{payload_b64}"
        expected_signature = hmac.new(
            settings.jwt_secret_key.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_b64url_encode(expected_signature), signature_b64):
            raise credentials_error
        payload = json.loads(_b64url_decode(payload_b64))
        if int(payload.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
            raise credentials_error
        return payload
    except (ValueError, json.JSONDecodeError, TypeError):
        raise credentials_error from None


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"
