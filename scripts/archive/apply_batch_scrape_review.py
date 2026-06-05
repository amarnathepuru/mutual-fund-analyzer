"""
Rebuild batch-scrape review decisions from progress CSV and apply to fund_scheme_map.

Use when Streamlit save did not persist. Excludes funds with name_match below threshold
(default 70%) as likely wrong scrapes — tune with --no-link-codes or --match-threshold.

  python scripts/apply_batch_scrape_review.py --dry-run
  python scripts/apply_batch_scrape_review.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mfapi_et_decisions import DECISIONS_CSV, load_decisions, save_decisions, upsert_decision  # noqa: E402
from mfapi_scheme_name import fund_name_match_score, mf_fund_name_cleaned  # noqa: E402

PROGRESS_CSV = ROOT / "data/reports/mfapi_et_scrape_batch_progress.csv"
MANUAL_CUTOFF = "2026-06-01T12:00:00"


def load_batch_ok() -> pd.DataFrame:
    prog = pd.read_csv(PROGRESS_CSV, encoding="utf-8-sig")
    ok = prog[prog["status"].astype(str).str.lower() == "ok"].copy()
    ok = ok[ok["scraped_at"].astype(str) < MANUAL_CUTOFF]
    ok["mf_scheme_code"] = ok["mf_scheme_code"].astype(int)
    ok["scheme_id"] = pd.to_numeric(ok["et_scheme_id"], errors="coerce").astype("Int64")
    ok["mfapi_cleaned"] = ok["mfapi_name_cleaned"].fillna("").astype(str).apply(mf_fund_name_cleaned)
    ok["name_match_pct"] = ok.apply(
        lambda r: round(fund_name_match_score(str(r["mfapi_cleaned"]), str(r["et_fund_name"])), 1),
        axis=1,
    )
    return ok.sort_values("name_match_pct").reset_index(drop=True)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--match-threshold",
        type=float,
        default=70.0,
        help="Auto no-link if name match %% below this (default 70)",
    )
    parser.add_argument(
        "--no-link-codes",
        type=str,
        default="",
        help="Comma-separated mf_scheme_code to exclude (overrides threshold)",
    )
    parser.add_argument("--list-low-match", action="store_true", help="Print low-match funds and exit")
    args = parser.parse_args()

    batch = load_batch_ok()
    print(f"Batch OK funds: {len(batch)}")

    explicit_no_link: set[int] = set()
    if args.no_link_codes.strip():
        for part in args.no_link_codes.split(","):
            part = part.strip()
            if part:
                explicit_no_link.add(int(part))

    if args.list_low_match:
        print("\nLowest name match (review for no-link):")
        for _, r in batch.head(15).iterrows():
            print(
                f"  {int(r.mf_scheme_code):6d}  {r.name_match_pct:5.1f}%  "
                f"{str(r.mfapi_cleaned)[:40]:40} -> {str(r.et_fund_name)[:40]}"
            )
        below = batch[batch["name_match_pct"] < args.match_threshold]
        print(f"\nBelow {args.match_threshold}%: {len(below)} funds")
        return 0

    no_link: set[int] = set(explicit_no_link)
    if not explicit_no_link:
        no_link = set(batch.loc[batch["name_match_pct"] < args.match_threshold, "mf_scheme_code"].astype(int))

    decisions = load_decisions()
    approved = rejected = 0

    for _, r in batch.iterrows():
        code = int(r["mf_scheme_code"])
        mf_name = str(r.get("mfapi_name_cleaned") or r["mfapi_cleaned"])
        if code in no_link:
            decisions = upsert_decision(
                decisions,
                mf_scheme_code=code,
                decision="rejected",
                scheme_id=None,
                computed_score=None,
                mf_scheme_name=mf_name,
                et_fund_name="",
                notes="batch_scrape_review no link (rebuilt)",
            )
            rejected += 1
            continue

        sid = int(r["scheme_id"]) if pd.notna(r["scheme_id"]) else 0
        if sid <= 0:
            print(f"SKIP {code}: missing et_scheme_id")
            continue
        decisions = upsert_decision(
            decisions,
            mf_scheme_code=code,
            decision="approved",
            scheme_id=sid,
            computed_score=100.0,
            mf_scheme_name=mf_name,
            et_fund_name=str(r["et_fund_name"] or ""),
            notes="batch_scrape_review accept (rebuilt)",
        )
        approved += 1

    print(f"Decisions: approved={approved}, no_link={rejected}")
    if no_link:
        print("No-link mf_scheme_codes:", sorted(no_link))

    if args.dry_run:
        print("(dry-run — decisions and map not written)")
        return 0

    save_decisions(decisions)
    print(f"Wrote {DECISIONS_CSV}")

    from apply_mfapi_et_map import main as apply_main

    sys.argv = ["apply_mfapi_et_map.py"]
    return apply_main()


if __name__ == "__main__":
    raise SystemExit(main())
