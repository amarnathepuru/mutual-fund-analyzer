"""
Optional investment labels — user-defined tags for holdings (not dates or periods).

Supabase: public.investment_labels (see supabase/migrate_investment_labels.sql).
"""
from __future__ import annotations

import uuid
from typing import Any

import pandas as pd

ROW_KIND_HOLDING = "holding"
ROW_KIND_TRANSACTION = "transaction"

LABEL_HOLDING_COLS = (
    "investment_label_id",
    "investment_label",
    "row_kind",
    "lot_group_id",
)

# Legacy column names from earlier builds
_LEGACY_LABEL_COLS = {
    "investment_period_id": "investment_label_id",
    "investment_period_label": "investment_label",
}


def new_lot_group_id() -> str:
    return uuid.uuid4().hex


def migrate_label_column_names(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    for old, new in _LEGACY_LABEL_COLS.items():
        if old in out.columns and new not in out.columns:
            out = out.rename(columns={old: new})
    if "period_start_date" in out.columns:
        out = out.drop(columns=["period_start_date"])
    return out


def label_text_by_id(labels: list[dict[str, Any]], label_id: str) -> str:
    lid = str(label_id or "").strip()
    for row in labels:
        if str(row.get("id", "")) == lid:
            return str(row.get("label") or "").strip()
    return ""


def attach_label_metadata(
    df: pd.DataFrame,
    labels: list[dict[str, Any]],
) -> pd.DataFrame:
    """Normalize label columns; never assign a default label."""
    if df is None or df.empty:
        return df
    out = migrate_label_column_names(df)
    for col in LABEL_HOLDING_COLS:
        if col not in out.columns:
            out[col] = ""
    if "row_kind" not in out.columns or out["row_kind"].astype(str).str.strip().eq("").all():
        out["row_kind"] = ROW_KIND_HOLDING
    out["row_kind"] = out["row_kind"].fillna(ROW_KIND_HOLDING).astype(str).str.strip()
    out.loc[out["row_kind"] == "", "row_kind"] = ROW_KIND_HOLDING

    label_to_id = {
        str(row.get("label", "")).strip().lower(): str(row["id"])
        for row in labels
        if str(row.get("label", "")).strip()
    }
    for idx, row in out.iterrows():
        lid = str(row.get("investment_label_id") or "").strip()
        lbl_text = str(row.get("investment_label") or "").strip()
        if not lid:
            lbl_key = lbl_text.lower()
            if lbl_key and lbl_key in label_to_id:
                out.at[idx, "investment_label_id"] = label_to_id[lbl_key]
                lid = label_to_id[lbl_key]
            else:
                out.at[idx, "investment_label_id"] = ""
                out.at[idx, "investment_label"] = ""
        elif not lbl_text:
            out.at[idx, "investment_label"] = label_text_by_id(labels, lid)
        if str(row.get("row_kind") or "").strip() == ROW_KIND_HOLDING:
            if not str(row.get("lot_group_id") or "").strip():
                out.at[idx, "lot_group_id"] = new_lot_group_id()
    return out


def split_holdings_and_transactions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df is None or df.empty:
        empty = pd.DataFrame()
        return empty, empty
    if "row_kind" not in df.columns:
        return df.copy(), pd.DataFrame()
    kinds = df["row_kind"].astype(str).str.strip().str.lower()
    txn = df[kinds == ROW_KIND_TRANSACTION].copy()
    hold = df[kinds != ROW_KIND_TRANSACTION].copy()
    return hold, txn


def filter_by_investment_labels(
    df: pd.DataFrame,
    selected_label_ids: list[str] | None,
    *,
    include_unlabeled: bool = False,
) -> pd.DataFrame:
    """Empty selection = no filter (show all)."""
    if df is None or df.empty or not selected_label_ids:
        return df
    out = migrate_label_column_names(df)
    lids = {str(x).strip() for x in selected_label_ids if str(x).strip()}
    if not lids and not include_unlabeled:
        return out
    col = out["investment_label_id"].astype(str).str.strip() if "investment_label_id" in out.columns else pd.Series([""] * len(out))
    mask = col.isin(lids)
    if include_unlabeled or "__unlabeled__" in lids:
        mask = mask | (col == "")
    return out[mask].copy()
