from aiportfolio.config import load_base_raw
from aiportfolio.multiuser.usercfg import build_user_config, clamp_settings, ALLOWED_OVERRIDES


def test_clamp_bounds_risky_values():
    raw = {
        "risk": {"max_position_pct": 999, "min_confidence_to_trade": 0.01,
                 "daily_loss_limit_pct": 90, "max_trades_per_run": 50},
        "options": {"max_contracts": 1000, "max_premium_pct_per_trade": 80},
        "portfolio": {"starting_capital": 5},
    }
    notes = clamp_settings(raw)
    assert raw["risk"]["max_position_pct"] == 50          # capped
    assert raw["risk"]["min_confidence_to_trade"] == 0.4  # floored
    assert raw["risk"]["daily_loss_limit_pct"] == 50      # capped
    assert raw["risk"]["max_trades_per_run"] == 10        # int cap
    assert raw["options"]["max_contracts"] == 20
    assert raw["portfolio"]["starting_capital"] == 1000   # floored
    assert notes  # adjustments were recorded


def test_build_user_config_enforces_bounds():
    base = load_base_raw()
    keys = {"alpaca_key": "AK", "alpaca_secret": "AS", "anthropic_key": "AN", "finnhub_key": "FH"}
    # A user tries to loosen their own guardrails to absurd levels.
    settings = {"risk": {"max_position_pct": 100, "stop_loss_pct": 100},
                "portfolio": {"starting_capital": 250000}}
    cfg = build_user_config(base, settings, keys)
    assert cfg["risk"]["max_position_pct"] == 50    # clamped, not 100
    assert cfg["risk"]["stop_loss_pct"] == 50       # clamped
    assert cfg["portfolio"]["starting_capital"] == 250000  # within bounds, kept


def test_portfolio_is_overridable():
    assert "portfolio" in ALLOWED_OVERRIDES
