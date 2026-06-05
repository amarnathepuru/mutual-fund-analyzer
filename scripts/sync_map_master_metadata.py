"""
Backfill fund_scheme_map et_fund_name and isin from ET master + nav.db.

  python scripts/sync_map_master_metadata.py
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "data/fund_scheme_map.csv"
ET_MASTER = ROOT / "data/fund_master_auto.csv"
NAV_DB = ROOT / "data/nav/nav.db"
BACKUPS = ROOT / "data/backups"


def _isin_lookup() -> dict[int, str]:
    if not NAV_DB.is_file():
        return {}
    conn = sqlite3.connect(NAV_DB)
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
    m = pd.read_csv(MAP)
    et = pd.read_csv(ET_MASTER)
    et_by_id = {int(r["scheme_id"]): str(r.get("fund_name") or "") for _, r in et.iterrows()}
    isin_by_mf = _isin_lookup()

    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(MAP, BACKUPS / f"fund_scheme_map_{stamp}.csv")

    filled_name = filled_isin = 0
    for idx, row in m.iterrows():
        sid = int(row["scheme_id"])
        mf = int(row["mf_scheme_code"])
        en = str(row.get("et_fund_name") or "").strip()
        if not en or en.lower() == "nan":
            name = et_by_id.get(sid, "")
            if name:
                m.at[idx, "et_fund_name"] = name
                filled_name += 1
        isin = str(row.get("isin") or "").strip()
        if (not isin or isin.lower() == "nan") and mf in isin_by_mf:
            m.at[idx, "isin"] = isin_by_mf[mf]
            filled_isin += 1

    m.to_csv(MAP, index=False, encoding="utf-8")
    print(f"Backfilled et_fund_name: {filled_name}")
    print(f"Backfilled isin: {filled_isin}")
    print(f"Wrote {MAP} ({len(m)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
