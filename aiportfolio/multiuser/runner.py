"""Multi-user runner — one pass over all active users.

This is what the GitHub Actions cron calls. Each user runs with THEIR OWN keys
(BYOK), their own enabled modes/risk/notify settings, and their own namespaced
audit data. One user's failure (bad key, etc.) never affects the others.
"""
from __future__ import annotations

from rich.console import Console

from ..config import load_base_raw
from ..scheduler.loop import Engine
from ..storage.factory import open_user_store
from .usercfg import build_user_config, validate_user_keys

console = Console()


def run_all_users(config_path=None, db_path="portfolio.db", force=False) -> dict:
    base = load_base_raw(config_path)
    store = open_user_store(db_path)  # Postgres if DATABASE_URL set, else SQLite
    users = store.list_active()       # active AND not paused-by-user
    console.rule(f"[bold]Multi-user run — {len(users)} active user(s)")

    results = {}
    for u in users:
        uid = u["id"]
        label = u.get("email") or uid[:8]
        try:
            keys = store.get_keys(uid)
            missing = validate_user_keys(keys)
            if missing:
                console.print(f"[yellow]skip {label}: missing keys {missing}[/]")
                results[uid] = {"skipped": "missing_keys"}
                continue
            settings = store.get_settings(uid)
            cfg = build_user_config(base, settings, keys, phone=u.get("phone"))
            cfg.raw["storage"]["db_path"] = db_path
            console.print(f"[cyan]▶ {label}[/]")
            res = Engine(config=cfg, user_id=uid).run_cycle(force=force)
            results[uid] = res
        except Exception as e:
            console.print(f"[red]error {label}: {e}[/]")
            results[uid] = {"error": str(e)}
    return results
