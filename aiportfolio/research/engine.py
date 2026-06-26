"""Tiered decision engine.

Cost control by design:
  1. Build compact signals (cheap, no model).
  2. TRIAGE with a cheap model (Haiku) — "is anything worth a full look?"
  3. Only if yes, run the DECISION model (Sonnet) on a focused briefing.
Quiet cycles cost a fraction of a cent; the expensive model is reserved for
moments that actually look interesting. Opus is never used in the loop.
"""
from __future__ import annotations

import json

from anthropic import Anthropic

from . import prompts
from .. import modes as modes_mod


class ResearchEngine:
    def __init__(self, secrets, cfg, market, news, fundamentals, options=None):
        self.client = Anthropic(api_key=secrets.anthropic_key)
        self.cfg = cfg
        self.market = market
        self.news = news
        self.fundamentals = fundamentals
        self.options = options
        mc = cfg["models"]
        self.decision_model = mc["decision_model"]
        self.triage_model = mc["triage_model"]
        self.max_tokens = mc["max_tokens"]
        self.temperature = mc["temperature"]
        self.universe = cfg["research"]["candidate_universe"]
        self.opt_cfg = cfg.get("options", {}) or {}
        self.cost = cfg.get("cost_controls", {}) or {}
        self.enabled_modes, self.horizon = modes_mod.normalize(cfg)
        self.instruments = modes_mod.enabled_instruments(self.enabled_modes)

    # ── shared model helper ──────────────────────────────────────────
    def _tool_call(self, model, system, tool, user_msg):
        resp = self.client.messages.create(
            model=model, max_tokens=self.max_tokens, temperature=self.temperature,
            system=system, tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{"role": "user", "content": user_msg}])
        for b in resp.content:
            if getattr(b, "type", None) == "tool_use" and b.name == tool["name"]:
                return b.input
        return None

    # ── cheap triage ─────────────────────────────────────────────────
    def compact_signals(self) -> dict:
        positions = self.market.positions()
        held = {p["symbol"] for p in positions}
        symbols = sorted(held | set(self.universe))
        tech = {s: self.market.simple_technicals(s) for s in symbols}
        heads = {s: [n["headline"] for n in self.news.company_news(s, days=1, limit=2)]
                 for s in symbols}
        return {"technicals": tech, "headlines": heads, "held": list(held)}

    def triage(self, compact: dict) -> dict:
        if not self.cost.get("triage_enabled", True):
            return {"worth_analyzing": True, "watch": [], "reason": "triage disabled"}
        msg = ("Watchlist signals:\n```json\n"
               + json.dumps(compact, indent=2, default=str) + "\n```")
        out = self._tool_call(self.triage_model, prompts.TRIAGE_SYSTEM,
                              prompts.TRIAGE_TOOL, msg)
        return out or {"worth_analyzing": False, "watch": [], "reason": "triage failed"}

    # ── full decision ────────────────────────────────────────────────
    def build_briefing(self, focus: list[str] | None) -> dict:
        account = self.market.account()
        positions = self.market.positions()
        held = {p["symbol"] for p in positions}
        pool = set(self.universe) | held
        if focus:
            pool = (set(focus) & pool) | held or pool
        symbols = sorted(pool)

        news = {s: self.news.company_news(s, days=2, limit=3) for s in symbols}
        technicals = {s: self.market.simple_technicals(s) for s in symbols}
        funds = ({s: self.fundamentals.snapshot(s) for s in symbols}
                 if self.fundamentals.enabled else {})

        options_snapshot = {}
        if self.options and "option" in self.instruments and self.opt_cfg.get("enabled"):
            unders = self.opt_cfg.get("allowed_underlyings", [])
            spot = self.market.latest_prices(unders)
            options_snapshot = self.options.snapshot_for_prompt(unders, spot)

        return {
            "account": account, "positions": positions,
            "enabled_modes": self.enabled_modes, "short_term_horizon": self.horizon,
            "candidate_universe": self.universe,
            "market_news": self.news.market_news(limit=5),
            "company_news": news, "technicals": technicals, "fundamentals": funds,
            "options_chain_0dte": options_snapshot,
            "risk_limits": self.cfg["risk"],
        }

    def decide(self, briefing: dict) -> dict:
        guidance = modes_mod.prompt_guidance(self.enabled_modes, self.horizon)
        system = prompts.decision_system(guidance)
        msg = ("Briefing — surface your best idea(s) via submit_decisions "
               "(HOLD/empty is fine):\n```json\n"
               + json.dumps(briefing, indent=2, default=str) + "\n```")
        out = self._tool_call(self.decision_model, system, prompts.DECISION_TOOL, msg)
        if out is None:
            raise RuntimeError("Decision model returned no tool call.")
        return out
