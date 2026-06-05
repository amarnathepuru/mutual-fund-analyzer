"""
Remove regenerable reports, scrape backups, and raw MFAPI snapshots.

Keeps app-critical data (map, master, holdings, NAV universe, decisions).

  python scripts/cleanup_data_artifacts.py --dry-run
  python scripts/cleanup_data_artifacts.py
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data/reports"
BACKUPS = ROOT / "data/backups"
RAW_MFAPI = ROOT / "data/raw/mfapi"

# Regenerable raw MFAPI (keep nav universe + field inventory)
RAW_DELETE_NAMES = {
    "all_schemes_parsed.csv",
    "direct_growth_schemes.csv",
    "scheme_meta_all.csv",
    "scheme_meta_direct_growth.csv",
}
RAW_DELETE_GLOBS = ["mf_scheme_list_*.json"]


def _delete_path(p: Path, dry_run: bool) -> int:
    if not p.exists():
        return 0
    if dry_run:
        print(f"  would delete: {p.relative_to(ROOT)}")
        return 1
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()
    print(f"  deleted: {p.relative_to(ROOT)}")
    return 1


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    n = 0

    print("=== data/reports/ (all except .gitkeep) ===")
    if REPORTS.is_dir():
        for p in sorted(REPORTS.iterdir()):
            if p.name in (".gitkeep", "README.md"):
                continue
            n += _delete_path(p, args.dry_run)

    print("=== data/backups/ (all except .gitkeep) ===")
    if BACKUPS.is_dir():
        for p in sorted(BACKUPS.iterdir()):
            if p.name in (".gitkeep", "README.md"):
                continue
            n += _delete_path(p, args.dry_run)

    print("=== data/raw/mfapi/ (snapshots; keep nav_universe + inventory) ===")
    if RAW_MFAPI.is_dir():
        for name in RAW_DELETE_NAMES:
            n += _delete_path(RAW_MFAPI / name, args.dry_run)
        for pat in RAW_DELETE_GLOBS:
            for p in RAW_MFAPI.glob(pat):
                n += _delete_path(p, args.dry_run)

    print("=== data/processed/common_holdings.csv (optional derive) ===")
    n += _delete_path(ROOT / "data/processed/common_holdings.csv", args.dry_run)
    n += _delete_path(ROOT / "data/mfapi_to_et_approved.csv", args.dry_run)

    print()
    print(f"{'Would remove' if args.dry_run else 'Removed'} {n} path(s).")
    if args.dry_run:
        print("Re-run without --dry-run to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
