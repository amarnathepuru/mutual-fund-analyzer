"""
Export scheme metadata from nav.db (Batch 2 detail API meta) to CSV.

Includes scheme_category, fund_house, scheme_type, ISIN, NAV date range, etc.
Does not modify app.py or fund master.

Usage:
  python scripts/mfapi_export_scheme_meta.py
  python scripts/mfapi_export_scheme_meta.py --direct-growth-only
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
NAV_DB = ROOT / "data" / "nav" / "nav.db"
OUT_ALL = ROOT / "data" / "raw" / "mfapi" / "scheme_meta_all.csv"
OUT_DG = ROOT / "data" / "raw" / "mfapi" / "scheme_meta_direct_growth.csv"
DG_CSV = ROOT / "data" / "raw" / "mfapi" / "direct_growth_schemes.csv"

COLUMNS = [
    "mf_scheme_code",
    "scheme_name_raw",
    "fund_name_base",
    "isin_growth",
    "fund_house",
    "scheme_type",
    "scheme_category",
    "sync_status",
    "nav_rows",
    "first_nav_date",
    "last_nav_date",
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--direct-growth-only",
        action="store_true",
        help="Filter to codes in direct_growth_schemes.csv",
    )
    args = parser.parse_args()

    if not NAV_DB.is_file():
        print(f"Missing {NAV_DB}. Run: python scripts/mfapi_fetch_nav.py")
        return 1

    conn = sqlite3.connect(NAV_DB)
    df = pd.read_sql_query(
        f"""
        SELECT mf_scheme_code AS mf_scheme_code,
               scheme_name_raw,
               fund_name_base,
               isin_growth,
               fund_house,
               scheme_type,
               scheme_category,
               sync_status,
               nav_rows,
               first_nav_date,
               last_nav_date
        FROM schemes
        ORDER BY mf_scheme_code
        """,
        conn,
    )
    conn.close()

    df.to_csv(OUT_ALL, index=False, encoding="utf-8")
    print(f"Wrote {len(df)} rows -> {OUT_ALL}")

    if args.direct_growth_only or DG_CSV.is_file():
        if not DG_CSV.is_file():
            print(f"Warning: {DG_CSV} not found; skipping direct-growth export")
        else:
            dg = pd.read_csv(DG_CSV)
            codes = set(dg["mf_scheme_code"].astype(int))
            dg_df = df[df["mf_scheme_code"].astype(int).isin(codes)].copy()
            dg_df.to_csv(OUT_DG, index=False, encoding="utf-8")
            print(f"Wrote {len(dg_df)} rows -> {OUT_DG}")
            with_cat = dg_df["scheme_category"].notna().sum()
            print(f"  scheme_category populated: {with_cat}/{len(dg_df)}")

    sample = df[df["mf_scheme_code"] == 120465]
    if not sample.empty:
        row = sample.iloc[0]
        print(f"Sample 120465: scheme_category={row['scheme_category']!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
