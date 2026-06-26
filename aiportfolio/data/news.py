"""Company + market news via Finnhub (free tier friendly)."""
from __future__ import annotations

from datetime import date, timedelta

import finnhub


class NewsFeed:
    def __init__(self, secrets):
        self.client = finnhub.Client(api_key=secrets.finnhub_key)

    def company_news(self, symbol: str, days: int = 5, limit: int = 5) -> list[dict]:
        try:
            to = date.today()
            frm = to - timedelta(days=days)
            items = self.client.company_news(
                symbol, _from=frm.isoformat(), to=to.isoformat()
            )
            out = []
            for it in items[:limit]:
                out.append(
                    {
                        "headline": it.get("headline", ""),
                        "summary": (it.get("summary", "") or "")[:300],
                        "source": it.get("source", ""),
                        "url": it.get("url", ""),
                    }
                )
            return out
        except Exception:
            return []

    def market_news(self, limit: int = 6) -> list[dict]:
        try:
            items = self.client.general_news("general")
            return [
                {"headline": it.get("headline", ""), "source": it.get("source", "")}
                for it in items[:limit]
            ]
        except Exception:
            return []
