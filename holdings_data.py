"""
Holdings + sector allocation loaders (stock-level vs ET sector buckets).

Stock rows: normalized_holdings.csv
Sector-only funds: fund_sector_allocation.csv
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
SECTOR_RAW = ROOT / "data" / "processed" / "fund_sector_allocation.csv"
HOLDINGS_NORM = ROOT / "data" / "processed" / "normalized_holdings.csv"


def normalize_sector_label(value: str) -> str:
    s = str(value or "").strip()
    if not s:
        return "OTHER"
    return s.upper()


@lru_cache(maxsize=1)
def load_sector_allocation() -> pd.DataFrame:
    if not SECTOR_RAW.is_file():
        return pd.DataFrame()
    df = pd.read_csv(SECTOR_RAW)
    if df.empty:
        return df
    df = df.copy()
    df["fund_name"] = df["fund_name"].astype(str).str.strip()
    df["sector"] = df["sector"].map(normalize_sector_label)
    df["allocation_percent"] = pd.to_numeric(df["allocation_percent"], errors="coerce")
    df = df[df["allocation_percent"] > 0]
    return df


@lru_cache(maxsize=1)
def sector_only_fund_names() -> frozenset[str]:
    """Funds with ET sector data and no stock rows in normalized holdings."""
    sector = load_sector_allocation()
    if sector.empty:
        return frozenset()
    sector_funds = set(sector["fund_name"].dropna().astype(str))
    if not HOLDINGS_NORM.is_file():
        return frozenset(sector_funds)
    hold = pd.read_csv(HOLDINGS_NORM, usecols=["fund_name"])
    stock_funds = set(hold["fund_name"].dropna().astype(str))
    return frozenset(sector_funds - stock_funds)


@lru_cache(maxsize=1)
def stock_fund_names() -> frozenset[str]:
    if not HOLDINGS_NORM.is_file():
        return frozenset()
    hold = pd.read_csv(HOLDINGS_NORM, usecols=["fund_name"])
    return frozenset(hold["fund_name"].dropna().astype(str).str.strip())


def get_sector_breakdown(holdings_df: pd.DataFrame) -> pd.DataFrame:
    """
    Per-fund sector allocation: aggregate stocks where present; else sector file.
    """
    parts: list[pd.DataFrame] = []
    sector_only = sector_only_fund_names()

    if holdings_df is not None and not holdings_df.empty:
        h = holdings_df.copy()
        h = h[~h["fund_name"].astype(str).isin(sector_only)]
        if not h.empty and "sector" in h.columns:
            from_stocks = (
                h.groupby(["fund_name", "sector"], as_index=False)["allocation_percent"]
                .sum()
            )
            parts.append(from_stocks)

    sector = load_sector_allocation()
    if not sector.empty:
        so = sector[sector["fund_name"].astype(str).isin(sector_only)]
        if not so.empty:
            parts.append(
                so.groupby(["fund_name", "sector"], as_index=False)["allocation_percent"]
                .sum()
            )

    if not parts:
        return pd.DataFrame(columns=["fund_name", "sector", "allocation_percent"])
    out = pd.concat(parts, ignore_index=True)
    return out.sort_values(["fund_name", "allocation_percent"], ascending=[True, False])


def fund_has_stock_holdings(fund_name: str) -> bool:
    return str(fund_name).strip() in stock_fund_names()


def fund_has_sector_alloc(fund_name: str) -> bool:
    sector = load_sector_allocation()
    if sector.empty:
        return False
    fn = str(fund_name).strip()
    return fn in set(sector["fund_name"].astype(str))


def fund_can_analyse(fund_name: str) -> bool:
    fn = str(fund_name).strip()
    return fn in stock_fund_names() or fn in sector_only_fund_names()


def clear_caches() -> None:
    load_sector_allocation.cache_clear()
    sector_only_fund_names.cache_clear()
    stock_fund_names.cache_clear()
