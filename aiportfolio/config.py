"""Configuration loading.

Single-user: config.yaml + secrets from the environment (load_config).
Multi-user:  base config.yaml + per-user overrides + per-user decrypted BYOK
             secrets (see multiuser/usercfg.build_user_config).
"""
from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Secrets:
    alpaca_key: str
    alpaca_secret: str
    alpaca_base_url: str
    anthropic_key: str
    finnhub_key: str
    fmp_key: str | None = None
    twilio_sid: str | None = None
    twilio_token: str | None = None
    twilio_from: str | None = None
    alert_to: str | None = None
    telegram_token: str | None = None
    telegram_chat_id: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_pass: str | None = None
    smtp_from: str | None = None
    email_to: str | None = None

    @property
    def is_paper(self) -> bool:
        return "paper" in self.alpaca_base_url

    @property
    def twilio_ready(self) -> bool:
        return all([self.twilio_sid, self.twilio_token, self.twilio_from, self.alert_to])

    @property
    def telegram_ready(self) -> bool:
        return all([self.telegram_token, self.telegram_chat_id])

    @property
    def email_ready(self) -> bool:
        return all([self.smtp_host, self.smtp_user, self.smtp_pass, self.email_to])


@dataclass
class Config:
    raw: dict
    secrets: Secrets

    def __getitem__(self, key):
        return self.raw[key]

    def get(self, key, default=None):
        return self.raw.get(key, default)


def load_base_raw(path: str | None = None) -> dict:
    with open(Path(path) if path else ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively overlay override onto a copy of base."""
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


# ── single-user (env secrets) ────────────────────────────────────────
def _require(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val or val.startswith("your_"):
        raise SystemExit(f"Missing required secret: {name}. Copy .env.example to .env.")
    return val


def _opt(name: str) -> str | None:
    return os.environ.get(name, "").strip() or None


def load_config(path: str | None = None) -> Config:
    raw = load_base_raw(path)
    secrets = Secrets(
        alpaca_key=_require("ALPACA_API_KEY"),
        alpaca_secret=_require("ALPACA_SECRET_KEY"),
        alpaca_base_url=os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets").strip(),
        anthropic_key=_require("ANTHROPIC_API_KEY"),
        finnhub_key=_require("FINNHUB_API_KEY"),
        fmp_key=_opt("FMP_API_KEY"),
        twilio_sid=_opt("TWILIO_ACCOUNT_SID"), twilio_token=_opt("TWILIO_AUTH_TOKEN"),
        twilio_from=_opt("TWILIO_FROM_NUMBER"), alert_to=_opt("ALERT_TO_NUMBER"),
        telegram_token=_opt("TELEGRAM_BOT_TOKEN"), telegram_chat_id=_opt("TELEGRAM_CHAT_ID"),
        smtp_host=_opt("SMTP_HOST"),
        smtp_port=int(os.environ.get("SMTP_PORT", "587") or 587),
        smtp_user=_opt("SMTP_USER"), smtp_pass=_opt("SMTP_PASS"),
        smtp_from=_opt("SMTP_FROM"), email_to=_opt("EMAIL_TO"),
    )
    return Config(raw=raw, secrets=secrets)
