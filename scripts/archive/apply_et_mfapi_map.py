"""
Batch 4: Merge match report + review decisions into fund_scheme_map.csv.

Sources:
  - auto_ok rows from et_mfapi_match_report.csv
  - approved rows from et_mfapi_decisions.csv (override auto_ok; add manual links)
  - rejected rows remove any mapping for that scheme_id

Usage (repo root):
  python scripts/apply_et_mfapi_map.py
  python scripts/apply_et_mfapi_map.py --dry-run
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

from et_mfapi_decisions import (
    DECISIONS_CSV,
    OVERRIDES_CSV,
    export_overrides_from_decisions,
    load_decisions,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = DATA / "reports"
BACKUPS = DATA / "backups"
REPORT = REPORTS / "et_mfapi_match_report.csv"
MAP_OUT = DATA / "fund_scheme_map.csv"
NAV_DB = DATA / "nav" / "nav.db"
QC_OUT = REPORTS / "mfapi_batch4_apply_qc.txt"

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


def _row_from_report(r: pd.Series, isin_map: dict[int, str]) -> dict:
    code = int(float(r["mf_scheme_code"]))
    score = r.get("match_score")
    try:
        score_f = round(float(score), 2) if pd.notna(score) and str(score).strip() != "" else ""
    except (TypeError, ValueError):
        score_f = ""
    return {
        "scheme_id": int(r["scheme_id"]),
        "mf_scheme_code": code,
        "isin": isin_map.get(code, r.get("isin_growth") or ""),
        "et_fund_name": r.get("et_fund_name") or "",
        "match_score": score_f,
        "match_method": "auto",
        "matched_at": datetime.now(timezone.utc).isoformat(),
        "notes": "auto_ok from match report",
    }


def _row_from_decision(r: pd.Series, isin_map: dict[int, str]) -> dict:
    code = int(r["mf_scheme_code"])
    score = r.get("computed_score")
    try:
        score_f = round(float(score), 2) if pd.notna(score) and str(score).strip() != "" else ""
    except (TypeError, ValueError):
        score_f = ""
    return {
        "scheme_id": int(r["scheme_id"]),
        "mf_scheme_code": code,
        "isin": isin_map.get(code, ""),
        "et_fund_name": r.get("et_fund_name") or "",
        "match_score": score_f,
        "match_method": "manual",
        "matched_at": r.get("decided_at") or datetime.now(timezone.utc).isoformat(),
        "notes": r.get("notes") or "approved in review app",
    }


def build_scheme_map(
    report: pd.DataFrame, decisions: pd.DataFrame, isin_map: dict[int, str]
) -> tuple[pd.DataFrame, dict]:
    stats = {
        "auto_ok_seeded": 0,
        "approved_applied": 0,
        "rejected_removed": 0,
        "approved_override_auto": 0,
    }
    by_id: dict[int, dict] = {}

    auto = report[report["match_status"] == "auto_ok"]
    for _, r in auto.iterrows():
        sid = int(r["scheme_id"])
        if pd.isna(r.get("mf_scheme_code")) or str(r.get("mf_scheme_code")).strip() == "":
            continue
        by_id[sid] = _row_from_report(r, isin_map)
        stats["auto_ok_seeded"] += 1

    if not decisions.empty:
        approved = decisions[decisions["decision"].astype(str).str.lower() == "approved"]
        for _, r in approved.iterrows():
            sid = int(r["scheme_id"])
            if pd.isna(r.get("mf_scheme_code")) or str(r.get("mf_scheme_code")).strip() == "":
                continue
            if sid in by_id and by_id[sid].get("match_method") == "auto":
                stats["approved_override_auto"] += 1
            by_id[sid] = _row_from_decision(r, isin_map)
            stats["approved_applied"] += 1

        rejected = decisions[decisions["decision"].astype(str).str.lower() == "rejected"]
        for _, r in rejected.iterrows():
            sid = int(r["scheme_id"])
            if sid in by_id:
                del by_id[sid]
                stats["rejected_removed"] += 1

    out = pd.DataFrame(list(by_id.values()))
    if not out.empty:
        out = out.sort_values("scheme_id").reset_index(drop=True)
    return out, stats


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Batch 4: apply ET-MFAPI map")
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not write files")
    args = parser.parse_args()

    if not REPORT.is_file():
        print(f"Missing {REPORT}. Run: python scripts/match_et_mfapi.py")
        return 1

    report = pd.read_csv(REPORT)
    decisions = load_decisions(DECISIONS_CSV)
    isin_map = _load_isin_lookup(NAV_DB)

    scheme_map, stats = build_scheme_map(report, decisions, isin_map)

    dup_mf = scheme_map[scheme_map.duplicated("mf_scheme_code", keep=False)]
    dup_count = len(dup_mf)

    lines = [
        "MFApi Batch 4 — apply fund_scheme_map.csv",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Mode: {'dry-run' if args.dry_run else 'apply'}",
        "",
        f"Decisions file: {len(decisions)} rows",
        f"  approved: {len(decisions[decisions.decision=='approved']) if len(decisions) else 0}",
        f"  rejected: {len(decisions[decisions.decision=='rejected']) if len(decisions) else 0}",
        "",
        "Merge stats:",
        f"  auto_ok seeded: {stats['auto_ok_seeded']}",
        f"  approved applied: {stats['approved_applied']}",
        f"  approved overriding auto_ok: {stats['approved_override_auto']}",
        f"  rejected removed from map: {stats['rejected_removed']}",
        "",
        f"fund_scheme_map rows: {len(scheme_map)}",
        f"duplicate mf_scheme_code assignments: {dup_count // 2 if dup_count else 0} pairs ({dup_count} rows)",
        "",
    ]
    if dup_count:
        lines.append("Sample duplicate mf_scheme_code (first 10 rows):")
        for _, r in dup_mf.head(10).iterrows():
            name = str(r.get("et_fund_name") or "")[:50]
            lines.append(
                f"  scheme_id={r['scheme_id']} mf={r['mf_scheme_code']} {name}"
            )
        lines.append("")

    if args.dry_run:
        print("\n".join(lines))
        print("(dry-run — no files written)")
        return 0

    BACKUPS.mkdir(parents=True, exist_ok=True)
    if MAP_OUT.is_file():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        backup = BACKUPS / f"fund_scheme_map_{stamp}.csv"
        if not backup.is_file():
            shutil.copy2(MAP_OUT, backup)
            lines.append(f"Backup: {backup}")

    scheme_map.to_csv(MAP_OUT, index=False, encoding="utf-8")
    n_ov = export_overrides_from_decisions(decisions, OVERRIDES_CSV)

    lines.extend(
        [
            f"Wrote: {MAP_OUT}",
            f"Wrote: {OVERRIDES_CSV} ({n_ov} approved rows)",
            f"QC: {QC_OUT}",
        ]
    )
    REPORTS.mkdir(parents=True, exist_ok=True)
    QC_OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
