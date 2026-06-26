from aiportfolio import modes


def test_defaults(base_cfg):
    enabled, horizon = modes.normalize(base_cfg)
    assert enabled == ["equity_short"]
    assert horizon == "daily"


def test_bad_values_fall_back():
    enabled, horizon = modes.normalize({"modes": {"enabled": ["nonsense"], "short_term_horizon": "x"}})
    assert enabled == ["equity_short"]
    assert horizon == "daily"


def test_instruments_and_guidance():
    enabled = ["equity_short", "option_short"]
    assert modes.enabled_instruments(enabled) == {"equity", "option"}
    g = modes.prompt_guidance(enabled, "daily")
    assert "equity_short" in g and "option_short" in g and "exit_plan" in g
