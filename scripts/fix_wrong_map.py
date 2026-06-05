"""Remove wrong fund_scheme_map rows and mark rejected. Usage: python scripts/fix_wrong_map.py 120147 147587"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mfapi_et_decisions import load_decisions, save_decisions, upsert_decision  # noqa: E402
from mfapi_scheme_name import mf_fund_name_cleaned  # noqa: E402

MAP = ROOT / "data/fund_scheme_map.csv"
NAV = ROOT / "data/raw/mfapi/nav_universe_schemes.csv"
BACKUPS = ROOT / "data/backups"


def main() -> int:
    codes = [int(x) for x in sys.argv[1:]]
    if not codes:
        print("Usage: python scripts/fix_wrong_map.py <mf_scheme_code> ...")
        return 1

    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(MAP, BACKUPS / f"fund_scheme_map_{stamp}.csv")

    m = pd.read_csv(MAP)
    nav = pd.read_csv(NAV)
    removed = m[m["mf_scheme_code"].astype(int).isin(codes)]
    for _, r in removed.iterrows():
        print(f"REMOVE MF {int(r.mf_scheme_code)} -> ET {int(r.scheme_id)} | {r.et_fund_name}")

    m = m[~m["mf_scheme_code"].astype(int).isin(codes)]
    m.to_csv(MAP, index=False)
    print(f"Map: {len(removed)} removed, {len(m)} rows remain")

    d = load_decisions()
    for code in codes:
        nr = nav[nav["mf_scheme_code"].astype(int) == code]
        name = ""
        if not nr.empty:
            name = mf_fund_name_cleaned(str(nr.iloc[0]["scheme_name_raw"]))
        d = upsert_decision(
            d,
            mf_scheme_code=code,
            decision="rejected",
            scheme_id=None,
            computed_score=None,
            mf_scheme_name=name,
            et_fund_name="",
            notes="manual fix wrong batch map; no correct ET page; track/NAV only",
        )
    save_decisions(d)
    print(f"Decisions updated: {codes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
