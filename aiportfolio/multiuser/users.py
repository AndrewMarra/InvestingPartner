"""Per-user store: accounts, settings, and encrypted BYOK keys.

SQLite locally (zero setup, testable); the same schema maps to Supabase
Postgres in production (see supabase/schema.sql). Secrets are encrypted at rest.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from . import crypto

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, email TEXT UNIQUE, phone TEXT,
    active INTEGER DEFAULT 1, created_at TEXT);
CREATE TABLE IF NOT EXISTS user_keys (
    user_id TEXT, provider TEXT, ciphertext TEXT,
    PRIMARY KEY (user_id, provider));
CREATE TABLE IF NOT EXISTS user_settings (
    user_id TEXT PRIMARY KEY, settings TEXT);
"""

# Which BYOK secrets we store (per provider).
KEY_PROVIDERS = [
    "alpaca_key", "alpaca_secret", "anthropic_key", "finnhub_key", "fmp_key",
    "twilio_sid", "twilio_token", "twilio_from", "telegram_token", "telegram_chat_id",
]


def _now():
    return datetime.now(timezone.utc).isoformat()


class UserStore:
    def __init__(self, db_path="portfolio.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def add_user(self, email: str, phone: str) -> str:
        uid = str(uuid.uuid4())
        self.conn.execute("INSERT INTO users (id, email, phone, created_at) VALUES (?,?,?,?)",
                          (uid, email, phone, _now()))
        self.conn.commit()
        return uid

    def get_user(self, user_id: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(r) if r else None

    def list_active(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM users WHERE active=1").fetchall()]

    def set_active(self, user_id: str, active: bool):
        self.conn.execute("UPDATE users SET active=? WHERE id=?", (1 if active else 0, user_id))
        self.conn.commit()

    # ── encrypted keys ───────────────────────────────────────────────
    def set_keys(self, user_id: str, keys: dict):
        for provider, value in keys.items():
            if provider not in KEY_PROVIDERS or not value:
                continue
            self.conn.execute(
                "INSERT OR REPLACE INTO user_keys (user_id, provider, ciphertext) VALUES (?,?,?)",
                (user_id, provider, crypto.encrypt(value)))
        self.conn.commit()

    def get_keys(self, user_id: str) -> dict:
        rows = self.conn.execute("SELECT provider, ciphertext FROM user_keys WHERE user_id=?",
                                 (user_id,)).fetchall()
        return {r["provider"]: crypto.decrypt(r["ciphertext"]) for r in rows}

    # ── settings ─────────────────────────────────────────────────────
    def set_settings(self, user_id: str, settings: dict):
        self.conn.execute("INSERT OR REPLACE INTO user_settings (user_id, settings) VALUES (?,?)",
                          (user_id, json.dumps(settings)))
        self.conn.commit()

    def get_settings(self, user_id: str) -> dict:
        r = self.conn.execute("SELECT settings FROM user_settings WHERE user_id=?",
                              (user_id,)).fetchone()
        return json.loads(r["settings"]) if r and r["settings"] else {}
