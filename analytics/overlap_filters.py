"""Fund filters for the overlap matrix journey (category, return period, min return)."""

from __future__ import annotations

import pandas as pd

from analytics.overlap_graph import CATEGORY_ORDER, funds_in_category

RETURN_PERIODS = ("1Y", "3Y", "5Y")
RETURN_COLUMN = {"1Y": "return_1y", "3Y": "return_3y", "5Y": "return_5y"}
MIN_RETURN_SLIDER_MAX = 20


def return_column(period: str) -> str:
    return RETURN_COLUMN.get(period, "return_1y")


def fund_return_pct(master: pd.DataFrame, fund_name: str, period: str) -> float | None:
    if master.empty or "fund_name" not in master.columns:
        return None
    col = return_column(period)
    if col not in master.columns:
        return None
    rows = master.loc[master["fund_name"] == fund_name, col]
    if rows.empty:
        return None
    val = rows.iloc[0]
    return float(val) if pd.notna(val) else None


def filter_funds(
    master: pd.DataFrame,
    category: str,
    period: str,
    min_return_pct: float | None,
    *,
    category_map: dict[str, list[str]] | None = None,
    stock_only: bool = False,
    allowed_funds: set[str] | None = None,
) -> list[str]:
    """Funds in category (browse card or raw label) that meet the minimum trailing return."""
    if category_map:
        raw_labels = category_map.get(category, [category])
        if master.empty or "category" not in master.columns:
            names: list[str] = []
        else:
            names = (
                master.loc[master["category"].isin(raw_labels), "fund_name"]
                .dropna()
                .unique()
                .tolist()
            )
    else:
        names = funds_in_category(master, category)
    if not names or master.empty:
        return []

    if stock_only and "has_holdings" in master.columns:
        held = set(
            master.loc[master["has_holdings"], "fund_name"].dropna().astype(str).str.strip()
        )
        names = [n for n in names if str(n).strip() in held]

    if allowed_funds is not None:
        names = [n for n in names if n in allowed_funds]

    col = return_column(period)
    if col not in master.columns:
        return names

    subset = master.loc[master["fund_name"].isin(names), ["fund_name", col]].drop_duplicates(
        "fund_name"
    )
    if min_return_pct is None:
        return [n for n in names if n in set(subset["fund_name"])]

    out: list[str] = []
    for _, row in subset.iterrows():
        val = row[col]
        if pd.isna(val):
            continue
        if float(val) >= min_return_pct:
            out.append(row["fund_name"])
    return [n for n in names if n in out]


def sort_funds_by_return(
    funds: list[str],
    master: pd.DataFrame,
    period: str,
    *,
    descending: bool = True,
) -> list[str]:
    col = return_column(period)

    def key(name: str) -> float:
        val = fund_return_pct(master, name, period)
        return val if val is not None else float("-inf")

    return sorted(funds, key=key, reverse=descending)


def format_return_suffix(master: pd.DataFrame, fund_name: str, period: str) -> str:
    val = fund_return_pct(master, fund_name, period)
    if val is None:
        return ""
    return f" {val:+.1f}%"


__all__ = [
    "CATEGORY_ORDER",
    "RETURN_PERIODS",
    "MIN_RETURN_SLIDER_MAX",
    "return_column",
    "fund_return_pct",
    "filter_funds",
    "sort_funds_by_return",
    "format_return_suffix",
]
