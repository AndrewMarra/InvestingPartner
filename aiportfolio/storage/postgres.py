"""Postgres (Supabase) backend — the production twin of the SQLite stores.

Selected when DATABASE_URL is set (see storage.factory / multiuser.users). The
worker connects with the Supabase service-role / direct Postgres role, which
bypasses RLS so it can act for every user. The web app, by contrast, uses the
anon key + RLS so each signed-in user only ever touches their own rows.

These classes mirror the method surface of storage.db.Store and
multiuser.users.UserStore exactly, so the rest of the engine is backend-agnostic.
Key dialect differences vs SQLite handled here:
  - placeholders %s (not ?), booleans true/false (not 1/0)
  - jsonb columns (payload/trade/order_result/adjustments/settings) — wrapped on
    write, and re-serialised to strings on read so callers see the same shapes
  - the multi-user account table is `profiles` (not `users`), matching schema.sql

psycopg (v3) is imported lazily so the SQLite-only test suite never needs it.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta


def _now():
    return datetime.now(timezone.utc)


def _connect(url: str):
    import psycopg
    from psycopg.rows import dict_row
    conn = psycopg.connect(url, row_factory=dict_row)
    conn.autocommit = True
    return conn


def _json(value):
    """Wrap a Python object for a jsonb parameter."""
    from psycopg.types.json import Json
    return Json(value)


def _as_text(value):
    """Read a jsonb column back as the JSON *string* SQLite callers expect."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str)


# ── audit trail / pending queue / planned exits (per user) ───────────────
class PgStore:
    def __init__(self, url, user_id="local"):
        self.user_id = user_id
        self.conn = _connect(url)

    def _exec(self, sql, params=()):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur

    def _rows(self, sql, params=()):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def _one(self, sql, params=()):
        rows = self._rows(sql, params)
        return rows[0] if rows else None

    # decisions
    def log_decision(self, market_view, payload):
        self._exec("INSERT INTO decisions (user_id, ts, market_view, payload) VALUES (%s,%s,%s,%s)",
                   (self.user_id, _now(), market_view, _json(payload)))

    def decisions_today(self):
        r = self._one("SELECT COUNT(*) c FROM decisions WHERE user_id=%s AND ts::date=%s",
                      (self.user_id, _now().date()))
        return r["c"] if r else 0

    # trades
    def log_trade(self, t, order_result):
        if t.instrument == "option":
            detail = f"{t.contracts}x {t.underlying} {t.expiry_label} {t.strike:g}{t.right[:1].upper()}"
        elif t.action == "BUY":
            detail = f"${t.notional}"
        else:
            detail = f"{t.sell_fraction:.0%}"
        self._exec("""INSERT INTO trades (user_id, ts, instrument, mode, action, symbol, detail,
            confidence, rationale, adjustments, order_result) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (self.user_id, _now(), t.instrument, t.mode, t.action, t.symbol or t.underlying,
             detail, t.confidence, t.rationale, _json(t.adjustments),
             _json(order_result) if order_result else None))

    def trades_today(self):
        r = self._one("SELECT COUNT(*) c FROM trades WHERE user_id=%s AND ts::date=%s",
                      (self.user_id, _now().date()))
        return r["c"] if r else 0

    def recent_trades(self, limit=20):
        return self._rows("SELECT * FROM trades WHERE user_id=%s ORDER BY id DESC LIMIT %s",
                          (self.user_id, limit))

    # pending
    def enqueue(self, trade_dict, execute_after):
        self._exec("INSERT INTO pending (user_id, ts, execute_after, trade) VALUES (%s,%s,%s,%s)",
                   (self.user_id, _now(), execute_after, _json(trade_dict)))

    def ripe_pending(self):
        rows = self._rows(
            "SELECT * FROM pending WHERE user_id=%s AND status='pending' AND execute_after<=%s",
            (self.user_id, _now()))
        for r in rows:  # callers json.loads(row["trade"]); keep the SQLite shape
            r["trade"] = _as_text(r["trade"])
        return rows

    def mark_pending(self, pid, status):
        self._exec("UPDATE pending SET status=%s WHERE id=%s", (status, pid))

    def cancel_pending_buys(self) -> int:
        cur = self._exec(
            "UPDATE pending SET status='cancelled' WHERE user_id=%s AND status='pending' "
            "AND trade->>'action' = 'BUY'", (self.user_id,))
        return cur.rowcount

    # planned exits
    def add_planned_exit(self, symbol, exit_type, hold_days=1, note=""):
        due = (_now() + timedelta(days=max(1, hold_days))).date()
        self._exec("INSERT INTO planned_exits (user_id, ts, symbol, exit_type, due_date, note) "
                   "VALUES (%s,%s,%s,%s,%s,%s)",
                   (self.user_id, _now(), symbol, exit_type, due, note))

    def due_exits(self):
        return self._rows(
            "SELECT * FROM planned_exits WHERE user_id=%s AND status='open' AND due_date<=%s",
            (self.user_id, _now().date()))

    def close_planned_exit(self, eid):
        self._exec("UPDATE planned_exits SET status='done' WHERE id=%s", (eid,))

    # snapshots
    def snapshot(self, equity, cash, bench):
        self._exec("INSERT INTO snapshots (user_id, ts, date, equity, cash, benchmark_price) "
                   "VALUES (%s,%s,%s,%s,%s,%s)",
                   (self.user_id, _now(), _now().date(), equity, cash, bench))

    def snapshots(self):
        return self._rows("SELECT * FROM snapshots WHERE user_id=%s ORDER BY id ASC", (self.user_id,))

    def day_open_equity(self):
        r = self._one(
            "SELECT equity FROM snapshots WHERE user_id=%s AND date=%s ORDER BY id ASC LIMIT 1",
            (self.user_id, _now().date()))
        return r["equity"] if r else None


# ── accounts / settings / encrypted BYOK keys ────────────────────────────
class PgUserStore:
    """Mirrors multiuser.users.UserStore against the Supabase `profiles` table."""

    def __init__(self, url):
        from .. import multiuser  # noqa: keep crypto import path consistent
        self.conn = _connect(url)

    def _rows(self, sql, params=()):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def _exec(self, sql, params=()):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)

    def add_user(self, email: str, phone: str) -> str:
        # In production, profiles rows are created by the web app on signup
        # (they FK to auth.users). Support a bare insert for parity/testing.
        uid = str(uuid.uuid4())
        self._exec("INSERT INTO profiles (id, email, phone, active, paused, created_at) "
                   "VALUES (%s,%s,%s,true,false,%s)", (uid, email, phone, _now()))
        return uid

    def get_user(self, user_id: str):
        rows = self._rows("SELECT * FROM profiles WHERE id=%s", (user_id,))
        return rows[0] if rows else None

    def list_active(self):
        return self._rows(
            "SELECT * FROM profiles WHERE active = true AND COALESCE(paused, false) = false")

    def list_all(self):
        return self._rows("SELECT * FROM profiles WHERE active = true")

    def set_active(self, user_id: str, active: bool):
        self._exec("UPDATE profiles SET active=%s WHERE id=%s", (bool(active), user_id))

    def set_paused(self, user_id: str, paused: bool):
        self._exec("UPDATE profiles SET paused=%s WHERE id=%s", (bool(paused), user_id))

    # keys
    def set_keys(self, user_id: str, keys: dict):
        from ..multiuser import crypto
        from ..multiuser.users import KEY_PROVIDERS
        for provider, value in keys.items():
            if provider not in KEY_PROVIDERS or not value:
                continue
            self._exec(
                "INSERT INTO user_keys (user_id, provider, ciphertext) VALUES (%s,%s,%s) "
                "ON CONFLICT (user_id, provider) DO UPDATE SET ciphertext = EXCLUDED.ciphertext",
                (user_id, provider, crypto.encrypt(value)))

    def get_keys(self, user_id: str) -> dict:
        from ..multiuser import crypto
        rows = self._rows("SELECT provider, ciphertext FROM user_keys WHERE user_id=%s", (user_id,))
        return {r["provider"]: crypto.decrypt(r["ciphertext"]) for r in rows}

    # settings
    def set_settings(self, user_id: str, settings: dict):
        self._exec(
            "INSERT INTO user_settings (user_id, settings) VALUES (%s,%s) "
            "ON CONFLICT (user_id) DO UPDATE SET settings = EXCLUDED.settings",
            (user_id, _json(settings)))

    def get_settings(self, user_id: str) -> dict:
        rows = self._rows("SELECT settings FROM user_settings WHERE user_id=%s", (user_id,))
        if not rows or rows[0]["settings"] is None:
            return {}
        s = rows[0]["settings"]
        return s if isinstance(s, dict) else json.loads(s)
