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

You have access to a `web_search` tool. Before forming your opinion, search for \
full articles on any headline that looks material — earnings surprises, analyst \
upgrades/downgrades, M&A rumours, regulatory actions, or major macro news. One \
targeted search per interesting catalyst is enough; skip search for minor or \
stale items.

Principles:
- Quality over quantity. HOLD / empty is a fine cycle; never force trades.
- You have no speed edge and can't reliably predict short-term prices. Lean on \
explainable setups: trend + momentum, catalysts, relative strength, sane \
risk/reward — not vibes.
- Earnings risk: if a symbol reports earnings in 1-2 days, factor that into size \
and exit plan — or skip it unless the setup explicitly accounts for the gap risk.
- Options Greeks: use delta to gauge directional sensitivity, IV to judge whether \
premium is cheap or expensive relative to the expected move.
- Options (incl. 0DTE) are HIGH RISK; size tiny, only on allowed underlyings.
- Insider buying (positive MSPR) and macro catalysts are supporting signals, not \
standalone entry reasons.
- Never invent prices, tickers, strikes, or facts — use only the briefing and \
your search results.

Once you have gathered the context you need, call `submit_decisions`."""


# One trade idea — shared by the autonomous decision tool and the consult tool so
# an override flows through exactly the same downstream machinery.
DECISION_ITEM = {
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
        "strategy": {"type": "string", "enum": ["single", "vertical"],
                     "description": "Option structure. 'vertical' = a debit "
                     "spread (buy strike, sell short_strike) — defined-risk, "
                     "safer than a naked long option."},
        "short_strike": {"type": "number",
                         "description": "For a vertical only: strike of the "
                         "SOLD leg (same right + expiry as strike)."},
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
}


DECISION_TOOL = {
    "name": "submit_decisions",
    "description": "Submit this cycle's trade ideas, each with an exit plan.",
    "input_schema": {
        "type": "object",
        "properties": {
            "market_view": {"type": "string"},
            "decisions": {"type": "array", "items": DECISION_ITEM},
        },
        "required": ["market_view", "decisions"],
    },
}


# ── Consult pass (user points the buddy at one ticker) ───────────────────
def consult_system(mode_guidance: str, intent: str) -> str:
    intents = {
        "advisory": "ADVISORY: give your honest take only. Do NOT propose a trade "
                    "(omit `trade`).",
        "hard_buy": "HARD OVERRIDE: the user wants to buy this. Provide a `trade` "
                    "with a sensible exit_plan anyway. Still give your honest verdict "
                    "and set `agree` to whether YOU think it's smart.",
        "conditional_buy": "CONDITIONAL OVERRIDE: buy ONLY if you genuinely agree it's "
                           "smart. If you agree, set agree=true and include a `trade` "
                           "with an exit_plan. If not, set agree=false, OMIT `trade`, "
                           "and explain why — you can talk the user out of it.",
    }
    return f"""You are an AI trading buddy fielding a question about ONE specific \
ticker. Be portfolio-aware: factor in whether it's already held, at what cost, and \
the current P&L (all in the briefing).

This request is: {intents.get(intent, intents['advisory'])}

{mode_guidance}

Principles:
- Be honest, not a yes-man. A good verdict can be 'avoid' even when asked to buy.
- Any `trade` you include MUST have a valid mode + an exit_plan (no open-ended entries).
- Never invent prices, tickers, or facts — use only the briefing.

Reply via the `consult` tool."""


CONSULT_TOOL = {
    "name": "consult",
    "description": "Your take on one ticker, plus an optional trade to act on.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string",
                        "enum": ["buy", "add", "hold", "trim", "sell", "avoid"]},
            "agree": {"type": "boolean",
                      "description": "For conditional buys: do YOU think buying is smart?"},
            "reasoning": {"type": "string"},
            "trade": DECISION_ITEM,
        },
        "required": ["verdict", "agree", "reasoning"],
    },
}
