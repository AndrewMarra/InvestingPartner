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
        """High/medium-impact macro events in the next N days (Fed, CPI, jobs, GDP)."""
        try:
            frm = date.today().isoformat()
            to = (date.today() + timedelta(days=days)).isoformat()
            res = self._cli().economic_calendar()
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
        """VIX level + plain-English interpretation. Returns {} if unavailable."""
        if not self._market:
            return {}
        try:
            # Alpaca supports VIX as a quoted index on some plans.
            px = self._market.latest_price("VIXY")  # VIX ETF proxy (more widely available)
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
            return {"proxy": "VIXY", "level": round(level, 2), "interpretation": interp}
        except Exception:
            return {}
