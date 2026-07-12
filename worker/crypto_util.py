"""Credential encryption helpers (AES-256-GCM)."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _key() -> bytes:
    secret = os.environ.get("APP_SECRET")
    if not secret:
        raise RuntimeError("APP_SECRET is required to encrypt/decrypt credentials")
    return hashlib.sha256(secret.encode("utf-8")).digest()


def encrypt_credentials(payload: dict[str, str]) -> str:
    key = _key()
    aes = AESGCM(key)
    nonce = os.urandom(12)
    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ciphertext = aes.encrypt(nonce, plaintext, None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_credentials(blob: str) -> dict[str, Any]:
    padded = blob + ("=" * (-len(blob) % 4))
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    nonce, ciphertext = raw[:12], raw[12:]
    aes = AESGCM(_key())
    plaintext = aes.decrypt(nonce, ciphertext, None)
    data = json.loads(plaintext.decode("utf-8"))
    if not isinstance(data, dict) or "id" not in data or "pw" not in data:
        raise ValueError("invalid credentials payload")
    return data
