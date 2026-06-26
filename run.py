"""AI Trading Buddy — command line entry point.

Single-user:
    python run.py once [--force]    One cycle (execute ripe queued, propose, text)
    python run.py loop              Run on the schedule
    python run.py backtest ...      Backtest a strategy
    python run.py report | status

Multi-user (BYOK):
    python run.py users keygen      Print a MASTER_ENCRYPTION_KEY to set
    python run.py users add ...      Create a user
    python run.py users setkey ...   Store an encrypted BYOK key
    python run.py users settings ... Set a user's JSON settings
    python run.py users list
    python run.py run-all [--force]  One cycle for every active user
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

from rich.console import Console

console = Console()


def _Engine():
    from aiportfolio.scheduler.loop import Engine
    return Engine


# ── single-user ──────────────────────────────────────────────────────
def cmd_once(args): _Engine()(args.config).run_cycle(force=args.force)
def cmd_report(args): _Engine()(args.config).report()


def cmd_status(args):
    eng = _Engine()(args.config)
    acct = eng.market.account()
    console.print(f"Mode: {'PAPER' if eng.cfg.secrets.is_paper else 'LIVE'} | "
                  f"Equity ${acct['equity']:.2f} | Cash ${acct['cash']:.2f} | "
                  f"Trades today {eng.store.trades_today()}")
    for p in eng.market.positions():
        console.print(f"  {p['symbol']:6} {p['qty']:.4f} @ ${p['avg_entry_price']:.2f} "
                      f"-> ${p['current_price']:.2f} ({p['unrealized_plpc']:+.1f}%)")


def cmd_loop(args):
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    eng = _Engine()(args.config)
    sch = eng.cfg["schedule"]; tz = sch["timezone"]
    days = "mon-sun" if sch.get("run_on_weekends") else "mon-fri"
    s = BlockingScheduler(timezone=tz)
    s.add_job(eng.run_cycle, CronTrigger(day_of_week=days, hour="9-16", minute="*/15", timezone=tz))
    console.print(f"[green]Buddy armed[/]. Polling every 15m, {days}, market hours. Ctrl-C to stop.")
    try: s.start()
    except (KeyboardInterrupt, SystemExit): console.print("\n[yellow]Stopped.[/]")


def cmd_backtest(args):
    eng = _Engine()(args.config)
    from aiportfolio.backtest.engine import fetch_history, run_backtest
    from aiportfolio.backtest.strategies import Momentum, BuyAndHold
    end = datetime.now(timezone.utc) - timedelta(days=1); start = end - timedelta(days=args.days)
    symbols = sorted(set(eng.cfg["research"]["candidate_universe"]) | {"SPY"})
    console.print(f"Fetching {args.days}d for {len(symbols)} symbols...")
    closes = fetch_history(eng.market, symbols, start, end)
    strat = Momentum(lookback=args.lookback, top_n=args.top_n) if args.strategy == "momentum" else BuyAndHold("SPY")
    res = run_backtest(closes, strat, eng.cfg["portfolio"]["starting_capital"])
    bh = run_backtest(closes, BuyAndHold("SPY"), eng.cfg["portfolio"]["starting_capital"])
    console.rule(f"[bold]Backtest: {strat.name} ({args.days}d)")
    for k in ("start_equity","end_equity","total_return_pct","cagr_pct","sharpe","max_drawdown_pct","trading_days"):
        console.print(f"  {k:20} {res[k]}")
    console.print(f"\n  vs SPY buy & hold: {bh['total_return_pct']}% (dd {bh['max_drawdown_pct']}%)")


# ── multi-user ───────────────────────────────────────────────────────
def cmd_run_all(args):
    from aiportfolio.multiuser.runner import run_all_users
    run_all_users(config_path=args.config, force=args.force)


def cmd_users(args):
    from aiportfolio.multiuser.users import UserStore
    from aiportfolio.multiuser import crypto
    if args.action == "keygen":
        console.print("MASTER_ENCRYPTION_KEY=" + crypto.generate_key())
        console.print("[dim]Set this in your env / Actions secrets. Losing it makes stored keys unrecoverable.[/]")
        return
    store = UserStore(args.db)
    if args.action == "add":
        uid = store.add_user(args.email, args.phone)
        console.print(f"Created user [green]{uid}[/] ({args.email}, {args.phone})")
    elif args.action == "setkey":
        store.set_keys(args.user, {args.provider: args.value})
        console.print(f"Stored encrypted {args.provider} for {args.user[:8]}")
    elif args.action == "settings":
        store.set_settings(args.user, json.loads(args.json))
        console.print(f"Updated settings for {args.user[:8]}")
    elif args.action == "list":
        for u in store.list_active():
            ks = list(store.get_keys(u["id"]).keys())
            console.print(f"  {u['id']}  {u['email']}  {u['phone']}  keys={ks}")


def main():
    p = argparse.ArgumentParser(description="AI Trading Buddy")
    p.add_argument("--config", default=None)
    sub = p.add_subparsers(dest="command", required=True)

    o = sub.add_parser("once"); o.add_argument("--force", action="store_true"); o.set_defaults(func=cmd_once)
    sub.add_parser("loop").set_defaults(func=cmd_loop)
    sub.add_parser("report").set_defaults(func=cmd_report)
    sub.add_parser("status").set_defaults(func=cmd_status)

    b = sub.add_parser("backtest")
    b.add_argument("--strategy", choices=["momentum","buyhold"], default="momentum")
    b.add_argument("--days", type=int, default=180); b.add_argument("--lookback", type=int, default=20)
    b.add_argument("--top-n", type=int, default=3); b.set_defaults(func=cmd_backtest)

    ra = sub.add_parser("run-all"); ra.add_argument("--force", action="store_true"); ra.set_defaults(func=cmd_run_all)

    u = sub.add_parser("users"); u.add_argument("--db", default="portfolio.db")
    usub = u.add_subparsers(dest="action", required=True)
    usub.add_parser("keygen")
    ua = usub.add_parser("add"); ua.add_argument("--email", required=True); ua.add_argument("--phone", required=True)
    uk = usub.add_parser("setkey"); uk.add_argument("--user", required=True)
    uk.add_argument("--provider", required=True); uk.add_argument("--value", required=True)
    us = usub.add_parser("settings"); us.add_argument("--user", required=True); us.add_argument("--json", required=True)
    usub.add_parser("list")
    u.set_defaults(func=cmd_users)

    args = p.parse_args(); args.func(args)


if __name__ == "__main__":
    main()
