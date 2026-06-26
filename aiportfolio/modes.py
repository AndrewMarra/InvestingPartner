"""Trade-style modes.

A user enables any combination of these. The AI may only propose trades whose
mode is enabled, and the prompt is built from exactly the enabled set so the
buddy stays on-style. This is the switchboard the frontend will expose.
"""
from __future__ import annotations

# instrument: equity | option ; horizon: day | short | long
MODES: dict[str, dict] = {
    "equity_short": {"instrument": "equity", "horizon": "short",
                     "label": "Short-term stock shares"},
    "equity_day":   {"instrument": "equity", "horizon": "day",
                     "label": "Intraday stock day trades"},
    "equity_long":  {"instrument": "equity", "horizon": "long",
                     "label": "Long-term stock holds"},
    "option_short": {"instrument": "option", "horizon": "short",
                     "label": "Short-term options (incl. 0DTE)"},
    "option_long":  {"instrument": "option", "horizon": "long",
                     "label": "Long-dated options (LEAPS)"},
}

# What "short term" means, by sub-horizon. Drives expected hold + exit framing.
SHORT_TERM_HORIZONS = {
    "intraday_1d": "open and close the same day (no overnight risk)",
    "daily":       "buy today, exit the next trading day",
    "multiday":    "hold a few days (2-5) then exit",
    "weekly":      "hold about a week then exit",
    "monthly":     "hold roughly a month then exit",
}

DEFAULT_ENABLED = ["equity_short"]
DEFAULT_HORIZON = "daily"


def normalize(cfg) -> tuple[list[str], str]:
    m = cfg.get("modes", {}) or {}
    enabled = [x for x in m.get("enabled", DEFAULT_ENABLED) if x in MODES] or DEFAULT_ENABLED
    horizon = m.get("short_term_horizon", DEFAULT_HORIZON)
    if horizon not in SHORT_TERM_HORIZONS:
        horizon = DEFAULT_HORIZON
    return enabled, horizon


def enabled_instruments(enabled: list[str]) -> set[str]:
    return {MODES[m]["instrument"] for m in enabled}


def prompt_guidance(enabled: list[str], horizon: str) -> str:
    lines = ["You may ONLY propose trades in these enabled modes:"]
    for m in enabled:
        meta = MODES[m]
        extra = ""
        if meta["horizon"] == "short":
            extra = f" — short-term means: {SHORT_TERM_HORIZONS[horizon]}."
        elif m == "option_long":
            extra = " — true LEAPS, expiry ~9-24 months out."
        lines.append(f"  • {m}: {meta['label']}{extra}")
    if any(MODES[m]["instrument"] == "option" for m in enabled):
        lines.append(
            "\nFor options, prefer a DEFINED-RISK debit vertical (strategy='vertical' "
            "with a short_strike) over a naked long option when you can — it caps the "
            "premium at risk. Use a single long option only when a spread doesn't fit.")
    lines.append(
        "\nFor every BUY you MUST include an exit_plan so the trade is never "
        "open-ended. Choose the exit that fits the mode:\n"
        "  - bracket: set BOTH a limit_price (take-profit) and stop_price (stop-loss).\n"
        "  - limit:   a single limit_price to sell into strength.\n"
        "  - stop:    a single stop_price to cap downside.\n"
        "  - time:    hold for hold_days, then sell at market.\n"
        "  - manual_next_day: you'll re-propose the sell next session (for daily style).\n"
        "  - hold:    long-term; no preset exit (long modes only).\n"
        "Decide manual vs automatic yourself and say which in the rationale, so "
        "the user knows whether to set up their own auto-sell when copying."
    )
    return "\n".join(lines)
