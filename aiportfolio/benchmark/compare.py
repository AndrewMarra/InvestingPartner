"""Compare the AI portfolio against the S&P 500 and (optionally) your own."""
from __future__ import annotations


def performance_report(cfg, store, market) -> dict:
    snaps = store.snapshots()
    starting = cfg["portfolio"]["starting_capital"]
    account = market.account()
    equity = account["equity"]

    bench_symbol = cfg["benchmark"]["symbol"]
    bench_now = market.latest_price(bench_symbol)

    # Find the first snapshot that recorded a benchmark price as the baseline.
    bench_start = next((s["benchmark_price"] for s in snaps if s["benchmark_price"]), None)

    ai_return = (equity / starting - 1) * 100 if starting else None
    bench_return = (
        (bench_now / bench_start - 1) * 100
        if bench_now and bench_start else None
    )
    personal = cfg["benchmark"].get("personal_return_pct")

    return {
        "ai_equity": round(equity, 2),
        "starting_capital": starting,
        "ai_return_pct": round(ai_return, 2) if ai_return is not None else None,
        "benchmark_symbol": bench_symbol,
        "benchmark_return_pct": round(bench_return, 2) if bench_return is not None else None,
        "personal_return_pct": personal,
        "snapshots": len(snaps),
    }
