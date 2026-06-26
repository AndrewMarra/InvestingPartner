import tempfile
from datetime import datetime, timezone, timedelta
from dataclasses import asdict
from aiportfolio.storage.db import Store
from aiportfolio.risk.guardrails import ApprovedTrade


def _store(uid="u1"):
    return Store(tempfile.mktemp(suffix=".db"), user_id=uid)


def test_trade_scoping():
    db = tempfile.mktemp(suffix=".db")
    a = Store(db, user_id="alice"); b = Store(db, user_id="bob")
    t = ApprovedTrade(action="BUY", mode="equity_short", symbol="NVDA", notional=50, confidence=0.8)
    a.log_trade(t, {"status": "filled"})
    assert len(a.recent_trades()) == 1
    assert len(b.recent_trades()) == 0
    assert a.trades_today() == 1 and b.trades_today() == 0


def test_pending_and_cancel_buys():
    s = _store()
    buy = ApprovedTrade(action="BUY", mode="equity_short", symbol="NVDA", notional=50)
    sell = ApprovedTrade(action="SELL", mode="equity_short", symbol="AAPL", sell_fraction=1.0)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    s.enqueue(asdict(buy), past)
    s.enqueue(asdict(sell), past)
    assert len(s.ripe_pending()) == 2
    assert s.cancel_pending_buys() == 1  # only the BUY
    # sell remains pending and ripe
    remaining = s.ripe_pending()
    assert len(remaining) == 1


def test_planned_exits():
    s = _store()
    s.add_planned_exit("NVDA", "manual_next_day", hold_days=1)
    # Minimum 1-day hold => a buy today is not exitable until at least the next day.
    assert s.due_exits() == []
    # Backdate to simulate the due day arriving, then verify it surfaces + closes.
    s.conn.execute("UPDATE planned_exits SET due_date='2000-01-01' WHERE symbol='NVDA'")
    s.conn.commit()
    due = s.due_exits()
    assert len(due) == 1 and due[0]["symbol"] == "NVDA"
    s.close_planned_exit(due[0]["id"])
    assert s.due_exits() == []


def test_day_open_equity():
    s = _store()
    assert s.day_open_equity() is None
    s.snapshot(1000.0, 500.0, 600.0)
    s.snapshot(950.0, 500.0, 600.0)
    assert s.day_open_equity() == 1000.0  # first of the day
