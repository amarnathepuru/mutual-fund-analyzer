"""
Close remaining NAV-universe funds with no ET map (missing on ET or duplicate MFAPI codes).

Writes rejected decisions + summary CSV. Does not change fund_scheme_map.csv.

  python scripts/close_out_nav_unmapped.py --dry-run
  python scripts/close_out_nav_unmapped.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mfapi_et_decisions import load_decisions, save_decisions, upsert_decision  # noqa: E402
from mfapi_scheme_name import mf_fund_name_cleaned  # noqa: E402

NAV_UNIVERSE = ROOT / "data/raw/mfapi/nav_universe_schemes.csv"
MAP = ROOT / "data/fund_scheme_map.csv"
OUT = ROOT / "data/reports/nav_unmapped_closed.csv"
NOTE = "nav_universe closed: no ET Money page or duplicate MFAPI; track/NAV only"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    nav = pd.read_csv(NAV_UNIVERSE)
    m = pd.read_csv(MAP)
    mapped_mf = set(m["mf_scheme_code"].dropna().astype(int))
    mapped_isin = {
        str(x).strip()
        for x in m["isin"].dropna()
        if str(x).strip() and str(x).strip().lower() != "nan"
    }

    decisions = load_decisions()
    already = set(decisions["mf_scheme_code"].dropna().astype(int))

    rows: list[dict] = []
    closed = 0
    for _, r in nav.iterrows():
        code = int(r["mf_scheme_code"])
        if code in mapped_mf:
            continue
        name = mf_fund_name_cleaned(str(r.get("scheme_name_raw") or ""))
        isin = str(r.get("isin_growth") or "").strip()
        reason = "no_et_or_unmapped_duplicate"
        if isin and isin in mapped_isin:
            reason = "duplicate_isin"

        rows.append(
            {
                "mf_scheme_code": code,
                "mfapi_cleaned": name,
                "isin_growth": isin,
                "close_reason": reason,
                "already_in_decisions": code in already,
            }
        )
        if code in already:
            continue
        if not args.dry_run:
            decisions = upsert_decision(
                decisions,
                mf_scheme_code=code,
                decision="rejected",
                scheme_id=None,
                computed_score=None,
                mf_scheme_name=name,
                et_fund_name="",
                notes=NOTE,
            )
        closed += 1

    out_df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
        save_decisions(decisions)
        out_df.to_csv(OUT, index=False, encoding="utf-8-sig")

    print(f"NAV universe: {len(nav)}")
    print(f"Mapped: {len(mapped_mf)}")
    print(f"Unmapped in universe: {len(rows)}")
    print(f"New rejected decisions: {closed}" + (" (dry-run)" if args.dry_run else ""))
    if not args.dry_run:
        print(f"Wrote {OUT}")
        print(f"Updated mfapi_et_decisions.csv ({len(decisions)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
