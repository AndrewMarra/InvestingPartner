"""Build a per-user Config from base defaults + DB settings + decrypted keys.

Two safety properties live here:
  1. WHITELIST — only certain top-level sections may be overridden per user, so a
     user can never repoint the bot at a live-money endpoint via settings.
  2. BOUNDS — even within those sections, risk-relevant numbers are clamped to
     sane limits server-side, so a user can't loosen their OWN guardrails to
     absurd levels (e.g. "100% per position, never kill-switch").
"""
from __future__ import annotations

from ..config import Config, Secrets, deep_merge

# Only these top-level sections may be overridden per user (safety: a user
# can't, say, point the bot at a live-money endpoint via settings).
ALLOWED_OVERRIDES = {"modes", "trading", "options", "risk", "schedule", "notify",
                     "research", "cost_controls", "benchmark", "portfolio"}

# Server-side clamps. Each entry: (dotted path, kind, low, high). A user may make
# things SAFER (e.g. a tighter stop, more cash) but not recklessly less safe.
# Values outside the range are clamped to the nearest bound and noted in the log.
BOUNDS: list[tuple[str, str, float, float]] = [
    ("risk.max_position_pct",            "float", 1,    50),
    ("risk.min_cash_pct",                "float", 0,    100),
    ("risk.max_trade_notional_pct",      "float", 1,    30),
    ("risk.max_trades_per_run",          "int",   1,    10),
    ("risk.daily_loss_limit_pct",        "float", 1,    50),
    ("risk.stop_loss_pct",               "float", 1,    50),
    ("risk.take_profit_pct",             "float", 1,    500),
    ("risk.min_confidence_to_trade",     "float", 0.4,  1.0),
    ("trading.max_trades_per_day",       "int",   1,    50),
    ("options.max_premium_pct_per_trade","float", 0.5,  10),
    ("options.max_contracts",            "int",   1,    20),
    ("options.max_options_trades_per_day","int",  0,    10),
    ("portfolio.starting_capital",       "float", 1000, 10_000_000),
]


def _get(raw: dict, path: str):
    cur = raw
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None, None
        parent, cur = cur, cur[part]
    return parent, path.rsplit(".", 1)[-1]


def clamp_settings(raw: dict) -> list[str]:
    """Clamp risk-relevant numbers in-place. Returns human-readable notes."""
    notes: list[str] = []
    for path, kind, lo, hi in BOUNDS:
        parent, key = _get(raw, path)
        if parent is None:
            continue
        val = parent.get(key)
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            continue
        clamped = max(lo, min(hi, val))
        if kind == "int":
            clamped = int(round(clamped))
        if clamped != val:
            parent[key] = clamped
            notes.append(f"{path} {val}→{clamped} (allowed {lo}-{hi})")
    return notes


def build_user_config(base_raw: dict, user_settings: dict, keys: dict,
                      phone: str | None = None) -> Config:
    safe = {k: v for k, v in (user_settings or {}).items() if k in ALLOWED_OVERRIDES}
    raw = deep_merge(base_raw, safe)
    clamp_settings(raw)  # enforce guardrail bounds even on user-supplied values
    # Each user's audit data is namespaced by user in the DB layer, so the
    # path stays shared; the Store scopes by user_id.
    #
    # KEY ISOLATION: secrets come ONLY from this user's decrypted BYOK keys.
    # There is deliberately no fallback to the host's environment, so one user
    # can never run on another user's (or the host's) API keys.
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
        smtp_host=keys.get("smtp_host") or None,
        smtp_port=int(keys["smtp_port"]) if str(keys.get("smtp_port") or "").isdigit() else None,
        smtp_user=keys.get("smtp_user") or None,
        smtp_pass=keys.get("smtp_pass") or None,
        smtp_from=keys.get("smtp_from") or None,
        email_to=keys.get("email_to") or None,
    )
    return Config(raw=raw, secrets=secrets)


def validate_user_keys(keys: dict) -> list[str]:
    """Return a list of missing REQUIRED keys for a user to run."""
    required = ["alpaca_key", "alpaca_secret", "anthropic_key", "finnhub_key"]
    return [k for k in required if not keys.get(k)]
