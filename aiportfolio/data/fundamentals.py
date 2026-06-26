"""Optional fundamentals via Financial Modeling Prep.

If no FMP key is configured this returns empty dicts gracefully, so the
rest of the system runs fine on free data alone.
"""
from __future__ import annotations

import urllib.request
import json


class Fundamentals:
    BASE = "https://financialmodelingprep.com/api/v3"

    def __init__(self, secrets):
        self.key = secrets.fmp_key

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    def _get(self, path: str) -> list | dict:
        if not self.enabled:
            return []
        url = f"{self.BASE}/{path}{'&' if '?' in path else '?'}apikey={self.key}"
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                return json.loads(r.read().decode())
        except Exception:
            return []

    def snapshot(self, symbol: str) -> dict:
        if not self.enabled:
            return {}
        prof = self._get(f"profile/{symbol}")
        ratios = self._get(f"ratios-ttm/{symbol}")
        p = prof[0] if isinstance(prof, list) and prof else {}
        r = ratios[0] if isinstance(ratios, list) and ratios else {}
        return {
            "symbol": symbol,
            "sector": p.get("sector"),
            "industry": p.get("industry"),
            "market_cap": p.get("mktCap"),
            "pe": r.get("peRatioTTM"),
            "roe": r.get("returnOnEquityTTM"),
            "debt_to_equity": r.get("debtEquityRatioTTM"),
            "beta": p.get("beta"),
        }
