"""Prompts + schemas for the tiered decision engine (triage + decision)."""

# ── Cheap triage pass (Haiku): is this cycle even worth a full analysis? ──
TRIAGE_SYSTEM = """You are a fast market triage filter. You are given compact \
signals (price trend, 5-day move, a few headlines) for a watchlist. Your only \
job is to decide whether anything looks worth a deeper, more expensive analysis \
RIGHT NOW, and if so which symbols. Be selective — most cycles, nothing is \
compelling and the right answer is worth_analyzing = false. Reply only via the \
`triage` tool."""

TRIAGE_TOOL = {
    "name": "triage",
    "description": "Decide whether a full analysis is warranted this cycle.",
    "input_schema": {
        "type": "object",
        "properties": {
            "worth_analyzing": {"type": "boolean"},
            "watch": {"type": "array", "items": {"type": "string"},
                      "description": "Symbols that look interesting (empty if none)."},
            "reason": {"type": "string"},
        },
        "required": ["worth_analyzing", "watch", "reason"],
    },
}


# ── Full decision pass (Sonnet) ──────────────────────────────────────────
def decision_system(mode_guidance: str) -> str:
    return f"""You are an AI trading buddy. Each cycle you surface the best \
trade idea(s) for a friend who approves and executes every real-money trade \
themselves. You also keep a paper-traded track record.

{mode_guidance}

Principles:
- Quality over quantity. HOLD / empty is a fine cycle; never force trades.
- You have no speed edge and can't reliably predict short-term prices. Lean on \
explainable setups: trend + momentum, catalysts, relative strength, sane \
risk/reward — not vibes.
- Options (incl. 0DTE) are HIGH RISK; size tiny, only on allowed underlyings.
- Never invent prices, tickers, strikes, or facts — use only the briefing.

Return everything via the `submit_decisions` tool."""


DECISION_TOOL = {
    "name": "submit_decisions",
    "description": "Submit this cycle's trade ideas, each with an exit plan.",
    "input_schema": {
        "type": "object",
        "properties": {
            "market_view": {"type": "string"},
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "mode": {"type": "string",
                                 "enum": ["equity_short", "equity_day", "equity_long",
                                          "option_short", "option_long"]},
                        "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
                        "symbol": {"type": "string"},
                        "notional": {"type": "number", "description": "Equity BUY $ amount."},
                        "sell_fraction": {"type": "number", "description": "Equity SELL fraction 0-1."},
                        "underlying": {"type": "string"},
                        "right": {"type": "string", "enum": ["call", "put"]},
                        "strike": {"type": "number"},
                        "zero_dte": {"type": "boolean"},
                        "contracts": {"type": "integer"},
                        "exit_plan": {
                            "type": "object",
                            "description": "REQUIRED for BUY. How/when this trade is closed.",
                            "properties": {
                                "type": {"type": "string",
                                         "enum": ["bracket", "limit", "stop", "time",
                                                  "manual_next_day", "hold"]},
                                "limit_price": {"type": "number"},
                                "stop_price": {"type": "number"},
                                "hold_days": {"type": "integer"},
                                "notes": {"type": "string"},
                            },
                            "required": ["type"],
                        },
                        "confidence": {"type": "number"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["mode", "action", "confidence", "rationale"],
                },
            },
        },
        "required": ["market_view", "decisions"],
    },
}
