"""Pluggable backtest strategies.

A strategy maps (day index, price history) -> target weights per symbol
(0..1, summing to <= 1; the remainder is cash). This keeps the backtester
agnostic to how signals are produced.

Shipped: BuyAndHold (benchmark) and Momentum (fast, free). An AI-driven
strategy is a documented extension — it requires reconstructing a point-in-time
briefing for each day and spends real API budget, so it is intentionally not
the default. See README.
"""
from __future__ import annotations


class Strategy:
    name = "base"

    def weights(self, i: int, closes: dict[str, list[float]]) -> dict[str, float]:
        raise NotImplementedError


class BuyAndHold(Strategy):
    name = "buy_and_hold"

    def __init__(self, symbol: str = "SPY"):
        self.symbol = symbol

    def weights(self, i, closes):
        return {self.symbol: 1.0} if self.symbol in closes else {}


class Momentum(Strategy):
    """Hold the top-N names by trailing return, if that return is positive."""
    name = "momentum"

    def __init__(self, lookback: int = 20, top_n: int = 3, min_return: float = 0.0):
        self.lookback = lookback
        self.top_n = top_n
        self.min_return = min_return

    def weights(self, i, closes):
        if i < self.lookback:
            return {}
        scored = []
        for sym, series in closes.items():
            if sym in ("SPY",):  # keep benchmark out of the tradable set
                continue
            past = series[i - self.lookback]
            now = series[i]
            if past and past > 0:
                scored.append((sym, now / past - 1))
        scored = [s for s in scored if s[1] > self.min_return]
        scored.sort(key=lambda x: x[1], reverse=True)
        picks = scored[: self.top_n]
        if not picks:
            return {}
        w = 1.0 / len(picks)
        return {sym: w for sym, _ in picks}
