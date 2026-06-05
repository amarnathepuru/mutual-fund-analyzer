"""
Merge MFAPI→ET review approvals into fund_scheme_map.csv.

Only applies rows from mfapi_et_decisions.csv (decision=approved) or
data/mfapi_to_et_approved.csv export.

Usage (repo root):
  python scripts/apply_mfapi_et_map.py
  python scripts/apply_mfapi_et_map.py --dry-run
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mfapi_et_decisions import DECISIONS_CSV, decisions_as_map_rows, load_decisions  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BACKUPS = DATA / "backups"
MAP_OUT = DATA / "fund_scheme_map.csv"
NAV_DB = DATA / "nav" / "nav.db"
QC_OUT = DATA / "reports" / "mfapi_to_et_apply_qc.txt"

MAP_COLUMNS = [
    "scheme_id",
    "mf_scheme_code",
    "isin",
    "et_fund_name",
    "match_score",
    "match_method",
    "matched_at",
    "notes",
]


def _load_isin_lookup(nav_db: Path) -> dict[int, str]:
    if not nav_db.is_file():
        return {}
    conn = sqlite3.connect(nav_db)
    try:
        df = pd.read_sql_query(
            "SELECT mf_scheme_code, isin_growth FROM schemes WHERE isin_growth IS NOT NULL",
            conn,
        )
    finally:
        conn.close()
    out: dict[int, str] = {}
    for _, r in df.iterrows():
        try:
            out[int(r["mf_scheme_code"])] = str(r["isin_growth"]).strip()
        except (TypeError, ValueError):
            continue
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Apply MFAPI→ET approved mappings")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    decisions = load_decisions(DECISIONS_CSV)
    new_rows = decisions_as_map_rows(decisions)
    if not new_rows:
        print("No approved decisions to apply.")
        return 0

    isin_map = _load_isin_lookup(NAV_DB)
    now = datetime.now(timezone.utc).isoformat()

    if MAP_OUT.is_file():
        existing = pd.read_csv(MAP_OUT)
        for col in MAP_COLUMNS:
            if col not in existing.columns:
                existing[col] = ""
    else:
        existing = pd.DataFrame(columns=MAP_COLUMNS)

    existing_by_sid = {
        int(r["scheme_id"]): r for _, r in existing.iterrows() if pd.notna(r.get("scheme_id"))
    }
    existing_by_mf = {
        int(r["mf_scheme_code"]): r
        for _, r in existing.iterrows()
        if pd.notna(r.get("mf_scheme_code"))
    }

    added = updated = skipped = 0
    lines = [f"Apply MFAPI→ET map — {now}", ""]

    for row in new_rows:
        sid = int(row["scheme_id"])
        code = int(row["mf_scheme_code"])
        if sid in existing_by_sid and int(existing_by_sid[sid]["mf_scheme_code"]) != code:
            lines.append(f"SKIP conflict ET {sid}: existing MF {existing_by_sid[sid]['mf_scheme_code']}")
            skipped += 1
            continue
        if code in existing_by_mf and int(existing_by_mf[code]["scheme_id"]) != sid:
            lines.append(f"SKIP conflict MF {code}: existing ET {existing_by_mf[code]['scheme_id']}")
            skipped += 1
            continue

        map_row = {
            "scheme_id": sid,
            "mf_scheme_code": code,
            "isin": isin_map.get(code, ""),
            "et_fund_name": row.get("et_fund_name") or "",
            "match_score": "",
            "match_method": "mfapi_et_review",
            "matched_at": now,
            "notes": row.get("notes") or "mfapi_et_review",
        }
        if sid in existing_by_sid:
            for k, v in map_row.items():
                existing.loc[existing["scheme_id"].astype(int) == sid, k] = v
            updated += 1
        else:
            existing = pd.concat([existing, pd.DataFrame([map_row])], ignore_index=True)
            existing_by_sid[sid] = map_row
            existing_by_mf[code] = map_row
            added += 1

    lines.extend([f"Added: {added}", f"Updated: {updated}", f"Skipped: {skipped}", f"Total map rows: {len(existing)}"])

    if args.dry_run:
        print("\n".join(lines + ["", "(dry-run — no files written)"]))
        return 0

    BACKUPS.mkdir(parents=True, exist_ok=True)
    if MAP_OUT.is_file():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(MAP_OUT, BACKUPS / f"fund_scheme_map_{stamp}.csv")

    existing[MAP_COLUMNS].to_csv(MAP_OUT, index=False, encoding="utf-8")
    QC_OUT.parent.mkdir(parents=True, exist_ok=True)
    QC_OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"Wrote {MAP_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
