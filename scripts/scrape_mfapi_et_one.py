"""
Scrape one MFAPI Direct-Growth fund from ET Money (sample / validation flow).

Example — Quantum Value Fund:
  python scripts/scrape_mfapi_et_one.py --mf-code 103490
  python scripts/scrape_mfapi_et_one.py --name "Quantum Value Fund"

Writes QC to data/reports/mfapi_et_scrape_one_qc.txt
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from et_mfapi_scrape_lib import (  # noqa: E402
    REPORTS,
    load_mfapi_row,
    load_mfapi_row_by_name,
    run_one_fund_scrape,
)

QC_OUT = REPORTS / "mfapi_et_scrape_one_qc.txt"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Scrape one MFAPI→ET fund from ET Money")
    parser.add_argument("--mf-code", type=int, help="MFAPI mf_scheme_code (AMFI)")
    parser.add_argument("--name", type=str, help="MFAPI Fund Name Cleaned, e.g. 'Quantum Value Fund'")
    parser.add_argument("--dry-run", action="store_true", help="Resolve ET only; do not write CSVs")
    parser.add_argument("--skip-holdings", action="store_true")
    parser.add_argument("--skip-map", action="store_true")
    args = parser.parse_args()

    if not args.mf_code and not args.name:
        parser.error("Provide --mf-code or --name")

    if args.mf_code:
        code = int(args.mf_code)
    else:
        row = load_mfapi_row_by_name(args.name)
        code = int(row["mf_scheme_code"])

    row = load_mfapi_row(code)
    print(f"MFAPI {code}: {row.get('scheme_name_raw')}")

    result = run_one_fund_scrape(
        code,
        dry_run=args.dry_run,
        skip_holdings=args.skip_holdings,
        skip_map=args.skip_map,
    )

    et = result["et_lookup"]
    master = result["et_master"]
    lines = [
        "MFAPI → ET single-fund scrape",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"dry_run: {args.dry_run}",
        "",
        f"MFAPI code: {code}",
        f"MFAPI cleaned: {result['mfapi_name_cleaned']}",
        f"MFAPI category: {result['mf_category']}",
        "",
        "ET lookup:",
        f"  scheme_id: {et['scheme_id']}",
        f"  slug: {et['slug']}",
        f"  et_fund_name: {et['et_fund_name']}",
        f"  match_score: {et['match_score']}",
        f"  listing: {et.get('listing_path')}",
        "",
        "ET master row:",
        f"  status: {master.get('status')}",
        f"  fund_name: {master.get('fund_name')}",
        f"  portfolio: {master.get('portfolio_url')}",
        f"  holdings_rows (validation): {master.get('holdings_rows')}",
        "",
        f"Holdings scraped rows: {result['holdings_rows']}",
        "",
        "Validate: streamlit run scripts/validate_mfapi_et_scrape_app.py",
    ]
    text = "\n".join(lines)
    REPORTS.mkdir(parents=True, exist_ok=True)
    QC_OUT.write_text(text, encoding="utf-8")
    print("\n" + text)
    print(f"\nQC: {QC_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
