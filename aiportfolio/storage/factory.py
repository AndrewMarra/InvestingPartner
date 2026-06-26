"""Pick the storage backend by environment.

If DATABASE_URL (a Supabase/Postgres connection string) is set, use Postgres;
otherwise fall back to local SQLite. This is the single switch that lets the same
worker code run against either store — local dev/tests on SQLite, production on
the same Supabase Postgres the web app writes to.
"""
from __future__ import annotations

import os


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "").strip()


def open_store(db_path, user_id="local"):
    url = database_url()
    if url:
        from .postgres import PgStore
        return PgStore(url, user_id=user_id)
    from .db import Store
    return Store(db_path, user_id=user_id)


def open_user_store(db_path="portfolio.db"):
    url = database_url()
    if url:
        from .postgres import PgUserStore
        return PgUserStore(url)
    from ..multiuser.users import UserStore
    return UserStore(db_path)
