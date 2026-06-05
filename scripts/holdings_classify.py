"""Classify ET portfolio scrape rows into stock holdings vs sector allocation buckets."""
from __future__ import annotations

import re

import pandas as pd

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


def is_sector_bucket_row(stock_name: str, sector: str) -> bool:
    sn = (stock_name or "").strip()
    sec = (sector or "").strip()
    if not sn:
        return True
    if SECTOR_BUCKET_RE.search(sn):
        return True
    if sec and sn.upper() == sec.upper():
        return True
    if sec and sn.lower() == sec.lower() and not re.search(
        r"\b(ltd|limited|llp|inc|plc|corp|company)\b", sn, re.I
    ):
        return True
    return False


def classify_scrape_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """
    Split raw scrape into stock rows and sector-allocation rows.

    Returns (stock_df, sector_df, quality_tier) where quality_tier is one of:
    empty | stock_holdings | sector_buckets_only | mixed
    """
    if df is None or df.empty:
        return pd.DataFrame(), pd.DataFrame(), "empty"

    work = df.copy()
    mask = work.apply(
        lambda r: is_sector_bucket_row(
            str(r.get("stock_name", "")),
            str(r.get("sector", "")),
        ),
        axis=1,
    )
    sector_part = work[mask].copy()
    stock_part = work[~mask].copy()

    n_sec = len(sector_part)
    n_stk = len(stock_part)
    if n_stk == 0 and n_sec == 0:
        tier = "empty"
    elif n_stk == 0:
        tier = "sector_buckets_only"
    elif n_sec == 0:
        tier = "stock_holdings"
    else:
        tier = "mixed"

    return stock_part, sector_part, tier


def sector_rows_to_allocation(sector_part: pd.DataFrame) -> pd.DataFrame:
    """Map bucket rows to sector allocation records (sector label from stock_name)."""
    if sector_part.empty:
        return pd.DataFrame()

    rows = []
    for _, r in sector_part.iterrows():
        label = str(r.get("stock_name") or "").strip()
        if not label:
            label = str(r.get("sector") or "").strip()
        if not label:
            continue
        rows.append(
            {
                "scheme_id": r.get("scheme_id"),
                "fund_name": r.get("fund_name"),
                "category": r.get("category"),
                "fund_house": r.get("fund_house"),
                "sector": label,
                "allocation_percent": r.get("allocation_percent"),
                "granularity": "sector",
                "source": r.get("source", "ETMoney"),
                "scrape_date": r.get("scrape_date"),
            }
        )
    return pd.DataFrame(rows)
