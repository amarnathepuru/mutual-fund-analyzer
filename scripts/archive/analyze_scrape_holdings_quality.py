"""
Holdings quality report for the last two MFAPI→ET scrape runs (batch + manual links).

  python scripts/analyze_scrape_holdings_quality.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = ROOT / "data/reports/mfapi_et_scrape_batch_progress.csv"
MANUAL_CSV = ROOT / "data/reports/mfapi_et_manual_links.csv"
MASTER = ROOT / "data/fund_master_auto.csv"
HOLDINGS = ROOT / "data/processed/master_holdings.csv"
SCHEME_MAP = ROOT / "data/fund_scheme_map.csv"
OUT = ROOT / "data/reports/mfapi_et_holdings_quality.csv"
SUMMARY = ROOT / "data/reports/mfapi_et_holdings_quality_summary.txt"

# ET sometimes lists sector/asset-class buckets instead of securities in the stock table.
SECTOR_BUCKET_PATTERNS = (
    r"^equity$",
    r"^debt$",
    r"^cash",
    r"^net receivable",
    r"^net current asset",
    r"^others?$",
    r"^mutual fund",
    r"^government securities",
    r"^treasury bill",
    r"^commercial paper",
    r"^certificate of deposit",
    r"^bonds?$",
    r"^debenture",
    r"^fixed income",
    r"^money market",
    r"^corporate bond",
    r"^sovereign",
    r"^sebi",
    r"^units of",
    r"^reverse repo",
    r"^treps",
    r"^cblo",
    r"^gold$",
    r"^commodit",
    r"^real estate",
    r"^international equity",
    r"^foreign",
    r"^cash & cash equivalent",
    r"^net cash",
    r"^total$",
    r"^sub total",
    r"^aggregate",
)
SECTOR_BUCKET_RE = re.compile("|".join(SECTOR_BUCKET_PATTERNS), re.I)

# stock_name equals sector label (sector breakdown rows mis-parsed as holdings)
def _is_sector_bucket_row(stock_name: str, sector: str) -> bool:
    sn = (stock_name or "").strip()
    sec = (sector or "").strip()
    if not sn:
        return True
    if SECTOR_BUCKET_RE.search(sn):
        return True
    if sec and sn.upper() == sec.upper():
        return True
    # "Financial Services" in both columns with no Ltd/LLP/Inc
    if sec and sn.lower() == sec.lower() and not re.search(
        r"\b(ltd|limited|llp|inc|plc|corp|company)\b", sn, re.I
    ):
        return True
    return False


def _load_manual_codes() -> set[int]:
    df = pd.read_csv(MANUAL_CSV, encoding="utf-8-sig")
    cols = {c.strip().lower().replace(" ", "_"): c for c in df.columns}
    link_col = cols.get("et_link", "ET Link")
    df["_link"] = df[link_col].fillna("").astype(str)
    has = df["_link"].str.contains("etmoney", case=False, na=False)
    return set(df.loc[has, df.columns[0]].astype(int))


def _cohort_label(code: int, manual_codes: set[int], scraped_at: str) -> str:
    if code in manual_codes:
        return "manual_link_scrape"
    if scraped_at and scraped_at >= "2026-06-01T12:":
        return "manual_link_scrape"
    if scraped_at and scraped_at >= "2026-06-01T05:":
        return "batch_scrape"
    return "batch_scrape"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    manual_codes = _load_manual_codes()
    prog = pd.read_csv(PROGRESS, encoding="utf-8-sig")
    prog["mf_scheme_code"] = prog["mf_scheme_code"].astype(int)
    ok = prog[prog["status"].astype(str).str.lower() == "ok"].copy()

    # Last two runs: batch (~206) + manual (154)
    ok["scrape_cohort"] = ok.apply(
        lambda r: _cohort_label(
            int(r["mf_scheme_code"]),
            manual_codes,
            str(r.get("scraped_at") or ""),
        ),
        axis=1,
    )
    # Prefer manual cohort if code is in manual list
    ok.loc[ok["mf_scheme_code"].isin(manual_codes), "scrape_cohort"] = "manual_link_scrape"

    cohorts = ok[ok["scrape_cohort"].isin(["batch_scrape", "manual_link_scrape"])]

    master = pd.read_csv(MASTER)
    master_by_sid = master.set_index(master["scheme_id"].astype(int))

    if HOLDINGS.is_file():
        h = pd.read_csv(HOLDINGS, encoding="utf-8-sig")
        h["scheme_id"] = h["scheme_id"].astype(int)
    else:
        h = pd.DataFrame(columns=["scheme_id", "stock_name", "sector", "allocation_percent"])

    rows_out = []
    for _, r in cohorts.iterrows():
        mf_code = int(r["mf_scheme_code"])
        sid = int(float(r["et_scheme_id"])) if pd.notna(r["et_scheme_id"]) else 0
        et_status = str(r.get("et_master_status") or "")
        validated_rows = int(float(r["holdings_rows"])) if pd.notna(r["holdings_rows"]) else 0

        fund_h = h[h["scheme_id"] == sid] if sid else pd.DataFrame()
        scraped_rows = len(fund_h)
        alloc_sum = (
            float(fund_h["allocation_percent"].sum()) if not fund_h.empty else 0.0
        )

        if fund_h.empty:
            stock_rows = 0
            sector_bucket_rows = 0
            stock_alloc = 0.0
            sector_alloc = 0.0
            quality = "no_holdings_scraped"
        else:
            bucket_mask = fund_h.apply(
                lambda x: _is_sector_bucket_row(
                    str(x.get("stock_name", "")), str(x.get("sector", ""))
                ),
                axis=1,
            )
            sector_bucket_rows = int(bucket_mask.sum())
            stock_rows = scraped_rows - sector_bucket_rows
            sector_alloc = float(fund_h.loc[bucket_mask, "allocation_percent"].sum())
            stock_alloc = float(fund_h.loc[~bucket_mask, "allocation_percent"].sum())

            if scraped_rows == 0 or validated_rows == 0:
                quality = "no_holdings_on_et"
            elif stock_rows == 0 and sector_bucket_rows > 0:
                quality = "sector_buckets_only"
            elif sector_bucket_rows > 0 and stock_alloc < 50:
                quality = "mostly_sector_buckets"
            elif alloc_sum >= 85:
                quality = "good_stock_holdings"
            elif alloc_sum >= 50:
                quality = "partial_coverage"
            else:
                quality = "low_coverage"

        rows_out.append(
            {
                "mf_scheme_code": mf_code,
                "mfapi_name_cleaned": r.get("mfapi_name_cleaned", ""),
                "scrape_cohort": r["scrape_cohort"],
                "et_scheme_id": sid,
                "et_fund_name": r.get("et_fund_name", ""),
                "et_master_status": et_status,
                "validated_rows_on_et": validated_rows,
                "scraped_rows_in_master": scraped_rows,
                "stock_level_rows": stock_rows,
                "sector_bucket_rows": sector_bucket_rows,
                "allocation_sum_pct": round(alloc_sum, 2),
                "stock_level_alloc_pct": round(stock_alloc, 2),
                "sector_bucket_alloc_pct": round(sector_alloc, 2),
                "holdings_available_pct": round(min(alloc_sum, 100.0), 2),
                "quality_tier": quality,
            }
        )

    report = pd.DataFrame(rows_out)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(OUT, index=False, encoding="utf-8-sig")

    lines = ["MFAPI→ET holdings quality (batch + manual link scrapes)", ""]

    for cohort in ("batch_scrape", "manual_link_scrape"):
        sub = report[report["scrape_cohort"] == cohort]
        if sub.empty:
            continue
        lines.append(f"=== {cohort} ({len(sub)} funds) ===")
        tier_counts = sub["quality_tier"].value_counts()
        for tier, n in tier_counts.items():
            lines.append(f"  {tier}: {n}")

        good = sub[sub["quality_tier"] == "good_stock_holdings"]
        sector_only = sub[sub["quality_tier"] == "sector_buckets_only"]
        mostly_sec = sub[sub["quality_tier"] == "mostly_sector_buckets"]
        no_h = sub[sub["quality_tier"].isin(["no_holdings_scraped", "no_holdings_on_et"])]

        lines.append(f"  Median allocation sum %: {sub['allocation_sum_pct'].median():.1f}")
        lines.append(f"  Median stock-level alloc %: {sub['stock_level_alloc_pct'].median():.1f}")
        lines.append(
            f"  Funds with good stock holdings (alloc sum ≥85%): {len(good)} "
            f"({100*len(good)/len(sub):.1f}%)"
        )
        lines.append(
            f"  Sector/asset-class buckets ONLY (no stock names): {len(sector_only)}"
        )
        lines.append(
            f"  Mostly sector buckets (<50% stock-level alloc): {len(mostly_sec)}"
        )
        lines.append(
            f"  No holdings scraped (0 rows in master): {len(sub[sub['scraped_rows_in_master']==0])}"
        )
        lines.append(
            f"  ET validated 0 rows (NO_HOLDINGS): {len(sub[sub['validated_rows_on_et']==0])}"
        )
        lines.append("")

    both = report
    lines.append(f"=== Combined ({len(both)} funds) ===")
    lines.append(
        f"Sector buckets only: {(both['quality_tier']=='sector_buckets_only').sum()}"
    )
    lines.append(
        f"Mostly sector buckets: {(both['quality_tier']=='mostly_sector_buckets').sum()}"
    )
    lines.append(
        f"No holdings: {both['scraped_rows_in_master'].eq(0).sum()}"
    )
    lines.append(f"\nDetail: {OUT}")

    text = "\n".join(lines)
    SUMMARY.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
