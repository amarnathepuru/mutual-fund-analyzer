"""
Prune nav.db to Equity + Hybrid + Liquid universe only.

Deletes nav_prices and schemes rows outside the universe. Writes QC report and
nav_universe_schemes.csv for Batch 2 resume.

Usage (repo root):
  python scripts/mfapi_prune_nav_db.py --dry-run
  python scripts/mfapi_prune_nav_db.py
  python scripts/mfapi_prune_nav_db.py --no-backup
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from mfapi_nav_universe import scheme_in_nav_universe

ROOT = Path(__file__).resolve().parents[1]
NAV_DB = ROOT / "data" / "nav" / "nav.db"
BACKUPS = ROOT / "data" / "backups"
REPORTS = ROOT / "data" / "reports"
UNIVERSE_CSV = ROOT / "data" / "raw" / "mfapi" / "nav_universe_schemes.csv"


def _classify_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["in_universe"] = out.apply(
        lambda r: scheme_in_nav_universe(
            r.get("scheme_category"), r.get("scheme_name_raw")
        ),
        axis=1,
    )
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Prune nav.db to Equity/Hybrid/Liquid")
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not delete")
    parser.add_argument("--no-backup", action="store_true", help="Skip copying nav.db to backups/")
    args = parser.parse_args()

    if not NAV_DB.is_file():
        print(f"Missing {NAV_DB}")
        return 1

    conn = sqlite3.connect(NAV_DB)
    try:
        df = pd.read_sql_query(
            """
            SELECT mf_scheme_code, scheme_name_raw, fund_name_base, isin_growth,
                   fund_house, scheme_category, scheme_type, sync_status,
                   nav_rows, first_nav_date, last_nav_date
            FROM schemes
            """,
            conn,
        )
        nav_before = conn.execute("SELECT COUNT(*) FROM nav_prices").fetchone()[0]
        classified = _classify_df(df)
        keep = classified[classified["in_universe"]]
        drop = classified[~classified["in_universe"]]

        drop_codes = [int(c) for c in drop["mf_scheme_code"].astype(int)]

        from mfapi_nav_universe import is_equity_or_hybrid, is_liquid_fund

        n_eq_hy = int(
            keep.apply(
                lambda r: is_equity_or_hybrid(r.get("scheme_category")), axis=1
            ).sum()
        )
        n_liquid = int(
            keep.apply(
                lambda r: is_liquid_fund(
                    r.get("scheme_category"), r.get("scheme_name_raw")
                ),
                axis=1,
            ).sum()
        )

        lines = [
            "MFApi NAV prune — Equity + Hybrid + Liquid",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            f"Mode: {'dry-run' if args.dry_run else 'apply'}",
            "",
            f"Schemes before: {len(df)}",
            f"Schemes keep: {len(keep)} (equity+hybrid={n_eq_hy}, liquid={n_liquid})",
            f"Schemes drop: {len(drop)}",
            f"nav_prices rows before: {nav_before}",
            "",
            "Keep by scheme_category (top 20):",
        ]
        for cat, n in (
            keep["scheme_category"].value_counts().head(20).items()
        ):
            lines.append(f"  {cat}: {n}")

        lines.append("")
        lines.append("Dropped category buckets (top 15):")
        for cat, n in drop["scheme_category"].value_counts().head(15).items():
            lines.append(f"  {cat}: {n}")

        qc_path = REPORTS / "mfapi_nav_prune_qc.txt"
        REPORTS.mkdir(parents=True, exist_ok=True)
        qc_path.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        print(f"\nQC: {qc_path}")

        if args.dry_run:
            return 0

        if not args.no_backup:
            BACKUPS.mkdir(parents=True, exist_ok=True)
            stamp = date.today().strftime("%Y%m%d")
            backup = BACKUPS / f"nav_pre_prune_{stamp}.db"
            if not backup.is_file():
                shutil.copy2(NAV_DB, backup)
                print(f"Backup: {backup}")
            else:
                print(f"Backup exists (skipped): {backup}")

        if drop_codes:
            placeholders = ",".join("?" * len(drop_codes))
            conn.execute(
                f"DELETE FROM nav_prices WHERE mf_scheme_code IN ({placeholders})",
                drop_codes,
            )
            conn.execute(
                f"DELETE FROM schemes WHERE mf_scheme_code IN ({placeholders})",
                drop_codes,
            )
            conn.commit()
            conn.execute("VACUUM")

        nav_after = conn.execute("SELECT COUNT(*) FROM nav_prices").fetchone()[0]
        schemes_after = conn.execute("SELECT COUNT(*) FROM schemes").fetchone()[0]

        UNIVERSE_CSV.parent.mkdir(parents=True, exist_ok=True)
        export_cols = [
            "mf_scheme_code",
            "scheme_name_raw",
            "fund_name_base",
            "isin_growth",
            "fund_house",
            "scheme_category",
            "scheme_type",
            "sync_status",
            "nav_rows",
            "first_nav_date",
            "last_nav_date",
        ]
        keep[export_cols].sort_values("mf_scheme_code").to_csv(
            UNIVERSE_CSV, index=False, encoding="utf-8"
        )

        lines.extend(
            [
                "",
                f"nav_prices rows after: {nav_after}",
                f"schemes rows after: {schemes_after}",
                f"Universe CSV: {UNIVERSE_CSV}",
            ]
        )
        qc_path.write_text("\n".join(lines), encoding="utf-8")

        print(f"\nPruned. schemes={schemes_after} nav_prices={nav_after}")
        print(f"Universe CSV: {UNIVERSE_CSV}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
