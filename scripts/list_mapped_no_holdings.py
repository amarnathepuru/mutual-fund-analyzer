"""List ET-mapped funds with zero rows in master_holdings.csv."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MAP = DATA / "fund_scheme_map.csv"
HOLDINGS = DATA / "processed" / "master_holdings.csv"
MASTER = DATA / "fund_master_auto.csv"
NAV = DATA / "raw/mfapi/nav_universe_schemes.csv"
OUT = DATA / "reports" / "mapped_no_holdings.csv"


def main() -> None:
    mapped = pd.read_csv(MAP)
    hold = pd.read_csv(HOLDINGS)
    master = pd.read_csv(MASTER)

    et_with_hold = set(hold["scheme_id"].astype(int).unique())
    mapped["scheme_id"] = mapped["scheme_id"].astype(int)
    no_hold = mapped[~mapped["scheme_id"].isin(et_with_hold)].copy()

    master["scheme_id"] = master["scheme_id"].astype(int)
    no_hold = no_hold.merge(
        master[["scheme_id", "fund_name", "status", "url"]],
        on="scheme_id",
        how="left",
    )

    nav = pd.read_csv(NAV)
    code_col = "scheme_code" if "scheme_code" in nav.columns else "mf_scheme_code"
    nav = nav.rename(columns={code_col: "mf_scheme_code"})
    nav["mf_scheme_code"] = nav["mf_scheme_code"].astype(int)
    name_col = next(
        c
        for c in (
            "fund_name_base",
            "scheme_name_raw",
            "scheme_name",
            "fund_name_cleaned",
            "fund_name",
            "name",
        )
        if c in nav.columns
    )
    no_hold["mf_scheme_code"] = no_hold["mf_scheme_code"].astype(int)
    no_hold = no_hold.merge(
        nav[["mf_scheme_code", name_col]].rename(columns={name_col: "mfapi_name"}),
        on="mf_scheme_code",
        how="left",
    )

    if "et_fund_name" in no_hold.columns:
        no_hold["display_name"] = (
            no_hold["et_fund_name"]
            .astype(str)
            .where(no_hold["et_fund_name"].notna(), no_hold.get("mfapi_name"))
        )
    else:
        no_hold["display_name"] = no_hold.get("mfapi_name", no_hold.get("fund_name"))

    cols = [
        "mf_scheme_code",
        "scheme_id",
        "display_name",
        "mfapi_name",
        "et_fund_name",
        "fund_name",
        "status",
        "match_method",
        "match_score",
        "notes",
        "url",
    ]
    no_hold = no_hold[[c for c in cols if c in no_hold.columns]].sort_values(
        ["fund_name", "mf_scheme_code"]
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    no_hold.to_csv(OUT, index=False)

    n_map = len(mapped)
    n_no = len(no_hold)
    print(f"Mapped total: {n_map}")
    print(f"With holdings: {n_map - n_no}")
    print(f"Mapped, no holdings: {n_no}")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    if "status" in no_hold.columns:
        print("\nET master status:")
        print(no_hold["status"].value_counts().to_string())
    print("\n--- Full list (mf_code | ET id | name) ---")
    for _, r in no_hold.iterrows():
        name = str(r.get("display_name") or r.get("et_fund_name") or r.get("mfapi_name") or "")
        print(f"{int(r['mf_scheme_code']):6d}  ET {int(r['scheme_id']):5d}  {name[:72]}")


if __name__ == "__main__":
    main()
