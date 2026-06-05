"""
Import manual MFAPI→ET link CSV, scrape master+holdings, write fund_scheme_map.

CSV columns: mf_scheme_code, mfapi_name_cleaned, ET Link, mf_category
Blank ET Link = intentionally unmapped (no scrape).

  python scripts/scrape_mfapi_et_manual_links.py
  python scripts/scrape_mfapi_et_manual_links.py --csv data/reports/mfapi_et_manual_links.csv
  python scripts/scrape_mfapi_et_manual_links.py --dry-run --limit 5
  python scripts/scrape_mfapi_et_manual_links.py --delay 2 --force
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from et_mfapi_scrape_lib import (  # noqa: E402
    REPORTS,
    SCRAPE_HINTS,
    clear_scrape_hints_cache,
    load_mfapi_row,
    run_one_fund_scrape,
)
from mfapi_scheme_name import mf_fund_name_cleaned  # noqa: E402
from scrape_mfapi_et_batch import (  # noqa: E402
    PROGRESS_COLS,
    PROGRESS_CSV,
    _append_progress,
    _done_codes,
    _load_progress,
)

DEFAULT_CSV = REPORTS / "mfapi_et_manual_links.csv"
UNMAPPED_CSV = REPORTS / "mfapi_et_manual_unmapped.csv"
SUMMARY_TXT = REPORTS / "mfapi_et_manual_scrape_summary.txt"

ET_URL_RE = re.compile(
    r"etmoney\.com/mutual-funds/([a-z0-9\-]+)(?:/portfolio-details)?/(\d+)",
    re.IGNORECASE,
)


def parse_et_link(url: str) -> tuple[str, int] | None:
    m = ET_URL_RE.search(str(url or "").strip())
    if not m:
        return None
    slug = m.group(1)
    if slug == "portfolio-details":
        return None
    return slug, int(m.group(2))


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for c in df.columns:
        cl = str(c).strip().lower()
        if cl == "et link":
            rename[c] = "et_link"
        elif cl == "mf_scheme_code":
            rename[c] = "mf_scheme_code"
        elif cl == "mfapi_name_cleaned":
            rename[c] = "mfapi_name_cleaned"
        elif cl == "mf_category":
            rename[c] = "mf_category"
    return df.rename(columns=rename)


def load_manual_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    df = _normalize_columns(df)
    for col in ("mf_scheme_code", "mfapi_name_cleaned", "et_link", "mf_category"):
        if col not in df.columns:
            df[col] = ""
    df["mf_scheme_code"] = df["mf_scheme_code"].astype(int)
    df["et_link"] = df["et_link"].fillna("").astype(str).str.strip()
    return df


def write_hints(mapped: pd.DataFrame) -> int:
    rows = []
    for _, r in mapped.iterrows():
        parsed = parse_et_link(r["et_link"])
        if not parsed:
            continue
        slug, sid = parsed
        rows.append(
            {
                "mf_scheme_code": int(r["mf_scheme_code"]),
                "et_slug": slug,
                "et_scheme_id": int(sid),
                "et_fund_name": "",
                "notes": "manual_et_link",
            }
        )
    if not rows:
        return 0
    hints = pd.DataFrame(rows)
    if SCRAPE_HINTS.is_file():
        prev = pd.read_csv(SCRAPE_HINTS, encoding="utf-8-sig")
        hints = (
            pd.concat([prev, hints], ignore_index=True)
            .drop_duplicates(subset=["mf_scheme_code"], keep="last")
            .sort_values("mf_scheme_code")
        )
    hints.to_csv(SCRAPE_HINTS, index=False, encoding="utf-8-sig")
    clear_scrape_hints_cache()
    return len(rows)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Scrape manual MFAPI→ET link mappings")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Re-scrape even if batch progress=ok")
    parser.add_argument("--skip-holdings", action="store_true")
    args = parser.parse_args()

    if not args.csv.is_file():
        print(f"Missing {args.csv}")
        return 1

    df = load_manual_csv(args.csv)
    has_link = df["et_link"].str.contains("etmoney.com", case=False, na=False)
    mapped = df[has_link].copy()
    unmapped = df[~has_link].copy()

    REPORTS.mkdir(parents=True, exist_ok=True)
    mapped.to_csv(args.csv, index=False, encoding="utf-8-sig")
    unmapped[
        ["mf_scheme_code", "mfapi_name_cleaned", "mf_category"]
    ].to_csv(UNMAPPED_CSV, index=False, encoding="utf-8-sig")

    n_hints = write_hints(mapped)
    print(f"Manual links CSV: {len(df)} rows")
    print(f"  Mapped (ET link):   {len(mapped)}")
    print(f"  Unmapped (no link): {len(unmapped)} -> {UNMAPPED_CSV}")
    print(f"  Hints written:      {n_hints} -> {SCRAPE_HINTS}")

    progress = _load_progress()
    done = set() if args.force else _done_codes(progress)
    queue = [int(c) for c in mapped["mf_scheme_code"] if int(c) not in done]
    if args.limit and args.limit > 0:
        queue = queue[: int(args.limit)]

    if not queue:
        print("Nothing to scrape (all mapped codes already ok in progress CSV).")
        return 0

    started = datetime.now(timezone.utc).isoformat()
    print(f"\nScraping {len(queue)} fund(s) | dry_run={args.dry_run} | delay={args.delay}s")

    ok_n = 0
    fail_n = 0
    link_by_code = mapped.set_index(mapped["mf_scheme_code"].astype(int))["et_link"].to_dict()

    for i, code in enumerate(queue, 1):
        row = mapped[mapped["mf_scheme_code"].astype(int) == code].iloc[0]
        name = str(row.get("mfapi_name_cleaned") or "")
        cat = str(row.get("mf_category") or "")
        et_url = str(link_by_code.get(code) or "")
        parsed = parse_et_link(et_url)
        print(f"\n[{i}/{len(queue)}] MFAPI {code} — {name}")

        rec = {
            "mf_scheme_code": code,
            "mfapi_name_cleaned": name,
            "mf_category": cat,
            "status": "error",
            "et_scheme_id": "",
            "et_fund_name": "",
            "match_score": "",
            "holdings_rows": "",
            "et_master_status": "",
            "error": "",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

        if not parsed:
            rec["status"] = "lookup_failed"
            rec["error"] = f"Bad ET link: {et_url[:120]}"
            fail_n += 1
            print(f"  FAIL: {rec['error']}")
            if not args.dry_run:
                _append_progress(rec)
            continue

        slug, sid = parsed
        try:
            mf_row = load_mfapi_row(code)
            mf_cleaned = mf_fund_name_cleaned(str(mf_row.get("scheme_name_raw") or name))
            result = run_one_fund_scrape(
                code,
                dry_run=args.dry_run,
                skip_holdings=args.skip_holdings,
                skip_map=args.dry_run,
                match_method="manual_et_link",
                map_notes=f"manual ET link {et_url[:100]}",
            )
            et = result["et_lookup"]
            master = result["et_master"]
            rec["status"] = "ok"
            rec["et_scheme_id"] = int(et["scheme_id"])
            rec["et_fund_name"] = str(et.get("et_fund_name") or master.get("fund_name") or "")
            rec["match_score"] = et.get("match_score", 100.0)
            rec["holdings_rows"] = result.get("holdings_rows", "")
            rec["et_master_status"] = master.get("status", "")
            ok_n += 1
            print(
                f"  OK → {slug}/{sid} | {rec['et_fund_name']} | "
                f"holdings={rec['holdings_rows']} | map updated"
            )
        except Exception as exc:
            rec["status"] = "lookup_failed" if isinstance(exc, LookupError) else "error"
            rec["error"] = str(exc)[:500]
            fail_n += 1
            print(f"  FAIL: {rec['error']}")
            if not isinstance(exc, LookupError):
                traceback.print_exc()

        if not args.dry_run:
            _append_progress(rec)

        if i < len(queue) and args.delay > 0:
            time.sleep(args.delay)

    finished = datetime.now(timezone.utc).isoformat()
    lines = [
        "Manual MFAPI→ET link scrape",
        f"Started:  {started}",
        f"Finished: {finished}",
        f"Mapped in CSV:     {len(mapped)}",
        f"Unmapped in CSV:   {len(unmapped)}",
        f"Scraped this run:  {len(queue)}",
        f"OK:                {ok_n}",
        f"Failed:            {fail_n}",
        f"Progress: {PROGRESS_CSV}",
        f"Unmapped list: {UNMAPPED_CSV}",
    ]
    SUMMARY_TXT.write_text("\n".join(lines), encoding="utf-8")
    print("\n" + "\n".join(lines))
    return 0 if fail_n == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
