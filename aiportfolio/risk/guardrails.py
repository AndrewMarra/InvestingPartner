"""Hard risk guardrails. The AI proposes; this layer disposes.

Now also enforces enabled trade-MODES (rejects any idea whose mode the user
hasn't turned on) and carries each trade's exit_plan through to execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import modes as modes_mod


@dataclass
class ApprovedTrade:
    action: str
    instrument: str = "equity"
    mode: str = "equity_short"
    symbol: str = ""
    notional: float | None = None
    sell_fraction: float | None = None
    underlying: str = ""
    right: str = ""
    strike: float = 0.0
    expiry_label: str = ""
    zero_dte: bool = False
    contracts: int = 0
    est_premium: float | None = None
    exit_plan: dict = field(default_factory=dict)
    rationale: str = ""
    confidence: float = 0.0
    adjustments: list[str] = field(default_factory=list)


class RiskManager:
    def __init__(self, cfg):
        r = cfg["risk"]
        self.max_position_pct = r["max_position_pct"]
        self.min_cash_pct = r["min_cash_pct"]
        self.max_trades_per_run = r["max_trades_per_run"]
        self.max_trade_notional_pct = r["max_trade_notional_pct"]
        self.min_confidence = r["min_confidence_to_trade"]
        self.stop_loss_pct = r["stop_loss_pct"]
        self.take_profit_pct = r["take_profit_pct"]
        self.daily_loss_limit_pct = r.get("daily_loss_limit_pct", 100)

        t = cfg.get("trading", {}) or {}
        self.max_trades_per_day = t.get("max_trades_per_day", 8)
        self.no_crypto = t.get("no_crypto", True)

        o = cfg.get("options", {}) or {}
        self.allowed_underlyings = set(o.get("allowed_underlyings", []))
        self.max_options_trades_per_day = o.get("max_options_trades_per_day", 3)
        self.max_premium_pct = o.get("max_premium_pct_per_trade", 3)
        self.max_contracts = o.get("max_contracts", 5)
        self.allow_0dte = o.get("allow_0dte", True)

        self.enabled_modes, _ = modes_mod.normalize(cfg)

    def forced_exits(self, positions):
        exits = []
        for p in positions:
            plpc = p["unrealized_plpc"]
            if plpc <= -self.stop_loss_pct:
                exits.append(ApprovedTrade(action="SELL", symbol=p["symbol"], sell_fraction=1.0,
                    rationale=f"Stop-loss: down {plpc:.1f}%.", confidence=1.0,
                    adjustments=["forced stop-loss"]))
            elif plpc >= self.take_profit_pct:
                exits.append(ApprovedTrade(action="SELL", symbol=p["symbol"], sell_fraction=0.5,
                    rationale=f"Take-profit: up {plpc:.1f}%.", confidence=1.0,
                    adjustments=["forced take-profit"]))
        return exits

    @staticmethod
    def _is_crypto(sym):
        return "/" in sym

    def review(self, decisions, account, positions, trades_today=0, option_quoter=None):
        equity = account["equity"]; cash = account["cash"]
        pos = {p["symbol"]: p for p in positions}
        approved: list[ApprovedTrade] = []
        projected_cash = cash; options_used = 0
        max_notional = equity * self.max_trade_notional_pct / 100
        max_position_val = equity * self.max_position_pct / 100
        cash_floor = equity * self.min_cash_pct / 100
        max_premium = equity * self.max_premium_pct / 100

        for d in decisions:
            if len(approved) >= self.max_trades_per_run: break
            if trades_today + len(approved) >= self.max_trades_per_day: break

            mode = d.get("mode", "equity_short")
            if mode not in self.enabled_modes:
                continue  # user hasn't enabled this trade style
            action = d.get("action"); conf = float(d.get("confidence", 0))
            if action == "HOLD" or conf < self.min_confidence:
                continue
            instrument = modes_mod.MODES.get(mode, {}).get("instrument", "equity")
            notes = []

            if instrument == "option":
                underlying = (d.get("underlying") or d.get("symbol") or "").upper()
                if underlying not in self.allowed_underlyings: continue
                if options_used >= self.max_options_trades_per_day: continue
                zero_dte = bool(d.get("zero_dte", False))
                if zero_dte and not self.allow_0dte: continue
                right = (d.get("right") or "call").lower()
                strike = float(d.get("strike", 0) or 0)
                contracts = int(d.get("contracts", 1) or 1)
                if strike <= 0 or contracts < 1: continue
                if contracts > self.max_contracts:
                    notes.append(f"contracts capped at {self.max_contracts}")
                    contracts = self.max_contracts
                est_premium = None
                if option_quoter:
                    est = option_quoter(underlying, right, strike, zero_dte)
                    if est:
                        est_premium = est * 100 * contracts
                        while est_premium > max_premium and contracts > 1:
                            contracts -= 1; est_premium = est * 100 * contracts
                        if est_premium > max_premium:
                            continue
                        notes.append(f"premium ~${est_premium:.0f} (cap ${max_premium:.0f})")
                approved.append(ApprovedTrade(action="BUY", instrument="option", mode=mode,
                    underlying=underlying, right=right, strike=strike, contracts=contracts,
                    zero_dte=zero_dte, expiry_label="0DTE" if zero_dte else "weekly",
                    est_premium=est_premium, exit_plan=d.get("exit_plan", {}) or {},
                    rationale=d.get("rationale", ""), confidence=conf, adjustments=notes))
                options_used += 1
                continue

            # equity
            symbol = (d.get("symbol") or "").upper()
            if not symbol or (self.no_crypto and self._is_crypto(symbol)): continue
            if action == "SELL":
                if symbol not in pos: continue
                frac = max(0.0, min(1.0, float(d.get("sell_fraction", 1.0) or 1.0)))
                approved.append(ApprovedTrade(action="SELL", mode=mode, symbol=symbol,
                    sell_fraction=frac, rationale=d.get("rationale", ""),
                    confidence=conf, adjustments=notes))
                projected_cash += pos[symbol]["market_value"] * frac
            elif action == "BUY":
                notional = float(d.get("notional", 0) or 0)
                if notional <= 0: continue
                if notional > max_notional:
                    notes.append(f"trimmed to per-trade cap ${max_notional:.0f}"); notional = max_notional
                existing = pos.get(symbol, {}).get("market_value", 0.0)
                if existing + notional > max_position_val:
                    notional = max(0.0, max_position_val - existing); notes.append(f"capped to {self.max_position_pct}% position")
                if projected_cash - notional < cash_floor:
                    notional = max(0.0, projected_cash - cash_floor); notes.append(f"kept {self.min_cash_pct}% cash floor")
                if notional < 1: continue
                approved.append(ApprovedTrade(action="BUY", mode=mode, symbol=symbol,
                    notional=round(notional, 2), exit_plan=d.get("exit_plan", {}) or {},
                    rationale=d.get("rationale", ""), confidence=conf, adjustments=notes))
                projected_cash -= notional
        return approved
