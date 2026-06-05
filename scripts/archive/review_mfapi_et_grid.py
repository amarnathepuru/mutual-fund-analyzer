"""
Bulk grid: 4 columns — MFAPI name, ET dropdown (best + alts), Status, Manual ET id.
"""
from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from mfapi_et_decisions import DECISIONS_CSV, load_decisions, save_decisions, upsert_decision
from review_mfapi_et_candidates import build_et_options_from_report

PAGE_SIZE = 50
STATUS_OPTIONS = ["—", "Approved", "Manual", "Rejected", "No link", "No match"]


def _et_pick_label(sid: int, name: str, score: float) -> str:
    short = name[:55] + ("…" if len(name) > 55 else "")
    return f"{sid} — {short} ({score:.1f}%)"


def _parse_et_pick(label: str) -> tuple[int | None, float, str]:
    if not label or not isinstance(label, str):
        return None, 0.0, ""
    label = label.strip()
    m = re.match(r"^(\d+)\s*—\s*(.+?)\s*\(([\d.]+)%\)\s*$", label)
    if not m:
        return None, 0.0, ""
    return int(m.group(1)), float(m.group(3)), m.group(2).strip().rstrip("…")


def _et_by_id(et_active: pd.DataFrame) -> dict[int, pd.Series]:
    return {
        int(r["scheme_id"]): r
        for _, r in et_active.iterrows()
    }


def _options_for_report_row(
    report_row: pd.Series, et_by_id: dict[int, pd.Series]
) -> list[tuple[int, float, str]]:
    return build_et_options_from_report(report_row, et_by_id)


def _labels_for_options(options: list[tuple[int, float, str]]) -> list[str]:
    return [_et_pick_label(sid, name, sc) for sid, sc, name in options]


@st.cache_data(ttl=600)
def _load_report_slice(mf_codes: tuple[int, ...], report_mtime: float) -> pd.DataFrame:
    from match_mfapi_et import REPORT_OUT

    report = pd.read_csv(REPORT_OUT)
    return report[report["mf_scheme_code"].astype(int).isin(mf_codes)].copy()


def _decision_to_status(prior: dict | None) -> str:
    if not prior:
        return "—"
    dec = str(prior.get("decision") or "").lower()
    notes = str(prior.get("notes") or "").lower()
    if dec == "approved" and "manual" in notes:
        return "Manual"
    if dec == "approved":
        return "Approved"
    if dec == "rejected":
        return "Rejected"
    if dec == "no_match":
        return "No match"
    return "—"


def _default_et_pick(
    options: list[tuple[int, float, str]],
    prior: dict | None,
) -> str:
    """Highest-confidence option (first in sorted list)."""
    if prior and str(prior.get("decision", "")).lower() == "approved":
        notes = str(prior.get("notes") or "").lower()
        if "manual" not in notes:
            pc = prior.get("scheme_id")
            if pd.notna(pc) and str(pc).strip():
                psid = int(float(pc))
                for sid, sc, name in options:
                    if sid == psid:
                        return _et_pick_label(sid, name, sc)
    if options:
        sid, sc, name = options[0]
        return _et_pick_label(sid, name, sc)
    return ""


@st.cache_data(ttl=600)
def _enrich_page_grid_cached(
    mf_codes_page: tuple[int, ...],
    report_mtime: float,
    decisions_mtime: float,
) -> tuple[pd.DataFrame, list[str], dict[str, tuple[int, float, str]], dict[int, set[str]]]:
    from match_mfapi_et import ET_MASTER, REPORT_OUT

    report = pd.read_csv(REPORT_OUT)
    report = report[report["mf_scheme_code"].astype(int).isin(mf_codes_page)]
    et_active = pd.read_csv(ET_MASTER)
    et_active = et_active[et_active["status"].astype(str).str.upper() == "ACTIVE"]
    et_by_id = _et_by_id(et_active)
    decisions = load_decisions()

    grid_rows = []
    for mf_code in mf_codes_page:
        cleaned = ""
        full_name = ""
        match = report[report["mf_scheme_code"].astype(int) == mf_code]
        if not match.empty:
            r0 = match.iloc[0]
            cleaned = str(
                r0.get("mfapi_fund_name_cleaned") or r0.get("mfapi_fund_name_base") or ""
            ).strip()
            full_name = str(r0.get("mfapi_scheme_name") or cleaned)
        grid_rows.append(
            {
                "mf_scheme_code": mf_code,
                "mfapi_name": cleaned,
                "_mfapi_full_name": full_name,
            }
        )
    grid_view = pd.DataFrame(grid_rows)
    return _enrich_page_grid(grid_view, report, et_by_id, decisions)


def _enrich_page_grid(
    grid_view: pd.DataFrame,
    report: pd.DataFrame,
    et_by_id: dict[int, pd.Series],
    decisions: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str], dict[str, tuple[int, float, str]], dict[int, set[str]]]:
    prior_by_mf: dict[int, dict] = {}
    if not decisions.empty:
        for _, d in decisions.iterrows():
            prior_by_mf[int(d["mf_scheme_code"])] = d.to_dict()

    report_idx = report.set_index(report["mf_scheme_code"].astype(int))
    pick_options: list[str] = [""]
    label_meta: dict[str, tuple[int, float, str]] = {}
    allowed_by_mf: dict[int, set[str]] = {}

    et_picks: list[str] = []
    statuses: list[str] = []
    manuals: list[float] = []

    for _, row in grid_view.iterrows():
        mf_code = int(row["mf_scheme_code"])
        r = report_idx.loc[mf_code]
        if isinstance(r, pd.DataFrame):
            r = r.iloc[0]
        options = _options_for_report_row(r, et_by_id)
        labels = _labels_for_options(options)
        allowed_by_mf[mf_code] = set(labels)

        prior = prior_by_mf.get(mf_code)
        et_picks.append(_default_et_pick(options, prior))
        statuses.append(_decision_to_status(prior))

        manual = float("nan")
        if prior and str(prior.get("decision", "")).lower() == "approved":
            notes = str(prior.get("notes") or "").lower()
            if "manual" in notes:
                pc = prior.get("scheme_id")
                if pd.notna(pc) and str(pc).strip():
                    manual = float(int(float(pc)))
        manuals.append(manual)

        for sid, sc, name in options:
            lab = _et_pick_label(sid, name, sc)
            if lab not in pick_options:
                pick_options.append(lab)
            label_meta[lab] = (sid, sc, name)

    out = grid_view.copy()
    out["mfapi_fund_name"] = out["mfapi_name"]
    out["et_money_fund"] = et_picks
    out["status"] = statuses
    out["manual_et_scheme_id"] = manuals
    out["_original_status"] = statuses.copy()
    out["_original_et_money_fund"] = et_picks.copy()
    out["_original_manual"] = manuals.copy()
    return out, pick_options, label_meta, allowed_by_mf


def apply_mfapi_grid_save(
    edited: pd.DataFrame,
    baseline: pd.DataFrame,
    label_meta: dict[str, tuple[int, float, str]],
    allowed_by_mf: dict[int, set[str]],
    et_active: pd.DataFrame,
    scheme_map: pd.DataFrame,
    report: pd.DataFrame,
) -> tuple[pd.DataFrame, int, int, list[str]]:
    decisions = load_decisions()
    saved = 0
    skipped = 0
    errors: list[str] = []

    et_idx = et_active.set_index(et_active["scheme_id"].astype(int), drop=False)
    base_by_mf = {int(r["mf_scheme_code"]): r for _, r in baseline.iterrows()}
    report_idx = report.set_index(report["mf_scheme_code"].astype(int))
    mapped_et: dict[int, int] = {}
    if not scheme_map.empty:
        for _, m in scheme_map.iterrows():
            if pd.notna(m.get("scheme_id")) and pd.notna(m.get("mf_scheme_code")):
                mapped_et[int(m["scheme_id"])] = int(m["mf_scheme_code"])

    for _, row in edited.iterrows():
        mf_code = int(row["mf_scheme_code"])
        base = base_by_mf.get(mf_code)
        if base is None:
            continue

        status = str(row.get("status") or "—").strip()
        pick = str(row.get("et_money_fund") or "").strip()
        manual_raw = row.get("manual_et_scheme_id")

        orig_status = str(base.get("_original_status") or "—").strip()
        orig_pick = str(base.get("_original_et_money_fund") or "").strip()
        orig_manual = base.get("_original_manual")
        try:
            orig_manual_i = (
                int(float(orig_manual))
                if pd.notna(orig_manual) and str(orig_manual).strip() not in ("", "nan")
                else None
            )
        except (TypeError, ValueError):
            orig_manual_i = None

        manual_sid: int | None = None
        if pd.notna(manual_raw) and str(manual_raw).strip() not in ("", "nan"):
            try:
                manual_sid = int(float(manual_raw))
            except (TypeError, ValueError):
                manual_sid = None

        if status == orig_status and pick == orig_pick and manual_sid == orig_manual_i:
            skipped += 1
            continue

        mf_name = str(base.get("_mfapi_full_name") or "")

        if status in ("No link", "Rejected"):
            decisions = upsert_decision(
                decisions,
                mf_scheme_code=mf_code,
                decision="rejected",
                scheme_id=None,
                computed_score=None,
                mf_scheme_name=mf_name,
                et_fund_name="",
                notes=f"bulk_grid {status.lower()}",
            )
            saved += 1
            continue

        if status == "No match":
            decisions = upsert_decision(
                decisions,
                mf_scheme_code=mf_code,
                decision="no_match",
                scheme_id=None,
                computed_score=None,
                mf_scheme_name=mf_name,
                et_fund_name="",
                notes="bulk_grid no match",
            )
            saved += 1
            continue

        if status == "Manual":
            if not manual_sid or manual_sid <= 0:
                errors.append(f"{mf_name[:40]}: Manual needs **Manual ET scheme id**")
                skipped += 1
                continue
            et_sid = manual_sid
            et_name = ""
            if et_sid in et_idx.index:
                et_name = str(et_idx.loc[et_sid].get("fund_name") or "")
            else:
                et_name = f"(ET id {et_sid})"
            if et_sid in mapped_et and mapped_et[et_sid] != mf_code:
                errors.append(f"{mf_name[:40]}: ET {et_sid} already mapped to another MF")
                skipped += 1
                continue
            decisions = upsert_decision(
                decisions,
                mf_scheme_code=mf_code,
                decision="approved",
                scheme_id=et_sid,
                computed_score=None,
                mf_scheme_name=mf_name,
                et_fund_name=et_name,
                notes="bulk_grid manual",
            )
            saved += 1
            continue

        if status == "Approved":
            if not pick:
                errors.append(f"{mf_name[:40]}: Approved needs **ET Money fund** dropdown")
                skipped += 1
                continue
            allowed = allowed_by_mf.get(mf_code)
            if allowed and pick not in allowed:
                errors.append(f"{mf_name[:40]}: pick not in this row's suggestions")
                skipped += 1
                continue
            meta = label_meta.get(pick)
            if meta:
                et_sid, score, et_name = meta[0], meta[1], meta[2]
            else:
                et_sid, score, et_name = _parse_et_pick(pick)
            if not et_sid:
                errors.append(f"{mf_name[:40]}: could not parse ET pick")
                skipped += 1
                continue
            if et_sid in et_idx.index:
                et_name = str(et_idx.loc[et_sid].get("fund_name") or et_name)
            if et_sid in mapped_et and mapped_et[et_sid] != mf_code:
                errors.append(f"{mf_name[:40]}: ET {et_sid} already mapped to another MF")
                skipped += 1
                continue
            decisions = upsert_decision(
                decisions,
                mf_scheme_code=mf_code,
                decision="approved",
                scheme_id=et_sid,
                computed_score=score if score else None,
                mf_scheme_name=mf_name,
                et_fund_name=et_name,
                notes="bulk_grid",
            )
            saved += 1

    save_decisions(decisions)
    return decisions, saved, skipped, errors


def render_mfapi_bulk_grid(
    queue: pd.DataFrame,
    et_active: pd.DataFrame,
    scheme_map: pd.DataFrame,
    *,
    queue_label: str = "Rows",
) -> None:
    from match_mfapi_et import REPORT_OUT

    report_mtime = REPORT_OUT.stat().st_mtime if REPORT_OUT.is_file() else 0.0
    dec_mtime = DECISIONS_CSV.stat().st_mtime if DECISIONS_CSV.is_file() else 0.0
    mf_codes_all = tuple(int(c) for c in queue["mf_scheme_code"].astype(int).tolist())
    n_total = len(mf_codes_all)

    if n_total == 0:
        st.info("No rows for this filter.")
        return

    n_pages = max(1, (n_total + PAGE_SIZE - 1) // PAGE_SIZE)
    c1, c2 = st.columns([1, 4])
    with c1:
        page = st.number_input("Page", min_value=1, max_value=n_pages, value=1, step=1)
    start = (int(page) - 1) * PAGE_SIZE
    end = min(start + PAGE_SIZE, n_total)
    with c2:
        st.caption(f"Rows **{start + 1}–{end}** of **{n_total}** · {queue_label}")

    mf_codes_page = mf_codes_all[start:end]
    report = _load_report_slice(mf_codes_page, report_mtime)

    with st.spinner("Loading page…"):
        grid_view, pick_options, label_meta, allowed_by_mf = _enrich_page_grid_cached(
            mf_codes_page, report_mtime, dec_mtime
        )

    if grid_view.empty:
        st.info("No rows on this page.")
        return

    st.caption(
        "Edits apply when you click **Save this page** (changing Status does not reload the page)."
    )

    with st.form("mfapi_grid_page_form", clear_on_submit=False):
        edited = st.data_editor(
            grid_view[
                ["mfapi_fund_name", "et_money_fund", "status", "manual_et_scheme_id"]
            ].copy(),
            column_config={
                "mfapi_fund_name": st.column_config.TextColumn(
                    "MFAPI cleaned fund name",
                    disabled=True,
                    width="large",
                ),
                "et_money_fund": st.column_config.SelectboxColumn(
                    "ET Money fund",
                    options=pick_options,
                    width="large",
                    help="From match report (top candidates). Use Manual if the fund is not listed.",
                ),
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=STATUS_OPTIONS,
                    width="medium",
                ),
                "manual_et_scheme_id": st.column_config.NumberColumn(
                    "Manual ET scheme id",
                    min_value=0,
                    step=1,
                    format="%d",
                    width="small",
                    help="Only when Status = Manual (from ET Money URL).",
                ),
            },
            hide_index=True,
            use_container_width=True,
            height=min(720, 120 + len(grid_view) * 38),
            key=f"mfapi_grid_v5_{page}_{start}",
        )
        submitted = st.form_submit_button("Save this page", type="primary")

    if submitted:
        full = edited.copy()
        full["mf_scheme_code"] = grid_view["mf_scheme_code"].values
        merged = full.merge(
            grid_view[
                [
                    "mf_scheme_code",
                    "_original_status",
                    "_original_et_money_fund",
                    "_original_manual",
                    "_mfapi_full_name",
                ]
            ],
            on="mf_scheme_code",
            how="left",
        )
        _, saved, skipped, errors = apply_mfapi_grid_save(
            merged,
            grid_view,
            label_meta,
            allowed_by_mf,
            et_active,
            scheme_map,
            report,
        )
        for e in errors[:12]:
            st.error(e)
        if saved:
            st.success(f"Saved **{saved}** row(s). Unchanged: **{skipped}**.")
            _enrich_page_grid_cached.clear()
            st.rerun()
        elif errors:
            st.warning(f"No rows saved. Unchanged: **{skipped}**.")
        else:
            st.info(f"No changes to save. Unchanged: **{skipped}**.")
