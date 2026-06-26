"""Execution via Alpaca — equities with exit plans, plus options.

Exit handling for equity BUYs:
  - bracket: market buy whole shares + attached take-profit AND stop-loss (atomic)
  - limit / stop: market buy + a one-sided exit (OTO)
  - time / manual_next_day / hold: plain buy; the loop tracks the planned exit
Fractional or sub-$1-per-share notional falls back to a plain buy + planned exit
(advanced order types require whole shares on Alpaca).
"""
from __future__ import annotations

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from alpaca.trading.requests import (
    MarketOrderRequest, LimitOrderRequest, StopOrderRequest,
    TakeProfitRequest, StopLossRequest,
)


class Broker:
    def __init__(self, secrets, options_data=None):
        self.client = TradingClient(secrets.alpaca_key, secrets.alpaca_secret,
                                    paper=secrets.is_paper)
        self.is_paper = secrets.is_paper
        self.options = options_data

    # ── equities ────────────────────────────────────────────────────
    def buy_with_exit(self, symbol, notional, exit_plan, price):
        """Returns (order_result, planned_exit_or_None)."""
        plan = exit_plan or {}
        ptype = plan.get("type", "manual_next_day")
        whole = int(notional // price) if price and price > 0 else 0

        # Advanced exits need whole shares.
        if whole >= 1 and ptype in ("bracket", "limit", "stop"):
            try:
                kwargs = dict(symbol=symbol, qty=whole, side=OrderSide.BUY,
                              time_in_force=TimeInForce.DAY)
                if ptype == "bracket" and plan.get("limit_price") and plan.get("stop_price"):
                    kwargs.update(order_class=OrderClass.BRACKET,
                                  take_profit=TakeProfitRequest(limit_price=round(plan["limit_price"], 2)),
                                  stop_loss=StopLossRequest(stop_price=round(plan["stop_price"], 2)))
                elif ptype == "limit" and plan.get("limit_price"):
                    kwargs.update(order_class=OrderClass.OTO,
                                  take_profit=TakeProfitRequest(limit_price=round(plan["limit_price"], 2)))
                elif ptype == "stop" and plan.get("stop_price"):
                    kwargs.update(order_class=OrderClass.OTO,
                                  stop_loss=StopLossRequest(stop_price=round(plan["stop_price"], 2)))
                res = self._fmt(self.client.submit_order(order_data=MarketOrderRequest(**kwargs)))
                res["exit_attached"] = ptype
                return res, None
            except Exception as e:
                # Fall back to a plain buy + planned manual exit.
                res = self.buy_notional(symbol, notional)
                return res, {"symbol": symbol, "type": "manual_next_day",
                             "note": f"advanced exit failed ({e}); manual fallback"}

        # Plain buy; loop tracks a planned (manual/time) exit.
        res = self.buy_notional(symbol, notional)
        planned = None
        if ptype in ("time", "manual_next_day"):
            planned = {"symbol": symbol, "type": ptype,
                       "hold_days": plan.get("hold_days", 1), "note": plan.get("notes", "")}
        return res, planned

    def buy_notional(self, symbol, notional):
        o = MarketOrderRequest(symbol=symbol, notional=round(notional, 2),
                               side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
        return self._fmt(self.client.submit_order(order_data=o))

    def sell_fraction(self, symbol, fraction):
        try:
            pos = self.client.get_open_position(symbol)
        except Exception:
            return None
        qty = round(float(pos.qty) * max(0.0, min(1.0, fraction)), 6)
        if qty <= 0: return None
        o = MarketOrderRequest(symbol=symbol, qty=qty, side=OrderSide.SELL,
                               time_in_force=TimeInForce.DAY)
        return self._fmt(self.client.submit_order(order_data=o))

    # ── options ─────────────────────────────────────────────────────
    def buy_option(self, t):
        if not self.options:
            return {"status": "notify_only", "reason": "options data not configured"}
        c = self.options.find_contract(t.underlying, t.right, t.strike, t.zero_dte)
        if not c:
            return {"status": "notify_only", "reason": "contract not found"}
        try:
            o = MarketOrderRequest(symbol=c["symbol"], qty=t.contracts,
                                   side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
            res = self._fmt(self.client.submit_order(order_data=o))
            res["contract"] = c["symbol"]
            return res
        except Exception as e:
            return {"status": "notify_only", "reason": str(e), "contract": c["symbol"]}

    @staticmethod
    def _fmt(o):
        return {"id": str(o.id), "symbol": o.symbol,
                "side": str(o.side).split(".")[-1],
                "qty": float(o.qty) if o.qty else None,
                "notional": float(o.notional) if o.notional else None,
                "status": str(o.status).split(".")[-1]}
