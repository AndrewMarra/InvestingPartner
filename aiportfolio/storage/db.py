"""SQLite audit trail, pending queue, and planned-exit tracking.

Multi-tenant: every row is scoped by user_id (defaults to 'local' for the
single-user setup). The same schema maps to Supabase Postgres in production.
"""
from __future__ import annotations

import json, sqlite3
from datetime import datetime, timezone, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, ts TEXT, market_view TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, ts TEXT, instrument TEXT, mode TEXT,
    action TEXT, symbol TEXT, detail TEXT, confidence REAL, rationale TEXT,
    adjustments TEXT, order_result TEXT);
CREATE TABLE IF NOT EXISTS pending (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, ts TEXT, execute_after TEXT,
    status TEXT DEFAULT 'pending', trade TEXT);
CREATE TABLE IF NOT EXISTS planned_exits (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, ts TEXT, symbol TEXT, exit_type TEXT,
    due_date TEXT, status TEXT DEFAULT 'open', note TEXT);
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, ts TEXT, date TEXT, equity REAL,
    cash REAL, benchmark_price REAL);
CREATE TABLE IF NOT EXISTS consult_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, ts TEXT, symbol TEXT,
    intent TEXT, status TEXT DEFAULT 'pending', result TEXT);
"""


def _now(): return datetime.now(timezone.utc)


class Store:
    def __init__(self, db_path, user_id="local"):
        self.user_id = user_id
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA); self.conn.commit()

    def log_decision(self, market_view, payload):
        self.conn.execute("INSERT INTO decisions (user_id, ts, market_view, payload) VALUES (?,?,?,?)",
                          (self.user_id, _now().isoformat(), market_view, json.dumps(payload, default=str)))
        self.conn.commit()

    def decisions_today(self):
        d = _now().date().isoformat()
        r = self.conn.execute("SELECT COUNT(*) c FROM decisions WHERE user_id=? AND substr(ts,1,10)=?",
                              (self.user_id, d)).fetchone()
        return r["c"] if r else 0

    def log_trade(self, t, order_result):
        if t.instrument == "option":
            detail = f"{t.contracts}x {t.underlying} {t.expiry_label} {t.strike:g}{t.right[:1].upper()}"
        elif t.action == "BUY":
            detail = f"${t.notional}"
        else:
            detail = f"{t.sell_fraction:.0%}"
        self.conn.execute("""INSERT INTO trades (user_id, ts, instrument, mode, action, symbol, detail,
            confidence, rationale, adjustments, order_result) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (self.user_id, _now().isoformat(), t.instrument, t.mode, t.action, t.symbol or t.underlying,
             detail, t.confidence, t.rationale, json.dumps(t.adjustments),
             json.dumps(order_result, default=str) if order_result else None))
        self.conn.commit()

    def trades_today(self):
        d = _now().date().isoformat()
        r = self.conn.execute("SELECT COUNT(*) c FROM trades WHERE user_id=? AND substr(ts,1,10)=?",
                              (self.user_id, d)).fetchone()
        return r["c"] if r else 0

    def recent_trades(self, limit=20):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM trades WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (self.user_id, limit)).fetchall()]

    # pending
    def enqueue(self, trade_dict, execute_after):
        self.conn.execute("INSERT INTO pending (user_id, ts, execute_after, trade) VALUES (?,?,?,?)",
                          (self.user_id, _now().isoformat(), execute_after.isoformat(),
                           json.dumps(trade_dict, default=str)))
        self.conn.commit()

    def ripe_pending(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM pending WHERE user_id=? AND status='pending' AND execute_after<=?",
            (self.user_id, _now().isoformat())).fetchall()]

    def mark_pending(self, pid, status):
        self.conn.execute("UPDATE pending SET status=? WHERE id=?", (status, pid)); self.conn.commit()

    def cancel_pending_buys(self) -> int:
        """Cancel still-queued BUY entries (used by the kill switch). Returns count."""
        cur = self.conn.execute(
            "UPDATE pending SET status='cancelled' WHERE user_id=? AND status='pending' "
            "AND trade LIKE '%\"action\": \"BUY\"%'", (self.user_id,))
        self.conn.commit()
        return cur.rowcount

    # planned exits
    def add_planned_exit(self, symbol, exit_type, hold_days=1, note=""):
        due = (_now() + timedelta(days=max(1, hold_days))).date().isoformat()
        self.conn.execute("INSERT INTO planned_exits (user_id, ts, symbol, exit_type, due_date, note) VALUES (?,?,?,?,?,?)",
                          (self.user_id, _now().isoformat(), symbol, exit_type, due, note)); self.conn.commit()

    def due_exits(self):
        today = _now().date().isoformat()
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM planned_exits WHERE user_id=? AND status='open' AND due_date<=?",
            (self.user_id, today)).fetchall()]

    def close_planned_exit(self, eid):
        self.conn.execute("UPDATE planned_exits SET status='done' WHERE id=?", (eid,)); self.conn.commit()

    # snapshots
    def snapshot(self, equity, cash, bench):
        self.conn.execute("INSERT INTO snapshots (user_id, ts, date, equity, cash, benchmark_price) VALUES (?,?,?,?,?,?)",
                          (self.user_id, _now().isoformat(), _now().date().isoformat(), equity, cash, bench)); self.conn.commit()

    def snapshots(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM snapshots WHERE user_id=? ORDER BY id ASC", (self.user_id,)).fetchall()]

    def day_open_equity(self):
        """Equity at the first snapshot recorded today (the kill-switch baseline)."""
        d = _now().date().isoformat()
        r = self.conn.execute(
            "SELECT equity FROM snapshots WHERE user_id=? AND date=? ORDER BY id ASC LIMIT 1",
            (self.user_id, d)).fetchone()
        return r["equity"] if r else None

    # consult requests (web → worker: user asks the buddy about a ticker)
    def add_consult_request(self, symbol, intent="advisory"):
        self.conn.execute(
            "INSERT INTO consult_requests (user_id, ts, symbol, intent) VALUES (?,?,?,?)",
            (self.user_id, _now().isoformat(), symbol.upper(), intent)); self.conn.commit()

    def pending_consults(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM consult_requests WHERE user_id=? AND status='pending' ORDER BY id ASC",
            (self.user_id,)).fetchall()]

    def complete_consult(self, cid, result):
        self.conn.execute("UPDATE consult_requests SET status='done', result=? WHERE id=?",
                          (json.dumps(result, default=str), cid)); self.conn.commit()
