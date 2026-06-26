from aiportfolio.config import load_base_raw
from aiportfolio.multiuser.usercfg import build_user_config, validate_user_keys


def test_overrides_and_secrets():
    base = load_base_raw()
    keys = {"alpaca_key": "AK", "alpaca_secret": "AS", "anthropic_key": "AN", "finnhub_key": "FH"}
    settings = {"modes": {"enabled": ["equity_day", "option_short"]}, "risk": {"max_position_pct": 10}}
    cfg = build_user_config(base, settings, keys, phone="+15551234567")
    assert cfg["modes"]["enabled"] == ["equity_day", "option_short"]
    assert cfg["risk"]["max_position_pct"] == 10
    assert cfg["risk"]["min_cash_pct"] == base["risk"]["min_cash_pct"]  # untouched
    assert cfg.secrets.anthropic_key == "AN"
    assert cfg.secrets.alert_to == "+15551234567"
    assert cfg.secrets.is_paper  # BYOK paper by default


def test_disallowed_override_ignored():
    base = load_base_raw()
    cfg = build_user_config(base, {"storage": {"db_path": "/etc/evil"}}, {})
    assert cfg["storage"]["db_path"] == base["storage"]["db_path"]


def test_validate_missing_keys():
    assert set(validate_user_keys({})) == {"alpaca_key", "alpaca_secret", "anthropic_key", "finnhub_key"}
    assert validate_user_keys({"alpaca_key": "x", "alpaca_secret": "x",
                               "anthropic_key": "x", "finnhub_key": "x"}) == []
