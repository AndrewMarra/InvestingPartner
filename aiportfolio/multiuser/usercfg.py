"""Build a per-user Config from base defaults + DB settings + decrypted keys."""
from __future__ import annotations

from ..config import Config, Secrets, deep_merge

# Only these top-level sections may be overridden per user (safety: a user
# can't, say, point the bot at a live-money endpoint via settings).
ALLOWED_OVERRIDES = {"modes", "trading", "options", "risk", "schedule", "notify",
                     "research", "cost_controls", "benchmark"}


def build_user_config(base_raw: dict, user_settings: dict, keys: dict,
                      phone: str | None = None) -> Config:
    safe = {k: v for k, v in (user_settings or {}).items() if k in ALLOWED_OVERRIDES}
    raw = deep_merge(base_raw, safe)
    # Each user's audit data is namespaced by user in the DB layer, so the
    # path stays shared; the Store scopes by user_id.
    secrets = Secrets(
        alpaca_key=keys.get("alpaca_key", ""),
        alpaca_secret=keys.get("alpaca_secret", ""),
        alpaca_base_url="https://paper-api.alpaca.markets",  # BYOK paper by default
        anthropic_key=keys.get("anthropic_key", ""),
        finnhub_key=keys.get("finnhub_key", ""),
        fmp_key=keys.get("fmp_key") or None,
        twilio_sid=keys.get("twilio_sid") or None,
        twilio_token=keys.get("twilio_token") or None,
        twilio_from=keys.get("twilio_from") or None,
        alert_to=phone or None,
        telegram_token=keys.get("telegram_token") or None,
        telegram_chat_id=keys.get("telegram_chat_id") or None,
    )
    return Config(raw=raw, secrets=secrets)


def validate_user_keys(keys: dict) -> list[str]:
    """Return a list of missing REQUIRED keys for a user to run."""
    required = ["alpaca_key", "alpaca_secret", "anthropic_key", "finnhub_key"]
    return [k for k in required if not keys.get(k)]
