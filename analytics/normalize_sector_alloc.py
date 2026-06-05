"""Validate fund_sector_allocation.csv totals and sector labels."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IN_PATH = ROOT / "data" / "processed" / "fund_sector_allocation.csv"


def main() -> None:
    if not IN_PATH.is_file():
        print("No fund_sector_allocation.csv — skip")
        return
    df = pd.read_csv(IN_PATH)
    print(f"Loaded {len(df)} sector allocation rows")
    if df.empty:
        return
    df["allocation_percent"] = pd.to_numeric(df["allocation_percent"], errors="coerce")
    summary = (
        df.groupby("fund_name")["allocation_percent"]
        .sum()
        .reset_index(name="total_pct")
        .sort_values("total_pct", ascending=False)
    )
    print("\nAllocation totals per fund:\n")
    print(summary.to_string(index=False))
    low = summary[summary["total_pct"] < 50]
    if not low.empty:
        print(f"\nWarning: {len(low)} fund(s) with total < 50%")


if __name__ == "__main__":
    main()
