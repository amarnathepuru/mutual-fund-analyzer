"""
Build "needs review" queues: open match report rows + duplicate MF code pairs.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCHEME_MAP = ROOT / "data" / "fund_scheme_map.csv"
REPORT = ROOT / "data" / "reports" / "et_mfapi_match_report.csv"


def load_scheme_map(path: Path = SCHEME_MAP) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    return pd.read_csv(path)


def _et_lookup(et_active: pd.DataFrame) -> pd.Series:
    if et_active.empty or "scheme_id" not in et_active.columns:
        return pd.Series(dtype=object)
    return et_active.set_index(et_active["scheme_id"].astype(int), drop=False)


def enrich_needs_review_table(
    nr: pd.DataFrame, et_active: pd.DataFrame
) -> pd.DataFrame:
    """Fill ET names / house / category from fund_master when report/map left them blank."""
    if nr.empty:
        return nr
    out = nr.copy()
    et_idx = _et_lookup(et_active)
    for col, src in (
        ("et_fund_name", "fund_name"),
        ("et_fund_house", "fund_house"),
        ("et_category", "category"),
    ):
        if col not in out.columns:
            out[col] = ""
        for i, row in out.iterrows():
            sid = int(row["scheme_id"])
            if sid not in et_idx.index:
                continue
            cur = str(out.at[i, col] or "").strip()
            if cur and cur.lower() != "nan":
                continue
            val = et_idx.loc[sid].get(src, "")
            if pd.notna(val) and str(val).strip():
                out.at[i, col] = str(val).strip()
    return out


def mfapi_scheme_name(mf_df: pd.DataFrame, mf_code: int) -> str:
    if mf_df is None or mf_df.empty:
        return ""
    m = mf_df[mf_df["mf_scheme_code"].astype(int) == int(mf_code)]
    if m.empty:
        return ""
    row = m.iloc[0]
    for key in ("fund_name_base", "scheme_name", "fund_name"):
        v = row.get(key)
        if pd.notna(v) and str(v).strip():
            return str(v).strip()
    return ""


def build_duplicate_pairs_detail(
    scheme_map: pd.DataFrame,
    et_active: pd.DataFrame,
    mf_df: pd.DataFrame,
) -> pd.DataFrame:
    """One row per ET fund in a duplicate mf_scheme_code pair (for review UI)."""
    dups = duplicate_map_rows(scheme_map)
    if dups.empty:
        return pd.DataFrame()
    et_idx = _et_lookup(et_active)
    rows: list[dict] = []
    for mf_code, grp in dups.groupby(dups["mf_scheme_code"].astype(int)):
        grp = grp.sort_values("scheme_id")
        peers: list[tuple[int, str]] = []
        for _, m in grp.iterrows():
            sid = int(m["scheme_id"])
            name = str(m.get("et_fund_name") or "").strip()
            if (not name or name.lower() == "nan") and sid in et_idx.index:
                name = str(et_idx.loc[sid].get("fund_name") or "").strip()
            peers.append((sid, name))
        peer_txt = " · ".join(f"{s} {n}" for s, n in peers)
        mf_name = mfapi_scheme_name(mf_df, int(mf_code))
        for _, m in grp.iterrows():
            sid = int(m["scheme_id"])
            et_name = str(m.get("et_fund_name") or "").strip()
            house = ""
            category = ""
            if sid in et_idx.index:
                er = et_idx.loc[sid]
                if not et_name or et_name.lower() == "nan":
                    et_name = str(er.get("fund_name") or "").strip()
                house = str(er.get("fund_house") or "").strip()
                category = str(er.get("category") or "").strip()
            others = [f"{s} {n}" for s, n in peers if s != sid]
            rows.append(
                {
                    "mf_scheme_code": int(mf_code),
                    "mfapi_scheme_name": mf_name,
                    "scheme_id": sid,
                    "et_fund_name": et_name,
                    "et_fund_house": house,
                    "et_category": category,
                    "map_method": m.get("match_method", ""),
                    "map_score": m.get("match_score", ""),
                    "conflicts_with": " | ".join(others),
                    "what_to_do": "Keep ONE mapping per MF code — Confirm correct fund, No link or new Correction for the other.",
                }
            )
    return pd.DataFrame(rows)


def build_open_review_detail(nr: pd.DataFrame) -> pd.DataFrame:
    if nr.empty:
        return pd.DataFrame()
    open_df = nr[nr["review_reason"].isin(("review", "ambiguous"))].copy()
    cols = [
        c
        for c in [
            "scheme_id",
            "et_fund_name",
            "et_fund_house",
            "et_category",
            "match_status",
            "match_score",
            "mf_scheme_code",
            "mf_scheme_name",
            "review_reason",
        ]
        if c in open_df.columns
    ]
    return open_df[cols] if cols else open_df


def duplicate_map_rows(scheme_map: pd.DataFrame) -> pd.DataFrame:
    if scheme_map.empty or "mf_scheme_code" not in scheme_map.columns:
        return scheme_map.iloc[0:0]
    codes = pd.to_numeric(scheme_map["mf_scheme_code"], errors="coerce")
    valid = scheme_map[codes.notna()].copy()
    return valid[valid.duplicated("mf_scheme_code", keep=False)].copy()


def build_needs_review_table(
    report: pd.DataFrame,
    scheme_map: pd.DataFrame,
    *,
    decided_ids: set[int] | None = None,
) -> pd.DataFrame:
    """
    Union of:
      - report rows with status review / ambiguous
      - rows in fund_scheme_map sharing mf_scheme_code with another ET fund
    """
    decided_ids = decided_ids or set()
    pieces: list[pd.DataFrame] = []

    open_match = report[report["match_status"].isin(("review", "ambiguous"))].copy()
    if not open_match.empty:
        open_match["review_reason"] = open_match["match_status"].astype(str)
        pieces.append(open_match)

    dups = duplicate_map_rows(scheme_map)
    if not dups.empty:
        dup_ids = set(dups["scheme_id"].astype(int))
        already = set()
        if pieces:
            already = set(pieces[0]["scheme_id"].astype(int))
        extra_ids = dup_ids - already
        if extra_ids:
            dup_only = dups[dups["scheme_id"].astype(int).isin(extra_ids)].copy()
            rep_idx = report.set_index(report["scheme_id"].astype(int), drop=False)
            rows = []
            for _, m in dup_only.iterrows():
                sid = int(m["scheme_id"])
                if sid in rep_idx.index:
                    base = rep_idx.loc[sid].to_dict()
                    base["mf_scheme_code"] = m.get("mf_scheme_code", base.get("mf_scheme_code"))
                else:
                    base = {
                        "scheme_id": sid,
                        "et_fund_name": m.get("et_fund_name", ""),
                        "et_category": "",
                        "et_fund_house": "",
                        "mf_scheme_code": m.get("mf_scheme_code", ""),
                        "mf_scheme_name": "",
                        "match_score": m.get("match_score", ""),
                        "match_status": "in_map",
                        "alt_candidates": "",
                    }
                base["review_reason"] = "duplicate_mf_code"
                base["mapped_mf_scheme_code"] = m.get("mf_scheme_code", "")
                base["map_match_method"] = m.get("match_method", "")
                rows.append(base)
            pieces.append(pd.DataFrame(rows))

    if not pieces:
        return pd.DataFrame()

    out = pd.concat(pieces, ignore_index=True)
    out["scheme_id"] = out["scheme_id"].astype(int)
    out = out.drop_duplicates(subset=["scheme_id"], keep="first")

    out["already_decided"] = out["scheme_id"].astype(int).isin(decided_ids)
    out = out.sort_values(
        ["review_reason", "match_score"],
        ascending=[True, True],
        kind="mergesort",
    )
    return out.reset_index(drop=True)


def needs_review_counts(report: pd.DataFrame, scheme_map: pd.DataFrame) -> dict[str, int]:
    dups = duplicate_map_rows(scheme_map)
    open_n = len(report[report["match_status"].isin(("review", "ambiguous"))])
    dup_pairs = dups["mf_scheme_code"].nunique() if not dups.empty else 0
    dup_rows = len(dups)
    table = build_needs_review_table(report, scheme_map)
    return {
        "open_review_ambiguous": open_n,
        "duplicate_pairs": dup_pairs,
        "duplicate_rows": dup_rows,
        "unique_needs_review": len(table),
    }
