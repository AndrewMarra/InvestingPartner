from aiportfolio.risk.guardrails import RiskManager, ApprovedTrade


def test_mode_gating_rejects_disabled(base_cfg, account):
    rm = RiskManager(base_cfg)  # only equity_short enabled
    props = [
        {"mode": "equity_day", "action": "BUY", "symbol": "SPY", "notional": 50,
         "confidence": 0.9, "rationale": "x", "exit_plan": {"type": "limit", "limit_price": 1}},
        {"mode": "equity_short", "action": "BUY", "symbol": "NVDA", "notional": 50,
         "confidence": 0.9, "rationale": "y", "exit_plan": {"type": "bracket", "limit_price": 1, "stop_price": 1}},
    ]
    approved = rm.review(props, account, [])
    assert [t.mode for t in approved] == ["equity_short"]


def test_per_trade_notional_cap(base_cfg, account):
    rm = RiskManager(base_cfg)  # max_trade_notional_pct 15 -> $150 on $1000
    props = [{"mode": "equity_short", "action": "BUY", "symbol": "NVDA", "notional": 500,
              "confidence": 0.9, "rationale": "x", "exit_plan": {"type": "time", "hold_days": 1}}]
    approved = rm.review(props, account, [])
    assert approved[0].notional == 150.0


def test_low_confidence_dropped(base_cfg, account):
    rm = RiskManager(base_cfg)  # min_confidence_to_trade 0.55
    props = [{"mode": "equity_short", "action": "BUY", "symbol": "NVDA", "notional": 50,
              "confidence": 0.3, "rationale": "x", "exit_plan": {"type": "time"}}]
    assert rm.review(props, account, []) == []


def test_crypto_blocked(base_cfg, account):
    rm = RiskManager(base_cfg)
    props = [{"mode": "equity_short", "action": "BUY", "symbol": "BTC/USD", "notional": 50,
              "confidence": 0.9, "rationale": "x", "exit_plan": {"type": "time"}}]
    assert rm.review(props, account, []) == []


def test_option_premium_trim(base_cfg, account):
    cfg = dict(base_cfg)
    cfg["modes"] = {"enabled": ["option_short"], "short_term_horizon": "daily"}
    rm = RiskManager(cfg)  # premium cap 3% -> $30; ask $0.08 -> $8/contract -> max 3
    props = [{"mode": "option_short", "action": "BUY", "underlying": "QQQ", "right": "call",
              "strike": 500, "zero_dte": True, "contracts": 5, "confidence": 0.8,
              "rationale": "x", "exit_plan": {"type": "manual_next_day"}}]
    approved = rm.review(props, account, [], option_quoter=lambda *a: 0.08)
    assert approved and approved[0].contracts == 3


def test_option_dropped_when_too_rich(base_cfg, account):
    cfg = dict(base_cfg)
    cfg["modes"] = {"enabled": ["option_short"]}
    rm = RiskManager(cfg)  # ask $2.00 -> $200/contract > $30 cap
    props = [{"mode": "option_short", "action": "BUY", "underlying": "SPY", "right": "call",
              "strike": 580, "zero_dte": True, "contracts": 1, "confidence": 0.9,
              "rationale": "x", "exit_plan": {"type": "manual_next_day"}}]
    assert rm.review(props, account, [], option_quoter=lambda *a: 2.00) == []


def test_forced_exits():
    rm = RiskManager({"risk": {"max_position_pct": 20, "min_cash_pct": 5, "max_trades_per_run": 3,
        "max_trade_notional_pct": 15, "allow_shorting": False, "min_confidence_to_trade": 0.55,
        "stop_loss_pct": 25, "take_profit_pct": 60}})
    positions = [{"symbol": "AAA", "unrealized_plpc": -30.0, "market_value": 100},
                 {"symbol": "BBB", "unrealized_plpc": 65.0, "market_value": 100},
                 {"symbol": "CCC", "unrealized_plpc": 5.0, "market_value": 100}]
    exits = rm.forced_exits(positions)
    by = {e.symbol: e.sell_fraction for e in exits}
    assert by["AAA"] == 1.0 and by["BBB"] == 0.5 and "CCC" not in by
