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

    def insider_sentiment(self, symbol: str) -> dict:
        """Net insider buying/selling signal via Finnhub MSPR score.
        MSPR ∈ [-1, 1]: positive = insiders net buying."""
        try:
            to = date.today().isoformat()
            frm = (date.today() - timedelta(days=90)).isoformat()
            res = self.client.stock_insider_sentiment(symbol, _from=frm, to=to)
            data = res.get("data", []) if isinstance(res, dict) else []
            if not data:
                return {}
            latest = data[-1]
            return {
                "mspr": latest.get("mspr"),
                "change": latest.get("change"),
            }
        except Exception:
            return {}

    def sec_filings(self, symbol: str, limit: int = 2) -> list[dict]:
        """Most recent 10-K or 10-Q filing dates."""
        try:
            items = self.client.filings(symbol=symbol, _from="", to="") or []
            major = [f for f in items if f.get("form") in ("10-K", "10-Q")]
            return [
                {"form": f["form"], "date": f.get("filedDate", "")}
                for f in major[:limit]
            ]
        except Exception:
            return []
