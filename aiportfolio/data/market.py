"""Market data + account state via Alpaca."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient


class MarketData:
    def __init__(self, secrets):
        self._secrets = secrets
        self.trading = TradingClient(
            secrets.alpaca_key, secrets.alpaca_secret, paper=secrets.is_paper
        )
        self.data = StockHistoricalDataClient(secrets.alpaca_key, secrets.alpaca_secret)

    # ── account / positions ────────────────────────────────────────
    def account(self) -> dict:
        a = self.trading.get_account()
        return {
            "equity": float(a.equity),
            "cash": float(a.cash),
            "buying_power": float(a.buying_power),
            "portfolio_value": float(a.portfolio_value),
        }

    def positions(self) -> list[dict]:
        out = []
        for p in self.trading.get_all_positions():
            out.append(
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "avg_entry_price": float(p.avg_entry_price),
                    "current_price": float(p.current_price),
                    "market_value": float(p.market_value),
                    "unrealized_pl": float(p.unrealized_pl),
                    "unrealized_plpc": float(p.unrealized_plpc) * 100,
                }
            )
        return out

    # ── prices ──────────────────────────────────────────────────────
    def latest_price(self, symbol: str) -> float | None:
        try:
            req = StockLatestTradeRequest(symbol_or_symbols=symbol)
            res = self.data.get_stock_latest_trade(req)
            return float(res[symbol].price)
        except Exception:
            return None

    def latest_prices(self, symbols: list[str]) -> dict[str, float]:
        out = {}
        for s in symbols:
            p = self.latest_price(s)
            if p is not None:
                out[s] = p
        return out

    def recent_bars(self, symbol: str, days: int = 30) -> list[dict]:
        """Daily bars for simple technical context (trend, momentum)."""
        try:
            req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=datetime.now(timezone.utc) - timedelta(days=days + 5),
            )
            bars = self.data.get_stock_bars(req).data.get(symbol, [])
            return [{"date": b.timestamp.date().isoformat(), "close": float(b.close)} for b in bars][-days:]
        except Exception:
            return []

    def simple_technicals(self, symbol: str) -> dict:
        """Lightweight, dependency-free trend signals for the prompt."""
        bars = self.recent_bars(symbol, days=30)
        closes = [b["close"] for b in bars]
        if len(closes) < 10:
            return {"symbol": symbol, "note": "insufficient history"}
        sma10 = sum(closes[-10:]) / 10
        sma30 = sum(closes) / len(closes)
        change_5d = (closes[-1] / closes[-6] - 1) * 100 if len(closes) >= 6 else None
        return {
            "symbol": symbol,
            "last": round(closes[-1], 2),
            "sma10": round(sma10, 2),
            "sma30": round(sma30, 2),
            "trend": "up" if sma10 > sma30 else "down",
            "change_5d_pct": round(change_5d, 2) if change_5d is not None else None,
        }

    # ── market clock ────────────────────────────────────────────────
    def is_market_open(self) -> bool:
        try:
            return bool(self.trading.get_clock().is_open)
        except Exception:
            return False
