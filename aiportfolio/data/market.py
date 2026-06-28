"""Market data + account state via Alpaca."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient


def _compute_rsi(closes: list[float], period: int = 14) -> float | None:
    """Wilder's smoothed RSI. Returns None if there are fewer than period+1 bars."""
    if len(closes) < period + 1:
        return None
    deltas = [closes[i + 1] - closes[i] for i in range(len(closes) - 1)]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1 + rs))


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

    def recent_bars(self, symbol: str, days: int = 60) -> list[dict]:
        """Daily bars including volume for technical analysis."""
        try:
            req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=datetime.now(timezone.utc) - timedelta(days=days + 10),
            )
            bars = self.data.get_stock_bars(req).data.get(symbol, [])
            return [
                {
                    "date": b.timestamp.date().isoformat(),
                    "close": float(b.close),
                    "volume": float(b.volume),
                }
                for b in bars
            ][-days:]
        except Exception:
            return []

    def simple_technicals(self, symbol: str) -> dict:
        """Trend, momentum, RSI-14, volume trend, and period hi/lo proximity."""
        bars = self.recent_bars(symbol, days=60)
        closes = [b["close"] for b in bars]
        volumes = [b.get("volume", 0) for b in bars]
        if len(closes) < 10:
            return {"symbol": symbol, "note": "insufficient history"}

        n = len(closes)
        sma10 = sum(closes[-10:]) / 10
        sma30 = sum(closes[-min(30, n):]) / min(30, n)
        change_5d = (closes[-1] / closes[-6] - 1) * 100 if n >= 6 else None

        rsi = _compute_rsi(closes)

        vol_ratio = None
        if len(volumes) >= 20 and volumes[-1] and sum(volumes[-20:]):
            avg20 = sum(volumes[-20:]) / 20
            vol_ratio = round(volumes[-1] / avg20, 2) if avg20 else None

        hi = max(closes)
        lo = min(closes)
        pct_from_hi = round((closes[-1] - hi) / hi * 100, 1)
        pct_from_lo = round((closes[-1] - lo) / lo * 100, 1) if lo else None

        return {
            "symbol": symbol,
            "last": round(closes[-1], 2),
            "sma10": round(sma10, 2),
            "sma30": round(sma30, 2),
            "trend": "up" if sma10 > sma30 else "down",
            "change_5d_pct": round(change_5d, 2) if change_5d is not None else None,
            "rsi_14": round(rsi, 1) if rsi is not None else None,
            "volume_vs_20d_avg": vol_ratio,
            "pct_from_period_high": pct_from_hi,
            "pct_from_period_low": pct_from_lo,
        }

    # ── market clock ────────────────────────────────────────────────
    def is_market_open(self) -> bool:
        try:
            return bool(self.trading.get_clock().is_open)
        except Exception:
            return False
