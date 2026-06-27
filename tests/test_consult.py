"""Integration-style tests for the consult / override path and signals-only,
exercising the real RiskManager + Store + Notifier with a faked market + model."""
import tempfile
from aiportfolio.scheduler.loop import Engine
from aiportfolio.risk.guardrails import RiskManager
from aiportfolio.storage.db import Store
from aiportfolio.notify.sms import Notifier
from aiportfolio.config import Secrets


class FakeMarket:
    def __init__(self, equity=1000.0, cash=1000.0, positions=None, price=100.0):
        self._e, self._c, self._p, self._px = equity, cash, positions or [], price
    def account(self): return {"equity": self._e, "cash": self._c}
    def positions(self): return list(self._p)
    def latest_price(self, s): return self._px


class FakeResearch:
    def __init__(self, out): self.out = out
    def consult(self, symbol, intent): return dict(self.out)


def _secrets():
    return Secrets(alpaca_key="x", alpaca_secret="x",
                   alpaca_base_url="https://paper-api.alpaca.markets",
                   anthropic_key="x", finnhub_key="x")


def make_engine(base_cfg, out, market=None, signals_only=False):
    eng = object.__new__(Engine)
    eng.cfg = base_cfg
    eng.user_id = "t"
    eng.market = market or FakeMarket()
    eng.research = FakeResearch(out)
    eng.risk = RiskManager(base_cfg)
    eng.store = Store(tempfile.mktemp(suffix=".db"), user_id="t")
    eng.notifier = Notifier(_secrets(), base_cfg)
    eng.options = None
    eng.signals_only = signals_only
    eng.lead = 10
    return eng


BUY_TRADE = {"mode": "equity_long", "action": "BUY", "symbol": "TSLA", "notional": 50,
             "confidence": 0.2, "rationale": "user wants it",
             "exit_plan": {"type": "time", "hold_days": 3}}


def test_advisory_never_trades(base_cfg):
    out = {"verdict": "avoid", "agree": False, "reasoning": "meh", "trade": BUY_TRADE}
    eng = make_engine(base_cfg, out)
    res = eng.consult("TSLA", "advisory")
    assert res["acted"] is False and res["queued"] == 0
    assert eng.store.ripe_pending() == []  # nothing queued


def test_hard_buy_queues_through_risk(base_cfg):
    out = {"verdict": "avoid", "agree": False, "reasoning": "meh", "trade": BUY_TRADE}
    eng = make_engine(base_cfg, out)
    res = eng.consult("TSLA", "hard_buy")
    # equity_long isn't enabled and confidence is low, but a hard override bypasses
    # the mode gate + confidence gate — yet still flows through risk.review.
    assert res["acted"] is True and res["queued"] == 1


def test_conditional_buy_declines_when_disagrees(base_cfg):
    out = {"verdict": "avoid", "agree": False, "reasoning": "no", "trade": BUY_TRADE}
    eng = make_engine(base_cfg, out)
    res = eng.consult("TSLA", "conditional_buy")
    assert res["acted"] is False and res["queued"] == 0


def test_conditional_buy_acts_when_agrees(base_cfg):
    out = {"verdict": "buy", "agree": True, "reasoning": "yes", "trade": BUY_TRADE}
    eng = make_engine(base_cfg, out)
    res = eng.consult("TSLA", "conditional_buy")
    assert res["acted"] is True and res["queued"] == 1


def test_kill_switch_blocks_override(base_cfg):
    out = {"verdict": "buy", "agree": True, "reasoning": "yes", "trade": BUY_TRADE}
    eng = make_engine(base_cfg, out, market=FakeMarket(equity=800.0))
    eng.store.snapshot(1000.0, 1000.0, 100.0)  # day opened at 1000, now 800 = -20%
    res = eng.consult("TSLA", "hard_buy")
    assert res.get("blocked") == "kill_switch" and res["queued"] == 0


def test_signals_only_notifies_but_does_not_queue(base_cfg):
    out = {"verdict": "buy", "agree": True, "reasoning": "yes", "trade": BUY_TRADE}
    eng = make_engine(base_cfg, out, signals_only=True)
    res = eng.consult("TSLA", "hard_buy")
    assert res["acted"] is True and res["queued"] == 0 and res.get("signalled") == 1
    assert eng.store.ripe_pending() == []


def test_process_consults_drains_queue(base_cfg):
    out = {"verdict": "hold", "agree": False, "reasoning": "n/a", "trade": None}
    eng = make_engine(base_cfg, out)
    eng.store.add_consult_request("NVDA", "advisory")
    eng.store.add_consult_request("AMD", "advisory")
    assert eng.process_consults() == 2
    assert eng.store.pending_consults() == []
