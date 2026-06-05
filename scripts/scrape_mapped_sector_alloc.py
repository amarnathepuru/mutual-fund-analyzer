"""
Scrape ET portfolio data for mapped funds with no stock holdings (43-fund cohort).

Classifies each page as stock_holdings | sector_buckets_only | mixed | empty.
Writes stock rows to master_holdings.csv and sector rows to fund_sector_allocation.csv.

  python scripts/scrape_mapped_sector_alloc.py
  python scripts/scrape_mapped_sector_alloc.py --dry-run --limit 3
  python scripts/scrape_mapped_sector_alloc.py --resume
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRAPER = ROOT / "scraper"
if str(SCRAPER) not in sys.path:
    sys.path.insert(0, str(SCRAPER))

from scrape_holdings import scrape_fund  # noqa: E402
from scrape_sector_allocation import scrape_sector_allocation_from_url  # noqa: E402

MAP = ROOT / "data" / "fund_scheme_map.csv"
QUEUE = ROOT / "data" / "reports" / "mapped_no_holdings.csv"
HOLDINGS = ROOT / "data" / "processed" / "master_holdings.csv"
SECTOR_OUT = ROOT / "data" / "processed" / "fund_sector_allocation.csv"
PROGRESS = ROOT / "data" / "reports" / "mapped_sector_scrape_progress.csv"
QC = ROOT / "data" / "reports" / "mapped_sector_scrape_qc.txt"

ET_LINK_RE = re.compile(
    r"https?://www\.etmoney\.com/mutual-funds/([a-z0-9\-]+)/(\d+)",
    re.I,
)
DELAY_SEC = 1.5


def portfolio_url_from_row(row: pd.Series) -> str:
    notes = str(row.get("notes") or "")
    et_name = str(row.get("et_fund_name") or "")
    sid = int(row["scheme_id"])
    m = ET_LINK_RE.search(notes)
    if m:
        slug = m.group(1)
    else:
        slug = re.sub(r"[^a-z0-9]+", "-", et_name.lower()).strip("-")
    return f"https://www.etmoney.com/mutual-funds/{slug}/portfolio-details/{sid}"


def load_queue() -> pd.DataFrame:
    if QUEUE.is_file():
        return pd.read_csv(QUEUE)
    mapped = pd.read_csv(MAP)
    hold = pd.read_csv(HOLDINGS)
    et_with = set(hold["scheme_id"].astype(int).unique())
    mapped["scheme_id"] = mapped["scheme_id"].astype(int)
    return mapped[~mapped["scheme_id"].isin(et_with)].copy()


def upsert_holdings(df: pd.DataFrame, scheme_id: int) -> None:
    if df.empty:
        return
    HOLDINGS.parent.mkdir(parents=True, exist_ok=True)
    if HOLDINGS.is_file():
        existing = pd.read_csv(HOLDINGS)
        existing = existing[existing["scheme_id"].astype(int) != scheme_id]
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df
    combined.drop_duplicates().to_csv(HOLDINGS, index=False)


def upsert_sector(df: pd.DataFrame, scheme_id: int) -> None:
    if df.empty:
        return
    SECTOR_OUT.parent.mkdir(parents=True, exist_ok=True)
    if SECTOR_OUT.is_file():
        existing = pd.read_csv(SECTOR_OUT)
        existing = existing[existing["scheme_id"].astype(int) != scheme_id]
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df
    combined.drop_duplicates().to_csv(SECTOR_OUT, index=False)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Skip MF codes already OK in progress CSV")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--delay", type=float, default=DELAY_SEC)
    args = parser.parse_args()

    queue = load_queue()
    if queue.empty:
        print("No mapped funds without holdings.")
        return 0

    done_codes: set[int] = set()
    progress_rows: list[dict] = []
    if args.resume and PROGRESS.is_file():
        prog = pd.read_csv(PROGRESS)
        ok = prog[prog["status"].astype(str).str.lower() == "ok"]
        done_codes = set(ok["mf_scheme_code"].astype(int))
        progress_rows = prog.to_dict("records")

    if args.limit:
        queue = queue.head(args.limit)

    results: list[dict] = []
    for i, (_, row) in enumerate(queue.iterrows(), 1):
        code = int(row["mf_scheme_code"])
        sid = int(row["scheme_id"])
        et_name = str(row.get("et_fund_name") or "").strip()
        if code in done_codes:
            print(f"[{i}] skip {code} (done)")
            continue

        url = portfolio_url_from_row(row)
        fund = {
            "fund_name": et_name,
            "category": "Sectoral/Thematic",
            "fund_house": "",
            "scheme_id": sid,
            "url": url,
        }
        print(f"\n[{i}/{len(queue)}] MF {code} ET {sid}: {et_name[:60]}")
        print(f"  {url}")

        if args.dry_run:
            results.append(
                {
                    "mf_scheme_code": code,
                    "scheme_id": sid,
                    "et_fund_name": et_name,
                    "status": "dry_run",
                    "quality_tier": "",
                    "stock_rows": 0,
                    "sector_rows": 0,
                    "url": url,
                }
            )
            continue

        stock_part = scrape_fund(fund)
        sector_alloc = scrape_sector_allocation_from_url(fund=fund)

        has_stock = not (stock_part is None or stock_part.empty)
        has_sector = not (sector_alloc is None or sector_alloc.empty)

        if not has_stock and not has_sector:
            status = "no_table"
            tier = "empty"
        elif has_sector and not has_stock:
            status = "ok"
            tier = "sector_buckets_only"
            upsert_sector(sector_alloc, sid)
        elif has_stock and not has_sector:
            status = "ok"
            tier = "stock_holdings"
            upsert_holdings(stock_part, sid)
        else:
            status = "ok"
            tier = "mixed"
            upsert_holdings(stock_part, sid)
            upsert_sector(sector_alloc, sid)

        rec = {
            "mf_scheme_code": code,
            "scheme_id": sid,
            "et_fund_name": et_name,
            "status": status,
            "quality_tier": tier,
            "stock_rows": len(stock_part),
            "sector_rows": len(sector_alloc),
            "url": url,
            "scraped_at": datetime.now().isoformat(timespec="seconds"),
        }
        results.append(rec)
        progress_rows = [r for r in progress_rows if int(r.get("mf_scheme_code", -1)) != code]
        progress_rows.append(rec)

        PROGRESS.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(progress_rows).to_csv(PROGRESS, index=False)

        if i < len(queue):
            time.sleep(args.delay)

    # QC summary
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(results if results else progress_rows)
    lines = [
        "Mapped no-holdings cohort — sector scrape QC",
        f"Generated: {datetime.now().isoformat()}",
        f"dry_run: {args.dry_run}",
        "",
    ]
    if not df.empty and "quality_tier" in df.columns:
        lines.append(df["quality_tier"].value_counts().to_string())
        lines.append("")
        lines.append(df["status"].value_counts().to_string())
    QC.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {QC.relative_to(ROOT)}")
    if not args.dry_run:
        print("Re-run: python analytics/normalize_holdings.py")
        print("      python analytics/normalize_sector_alloc.py  (if added)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
