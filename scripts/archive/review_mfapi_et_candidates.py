"""ET candidates for MFAPI→ET review — report + name search on ET ACTIVE master."""
from __future__ import annotations

import re

import pandas as pd

from mfapi_scheme_name import (
    et_significant_tokens,
    fund_name_match_score,
    mf_fund_name_cleaned,
    mf_significant_tokens,
)


def parse_et_alts(raw: str) -> list[tuple[int, float]]:
    out: list[tuple[int, float]] = []
    for part in str(raw or "").split(";"):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"(\d+)\s*:\s*([\d.]+)", part)
        if not m:
            continue
        out.append((int(m.group(1)), float(m.group(2))))
    return out


def _mf_cleaned_from_row(row: pd.Series) -> str:
    raw = str(row.get("mfapi_scheme_name") or row.get("scheme_name_raw") or "")
    base = str(
        row.get("mfapi_fund_name_cleaned")
        or row.get("mfapi_fund_name_base")
        or row.get("fund_name_base")
        or ""
    )
    return mf_fund_name_cleaned(raw or raw)


def build_et_options_from_report(
    row: pd.Series,
    et_by_id: dict[int, pd.Series],
    *,
    max_options: int = 8,
) -> list[tuple[int, float, str]]:
    """Fast dropdown options: precomputed report best + alt_candidates only."""
    seen: set[int] = set()
    options: list[tuple[int, float, str]] = []

    def add(sid: int, score: float, name: str) -> None:
        if sid in seen or sid <= 0:
            return
        seen.add(sid)
        options.append((sid, score, name))

    sid0 = row.get("scheme_id")
    score0 = pd.to_numeric(row.get("match_score"), errors="coerce")
    if pd.notna(sid0) and str(sid0).strip() != "":
        sid = int(float(sid0))
        sc = float(score0) if pd.notna(score0) else 0.0
        name = str(row.get("et_fund_name") or "")
        if not name and sid in et_by_id:
            name = str(et_by_id[sid].get("fund_name") or "")
        add(sid, sc, name)

    for sid, sc in parse_et_alts(str(row.get("alt_candidates") or "")):
        name = ""
        if sid in et_by_id:
            name = str(et_by_id[sid].get("fund_name") or "")
        add(sid, sc, name)

    options.sort(key=lambda x: (-x[1], x[0]))
    return options[:max_options]


def build_et_options_enhanced(
    row: pd.Series,
    et_active: pd.DataFrame,
    *,
    max_options: int = 8,
    min_name_score: float = 40.0,
) -> list[tuple[int, float, str]]:
    """ET picks: report alts + optional name-token search (slow — avoid in bulk grid)."""
    seen: set[int] = set()
    options: list[tuple[int, float, str]] = []

    def add(sid: int, score: float, name: str) -> None:
        if sid in seen or sid <= 0:
            return
        seen.add(sid)
        options.append((sid, score, name))

    et_idx = et_active.set_index(et_active["scheme_id"].astype(int), drop=False)
    mf_clean = _mf_cleaned_from_row(row)
    mf_toks = mf_significant_tokens(mf_clean)

    sid0 = row.get("scheme_id")
    score0 = pd.to_numeric(row.get("match_score"), errors="coerce")
    if pd.notna(sid0) and str(sid0).strip() != "":
        sid = int(float(sid0))
        sc = float(score0) if pd.notna(score0) else 0.0
        er = et_idx.loc[sid] if sid in et_idx.index else None
        name = str(row.get("et_fund_name") or (er.get("fund_name") if er is not None else ""))
        add(sid, sc, name)

    for sid, sc in parse_et_alts(str(row.get("alt_candidates") or "")):
        er = et_idx.loc[sid] if sid in et_idx.index else None
        name = str(er.get("fund_name") if er is not None else "")
        add(sid, sc, name)

    for _, et in et_active.iterrows():
        sid = int(et["scheme_id"])
        if sid in seen:
            continue
        et_name = str(et.get("fund_name") or "")
        if mf_toks and not (mf_toks & et_significant_tokens(et_name)):
            continue
        sc = fund_name_match_score(mf_clean, et_name)
        if sc >= min_name_score:
            add(sid, sc, et_name)

    options.sort(key=lambda x: (-x[1], x[0]))
    return options[:max_options]


def format_top5_labels(options: list[tuple[int, float, str]], max_n: int = 5) -> str:
    parts = [f"{sid} {name} ({sc:.0f}%)" for sid, sc, name in options[:max_n]]
    return " | ".join(parts)


def pick_label(mf_code: int, sid: int, name: str, score: float) -> str:
    short = name[:55] + ("…" if len(name) > 55 else "")
    return f"{mf_code} | {sid} — {short} ({score:.1f}%)"


def parse_pick_label(label: str) -> tuple[int | None, int | None, float, str]:
    """Return (mf_code, et_sid, score, et_name) from dropdown value."""
    if not label or not isinstance(label, str):
        return None, None, 0.0, ""
    label = label.strip()
    if " | " not in label:
        m = re.match(r"^(\d+)\s*—\s*(.+?)\s*\(([\d.]+)%\)", label)
        if m:
            return None, int(m.group(1)), float(m.group(3)), m.group(2).strip()
        return None, None, 0.0, ""
    mf_s, rest = label.split(" | ", 1)
    try:
        mf_code = int(mf_s.strip())
    except ValueError:
        mf_code = None
    m = re.match(r"^(\d+)\s*—\s*(.+?)\s*\(([\d.]+)%\)\s*$", rest.strip())
    if not m:
        return mf_code, None, 0.0, ""
    return mf_code, int(m.group(1)), float(m.group(3)), m.group(2).strip().rstrip("…")
