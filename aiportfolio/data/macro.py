"""Macro signals: upcoming economic events + VIX level."""
from __future__ import annotations

from datetime import date, timedelta


class MacroData:
    def __init__(self, secrets, market=None):
        self._key = secrets.finnhub_key
        self._client = None
        self._market = market  # MarketData, for VIX price lookup

    def _cli(self):
        if self._client is None:
            import finnhub
            self._client = finnhub.Client(api_key=self._key)
        return self._client

    def economic_calendar(self, days: int = 7) -> list[dict]:
        """High/medium-impact macro events in the next N days (Fed, CPI, jobs, GDP).
        Note: Finnhub's economic calendar is a premium endpoint — on the free
        tier this 403s and degrades to an empty list (handled below)."""
        try:
            frm = date.today().isoformat()
            to = (date.today() + timedelta(days=days)).isoformat()
            res = self._cli().calendar_economic()
            items = res.get("economicCalendar", []) if isinstance(res, dict) else []
            out = []
            for it in items:
                event_date = (it.get("time") or "")[:10]
                if event_date < frm or event_date > to:
                    continue
                impact = (it.get("impact") or "").lower()
                if impact not in ("high", "medium"):
                    continue
                out.append({
                    "event": it.get("event", ""),
                    "date": event_date,
                    "impact": impact,
                    "country": it.get("country", ""),
                })
            return out[:10]
        except Exception:
            return []

    def vix(self) -> dict:
        """VIX level + plain-English interpretation. Returns {} if unavailable.

        Uses the real ^VIX index, which is only quoted on some Alpaca plans —
        when it isn't, we omit VIX entirely rather than substitute a VIX-futures
        ETF (e.g. VIXY trades ~$40-60, on a totally different scale than the
        ~15-30 VIX level these thresholds assume, so it would always misread)."""
        if not self._market:
            return {}
        try:
            px = self._market.latest_price("^VIX")
            if px is None:
                return {}
            level = float(px)
            if level > 30:
                interp = "extreme fear"
            elif level > 20:
                interp = "high fear"
            elif level > 15:
                interp = "moderate"
            else:
                interp = "calm"
            return {"level": round(level, 2), "interpretation": interp}
        except Exception:
            return {}
