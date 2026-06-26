"""Options chain lookup + quotes via Alpaca (defensive).

Used to (a) give the AI a small, current options snapshot to reason over and
(b) resolve a proposed idea (underlying/right/strike/expiry) into a concrete
OCC contract symbol for paper execution. All calls degrade gracefully: if the
options API isn't reachable, idea-generation and SMS alerts still work and the
trade simply becomes notify-only.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta


class OptionsData:
    def __init__(self, secrets):
        self.secrets = secrets
        self._trading = None
        self._data = None

    def _trading_client(self):
        if self._trading is None:
            from alpaca.trading.client import TradingClient
            self._trading = TradingClient(
                self.secrets.alpaca_key, self.secrets.alpaca_secret,
                paper=self.secrets.is_paper,
            )
        return self._trading

    def _data_client(self):
        if self._data is None:
            from alpaca.data.historical.option import OptionHistoricalDataClient
            self._data = OptionHistoricalDataClient(
                self.secrets.alpaca_key, self.secrets.alpaca_secret
            )
        return self._data

    @staticmethod
    def _next_expiry(zero_dte: bool) -> date:
        today = date.today()
        if zero_dte:
            return today
        # nearest Friday (weekly) as a simple default
        ahead = (4 - today.weekday()) % 7
        return today + timedelta(days=ahead or 7)

    def find_contract(self, underlying: str, right: str, target_strike: float,
                      zero_dte: bool = False) -> dict | None:
        """Resolve to the nearest-strike active contract. Returns dict or None."""
        try:
            from alpaca.trading.requests import GetOptionContractsRequest
            from alpaca.trading.enums import ContractType, AssetStatus

            exp = self._next_expiry(zero_dte)
            ctype = ContractType.CALL if right.lower() == "call" else ContractType.PUT
            req = GetOptionContractsRequest(
                underlying_symbols=[underlying],
                expiration_date=exp,
                type=ctype,
                status=AssetStatus.ACTIVE,
                strike_price_gte=str(target_strike * 0.95),
                strike_price_lte=str(target_strike * 1.05),
                limit=40,
            )
            contracts = self._trading_client().get_option_contracts(req).option_contracts
            if not contracts:
                return None
            best = min(contracts, key=lambda c: abs(float(c.strike_price) - target_strike))
            return {
                "symbol": best.symbol,
                "strike": float(best.strike_price),
                "expiry": str(best.expiration_date),
                "right": right.lower(),
                "underlying": underlying,
            }
        except Exception:
            return None

    def quote(self, occ_symbol: str) -> dict | None:
        try:
            from alpaca.data.requests import OptionLatestQuoteRequest
            req = OptionLatestQuoteRequest(symbol_or_symbols=occ_symbol)
            q = self._data_client().get_option_latest_quote(req)[occ_symbol]
            return {"bid": float(q.bid_price), "ask": float(q.ask_price)}
        except Exception:
            return None

    def snapshot_for_prompt(self, underlyings: list[str], spot: dict) -> dict:
        """A tiny chain summary the AI can reason over (ATM-ish strikes)."""
        out = {}
        for u in underlyings:
            px = spot.get(u)
            if not px:
                continue
            atm = round(px)
            row = {}
            for right in ("call", "put"):
                c = self.find_contract(u, right, atm, zero_dte=True)
                if c:
                    qt = self.quote(c["symbol"]) or {}
                    row[right] = {"strike": c["strike"], "expiry": c["expiry"],
                                  "ask": qt.get("ask"), "bid": qt.get("bid")}
            out[u] = {"spot": px, "atm_0dte": row}
        return out
