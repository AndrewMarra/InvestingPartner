"""One decision cycle, mode-aware, cost-gated, with exit plans + notifications.

Flow:
  1. Execute ripe queued trades (set up their exit orders / planned exits).
  2. Surface DUE planned exits (e.g. yesterday's daily buy) -> notify + queue sell.
  3. Immediate risk exits (stop-loss / take-profit).
  4. Cost gate: cheap triage decides if the expensive decision call is worth it.
  5. Decision (only if warranted & under the daily cap) -> risk review.
  6. Notify (with share counts + exit plan) and queue each idea to execute in ~10m.
  7. Snapshot equity.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import timedelta

from rich.console import Console

from ..config import load_config
from ..data.market import MarketData
from ..data.news import NewsFeed
from ..data.fundamentals import Fundamentals
from ..data.options import OptionsData
from ..research.engine import ResearchEngine
from ..risk.guardrails import RiskManager, ApprovedTrade
from ..execution.broker import Broker
from ..storage.db import _now
from ..storage.factory import open_store
from ..notify.sms import Notifier
from ..benchmark.compare import performance_report

console = Console()


class Engine:
    def __init__(self, config_path=None, config=None, user_id="local"):
        self.cfg = config if config is not None else load_config(config_path)
        self.user_id = user_id
        s = self.cfg.secrets
        self.market = MarketData(s)
        self.news = NewsFeed(s)
        self.funds = Fundamentals(s)
        self.options = OptionsData(s) if (self.cfg.get("options", {}) or {}).get("enabled") else None
        self.research = ResearchEngine(s, self.cfg, self.market, self.news, self.funds, self.options)
        self.risk = RiskManager(self.cfg)
        self.broker = Broker(s, self.options)
        self.store = open_store(self.cfg["storage"]["db_path"], user_id=user_id)
        self.notifier = Notifier(s, self.cfg)
        trading = self.cfg.get("trading", {}) or {}
        self.lead = int(trading.get("notify_lead_minutes", 10))
        # Signals-only: analyse + text ideas, but never place ANY paper order.
        self.signals_only = bool(trading.get("signals_only", False))
        self.notify_min = (self.cfg.get("notify", {}) or {}).get("min_confidence_to_notify", 0.6)
        self.max_decisions = (self.cfg.get("cost_controls", {}) or {}).get("max_decision_calls_per_day", 12)

    def _to_trade(self, blob): return ApprovedTrade(**json.loads(blob))

    def _execute(self, t):
        if t.instrument == "option":
            return self.broker.buy_option(t), None
        if t.action == "SELL":
            return self.broker.sell_fraction(t.symbol, t.sell_fraction or 1.0), None
        price = self.market.latest_price(t.symbol) or 0
        return self.broker.buy_with_exit(t.symbol, t.notional, t.exit_plan, price)

    def _option_quoter(self, u, r, k, z, mode=None):
        if not self.options: return None
        style = "leaps" if mode == "option_long" else ("0dte" if z else "weekly")
        c = self.options.find_contract(u, r, k, z, expiry_style=style)
        if not c: return None
        q = self.options.quote(c["symbol"])
        return q["ask"] if q and q.get("ask") else None

    def _awake(self):
        sch = self.cfg["schedule"]
        if not sch.get("market_hours_only", True): return True
        return self.market.is_market_open() or bool(sch.get("after_hours", False))

    def run_cycle(self, force=False, skip_triage=False):
        mode = "PAPER" if self.cfg.secrets.is_paper else "*** LIVE ***"
        tag = " · signals-only" if self.signals_only else ""
        console.rule(f"[bold]Cycle [{mode}{tag}]")

        # 1) ripe pending -> execute (and register any planned exits).
        #    Signals-only never queues, so this is normally empty; if a user just
        #    flipped the flag on, leave anything still queued untouched (no order).
        if not self.signals_only:
            for row in self.store.ripe_pending():
                t = self._to_trade(row["trade"])
                res, planned = self._execute(t)
                self.store.log_trade(t, res)
                if planned:
                    self.store.add_planned_exit(planned["symbol"], planned["type"],
                                                planned.get("hold_days", 1), planned.get("note", ""))
                self.store.mark_pending(row["id"], "executed")
                console.print(f"[green]EXECUTED[/] {t.symbol or t.underlying}: {res}")

        if not force and not self._awake():
            console.print("[yellow]Closed / after-hours off — pending handled, skipping research.[/]")
            return {"skipped_research": True}

        account = self.market.account()
        positions = self.market.positions()
        console.print(f"Equity ${account['equity']:.2f}  Cash ${account['cash']:.2f}  "
                      f"Pos {len(positions)}  TradesToday {self.store.trades_today()}  "
                      f"DecisionsToday {self.store.decisions_today()}/{self.max_decisions}")

        # 2) due planned exits -> notify + queue a sell (signals-only: notify only)
        for ex in self.store.due_exits():
            self.notifier.send(self.notifier.format_exit(ex["symbol"], self.lead, "planned"))
            self.store.close_planned_exit(ex["id"])
            if self.signals_only:
                console.print(f"[magenta]DUE EXIT[/] {ex['symbol']} (signals-only: texting you, no order)")
                continue
            sell = ApprovedTrade(action="SELL", mode="equity_short", symbol=ex["symbol"],
                                 sell_fraction=1.0, confidence=1.0,
                                 rationale=f"Planned exit ({ex['exit_type']}) from a prior buy.")
            self.store.enqueue(asdict(sell), _now() + timedelta(minutes=self.lead))
            console.print(f"[magenta]DUE EXIT queued[/] {ex['symbol']} (texting you)")

        # 3) immediate risk exits (signals-only: notify only, no order)
        for rx in self.risk.forced_exits(positions):
            self.notifier.send(self.notifier.format_exit(rx.symbol, self.lead, "risk",
                                                         rx.sell_fraction, rx.rationale))
            if self.signals_only:
                console.print(f"[red]RISK EXIT (signal)[/] {rx.symbol}: {rx.rationale}")
                continue
            res = self.broker.sell_fraction(rx.symbol, rx.sell_fraction)
            self.store.log_trade(rx, res)
            console.print(f"[red]RISK EXIT[/] {rx.symbol}: {rx.rationale}")

        # 3b) daily-loss kill switch — pause NEW buys (sells/exits still run)
        day_dd = self._day_drawdown_pct(account)
        kill = day_dd <= -self.risk.daily_loss_limit_pct
        if kill:
            console.print(f"[red]KILL SWITCH[/] down {day_dd:.1f}% on the day "
                          f"(limit -{self.risk.daily_loss_limit_pct}%). No new buys today.")
            # Cancel any still-queued BUYs so they don't fire after the limit.
            cancelled = self.store.cancel_pending_buys()
            self.notifier.send(f"🛑 Daily loss limit hit ({day_dd:.1f}%). Pausing new "
                               f"buys for today; existing exits still active."
                               + (f" Cancelled {cancelled} queued buy(s)." if cancelled else ""))
            self._snapshot()
            return {"kill_switch": True, "day_drawdown_pct": round(day_dd, 2)}

        # 4) cost gate
        if self.store.decisions_today() >= self.max_decisions:
            console.print("[yellow]Daily decision-call cap reached — no expensive analysis.[/]")
            self._snapshot(); return {"capped": True}

        compact = self.research.compact_signals()
        tri = self.research.triage(compact)
        console.print(f"[dim]triage: worth={tri.get('worth_analyzing')} "
                      f"watch={tri.get('watch')} ({tri.get('reason','')[:60]})[/]")
        if not skip_triage and not tri.get("worth_analyzing"):
            self._snapshot(); return {"queued": 0, "triaged_out": True}

        # 5) decision
        briefing = self.research.build_briefing(focus=tri.get("watch") or None)
        decisions = self.research.decide(briefing)
        self.store.log_decision(decisions.get("market_view", ""), decisions)
        console.print(f"\n[cyan]View:[/] {decisions.get('market_view','')}\n")

        # 6) risk review -> notify + queue
        account = self.market.account(); positions = self.market.positions()
        approved = self.risk.review(decisions.get("decisions", []), account, positions,
                                    trades_today=self.store.trades_today(),
                                    option_quoter=self._option_quoter)
        eta = _now() + timedelta(minutes=self.lead)
        for t in approved:
            if not self.signals_only:
                self.store.enqueue(asdict(t), eta)
            price = shares = None
            if t.instrument == "equity" and t.action == "BUY":
                price = self.market.latest_price(t.symbol)
                shares = round(t.notional / price, 2) if price else None
            if t.confidence >= self.notify_min:
                self.notifier.send(self.notifier.format_proposal(t, self.lead, price, shares,
                                                                 signals_only=self.signals_only))
            label = t.symbol or f"{t.underlying} {t.strike:g}{t.right[:1].upper()}"
            verb = "SIGNAL" if self.signals_only else "QUEUED"
            console.print(f"[bold green]{verb}[/] [{t.mode}] {label} "
                          f"(exit: {(t.exit_plan or {}).get('type','-')}) — texting you\n   {t.rationale}")
        if not approved:
            console.print("[dim]Nothing compelling — holding.[/]")

        self._snapshot()
        return {"queued": 0 if self.signals_only else len(approved),
                "signalled": len(approved) if self.signals_only else 0}

    def _day_drawdown_pct(self, account):
        day_open = self.store.day_open_equity() or account["equity"]
        return (account["equity"] / day_open - 1) * 100 if day_open else 0

    # ── user-initiated consult / override (Ticket 3) ─────────────────────
    def consult(self, symbol: str, intent: str = "advisory") -> dict:
        """Buddy's take on one ticker. intent ∈ {advisory, hard_buy, conditional_buy}.
        Acts (queues + notifies) only on hard_buy, or conditional_buy when it agrees —
        always through the same risk review + enqueue + notify path as autonomous ideas."""
        symbol = symbol.upper()
        out = self.research.consult(symbol, intent)
        verdict = out.get("verdict", "?"); reasoning = out.get("reasoning", "")
        agree = bool(out.get("agree", False))
        trade = out.get("trade") or None
        self.store.log_decision(f"CONSULT {symbol} [{intent}] -> {verdict} (agree={agree})", out)
        console.print(f"[cyan]CONSULT[/] {symbol} [{intent}] → [bold]{verdict}[/] "
                      f"(agree={agree})\n   {reasoning}")

        result = {"symbol": symbol, "intent": intent, "verdict": verdict,
                  "agree": agree, "reasoning": reasoning, "queued": 0, "acted": False}

        will_act = trade and (intent == "hard_buy" or (intent == "conditional_buy" and agree))
        if not will_act:
            self.notifier.send(self.notifier.format_consult(symbol, verdict, reasoning,
                                                            intent, agree, acted=False))
            return result

        # Acting path — hard caps + kill switch still bind.
        account = self.market.account()
        if self._day_drawdown_pct(account) <= -self.risk.daily_loss_limit_pct:
            msg = f"🛑 Not acting on {symbol}: daily loss limit hit. ({reasoning[:100]})"
            self.notifier.send(msg); result["blocked"] = "kill_switch"; return result

        positions = self.market.positions()
        approved = self.risk.review([trade], account, positions,
                                    trades_today=self.store.trades_today(),
                                    option_quoter=self._option_quoter,
                                    override_modes={trade.get("mode")},  # override bypasses mode gate
                                    bypass_confidence=True)               # user asked explicitly
        if not approved:
            self.notifier.send(f"⚠️ Couldn't place {symbol}: blocked by risk limits. "
                               f"My take: {verdict}. {reasoning[:120]}")
            result["blocked"] = "risk"; return result

        eta = _now() + timedelta(minutes=self.lead)
        for t in approved:
            if not self.signals_only:
                self.store.enqueue(asdict(t), eta)
            price = shares = None
            if t.instrument == "equity" and t.action == "BUY":
                price = self.market.latest_price(t.symbol)
                shares = round(t.notional / price, 2) if price else None
            self.notifier.send(self.notifier.format_proposal(t, self.lead, price, shares,
                                                             signals_only=self.signals_only))
            label = t.symbol or f"{t.underlying} {t.strike:g}{t.right[:1].upper()}"
            console.print(f"[bold green]{'SIGNAL' if self.signals_only else 'QUEUED'}[/] "
                          f"(override) [{t.mode}] {label}")
        result["acted"] = True
        result["queued"] = 0 if self.signals_only else len(approved)
        result["signalled"] = len(approved) if self.signals_only else 0
        return result

    def _snapshot(self):
        a = self.market.account()
        b = self.market.latest_price(self.cfg["benchmark"]["symbol"])
        self.store.snapshot(a["equity"], a["cash"], b)

    def report(self):
        rep = performance_report(self.cfg, self.store, self.market)
        console.rule("[bold]Performance")
        console.print(f"AI:  ${rep['ai_equity']:.2f} ({_pct(rep['ai_return_pct'])})  | "
                      f"{rep['benchmark_symbol']}: {_pct(rep['benchmark_return_pct'])}"
                      + (f"  | You: {_pct(rep['personal_return_pct'])}" if rep['personal_return_pct'] is not None else ""))
        return rep


def _pct(v): return "n/a" if v is None else f"{'+' if v >= 0 else ''}{v:.2f}%"
