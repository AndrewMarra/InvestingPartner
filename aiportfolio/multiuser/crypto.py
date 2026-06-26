"""Encryption for BYOK secrets at rest.

Users bring their own API keys; we must never store them in plaintext. Keys are
encrypted with Fernet (AES-128-CBC + HMAC) using a server-held master key from
MASTER_ENCRYPTION_KEY. Generate one with `python run.py users keygen`.
"""
from __future__ import annotations

import os

from cryptography.fernet import Fernet


def generate_key() -> str:
    return Fernet.generate_key().decode()


def _fernet() -> Fernet:
    key = os.environ.get("MASTER_ENCRYPTION_KEY", "").strip()
    if not key:
        raise SystemExit(
            "MASTER_ENCRYPTION_KEY not set. Generate one with "
            "`python run.py users keygen` and put it in your environment / Actions secrets."
        )
    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    if plaintext is None:
        return ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    if not token:
        return ""
    return _fernet().decrypt(token.encode()).decode()
