import tempfile, os
from aiportfolio.benchmark.personal import personal_return_from_csv, load_positions


class FakeMarket:
    def __init__(self, prices):
        self.prices = prices
    def latest_price(self, symbol):
        return self.prices.get(symbol)


def _csv(text):
    path = tempfile.mktemp(suffix=".csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(text)
    return path


def test_personal_return_basic():
    path = _csv("symbol,quantity,avg_cost\nNVDA,10,100\nMSFT,5,200\n")
    m = FakeMarket({"NVDA": 150.0, "MSFT": 200.0})
    # cost 2000, value 2500 -> +25%
    assert personal_return_from_csv(path, m) == 25.0
    os.remove(path)


def test_personal_handles_alternate_headers_and_missing_price():
    path = _csv("Symbol,Shares,Avg Price\nAAPL,10,100\nZZZZ,5,50\n")
    m = FakeMarket({"AAPL": 110.0})  # ZZZZ has no price -> skipped
    assert load_positions(path)[0]["symbol"] == "AAPL"
    assert personal_return_from_csv(path, m) == 10.0
    os.remove(path)


def test_personal_none_when_empty():
    assert personal_return_from_csv("does_not_exist.csv", FakeMarket({})) is None
