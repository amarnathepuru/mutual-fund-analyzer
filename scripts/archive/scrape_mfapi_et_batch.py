"""
Batch scrape MFAPI Direct-Growth funds missing from fund_scheme_map.

Scrapes ET master + holdings only (no fund_scheme_map writes — map after review).

  python scripts/scrape_mfapi_et_batch.py --dry-run --limit 5
  python scripts/scrape_mfapi_et_batch.py --resume
  python scripts/scrape_mfapi_et_batch.py --delay 2.5

Progress: data/reports/mfapi_et_scrape_batch_progress.csv
"""
from __future__ import annotations

import argparse
import csv
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
    MF_UNIVERSE,
    REPORTS,
    all_batch_listing_paths,
    clear_listing_cache,
    load_mfapi_row,
    load_unmapped_mf_codes,
    prefetch_listings,
    run_one_fund_scrape,
)
from mfapi_scheme_name import mf_fund_name_cleaned  # noqa: E402

PROGRESS_CSV = REPORTS / "mfapi_et_scrape_batch_progress.csv"
SUMMARY_TXT = REPORTS / "mfapi_et_scrape_batch_summary.txt"

PROGRESS_COLS = [
    "mf_scheme_code",
    "mfapi_name_cleaned",
    "mf_category",
    "status",
    "et_scheme_id",
    "et_fund_name",
    "match_score",
    "holdings_rows",
    "et_master_status",
    "error",
    "scraped_at",
]


def _sanitize_progress_row(row: dict) -> dict:
    out = {c: row.get(c, "") for c in PROGRESS_COLS}
    err = str(out.get("error") or "")
    out["error"] = err.replace(",", ";").replace("\n", " ").strip()[:500]
    return out


def _load_progress() -> pd.DataFrame:
    if not PROGRESS_CSV.is_file():
        return pd.DataFrame(columns=PROGRESS_COLS)
    try:
        df = pd.read_csv(PROGRESS_CSV, encoding="utf-8-sig")
    except pd.errors.ParserError:
        df = pd.read_csv(
            PROGRESS_CSV,
            encoding="utf-8-sig",
            engine="python",
            on_bad_lines="skip",
        )
    for c in PROGRESS_COLS:
        if c not in df.columns:
            df[c] = ""
    return df[PROGRESS_COLS]


def _append_progress(row: dict) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    row = _sanitize_progress_row(row)
    df = _load_progress()
    code = int(row["mf_scheme_code"])
    df = df[df["mf_scheme_code"].astype(int) != code]
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    tmp = PROGRESS_CSV.with_suffix(".csv.tmp")
    df.to_csv(
        tmp,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_NONNUMERIC,
    )
    tmp.replace(PROGRESS_CSV)


def _done_codes(progress: pd.DataFrame) -> set[int]:
    if progress.empty:
        return set()
    ok = progress[progress["status"].astype(str).str.lower() == "ok"]
    return set(ok["mf_scheme_code"].astype(int).tolist())


def _write_summary(
    *,
    total: int,
    ok: int,
    failed: int,
    skipped: int,
    started: str,
    finished: str,
) -> None:
    lines = [
        "MFAPI → ET batch scrape",
        f"Started:  {started}",
        f"Finished: {finished}",
        "",
        f"Queue total:     {total}",
        f"Skipped (done):  {skipped}",
        f"OK this run:     {ok}",
        f"Failed this run: {failed}",
        "",
        f"Progress CSV: {PROGRESS_CSV}",
        "Next: python scripts/match_mfapi_et.py  (regenerate candidates)",
        "      streamlit run scripts/review_mfapi_et_app.py",
    ]
    SUMMARY_TXT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Batch scrape unmapped MFAPI→ET funds")
    parser.add_argument("--limit", type=int, default=0, help="Max funds this run (0 = all)")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between funds")
    parser.add_argument("--dry-run", action="store_true", help="Resolve ET only")
    parser.add_argument("--skip-holdings", action="store_true")
    parser.add_argument("--no-resume", action="store_true", help="Re-scrape even if status=ok")
    parser.add_argument("--no-prefetch", action="store_true", help="Skip listing pre-warm")
    parser.add_argument(
        "--mf-code",
        type=int,
        action="append",
        dest="mf_codes",
        help="Only these MFAPI codes (repeatable)",
    )
    args = parser.parse_args()

    if args.mf_codes:
        queue = [int(c) for c in args.mf_codes]
    else:
        queue = load_unmapped_mf_codes()

    progress = _load_progress()
    done = set() if args.no_resume else _done_codes(progress)
    queue = [c for c in queue if c not in done]

    if args.limit and args.limit > 0:
        queue = queue[: int(args.limit)]

    if not queue:
        print("Nothing to scrape (queue empty or all done).")
        return 0

    nav = pd.read_csv(MF_UNIVERSE)
    nav_idx = nav.set_index(nav["mf_scheme_code"].astype(int))

    started = datetime.now(timezone.utc).isoformat()
    print(f"Batch scrape: {len(queue)} fund(s) | dry_run={args.dry_run} | resume={not args.no_resume}")

    if not args.no_prefetch:
        paths, label_by_path = all_batch_listing_paths()
        print(f"Prefetching {len(paths)} ET listing page(s)…")
        clear_listing_cache()
        n = prefetch_listings(paths, label_by_path=label_by_path)
        print(f"  fetched {n} listing page(s), cache size {len(paths)}")

    ok_n = 0
    fail_n = 0
    t0 = time.perf_counter()

    for i, code in enumerate(queue, 1):
        row = nav_idx.loc[code] if code in nav_idx.index else load_mfapi_row(code)
        cleaned = mf_fund_name_cleaned(str(row.get("scheme_name_raw") or ""))
        cat = str(row.get("scheme_category") or "")
        print(f"\n[{i}/{len(queue)}] MFAPI {code} — {cleaned}")

        rec = {
            "mf_scheme_code": code,
            "mfapi_name_cleaned": cleaned,
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

        try:
            result = run_one_fund_scrape(
                code,
                dry_run=args.dry_run,
                skip_holdings=args.skip_holdings,
                skip_map=True,
            )
            et = result["et_lookup"]
            master = result["et_master"]
            rec["status"] = "ok"
            rec["et_scheme_id"] = int(et["scheme_id"])
            rec["et_fund_name"] = str(et.get("et_fund_name") or master.get("fund_name") or "")
            rec["match_score"] = et.get("match_score", "")
            rec["holdings_rows"] = result.get("holdings_rows", "")
            rec["et_master_status"] = master.get("status", "")
            ok_n += 1
            print(
                f"  OK → ET {rec['et_scheme_id']} {rec['et_fund_name']} "
                f"({rec['match_score']}%) holdings={rec['holdings_rows']}"
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

    elapsed = time.perf_counter() - t0
    finished = datetime.now(timezone.utc).isoformat()
    _write_summary(
        total=len(queue) + len(done),
        ok=ok_n,
        failed=fail_n,
        skipped=len(done),
        started=started,
        finished=finished,
    )
    print(f"\nDone in {elapsed / 60:.1f} min — OK {ok_n}, failed {fail_n}")
    print(f"Progress: {PROGRESS_CSV}")
    print(f"Summary:  {SUMMARY_TXT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
