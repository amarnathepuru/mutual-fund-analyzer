"""Side-by-side holdings for overlap matrix quick compare."""

from __future__ import annotations

import pandas as pd

from analytics.overlap_graph import fund_label

__all__ = [
    "COLOR_OV_HIGH",
    "COLOR_OV_MID",
    "COLOR_OV_LOW",
    "overlap_list_color",
    "pair_common_count",
    "overlap_pair_summary",
    "top_common_holdings_table",
    "exclusive_holdings_table",
    "holdings_union_table",
    "display_table",
]

COLOR_OV_HIGH = "#A32D2D"
COLOR_OV_MID = "#854F0B"
COLOR_OV_LOW = "#534AB7"


def overlap_list_color(score: float) -> str:
    """Fund-list overlap % colours (fixed, not theme-dependent)."""
    if score >= 80:
        return COLOR_OV_HIGH
    if score >= 65:
        return COLOR_OV_MID
    return COLOR_OV_LOW


def pair_common_count(similarity: pd.DataFrame, fund_a: str, fund_b: str) -> int | None:
    if similarity.empty or "common_stocks" not in similarity.columns:
        return None
    mask = ((similarity["fund_a"] == fund_a) & (similarity["fund_b"] == fund_b)) | (
        (similarity["fund_a"] == fund_b) & (similarity["fund_b"] == fund_a)
    )
    if not mask.any():
        return None
    return int(similarity.loc[mask, "common_stocks"].iloc[0])


def overlap_pair_summary(score: float, common_count: int | None) -> dict:
    """Verdict badge + one-line description for the overlap card."""
    n_txt = f"~{common_count} common stocks" if common_count is not None else "Common stocks n/a"
    if score >= 80:
        return {
            "label": "Very high overlap",
            "badge_bg": "#FEE2E2",
            "badge_color": COLOR_OV_HIGH,
            "description": "These funds largely hold the same stocks — little diversification benefit from owning both.",
            "common_text": n_txt,
        }
    if score >= 65:
        return {
            "label": "High overlap",
            "badge_bg": "#FEF3C7",
            "badge_color": COLOR_OV_MID,
            "description": "Meaningful shared holdings — consider whether you need both in your portfolio.",
            "common_text": n_txt,
        }
    return {
        "label": "Moderate overlap",
        "badge_bg": "#EEEDFE",
        "badge_color": COLOR_OV_LOW,
        "description": "Some shared names, but still distinct enough that both may add value together.",
        "common_text": n_txt,
    }


def top_common_holdings_table(
    holdings: pd.DataFrame,
    fund_a: str,
    fund_b: str,
    *,
    top_n: int = 5,
) -> pd.DataFrame:
    """Top N stocks held by both funds, sorted by average allocation."""
    cols = ["stock_name", "fund_name", "allocation_percent"]
    if holdings.empty or not all(c in holdings.columns for c in cols):
        return pd.DataFrame()

    ha = holdings.loc[holdings["fund_name"] == fund_a, ["stock_name", "allocation_percent"]]
    hb = holdings.loc[holdings["fund_name"] == fund_b, ["stock_name", "allocation_percent"]]
    if ha.empty or hb.empty:
        return pd.DataFrame()

    ha = ha.rename(columns={"allocation_percent": "alloc_a"}).drop_duplicates("stock_name")
    hb = hb.rename(columns={"allocation_percent": "alloc_b"}).drop_duplicates("stock_name")
    merged = ha.merge(hb, on="stock_name", how="inner")
    if merged.empty:
        return pd.DataFrame()

    merged["alloc_a"] = merged["alloc_a"].round(2)
    merged["alloc_b"] = merged["alloc_b"].round(2)
    merged["_sort"] = merged[["alloc_a", "alloc_b"]].mean(axis=1)
    merged = merged.sort_values("_sort", ascending=False).head(top_n).drop(columns="_sort")

    label_a = fund_label(fund_a, max_len=11)
    label_b = fund_label(fund_b, max_len=11)
    return merged.rename(
        columns={
            "stock_name": "Stock",
            "alloc_a": f"{label_a} %",
            "alloc_b": f"{label_b} %",
        }
    )


def exclusive_holdings_table(
    holdings: "pd.DataFrame",
    fund_own: str,
    fund_other: str,
) -> "pd.DataFrame":
    """Stocks held by fund_own but NOT by fund_other, sorted by allocation desc."""
    cols = ["stock_name", "fund_name", "allocation_percent"]
    if holdings.empty or not all(c in holdings.columns for c in cols):
        return pd.DataFrame()

    own   = holdings.loc[holdings["fund_name"] == fund_own,   ["stock_name", "allocation_percent"]]
    other = holdings.loc[holdings["fund_name"] == fund_other, ["stock_name"]]
    if own.empty:
        return pd.DataFrame()

    other_stocks = set(other["stock_name"].unique()) if not other.empty else set()
    excl = own[~own["stock_name"].isin(other_stocks)].copy()
    excl = excl.drop_duplicates("stock_name").sort_values("allocation_percent", ascending=False)
    excl["allocation_percent"] = excl["allocation_percent"].round(2)

    label = fund_label(fund_own, max_len=14)
    return excl.rename(columns={"stock_name": "Stock", "allocation_percent": f"{label} %"})


def holdings_union_table(
    holdings: pd.DataFrame,
    fund_a: str,
    fund_b: str,
) -> pd.DataFrame:
    """All stocks in either fund with allocation % per fund (blank when not held)."""
    cols = ["stock_name", "fund_name", "allocation_percent"]
    if holdings.empty or not all(c in holdings.columns for c in cols):
        return pd.DataFrame()

    ha = holdings.loc[holdings["fund_name"] == fund_a, ["stock_name", "allocation_percent"]]
    hb = holdings.loc[holdings["fund_name"] == fund_b, ["stock_name", "allocation_percent"]]
    if ha.empty and hb.empty:
        return pd.DataFrame()

    ha = ha.rename(columns={"allocation_percent": "alloc_a"}).drop_duplicates("stock_name")
    hb = hb.rename(columns={"allocation_percent": "alloc_b"}).drop_duplicates("stock_name")
    merged = ha.merge(hb, on="stock_name", how="outer")
    merged["alloc_a"] = merged["alloc_a"].round(2)
    merged["alloc_b"] = merged["alloc_b"].round(2)

    merged["_sort"] = merged[["alloc_a", "alloc_b"]].max(axis=1, skipna=True).fillna(0)
    merged = merged.sort_values("_sort", ascending=False).drop(columns="_sort")

    label_a = fund_label(fund_a, max_len=22)
    label_b = fund_label(fund_b, max_len=22)
    return merged.rename(
        columns={
            "stock_name": "Stock",
            "alloc_a": f"{label_a} %",
            "alloc_b": f"{label_b} %",
        }
    )


def display_table(df: pd.DataFrame) -> pd.DataFrame:
    """Format for st.dataframe (dash for missing allocations)."""
    if df.empty:
        return df
    out = df.copy()
    for col in out.columns[1:]:
        out[col] = out[col].apply(lambda v: "—" if pd.isna(v) else f"{v:.1f}")
    return out
