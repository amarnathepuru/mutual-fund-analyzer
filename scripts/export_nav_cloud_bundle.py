"""
Export committed NAV files for Streamlit Cloud (nav.db is gitignored).

Writes:
  data/processed/nav_universe_schemes.csv
  data/processed/nav_latest.csv  (mf_scheme_code, nav_date, nav)

Run locally after refreshing nav.db:
  python scripts/export_nav_cloud_bundle.py
"""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_UNIVERSE = ROOT / "data" / "raw" / "mfapi" / "nav_universe_schemes.csv"
OUT_DIR = ROOT / "data" / "processed"
OUT_UNIVERSE = OUT_DIR / "nav_universe_schemes.csv"
OUT_LATEST = OUT_DIR / "nav_latest.csv"
NAV_DB = ROOT / "data" / "nav" / "nav.db"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not RAW_UNIVERSE.is_file():
        raise SystemExit(f"Missing {RAW_UNIVERSE} — run mfapi_nav_universe / prune first.")
    shutil.copy2(RAW_UNIVERSE, OUT_UNIVERSE)
    print(f"Wrote {OUT_UNIVERSE} ({OUT_UNIVERSE.stat().st_size:,} bytes)")

    if not NAV_DB.is_file():
        raise SystemExit(f"Missing {NAV_DB} — run mfapi_fetch_nav first.")
    conn = sqlite3.connect(NAV_DB)
    try:
        df = pd.read_sql_query(
            """
            SELECT p.mf_scheme_code, p.nav_date, p.nav
            FROM nav_prices p
            INNER JOIN (
                SELECT mf_scheme_code, MAX(nav_date) AS nav_date
                FROM nav_prices
                GROUP BY mf_scheme_code
            ) latest
              ON p.mf_scheme_code = latest.mf_scheme_code
             AND p.nav_date = latest.nav_date
            ORDER BY p.mf_scheme_code
            """,
            conn,
        )
    finally:
        conn.close()
    df["mf_scheme_code"] = pd.to_numeric(df["mf_scheme_code"], errors="coerce").astype("Int64")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df["nav_date"] = df["nav_date"].astype(str).str[:10]
    df = df.dropna(subset=["mf_scheme_code", "nav", "nav_date"])
    df.to_csv(OUT_LATEST, index=False)
    print(f"Wrote {OUT_LATEST} ({len(df)} schemes, {OUT_LATEST.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
