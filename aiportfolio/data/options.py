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
    def _style_for(zero_dte: bool, expiry_style: str | None) -> str:
        """Resolve the expiry style. Explicit style wins; else infer from 0DTE."""
        if expiry_style:
            return expiry_style
        return "0dte" if zero_dte else "weekly"

    @staticmethod
    def _expiry_window(style: str) -> tuple[date, date]:
        """(earliest, latest) acceptable expiry for a style. Equal = exact date."""
        today = date.today()
        if style == "0dte":
            return today, today
        if style == "leaps":
            # LEAPS: at least ~9 months out, up to ~2 years — real long-dated calls.
            return today + timedelta(days=270), today + timedelta(days=730)
        # weekly: nearest Friday
        ahead = (4 - today.weekday()) % 7
        d = today + timedelta(days=ahead or 7)
        return d, d

    @staticmethod
    def _next_expiry(zero_dte: bool) -> date:  # kept for back-compat
        lo, _ = OptionsData._expiry_window("0dte" if zero_dte else "weekly")
        return lo

    def find_contract(self, underlying: str, right: str, target_strike: float,
                      zero_dte: bool = False, expiry_style: str | None = None) -> dict | None:
        """Resolve to the nearest-strike active contract for the expiry style.
        For LEAPS we scan a window and pick the farthest-dated near-strike contract."""
        try:
            from alpaca.trading.requests import GetOptionContractsRequest
            from alpaca.trading.enums import ContractType, AssetStatus

            style = self._style_for(zero_dte, expiry_style)
            lo, hi = self._expiry_window(style)
            ctype = ContractType.CALL if right.lower() == "call" else ContractType.PUT
            kwargs = dict(
                underlying_symbols=[underlying],
                type=ctype,
                status=AssetStatus.ACTIVE,
                strike_price_gte=str(target_strike * 0.9),
                strike_price_lte=str(target_strike * 1.1),
                limit=100,
            )
            if lo == hi:
                kwargs["expiration_date"] = lo
            else:
                kwargs["expiration_date_gte"] = lo
                kwargs["expiration_date_lte"] = hi
            contracts = self._trading_client().get_option_contracts(
                GetOptionContractsRequest(**kwargs)).option_contracts
            if not contracts:
                return None
            contracts.sort(key=lambda c: abs(float(c.strike_price) - target_strike))
            if style == "leaps":
                # Among the nearest strikes, take the longest-dated (true LEAPS).
                nearest = abs(float(contracts[0].strike_price) - target_strike)
                near = [c for c in contracts
                        if abs(float(c.strike_price) - target_strike) <= nearest + 0.01]
                best = max(near, key=lambda c: str(c.expiration_date))
            else:
                best = contracts[0]
            return {
                "symbol": best.symbol,
                "strike": float(best.strike_price),
                "expiry": str(best.expiration_date),
                "right": right.lower(),
                "underlying": underlying,
            }
        except Exception:
            return None

    @staticmethod
    def looks_like_option(symbol: str) -> bool:
        """Heuristic for an OCC option symbol (e.g. SPY240614C00500000)."""
        return len(symbol) > 9 and any(ch.isdigit() for ch in symbol[1:])

    def position_marks(self, symbols: list[str]) -> dict[str, float]:
        """Best-effort mid-price marks for held option contracts (P&L tracking).
        Degrades to {} silently when option quotes aren't available on the plan."""
        out: dict[str, float] = {}
        for s in symbols:
            if not self.looks_like_option(s):
                continue
            q = self.quote(s)
            if q and q.get("bid") is not None and q.get("ask") is not None:
                out[s] = round((q["bid"] + q["ask"]) / 2, 2)
        return out

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
