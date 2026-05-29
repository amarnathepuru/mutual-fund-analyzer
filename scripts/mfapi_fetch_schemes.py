"""
Batch 1: Fetch MFApi scheme list, parse plan/option separately, export Direct-Growth universe.

Does not modify fund_master_auto.csv, app.py, or any UI.

Usage (from repo root):
  python scripts/mfapi_fetch_schemes.py
  python scripts/mfapi_fetch_schemes.py --refresh   # re-download list from MFApi
  python scripts/mfapi_fetch_schemes.py --no-fetch  # parse existing raw JSON only
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW_MFAPI = DATA / "raw" / "mfapi"
REPORTS = DATA / "reports"
BACKUPS = DATA / "backups"

MFAPI_LIST_URL = "https://api.mfapi.in/mf"
USER_AGENT = "FundLens/1.0 (mutual-fund-analyzer; batch1)"

# Import sibling module
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mfapi_scheme_name import parse_scheme_name  # noqa: E402


def _ensure_dirs() -> None:
    for d in (RAW_MFAPI, REPORTS, BACKUPS):
        d.mkdir(parents=True, exist_ok=True)


def _fetch_list_json() -> list[dict]:
    import urllib.request

    req = urllib.request.Request(MFAPI_LIST_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected list from MFApi, got {type(payload)}")
    return payload


def _raw_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return RAW_MFAPI / f"mf_scheme_list_{stamp}.json"


def _latest_raw_json() -> Path | None:
    files = sorted(RAW_MFAPI.glob("mf_scheme_list_*.json"), reverse=True)
    return files[0] if files else None


def _row_from_list_item(item: dict) -> dict:
    code = item.get("schemeCode")
    raw_name = item.get("schemeName") or ""
    parsed = parse_scheme_name(str(raw_name))
    isin_g = item.get("isinGrowth")
    isin_d = item.get("isinDivReinvestment")
    return {
        "mf_scheme_code": int(code) if code is not None else None,
        "scheme_name_raw": parsed["scheme_name_raw"],
        "fund_name_base": parsed["fund_name_base"],
        "fund_name_match_key": parsed["fund_name_match_key"],
        "plan_type": parsed["plan_type"],
        "option_type": parsed["option_type"],
        "is_direct_growth": bool(parsed["is_direct_growth"]),
        "isin_growth": (isin_g or "").strip() or None,
        "isin_div_reinvestment": (isin_d or "").strip() or None,
    }


def _write_field_inventory(path: Path, sample_list: dict, sample_detail: dict | None) -> None:
    lines = [
        "# MFApi field inventory (Batch 1)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## List endpoint `GET https://api.mfapi.in/mf`",
        "",
        "Array of objects. Observed keys:",
        "",
    ]
    if sample_list:
        for k, v in sample_list.items():
            lines.append(f"- `{k}` — example: `{repr(v)[:120]}`")
    lines.extend(
        [
            "",
            "## Detail endpoint `GET https://api.mfapi.in/mf/{schemeCode}`",
            "",
            "Top-level: `meta` (object), `data` (array of `[date, nav, ...]` NAV rows).",
            "",
            "### `meta` keys (from sample fetch)",
            "",
        ]
    )
    if sample_detail:
        for k, v in sample_detail.items():
            lines.append(f"- `{k}` — example: `{repr(v)[:120]}`")
    else:
        lines.append("- (detail sample not fetched in this run)")
    lines.extend(
        [
            "",
            "## Parsed columns (FundLens; not from API)",
            "",
            "- `fund_name_base` — scheme name with plan/option suffixes removed (for ET match)",
            "- `fund_name_match_key` — normalized key for fuzzy matching",
            "- `plan_type` — `Direct`, `Regular`, or empty",
            "- `option_type` — `Growth`, `IDCW`, `DividendReinvest`, `Bonus`, or empty",
            "- `is_direct_growth` — filter flag for NAV universe",
            "",
            "## Notes",
            "",
            "- ET fund names typically omit Direct/Growth; use `fund_name_base` for matching.",
            "- Direct-Growth ISIN: prefer `isin_growth` from list endpoint when present.",
            "- NAV history: detail `data` array (Batch 2).",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _fetch_detail_meta(scheme_code: int) -> dict | None:
    import urllib.request

    url = f"https://api.mfapi.in/mf/{scheme_code}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        meta = body.get("meta")
        return meta if isinstance(meta, dict) else None
    except Exception:
        return None


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="MFApi Batch 1: scheme list + Direct-Growth parse")
    parser.add_argument("--refresh", action="store_true", help="Force download even if raw JSON exists")
    parser.add_argument("--no-fetch", action="store_true", help="Only parse latest raw JSON on disk")
    args = parser.parse_args()

    _ensure_dirs()

    raw_file: Path | None = None
    if args.no_fetch:
        raw_file = _latest_raw_json()
        if raw_file is None:
            print("FAIL: No raw JSON in data/raw/mfapi/. Run without --no-fetch first.")
            return 1
        print(f"Using cached: {raw_file}")
        items = json.loads(raw_file.read_text(encoding="utf-8"))
    else:
        latest = _latest_raw_json()
        if args.refresh or latest is None:
            print("Fetching scheme list from MFApi (may take ~10s)...")
            items = _fetch_list_json()
            raw_file = _raw_path()
            raw_file.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
            print(f"Saved raw JSON: {raw_file} ({len(items)} schemes)")
        else:
            raw_file = latest
            print(f"Using existing raw JSON: {raw_file} (use --refresh to re-download)")
            items = json.loads(raw_file.read_text(encoding="utf-8"))

    print(f"Parsing {len(items)} schemes...")
    rows = [_row_from_list_item(x) for x in items]
    all_df = pd.DataFrame(rows)

    out_all = RAW_MFAPI / "all_schemes_parsed.csv"
    all_df.to_csv(out_all, index=False, encoding="utf-8")

    dg_df = all_df[all_df["is_direct_growth"]].copy()
    out_dg = RAW_MFAPI / "direct_growth_schemes.csv"
    dg_df.to_csv(out_dg, index=False, encoding="utf-8")

    # QC report
    qc_lines = [
        "MFApi Batch 1 — parse QC",
        f"Total schemes: {len(all_df)}",
        f"Direct-Growth: {len(dg_df)}",
        f"With isin_growth (DG): {dg_df['isin_growth'].notna().sum()}",
        "",
        "Plan type counts (all schemes):",
        all_df["plan_type"].value_counts(dropna=False).to_string(),
        "",
        "Option type counts (all schemes):",
        all_df["option_type"].value_counts(dropna=False).to_string(),
        "",
        "Direct-Growth samples (fund_name_base):",
    ]
    for name in dg_df["fund_name_base"].head(12):
        qc_lines.append(f"  - {name}")
    qc_path = REPORTS / "mfapi_batch1_qc.txt"
    qc_path.write_text("\n".join(qc_lines), encoding="utf-8")

    # Ambiguous: flagged DG but empty base or very short base
    ambiguous = dg_df[dg_df["fund_name_base"].str.len() < 8]
    if len(ambiguous):
        amb_path = REPORTS / "mfapi_direct_growth_ambiguous_base.csv"
        ambiguous.to_csv(amb_path, index=False)
        qc_lines.append(f"\nWARN: {len(ambiguous)} DG rows with short fund_name_base → {amb_path}")

    # Field inventory
    sample_list = items[0] if items else {}
    sample_detail = None
    if dg_df["mf_scheme_code"].notna().any():
        code = int(dg_df.iloc[0]["mf_scheme_code"])
        print(f"Fetching detail meta sample for scheme {code}...")
        sample_detail = _fetch_detail_meta(code)
    inv_path = RAW_MFAPI / "MFAPI_FIELD_INVENTORY.md"
    _write_field_inventory(inv_path, sample_list, sample_detail)

    print()
    print("=" * 60)
    print("BATCH 1 COMPLETE")
    print("=" * 60)
    print(f"  All parsed:        {out_all}")
    print(f"  Direct-Growth:     {out_dg}  ({len(dg_df)} rows)")
    print(f"  QC report:         {qc_path}")
    print(f"  Field inventory:   {inv_path}")
    if raw_file:
        print(f"  Raw JSON:          {raw_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
