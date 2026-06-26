import math
from aiportfolio.backtest.engine import run_backtest
from aiportfolio.backtest.strategies import Momentum, BuyAndHold


def _series():
    n = 120
    spy = [100 * (1.0005) ** i for i in range(n)]
    aaa = [50 * (1.004) ** i if i < 70 else 50 * (1.004) ** 70 * (0.997) ** (i - 70) for i in range(n)]
    bbb = [80 + 5 * math.sin(i / 8) for i in range(n)]
    return {"SPY": spy, "AAA": aaa, "BBB": bbb}


def test_buy_and_hold_captures_drift():
    res = run_backtest(_series(), BuyAndHold("SPY"), 1000)
    assert res["total_return_pct"] > 0
    assert res["trading_days"] == 120


def test_momentum_runs_and_has_metrics():
    res = run_backtest(_series(), Momentum(lookback=20, top_n=1), 1000)
    for k in ("total_return_pct", "cagr_pct", "sharpe", "max_drawdown_pct"):
        assert k in res
    assert res["end_equity"] > 0


def test_no_lookahead_before_lookback():
    # With insufficient history the strategy holds cash (no positions early).
    closes = {"SPY": [100] * 5, "AAA": [50] * 5}
    res = run_backtest(closes, Momentum(lookback=20), 1000)
    assert res["end_equity"] == 1000  # never traded -> flat
