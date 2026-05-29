from __future__ import annotations

"""
One-off quick QC for ET ↔ MFAPI merge.

Run from repo root:
  python scripts/_quick_merge_qc.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

from et_mfapi_decisions import load_decisions
from review_queue import (
    build_needs_review_table,
    duplicate_map_rows,
    load_scheme_map,
    needs_review_counts,
)


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    report = pd.read_csv(ROOT / "data/reports/et_mfapi_match_report.csv")
    map_df = load_scheme_map()
    decisions = load_decisions()

    print("=== Match status counts ===")
    print(report["match_status"].value_counts().to_string())

    print("\n=== Needs-review counts (map-based) ===")
    print(needs_review_counts(report, map_df))

    queue = build_needs_review_table(
        report,
        map_df,
        decided_ids=set(decisions["scheme_id"].astype(int)) if not decisions.empty else set(),
    )
    print("\nqueue_rows", len(queue))
    if not queue.empty:
        print(queue.groupby("review_reason").size().to_string())

    print("\n=== Duplicate MF-code pairs in map ===")
    dups = duplicate_map_rows(map_df)
    pair_count = dups["mf_scheme_code"].nunique() if not dups.empty else 0
    print("dup_rows", len(dups), "pairs", pair_count)
    if not dups.empty:
        for code, grp in dups.groupby(dups["mf_scheme_code"].astype(int)):
            print(f"mf {code}:")
            for _, r in grp.iterrows():
                name = str(r.get("et_fund_name") or "")[:55]
                print(
                    f"  scheme_id={int(r['scheme_id'])} et={name} "
                    f"method={r.get('match_method')} score={r.get('match_score')}"
                )

    conn = sqlite3.connect(ROOT / "data/nav/nav.db")
    try:
        nav_codes = set(
            pd.read_sql_query("SELECT mf_scheme_code FROM schemes", conn)["mf_scheme_code"].astype(int)
        )
    finally:
        conn.close()

    bad_codes = map_df[~map_df["mf_scheme_code"].astype(int).isin(nav_codes)]
    print("\n=== Map codes missing in nav.db ===")
    print("count", len(bad_codes))

    appr = decisions[decisions["decision"] == "approved"]
    rej = decisions[decisions["decision"] == "rejected"]
    map_ids = set(map_df["scheme_id"].astype(int))

    missing_from_map = appr[~appr["scheme_id"].astype(int).isin(map_ids)]
    print("\n=== Approved decisions not in map ===")
    print("count", len(missing_from_map))

    still_mapped = rej[rej["scheme_id"].astype(int).isin(map_ids)]
    print("\n=== Rejected but still mapped ===")
    print("count", len(still_mapped))

    dup_sid_map = map_df[map_df.duplicated("scheme_id", keep=False)]
    print("\n=== Duplicate scheme_id in map ===")
    print("count", len(dup_sid_map))

    dup_sid_dec = decisions[decisions.duplicated("scheme_id", keep=False)]
    print("\n=== Duplicate scheme_id in decisions ===")
    print("count", len(dup_sid_dec))


if __name__ == "__main__":
    main()

