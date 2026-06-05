"""
Move unmapped ET index funds out of ACTIVE master/holdings (defer until index MFAPI pass).

Keeps index funds that are already in fund_scheme_map.csv.

Usage (repo root):
  python scripts/et_defer_unmapped_index.py --dry-run
  python scripts/et_defer_unmapped_index.py
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from et_mfapi_match_scope import is_et_index_fund  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROC = DATA / "processed"
BACKUPS = DATA / "backups"
REPORTS = DATA / "reports"

MASTER = DATA / "fund_master_auto.csv"
INVALID = DATA / "fund_master_invalid.csv"
MAP = DATA / "fund_scheme_map.csv"
HOLDINGS = PROC / "master_holdings.csv"
NORM = PROC / "normalized_holdings.csv"
SIM = PROC / "fund_similarity.csv"
QC = REPORTS / "et_defer_unmapped_index_qc.txt"

STATUS_DEFERRED = "INDEX_DEFERRED"


def _backup(paths: list[Path]) -> None:
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = date.today().strftime("%Y%m%d")
    for p in paths:
        if not p.is_file():
            continue
        dest = BACKUPS / f"{p.stem}_pre_index_defer_{stamp}{p.suffix}"
        if not dest.is_file():
            shutil.copy2(p, dest)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    master = pd.read_csv(MASTER)
    mp = pd.read_csv(MAP)
    mapped_ids = set(mp["scheme_id"].astype(int))

    master["is_index"] = master.apply(
        lambda r: is_et_index_fund(r.get("category"), r.get("fund_name")), axis=1
    )
    defer = master[master["is_index"] & ~master["scheme_id"].astype(int).isin(mapped_ids)].copy()
    keep = master[~master.index.isin(defer.index)].copy()

    defer_names = set(defer["fund_name"].astype(str))
    defer_ids = set(defer["scheme_id"].astype(int))

    lines = [
        "Defer unmapped ET index funds",
        f"Mode: {'dry-run' if args.dry_run else 'apply'}",
        f"ACTIVE before: {len(master)}",
        f"Defer rows: {len(defer)}",
        f"ACTIVE after: {len(keep)}",
        f"Mapped index kept: {int((master['is_index'] & master['scheme_id'].astype(int).isin(mapped_ids)).sum())}",
    ]

    if defer.empty:
        print("Nothing to defer.")
        return 0

    holdings = pd.read_csv(HOLDINGS) if HOLDINGS.is_file() else pd.DataFrame()
    norm = pd.read_csv(NORM) if NORM.is_file() else pd.DataFrame()
    sim = pd.read_csv(SIM) if SIM.is_file() else pd.DataFrame()

    h_before = len(holdings)
    n_before = len(norm)
    s_before = len(sim)

    if not holdings.empty and "fund_name" in holdings.columns:
        holdings_out = holdings[~holdings["fund_name"].astype(str).isin(defer_names)]
    else:
        holdings_out = holdings

    if not norm.empty and "fund_name" in norm.columns:
        norm_out = norm[~norm["fund_name"].astype(str).isin(defer_names)]
    else:
        norm_out = norm

    if not sim.empty and {"fund_a", "fund_b"}.issubset(sim.columns):
        sim_out = sim[
            ~sim["fund_a"].astype(str).isin(defer_names)
            & ~sim["fund_b"].astype(str).isin(defer_names)
        ]
    else:
        sim_out = sim

    lines.extend(
        [
            f"holdings rows: {h_before} -> {len(holdings_out)}",
            f"normalized rows: {n_before} -> {len(norm_out)}",
            f"similarity pairs: {s_before} -> {len(sim_out)}",
        ]
    )

    if args.dry_run:
        REPORTS.mkdir(parents=True, exist_ok=True)
        QC.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        print(f"\nQC: {QC}")
        return 0

    _backup([MASTER, INVALID, HOLDINGS, NORM, SIM])

    defer_out = defer.drop(columns=["is_index"], errors="ignore").copy()
    defer_out["status"] = STATUS_DEFERRED
    defer_out["notes"] = "Unmapped index — deferred until index MFAPI scrape pass"

    if INVALID.is_file():
        invalid = pd.read_csv(INVALID)
        invalid = invalid[~invalid["scheme_id"].astype(int).isin(defer_ids)]
        invalid = pd.concat([invalid, defer_out], ignore_index=True)
    else:
        invalid = defer_out

    keep = keep.drop(columns=["is_index"], errors="ignore")
    keep.to_csv(MASTER, index=False, encoding="utf-8")
    invalid.to_csv(INVALID, index=False, encoding="utf-8")
    holdings_out.to_csv(HOLDINGS, index=False, encoding="utf-8")
    norm_out.to_csv(NORM, index=False, encoding="utf-8")
    sim_out.to_csv(SIM, index=False, encoding="utf-8")

    REPORTS.mkdir(parents=True, exist_ok=True)
    QC.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote QC: {QC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
