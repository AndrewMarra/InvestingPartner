"""Earnings calendar + per-symbol history via Finnhub (free tier)."""
from __future__ import annotations

from datetime import date, timedelta


class EarningsData:
    def __init__(self, secrets):
        self._key = secrets.finnhub_key
        self._client = None

    def _cli(self):
        if self._client is None:
            import finnhub
            self._client = finnhub.Client(api_key=self._key)
        return self._client

    def upcoming(self, symbols: list[str], days: int = 7) -> list[dict]:
        """Earnings expected within the next N days, filtered to symbols of interest."""
        try:
            frm = date.today().isoformat()
            to = (date.today() + timedelta(days=days)).isoformat()
            res = self._cli().earnings_calendar(
                _from=frm, to=to, symbol="", international=False
            )
            items = res.get("earningsCalendar", []) if isinstance(res, dict) else []
            sym_set = {s.upper() for s in symbols}
            return [
                {
                    "symbol": it["symbol"],
                    "date": it.get("date", ""),
                    "eps_est": it.get("epsEstimate"),
                    "revenue_est": it.get("revenueEstimate"),
                }
                for it in items
                if it.get("symbol", "").upper() in sym_set
            ]
        except Exception:
            return []

    def history(self, symbol: str, limit: int = 4) -> list[dict]:
        """Last N quarters: EPS actual vs estimate + surprise %."""
        try:
            items = self._cli().company_earnings(symbol, limit=limit)
            out = []
            for it in (items or [])[:limit]:
                actual = it.get("actual")
                est = it.get("estimate")
                surprise = None
                if actual is not None and est and abs(est) > 1e-6:
                    surprise = round((actual - est) / abs(est) * 100, 1)
                out.append({
                    "period": it.get("period", ""),
                    "eps_actual": actual,
                    "eps_est": est,
                    "surprise_pct": surprise,
                })
            return out
        except Exception:
            return []
