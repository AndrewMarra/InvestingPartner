from datetime import date
from aiportfolio.data.options import OptionsData
from aiportfolio.risk.guardrails import RiskManager


def test_expiry_window_styles():
    today = date.today()
    assert OptionsData._expiry_window("0dte") == (today, today)
    lo, hi = OptionsData._expiry_window("leaps")
    assert (lo - today).days >= 270 and (hi - today).days >= 720  # real long-dated
    wlo, whi = OptionsData._expiry_window("weekly")
    assert wlo == whi and wlo.weekday() == 4  # a Friday


def test_style_inference():
    assert OptionsData._style_for(True, None) == "0dte"
    assert OptionsData._style_for(False, None) == "weekly"
    assert OptionsData._style_for(False, "leaps") == "leaps"  # explicit wins


def test_looks_like_option():
    assert OptionsData.looks_like_option("SPY240614C00500000")
    assert not OptionsData.looks_like_option("SPY")
    assert not OptionsData.looks_like_option("NVDA")


def test_leaps_expiry_label(base_cfg, account):
    cfg = dict(base_cfg)
    cfg["modes"] = {"enabled": ["option_long"]}
    cfg["options"] = {**base_cfg["options"], "allowed_underlyings": ["SPY"]}
    rm = RiskManager(cfg)
    props = [{"mode": "option_long", "action": "BUY", "underlying": "SPY", "right": "call",
              "strike": 500, "contracts": 1, "confidence": 0.9, "rationale": "x",
              "exit_plan": {"type": "hold"}}]
    approved = rm.review(props, account, [])  # no quoter → premium skipped
    assert approved and approved[0].expiry_label == "LEAPS"


def test_vertical_carries_short_strike(base_cfg, account):
    cfg = dict(base_cfg)
    cfg["modes"] = {"enabled": ["option_short"]}
    rm = RiskManager(cfg)
    props = [{"mode": "option_short", "action": "BUY", "underlying": "SPY", "right": "call",
              "strike": 500, "short_strike": 505, "strategy": "vertical", "zero_dte": True,
              "contracts": 1, "confidence": 0.9, "rationale": "x",
              "exit_plan": {"type": "manual_next_day"}}]
    approved = rm.review(props, account, [], option_quoter=lambda *a: 0.05)
    assert approved and approved[0].strategy == "vertical" and approved[0].short_strike == 505


def test_override_mode_gate_and_confidence_bypass(base_cfg, account):
    rm = RiskManager(base_cfg)  # only equity_short enabled, min_conf 0.55
    prop = {"mode": "equity_long", "action": "BUY", "symbol": "TSLA", "notional": 50,
            "confidence": 0.2, "rationale": "user override",
            "exit_plan": {"type": "time", "hold_days": 3}}
    # Without override: dropped (mode not enabled).
    assert rm.review([prop], account, []) == []
    # With override + confidence bypass: allowed.
    approved = rm.review([prop], account, [], override_modes={"equity_long"}, bypass_confidence=True)
    assert approved and approved[0].mode == "equity_long"
