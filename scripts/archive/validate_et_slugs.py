"""
Validate user-supplied ET slugs / URLs against MFAPI failure rows.

Input (any of):
  - data/mfapi_et_scrape_hints.csv  (mf_scheme_code, et_slug, et_scheme_id)
  - data/reports/mfapi_et_slug_candidates.csv  (same columns; optional et_url)

Output:
  - data/reports/mfapi_et_slug_validation.csv

  python scripts/validate_et_slugs.py
  python scripts/validate_et_slugs.py --csv data/reports/my_slugs.csv
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(ROOT / "scraper") not in sys.path:
    sys.path.insert(0, str(ROOT / "scraper"))

from discover_funds import scrape_fund_detail, validate_portfolio_url  # noqa: E402
from et_mfapi_scrape_lib import SCRAPE_HINTS, load_mfapi_row  # noqa: E402
from review_mfapi_et_scrape_failures import parse_et_money_url  # noqa: E402
from mfapi_scheme_name import fund_name_match_score, mf_fund_name_cleaned  # noqa: E402

CANDIDATES = ROOT / "data" / "reports" / "mfapi_et_slug_candidates.csv"
OUT = ROOT / "data" / "reports" / "mfapi_et_slug_validation.csv"


def _read_input(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    for col in ("mf_scheme_code", "et_slug", "et_scheme_id", "et_url"):
        if col not in df.columns:
            df[col] = ""
    return df


def _row_et_ids(row: pd.Series) -> tuple[str, int] | None:
    url = str(row.get("et_url") or "").strip()
    if url:
        parsed = parse_et_money_url(url)
        if parsed:
            return parsed
    slug = str(row.get("et_slug") or "").strip()
    sid = row.get("et_scheme_id")
    if slug and pd.notna(sid) and str(sid).strip() not in ("", "nan"):
        try:
            return slug, int(float(sid))
        except (TypeError, ValueError):
            pass
    return None


def validate_one(mf_code: int, slug: str, scheme_id: int) -> dict:
    row = load_mfapi_row(mf_code)
    mf_clean = mf_fund_name_cleaned(str(row.get("scheme_name_raw") or ""))
    stub = {"slug": slug, "scheme_id": int(scheme_id), "category": "Unknown"}
    detail = scrape_fund_detail(stub)
    if not detail:
        return {
            "mf_scheme_code": mf_code,
            "mfapi_name_cleaned": mf_clean,
            "et_slug": slug,
            "et_scheme_id": scheme_id,
            "validation": "fail",
            "reason": "ET fund page not found (404 or parse error)",
            "et_fund_name": "",
            "name_match_pct": 0.0,
            "portfolio_status": "",
            "holdings_rows": 0,
        }
    et_name = str(detail.get("fund_name") or "")
    score = fund_name_match_score(mf_clean, et_name)
    time.sleep(0.6)
    status, _url, rows = validate_portfolio_url(slug, scheme_id)
    ok = score >= 85.0 and status == "ACTIVE" and rows > 0
    return {
        "mf_scheme_code": mf_code,
        "mfapi_name_cleaned": mf_clean,
        "et_slug": slug,
        "et_scheme_id": scheme_id,
        "validation": "ok" if ok else "review",
        "reason": ""
        if ok
        else (
            f"name_match={score:.1f}% portfolio={status} holdings_rows={rows}"
        ),
        "et_fund_name": et_name,
        "name_match_pct": round(score, 2),
        "portfolio_status": status,
        "holdings_rows": int(rows or 0),
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Validate ET slugs for MFAPI failures")
    parser.add_argument("--csv", type=Path, default=None, help="Input CSV (default: hints then candidates)")
    parser.add_argument("--delay", type=float, default=0.8, help="Seconds between ET requests")
    args = parser.parse_args()

    path = args.csv
    if path is None:
        if SCRAPE_HINTS.is_file():
            path = SCRAPE_HINTS
        elif CANDIDATES.is_file():
            path = CANDIDATES
        else:
            print(f"Create {CANDIDATES} with columns: mf_scheme_code, et_slug, et_scheme_id (or et_url)")
            return 1

    if not path.is_file():
        print(f"Missing {path}")
        return 1

    df = _read_input(path)
    results: list[dict] = []
    for _, r in df.iterrows():
        if pd.isna(r.get("mf_scheme_code")):
            continue
        mf_code = int(float(r["mf_scheme_code"]))
        ids = _row_et_ids(r)
        if not ids:
            results.append(
                {
                    "mf_scheme_code": mf_code,
                    "mfapi_name_cleaned": "",
                    "et_slug": "",
                    "et_scheme_id": "",
                    "validation": "skip",
                    "reason": "missing et_url or (et_slug + et_scheme_id)",
                    "et_fund_name": "",
                    "name_match_pct": 0.0,
                    "portfolio_status": "",
                    "holdings_rows": 0,
                }
            )
            continue
        slug, sid = ids
        try:
            rec = validate_one(mf_code, slug, sid)
        except Exception as exc:
            rec = {
                "mf_scheme_code": mf_code,
                "mfapi_name_cleaned": "",
                "et_slug": slug,
                "et_scheme_id": sid,
                "validation": "error",
                "reason": str(exc)[:200],
                "et_fund_name": "",
                "name_match_pct": 0.0,
                "portfolio_status": "",
                "holdings_rows": 0,
            }
        results.append(rec)
        tag = rec["validation"]
        print(
            f"[{tag}] MFAPI {mf_code} -> ET {sid} {rec.get('et_fund_name','')[:50]} "
            f"({rec.get('name_match_pct', 0)}%)"
        )
        if args.delay > 0:
            time.sleep(args.delay)

    out = pd.DataFrame(results)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"\nWrote {OUT}")
    if not out.empty:
        print(out["validation"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
