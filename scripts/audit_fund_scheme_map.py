"""
Audit fund_scheme_map.csv for duplicates, mismatches, and missed MFAPI funds.

Writes data/reports/fund_scheme_map_audit.csv

  python scripts/audit_fund_scheme_map.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mfapi_scheme_name import fund_name_match_score, mf_fund_name_cleaned  # noqa: E402

DATA = ROOT / "data"
MAP = DATA / "fund_scheme_map.csv"
ET_MASTER = DATA / "fund_master_auto.csv"
HOLDINGS = DATA / "processed" / "master_holdings.csv"
MF_UNIVERSE = DATA / "raw" / "mfapi" / "nav_universe_schemes.csv"
DIRECT_GROWTH = DATA / "raw" / "mfapi" / "direct_growth_schemes.csv"
DECISIONS = DATA / "mfapi_et_decisions.csv"
BATCH_PROGRESS = DATA / "reports" / "mfapi_et_scrape_batch_progress.csv"
MATCH_REPORT = DATA / "reports" / "et_mfapi_match_report.csv"
OUT = DATA / "reports" / "fund_scheme_map_audit.csv"
REVIEW_OUT = DATA / "reports" / "fund_scheme_map_audit_review.csv"

# Known batch no-link (L&T wrong AMC scrape)
BATCH_NO_LINK = {119298, 119308, 119347, 119397, 119413, 119807, 130450, 130825}

_HOUSE_ALIASES = {
    "l&t": "larsentoubro",
    "larsen": "larsentoubro",
    "icici": "iciciprudential",
    "iciciprudential": "iciciprudential",
    "hdfc": "hdfc",
    "sbi": "sbi",
    "uti": "uti",
    "kotak": "kotak",
    "axis": "axis",
    "dsp": "dsp",
    "nippon": "nippon",
    "franklin": "franklintempleton",
    "baroda": "barodabnpparibas",
    "bnp": "barodabnpparibas",
    "paribas": "barodabnpparibas",
    "hsbc": "hsbc",
    "quant": "quant",
    "pgim": "pgim",
    "iti": "iti",
}


def _house_key(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "", str(name or "").lower())
    if not s:
        return ""
    for prefix, key in sorted(_HOUSE_ALIASES.items(), key=lambda x: -len(x[0])):
        if s.startswith(prefix) or prefix in s[:12]:
            return key
    return s[:12]


def _first_house(name: str) -> str:
    tok = str(name or "").strip().split()
    return _house_key(tok[0] if tok else "")


def _load_map() -> pd.DataFrame:
    m = pd.read_csv(MAP)
    m["mf_scheme_code"] = pd.to_numeric(m["mf_scheme_code"], errors="coerce")
    m["scheme_id"] = pd.to_numeric(m["scheme_id"], errors="coerce")
    return m


def _mf_names(*, nav_universe_only: bool = False) -> dict[int, str]:
    names: dict[int, str] = {}
    paths = [MF_UNIVERSE] if nav_universe_only else [MF_UNIVERSE, DIRECT_GROWTH]
    for path in paths:
        if not path.is_file():
            continue
        df = pd.read_csv(path)
        code_col = "mf_scheme_code" if "mf_scheme_code" in df.columns else "scheme_code"
        name_col = "scheme_name" if "scheme_name" in df.columns else "scheme_name_raw"
        for _, r in df.iterrows():
            try:
                c = int(r[code_col])
            except (TypeError, ValueError):
                continue
            raw = str(r.get(name_col) or r.get("scheme_name_raw") or "")
            names[c] = mf_fund_name_cleaned(raw) or raw
    return names


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    issues: list[dict] = []

    if not MAP.is_file():
        print(f"Missing {MAP}")
        return 1

    m = _load_map()
    mf_names = _mf_names()
    nav_names = _mf_names(nav_universe_only=True)
    et_master = pd.read_csv(ET_MASTER) if ET_MASTER.is_file() else pd.DataFrame()
    et_active = set()
    et_name_by_id: dict[int, str] = {}
    if not et_master.empty:
        active = et_master[et_master["status"].astype(str).str.upper() == "ACTIVE"]
        et_active = set(active["scheme_id"].astype(int))
        for _, r in active.iterrows():
            et_name_by_id[int(r["scheme_id"])] = str(r.get("fund_name") or "")

    holdings_n: dict[int, int] = {}
    if HOLDINGS.is_file():
        h = pd.read_csv(HOLDINGS)
        for sid, g in h.groupby(h["scheme_id"].astype(int)):
            holdings_n[int(sid)] = len(g)

    # --- duplicates ---
    for sid, g in m.groupby(m["scheme_id"].astype(int)):
        if pd.isna(sid):
            continue
        g = g.dropna(subset=["mf_scheme_code"])
        if len(g) > 1:
            codes = g["mf_scheme_code"].astype(int).tolist()
            issues.append(
                {
                    "severity": "error",
                    "issue_type": "duplicate_et_scheme_id",
                    "mf_scheme_code": ",".join(map(str, codes)),
                    "scheme_id": int(sid),
                    "detail": f"ET {int(sid)} mapped to {len(g)} MF codes: {codes}",
                    "mfapi_name": "",
                    "et_fund_name": str(g.iloc[0].get("et_fund_name") or ""),
                    "name_match_pct": "",
                    "notes": "",
                }
            )

    for code, g in m.groupby(m["mf_scheme_code"].astype(int)):
        if pd.isna(code):
            continue
        if len(g) > 1:
            sids = g["scheme_id"].astype(int).tolist()
            issues.append(
                {
                    "severity": "error",
                    "issue_type": "duplicate_mf_scheme_code",
                    "mf_scheme_code": int(code),
                    "scheme_id": ",".join(map(str, sids)),
                    "detail": f"MF {int(code)} has {len(g)} map rows",
                    "mfapi_name": mf_names.get(int(code), ""),
                    "et_fund_name": "",
                    "name_match_pct": "",
                    "notes": "",
                }
            )

    mapped_mf = set(m["mf_scheme_code"].dropna().astype(int))
    mapped_et = set(m["scheme_id"].dropna().astype(int))

    # --- per-row quality ---
    for _, r in m.iterrows():
        code = int(r["mf_scheme_code"])
        sid = int(r["scheme_id"])
        et_name = str(r.get("et_fund_name") or "").strip()
        if not et_name or et_name.lower() == "nan":
            et_name = et_name_by_id.get(sid, "")
        mf_name = mf_names.get(code, nav_names.get(code, ""))
        if not mf_name:
            issues.append(
                {
                    "severity": "warn",
                    "issue_type": "mf_not_in_nav_universe",
                    "mf_scheme_code": code,
                    "scheme_id": sid,
                    "detail": "MF code not in nav_universe / direct_growth CSVs",
                    "mfapi_name": "",
                    "et_fund_name": et_name,
                    "name_match_pct": "",
                    "notes": str(r.get("notes") or ""),
                }
            )
            continue

        match_pct = round(fund_name_match_score(mf_name, et_name), 1)
        mf_h = _first_house(mf_name)
        et_h = _first_house(et_name)
        if mf_h and et_h and mf_h != et_h and et_name:
            issues.append(
                {
                    "severity": "error",
                    "issue_type": "amc_house_mismatch",
                    "mf_scheme_code": code,
                    "scheme_id": sid,
                    "detail": f"House {mf_h} vs {et_h}",
                    "mfapi_name": mf_name,
                    "et_fund_name": et_name,
                    "name_match_pct": match_pct,
                    "notes": str(r.get("notes") or ""),
                }
            )
        elif match_pct < 75.0:
            issues.append(
                {
                    "severity": "warn",
                    "issue_type": "low_name_match",
                    "mf_scheme_code": code,
                    "scheme_id": sid,
                    "detail": f"Name match {match_pct}% < 75%",
                    "mfapi_name": mf_name,
                    "et_fund_name": et_name,
                    "name_match_pct": match_pct,
                    "notes": str(r.get("notes") or ""),
                }
            )

        if sid not in et_active:
            issues.append(
                {
                    "severity": "warn",
                    "issue_type": "et_not_active_in_master",
                    "mf_scheme_code": code,
                    "scheme_id": sid,
                    "detail": "ET scheme_id not ACTIVE in fund_master_auto",
                    "mfapi_name": mf_name,
                    "et_fund_name": et_name,
                    "name_match_pct": match_pct,
                    "notes": str(r.get("notes") or ""),
                }
            )

        if holdings_n.get(sid, 0) == 0:
            issues.append(
                {
                    "severity": "info",
                    "issue_type": "no_holdings_rows",
                    "mf_scheme_code": code,
                    "scheme_id": sid,
                    "detail": "No rows in master_holdings for this ET id",
                    "mfapi_name": mf_name,
                    "et_fund_name": et_name,
                    "name_match_pct": match_pct,
                    "notes": str(r.get("notes") or ""),
                }
            )

    # --- missed: NAV universe (884) not mapped ---
    universe_codes = set(nav_names.keys())
    for code in sorted(universe_codes - mapped_mf):
        name = nav_names.get(code, mf_names.get(code, ""))
        reason = "unmapped_mfapi"
        if code in BATCH_NO_LINK:
            reason = "batch_no_link_intentional"
        issues.append(
            {
                "severity": "info" if code in BATCH_NO_LINK else "warn",
                "issue_type": "missed_mapping",
                "mf_scheme_code": code,
                "scheme_id": "",
                "detail": reason,
                "mfapi_name": name,
                "et_fund_name": "",
                "name_match_pct": "",
                "notes": "",
            }
        )

    batch_ok = pd.DataFrame()
    if BATCH_PROGRESS.is_file():
        prog = pd.read_csv(BATCH_PROGRESS)
        batch_ok = prog[
            (prog["status"].astype(str).str.lower() == "ok")
            & (prog["scraped_at"].astype(str) < "2026-06-01T12:00:00")
        ]
        for _, r in batch_ok.iterrows():
            code = int(r["mf_scheme_code"])
            if code in mapped_mf:
                continue
            if code in BATCH_NO_LINK:
                continue
            issues.append(
                {
                    "severity": "error",
                    "issue_type": "batch_ok_not_in_map",
                    "mf_scheme_code": code,
                    "scheme_id": int(r["et_scheme_id"]) if pd.notna(r.get("et_scheme_id")) else "",
                    "detail": "Batch scrape OK but not in fund_scheme_map",
                    "mfapi_name": str(r.get("mfapi_name_cleaned") or mf_names.get(code, "")),
                    "et_fund_name": str(r.get("et_fund_name") or ""),
                    "name_match_pct": "",
                    "notes": "check ET conflict skip",
                }
            )

    # --- BNP conflict detail: ET mapped to different MF ---
    bnp_batch = {119893, 119988, 140386, 150264}
    for code in bnp_batch:
        if code in mapped_mf:
            continue
        if batch_ok.empty:
            continue
        pr = batch_ok[batch_ok["mf_scheme_code"].astype(int) == code]
        if not pr.empty:
            et_id = int(pr.iloc[0]["et_scheme_id"])
            owner = m[m["scheme_id"].astype(int) == et_id]
            owner_mf = int(owner.iloc[0]["mf_scheme_code"]) if not owner.empty else None
            issues.append(
                {
                    "severity": "error",
                    "issue_type": "batch_et_conflict",
                    "mf_scheme_code": code,
                    "scheme_id": et_id,
                    "detail": f"ET {et_id} already mapped to MF {owner_mf}",
                    "mfapi_name": mf_names.get(code, ""),
                    "et_fund_name": str(pr.iloc[0].get("et_fund_name") or ""),
                    "name_match_pct": "",
                    "notes": "manual merge review",
                }
            )

    df = pd.DataFrame(issues)
    if df.empty:
        print("No issues found.")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(OUT, index=False, encoding="utf-8-sig")
        return 0

    # de-dup same mf+type keeping worst severity
    sev_order = {"error": 0, "warn": 1, "info": 2}
    df["_sev"] = df["severity"].map(sev_order)
    df = df.sort_values(["_sev", "issue_type", "mf_scheme_code"]).drop(columns=["_sev"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")

    review = df[
        (df["severity"].isin(["error", "warn"]))
        & ~((df["issue_type"] == "missed_mapping") & (df["detail"] == "batch_no_link_intentional"))
    ].copy()
    REVIEW_OUT.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(REVIEW_OUT, index=False, encoding="utf-8-sig")

    print(f"Map rows: {len(m)}")
    print(f"Universe MF codes: {len(universe_codes)}")
    print(f"Mapped MF: {len(mapped_mf)}")
    print(f"Unmapped MF: {len(universe_codes - mapped_mf)}")
    print()
    print("Issues by type:")
    print(df.groupby(["severity", "issue_type"]).size().to_string())
    print(f"\nWrote {OUT} ({len(df)} rows)")
    print(f"Review queue: {REVIEW_OUT} ({len(review)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
