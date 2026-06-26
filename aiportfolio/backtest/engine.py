"""Backtesting harness — replay daily history, measure a strategy vs buy-and-hold.

Equities only. (0DTE/options backtesting needs minute-level options data from a
provider like Databento and is out of scope here; see README.)
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone


def fetch_history(market, symbols, start, end) -> dict[str, list[float]]:
    """Aligned daily close series for each symbol over [start, end]."""
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    req = StockBarsRequest(symbol_or_symbols=symbols, timeframe=TimeFrame.Day,
                           start=start, end=end)
    raw = market.data.get_stock_bars(req).data
    by_date: dict[str, dict[str, float]] = {}
    for sym, bars in raw.items():
        for b in bars:
            d = b.timestamp.date().isoformat()
            by_date.setdefault(d, {})[sym] = float(b.close)
    dates = sorted(by_date)
    closes = {s: [] for s in symbols}
    last = {s: None for s in symbols}
    for d in dates:
        for s in symbols:
            px = by_date[d].get(s, last[s])
            closes[s].append(px if px is not None else 0.0)
            if px is not None:
                last[s] = px
    return {s: v for s, v in closes.items() if any(v)}


def run_backtest(closes: dict[str, list[float]], strategy, starting_capital=1000.0,
                 rebalance_every=1, slippage_bps=2):
    n = len(next(iter(closes.values())))
    cash = starting_capital
    shares: dict[str, float] = {}
    equity_curve = []

    for i in range(n):
        price_now = {s: closes[s][i] for s in closes}
        # mark-to-market
        holdings_val = sum(shares.get(s, 0) * price_now[s] for s in closes)
        equity = cash + holdings_val
        equity_curve.append(equity)

        if i % rebalance_every != 0:
            continue
        target = strategy.weights(i, closes)
        # liquidate everything, then re-buy to target (simple, robust).
        for s, sh in list(shares.items()):
            if sh:
                cash += sh * price_now[s] * (1 - slippage_bps / 10000)
        shares = {}
        for s, w in target.items():
            if price_now.get(s, 0) > 0 and w > 0:
                budget = min(equity * w, cash)
                unit_cost = price_now[s] * (1 + slippage_bps / 10000)
                sh = budget / unit_cost
                cost = sh * unit_cost
                if sh > 0 and cost <= cash + 1e-9:
                    shares[s] = shares.get(s, 0) + sh
                    cash -= cost

    return _metrics(equity_curve, starting_capital)


def _metrics(curve, start):
    end = curve[-1]
    total_return = (end / start - 1) * 100
    # daily returns
    rets = [(curve[i] / curve[i - 1] - 1) for i in range(1, len(curve)) if curve[i - 1]]
    avg = sum(rets) / len(rets) if rets else 0
    var = sum((r - avg) ** 2 for r in rets) / len(rets) if rets else 0
    std = math.sqrt(var)
    sharpe = (avg / std * math.sqrt(252)) if std else 0
    # max drawdown
    peak = curve[0]
    max_dd = 0
    for v in curve:
        peak = max(peak, v)
        max_dd = min(max_dd, v / peak - 1)
    days = len(curve)
    cagr = ((end / start) ** (252 / days) - 1) * 100 if days > 1 and start else 0
    return {
        "start_equity": round(start, 2),
        "end_equity": round(end, 2),
        "total_return_pct": round(total_return, 2),
        "cagr_pct": round(cagr, 2),
        "sharpe": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "trading_days": days,
        "equity_curve": [round(x, 2) for x in curve],
    }
