"""
Export full ET ↔ MFAPI audit CSV for manual mapping review.

Columns:
  - MFAPI Fund Name (scheme_name_raw)
  - MFAPI Fund Name Cleaned (display)
  - ET Fund Name
  - Fund Category (ET category when mapped; else MFAPI scheme_category)

Includes all NAV-universe MFAPI schemes (881) plus ET funds with no MFAPI link.

Usage (repo root):
  python scripts/export_et_mfapi_audit.py
  python scripts/export_et_mfapi_audit.py -o data/reports/my_audit.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mfapi_scheme_name import extract_fund_name_base, format_display_fund_name  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = DATA / "reports"

MF_UNIVERSE = DATA / "raw" / "mfapi" / "nav_universe_schemes.csv"
ET_MASTER = DATA / "fund_master_auto.csv"
SCHEME_MAP = DATA / "fund_scheme_map.csv"
MATCH_REPORT = REPORTS / "et_mfapi_match_report.csv"
DEFAULT_OUT = REPORTS / "et_mfapi_full_audit.csv"

OUT_COLUMNS = [
    "MFAPI Fund Name",
    "MFAPI Fund Name Cleaned",
    "ET Fund Name",
    "Fund Category",
]


def _load_mf_universe() -> pd.DataFrame:
    mf = pd.read_csv(MF_UNIVERSE)
    rows: list[dict] = []
    for _, r in mf.iterrows():
        raw = str(r.get("scheme_name_raw") or "").strip()
        base = str(r.get("fund_name_base") or "").strip()
        base = extract_fund_name_base(raw or base) or base or raw
        display = format_display_fund_name(base or raw)
        rows.append(
            {
                "mf_scheme_code": int(r["mf_scheme_code"]),
                "scheme_name_raw": raw,
                "display_fund_name": display,
                "scheme_category": str(r.get("scheme_category") or "").strip(),
            }
        )
    return pd.DataFrame(rows)


def _load_et_master() -> pd.DataFrame:
    et = pd.read_csv(ET_MASTER)
    et = et[et["scheme_id"].notna()].copy()
    et["scheme_id"] = et["scheme_id"].astype(int)
    return et[["scheme_id", "fund_name", "category"]].rename(
        columns={"fund_name": "et_fund_name", "category": "et_category"}
    )


def _load_map() -> pd.DataFrame:
    if not SCHEME_MAP.is_file():
        return pd.DataFrame(columns=["scheme_id", "mf_scheme_code", "et_fund_name"])
    m = pd.read_csv(SCHEME_MAP)
    m["scheme_id"] = m["scheme_id"].astype(int)
    m["mf_scheme_code"] = m["mf_scheme_code"].astype(int)
    return m[["scheme_id", "mf_scheme_code", "et_fund_name"]]


def build_audit_df() -> pd.DataFrame:
    mf = _load_mf_universe()
    et = _load_et_master()
    mp = _load_map()

    et_by_sid = et.set_index("scheme_id")
    mp_by_mf = mp.set_index("mf_scheme_code") if not mp.empty else None
    mapped_mf_codes: set[int] = set()

    mf_rows: list[dict] = []
    for _, r in mf.iterrows():
        code = int(r["mf_scheme_code"])
        et_name = ""
        category = str(r["scheme_category"] or "")
        if mp_by_mf is not None and code in mp_by_mf.index:
            mapped_mf_codes.add(code)
            row = mp_by_mf.loc[code]
            sid = int(row["scheme_id"])
            et_name = str(row["et_fund_name"] or "").strip()
            if sid in et_by_sid.index:
                category = str(et_by_sid.loc[sid, "et_category"] or category).strip()
        mf_rows.append(
            {
                "MFAPI Fund Name": r["scheme_name_raw"],
                "MFAPI Fund Name Cleaned": r["display_fund_name"],
                "ET Fund Name": et_name,
                "Fund Category": category,
                "_sort_mf": r["display_fund_name"],
                "_sort_et": et_name,
            }
        )

    et_only_rows: list[dict] = []
    mapped_sids = set(mp["scheme_id"].astype(int)) if not mp.empty else set()
    for _, r in et.iterrows():
        sid = int(r["scheme_id"])
        if sid in mapped_sids:
            continue
        et_only_rows.append(
            {
                "MFAPI Fund Name": "",
                "MFAPI Fund Name Cleaned": "",
                "ET Fund Name": str(r["et_fund_name"] or "").strip(),
                "Fund Category": str(r["et_category"] or "").strip(),
                "_sort_mf": "",
                "_sort_et": str(r["et_fund_name"] or "").strip(),
            }
        )

    out = pd.DataFrame(mf_rows + et_only_rows)
    out = out.sort_values(
        by=["_sort_et", "_sort_mf"],
        ascending=[True, True],
        na_position="last",
    ).drop(columns=["_sort_mf", "_sort_et"])
    return out[OUT_COLUMNS]


def main() -> None:
    ap = argparse.ArgumentParser(description="Export ET/MFAPI full audit CSV")
    ap.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    out_path: Path = args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = build_audit_df()
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    n_mf = (df["MFAPI Fund Name"].astype(str).str.len() > 0).sum()
    n_et = (df["ET Fund Name"].astype(str).str.len() > 0).sum()
    n_both = (
        (df["MFAPI Fund Name"].astype(str).str.len() > 0)
        & (df["ET Fund Name"].astype(str).str.len() > 0)
    ).sum()
    print(f"Wrote {len(df)} rows -> {out_path}")
    print(f"  MFAPI rows: {n_mf}  |  ET rows: {n_et}  |  Both populated: {n_both}")
    print(f"  MFAPI-only: {n_mf - n_both}  |  ET-only: {n_et - n_both}")


if __name__ == "__main__":
    main()
