"""
Scrape holdings only for ACTIVE funds not yet in master_holdings.csv.
Appends new rows and saves data/processed/master_holdings.csv.
"""

import sys
import time
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Reuse scrape_fund from scrape_holdings.py
from scrape_holdings import scrape_fund  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MASTER_PATH = ROOT / "data" / "fund_master_auto.csv"
HOLDINGS_PATH = ROOT / "data" / "processed" / "master_holdings.csv"
DELAY = 2.0


def main():
    funds_df = pd.read_csv(MASTER_PATH)
    funds_df = funds_df[funds_df["status"] == "ACTIVE"].reset_index(drop=True)

    if HOLDINGS_PATH.exists():
        existing = pd.read_csv(HOLDINGS_PATH)
        have = set(existing["fund_name"].unique())
        print(f"Existing holdings: {len(existing)} rows, {len(have)} funds")
    else:
        existing = pd.DataFrame()
        have = set()
        HOLDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

    todo = funds_df[~funds_df["fund_name"].isin(have)].reset_index(drop=True)
    print(f"Funds to scrape: {len(todo)} / {len(funds_df)}")

    if todo.empty:
        print("Nothing new to scrape.")
        return

    new_rows = []
    for i, (_, fund) in enumerate(todo.iterrows(), 1):
        print(f"\n[{i}/{len(todo)}]", end=" ")
        fund_data = scrape_fund(fund)
        if len(fund_data) > 0:
            new_rows.append(fund_data)
        time.sleep(DELAY)

    if not new_rows:
        print("\nNo new holdings extracted.")
        return

    new_df = pd.concat(new_rows, ignore_index=True).drop_duplicates()
    combined = pd.concat([existing, new_df], ignore_index=True).drop_duplicates()
    combined.to_csv(HOLDINGS_PATH, index=False)
    print(f"\nSaved {len(combined)} total rows -> {HOLDINGS_PATH}")
    print(f"  Added {len(new_df)} rows from {new_df['fund_name'].nunique()} funds")


if __name__ == "__main__":
    main()
