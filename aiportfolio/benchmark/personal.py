"""Compute the user's OWN portfolio return from a positions CSV.

This replaces hand-typing benchmark.personal_return_pct: point the config at a CSV
export of your real holdings and the buddy values them at live prices so
"AI vs my portfolio" is automatic. The CSV is read-only — nothing is ever traded
from it.

Expected columns (header row, case-insensitive): symbol, quantity, avg_cost
  - avg_cost is your average cost PER SHARE.
  - extra columns are ignored; rows missing a price are skipped.
"""
from __future__ import annotations

import csv
from pathlib import Path


def _norm(key: str) -> str:
    """Normalise a header so 'Avg Price' / 'avg_price' / 'Average  Price' all match."""
    return "_".join((key or "").strip().lower().split())


def _f(row: dict, *names) -> float | None:
    wanted = set(names)
    for k, v in row.items():
        if _norm(k) in wanted and str(v).strip() != "":
            try:
                return float(str(v).replace("$", "").replace(",", ""))
            except ValueError:
                return None
    return None


def load_positions(csv_path: str) -> list[dict]:
    path = Path(csv_path)
    if not path.exists():
        return []
    out = []
    with path.open(newline="", encoding="utf-8-sig") as f:  # tolerate a BOM
        for row in csv.DictReader(f):
            sym = next((str(v).strip().upper() for k, v in row.items()
                        if _norm(k) in {"symbol", "ticker"} and str(v).strip()), None)
            qty = _f(row, "quantity", "qty", "shares")
            cost = _f(row, "avg_cost", "cost", "avg_price", "price", "average_cost", "average_price")
            if sym and qty and cost:
                out.append({"symbol": sym, "quantity": qty, "avg_cost": cost})
    return out


def personal_return_from_csv(csv_path: str, market) -> float | None:
    """Return the user's portfolio % return (current value vs cost), or None."""
    positions = load_positions(csv_path)
    if not positions:
        return None
    cost_total = 0.0
    value_total = 0.0
    for p in positions:
        price = market.latest_price(p["symbol"])
        if price is None:
            continue
        cost_total += p["quantity"] * p["avg_cost"]
        value_total += p["quantity"] * price
    if cost_total <= 0:
        return None
    return round((value_total / cost_total - 1) * 100, 2)
