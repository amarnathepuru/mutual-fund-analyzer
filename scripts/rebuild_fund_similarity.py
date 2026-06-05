"""
Fast rebuild of fund_similarity.csv from normalized_holdings.csv.

Replaces analytics/similarity_engine.py for full-universe runs (~700 funds in minutes).

  python scripts/rebuild_fund_similarity.py
"""
from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
NORM = ROOT / "data/processed/normalized_holdings.csv"
OUT = ROOT / "data/processed/fund_similarity.csv"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    df = pd.read_csv(NORM)
    print(f"Loaded {len(df)} normalized rows")

    fund_stocks: dict[str, dict[str, float]] = {}
    fund_totals: dict[str, float] = {}
    for fund, g in df.groupby("fund_name", sort=False):
        fund_stocks[fund] = dict(zip(g["stock_name"], g["allocation_percent"].astype(float)))
        fund_totals[fund] = float(g["allocation_percent"].sum())

    funds = list(fund_stocks.keys())
    print(f"Funds: {len(funds)}")

    results: list[dict] = []
    n_pairs = len(funds) * (len(funds) - 1) // 2
    done = 0
    for fund_a, fund_b in combinations(funds, 2):
        a = fund_stocks[fund_a]
        b = fund_stocks[fund_b]
        common = a.keys() & b.keys()
        common_stock_count = len(common)
        similarity_score = sum(min(a[s], b[s]) for s in common) if common else 0.0
        min_total = min(fund_totals[fund_a], fund_totals[fund_b])
        normalized_score = (
            round(similarity_score / min_total * 100, 2) if min_total > 0 else 0.0
        )
        results.append(
            {
                "fund_a": fund_a,
                "fund_b": fund_b,
                "common_stocks": common_stock_count,
                "similarity_score": round(similarity_score, 2),
                "normalized_score": normalized_score,
            }
        )
        done += 1
        if done % 50000 == 0:
            print(f"  {done}/{n_pairs} pairs...")

    out = pd.DataFrame(results).sort_values("normalized_score", ascending=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"Wrote {OUT} ({len(out)} pairs)")
    print(out.head(5).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
