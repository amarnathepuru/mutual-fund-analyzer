"""
Bulk grid review for ET ↔ MFAPI matches (one-shot save).

Used from review_et_mfapi_app.py — Grid (bulk) mode.
"""
from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from et_mfapi_decisions import (
    OVERRIDES_CSV,
    export_overrides_from_decisions,
    load_decisions,
    save_decisions,
    upsert_decision,
)
from review_queue import (
    build_duplicate_pairs_detail,
    build_needs_review_table,
    build_open_review_detail,
    enrich_needs_review_table,
    load_scheme_map,
    needs_review_counts,
)

_LABEL_CODE_RE = re.compile(r"^(\d+)\s*—")


def _parse_code_from_label(label: str) -> int | None:
    if not label or not isinstance(label, str):
        return None
    m = _LABEL_CODE_RE.match(label.strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _parse_score_from_label(label: str) -> float:
    if not label:
        return 0.0
    parts = label.split("—")
    if len(parts) >= 2:
        try:
            return float(parts[1].strip().replace("%", ""))
        except ValueError:
            pass
    return 0.0


def _name_from_label(label: str) -> str:
    parts = label.split("—", 2)
    return parts[2].strip() if len(parts) >= 3 else ""


def build_candidate_labels(
    row: pd.Series, mf_df: pd.DataFrame, et_row: pd.Series, rank_fn, options_fn
) -> tuple[list[str], dict[str, int], dict[str, float]]:
    """Return labels, label->code, label->score for one ET fund."""
    opts = options_fn(row, mf_df, et_row)
    label_to_code: dict[str, int] = {}
    label_to_score: dict[str, float] = {}
    labels: list[str] = []
    for o in opts:
        lab = o["label"]
        labels.append(lab)
        label_to_code[lab] = int(o["code"])
        label_to_score[lab] = float(o["score"])
    return labels, label_to_code, label_to_score


def _prefixed(sid: int, label: str) -> str:
    if not label:
        return ""
    return f"{sid} | {label}"


def _strip_prefix(value: str) -> tuple[int | None, str]:
    if not value or not isinstance(value, str):
        return None, ""
    if " | " not in value:
        return None, value.strip()
    sid_s, lab = value.split(" | ", 1)
    try:
        return int(sid_s.strip()), lab.strip()
    except ValueError:
        return None, value.strip()


def build_grid_dataframe(
    report: pd.DataFrame,
    et_active: pd.DataFrame,
    mf_df: pd.DataFrame,
    decisions: pd.DataFrame,
    *,
    rank_fn,
    options_fn,
    filter_mode: str,
    auto_ok_below_100_fn,
    restrict_scheme_ids: set[int] | None = None,
    reason_by_id: dict[int, str] | None = None,
    map_mf_by_id: dict[int, int] | None = None,
) -> tuple[pd.DataFrame, dict[str, int], dict[str, float], list[str]]:
    scope = report[report["match_status"] != "excluded_index"].copy()
    if restrict_scheme_ids is not None:
        scope = scope[scope["scheme_id"].astype(int).isin(restrict_scheme_ids)]
    scores = pd.to_numeric(scope["match_score"], errors="coerce")

    if filter_mode == "Auto-OK < 100%":
        scope = scope[(scope["match_status"] == "auto_ok") & (scores < 100)]
    elif filter_mode == "Review + ambiguous":
        scope = scope[scope["match_status"].isin(("review", "ambiguous"))]
    elif filter_mode == "Auto-OK only":
        scope = scope[scope["match_status"] == "auto_ok"]

    prior: dict[int, dict] = {}
    if not decisions.empty:
        for _, d in decisions.iterrows():
            prior[int(d["scheme_id"])] = d.to_dict()

    rows: list[dict] = []
    global_label_to_code: dict[str, int] = {}
    global_label_to_score: dict[str, float] = {}
    all_prefixed_options: list[str] = [""]

    for _, r in scope.iterrows():
        sid = int(r["scheme_id"])
        et_match = et_active[et_active["scheme_id"].astype(int) == sid]
        if et_match.empty:
            continue
        et_row = et_match.iloc[0]
        et_display_name = str(et_row.get("fund_name") or r.get("et_fund_name") or "").strip()

        _, l2c, l2s = build_candidate_labels(r, mf_df, et_row, rank_fn, options_fn)
        global_label_to_code.update(l2c)
        global_label_to_score.update(l2s)

        row_prefixed: list[str] = []
        for lab in l2c:
            pl = _prefixed(sid, lab)
            row_prefixed.append(pl)
            all_prefixed_options.append(pl)

        cur_label = ""
        code_raw = None
        if map_mf_by_id and sid in map_mf_by_id:
            code_raw = map_mf_by_id[sid]
        if code_raw is None:
            code_raw = r.get("mf_scheme_code")
        if pd.notna(code_raw) and str(code_raw).strip() != "":
            code_int = int(float(code_raw))
            for lab, c in l2c.items():
                if c == code_int:
                    cur_label = lab
                    break
            if not cur_label:
                cur_label = f"{code_int} — — {str(r.get('mf_scheme_name') or '')[:60]}"

        cur_prefixed = _prefixed(sid, cur_label)
        if cur_prefixed:
            all_prefixed_options.append(cur_prefixed)
        decision = "—"
        correction = cur_prefixed
        if sid in prior:
            p = prior[sid]
            if str(p.get("decision", "")).lower() == "approved":
                decision = "Confirm"
                pc = p.get("mf_scheme_code")
                if pd.notna(pc):
                    for lab, c in l2c.items():
                        if c == int(pc):
                            correction = _prefixed(sid, lab)
                            break
            elif str(p.get("decision", "")).lower() == "rejected":
                decision = "No link"
                correction = ""

        review_reason = (reason_by_id or {}).get(sid, "")
        shared_mf: int | str = ""
        if pd.notna(code_raw) and str(code_raw).strip():
            shared_mf = int(float(code_raw))
        rows.append(
            {
                "scheme_id": sid,
                "review_reason": review_reason,
                "shared_mf_code": shared_mf,
                "et_fund_name": et_display_name,
                "mfapi_fund_name": r.get("mf_scheme_name") or "",
                "match_pct": r.get("match_score") if pd.notna(r.get("match_score")) else "",
                "match_status": r.get("match_status") or "",
                "decision": decision,
                "correction": correction,
                "_original_correction": cur_prefixed,
                "_original_decision": "—",
            }
        )

    df = pd.DataFrame(rows)
    return df, global_label_to_code, global_label_to_score, sorted(set(all_prefixed_options))


def apply_grid_save(
    edited: pd.DataFrame,
    baseline: pd.DataFrame,
    label_to_code: dict[str, int],
    label_to_score: dict[str, float],
) -> tuple[pd.DataFrame, int, int]:
    decisions = load_decisions()
    saved = 0
    skipped = 0

    base_by_id = {int(r["scheme_id"]): r for _, r in baseline.iterrows()}

    for _, row in edited.iterrows():
        sid = int(row["scheme_id"])
        base = base_by_id.get(sid)
        if base is None:
            continue

        dec = str(row.get("decision") or "—").strip()
        corr = str(row.get("correction") or "").strip()
        orig_corr = str(base.get("_original_correction") or "").strip()
        orig_dec = str(base.get("_original_decision") or "—").strip()

        changed = dec != orig_dec or corr != orig_corr
        if not changed:
            skipped += 1
            continue

        et_name = str(row.get("et_fund_name") or "")

        if dec == "No link":
            decisions = upsert_decision(
                decisions,
                scheme_id=sid,
                decision="rejected",
                mf_scheme_code=None,
                computed_score=None,
                et_fund_name=et_name,
                mf_scheme_name="",
                notes="bulk_grid no link",
            )
            saved += 1
            continue

        if dec in ("Confirm", "—") and corr:
            _, bare_label = _strip_prefix(corr)
            code = label_to_code.get(bare_label) or _parse_code_from_label(bare_label)
            if not code:
                skipped += 1
                continue
            score = label_to_score.get(bare_label, _parse_score_from_label(bare_label))
            mf_name = _name_from_label(bare_label)
            decisions = upsert_decision(
                decisions,
                scheme_id=sid,
                decision="approved",
                mf_scheme_code=int(code),
                computed_score=score,
                et_fund_name=et_name,
                mf_scheme_name=mf_name,
                notes="bulk_grid",
            )
            saved += 1

    save_decisions(decisions)
    return decisions, saved, skipped


def render_needs_review_panels(
    report: pd.DataFrame,
    scheme_map: pd.DataFrame,
    et_active: pd.DataFrame,
    mf_df: pd.DataFrame,
    decisions: pd.DataFrame,
) -> pd.DataFrame:
    """Summary tables: duplicate pairs + open matcher review. Returns enriched queue."""
    decided_ids = (
        set(decisions["scheme_id"].astype(int).tolist()) if not decisions.empty else set()
    )
    nr = enrich_needs_review_table(
        build_needs_review_table(report, scheme_map, decided_ids=decided_ids),
        et_active,
    )
    counts = needs_review_counts(report, scheme_map)
    n_open = counts["open_review_ambiguous"]
    n_pairs = counts["duplicate_pairs"]
    n_dup_rows = counts["duplicate_rows"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Open matcher review", n_open)
    c2.metric("Duplicate MF pairs", n_pairs)
    c3.metric("Funds in queue", len(nr))

    dup_detail = build_duplicate_pairs_detail(scheme_map, et_active, mf_df)
    if not dup_detail.empty:
        st.subheader("Duplicate MF-code pairs")
        st.caption(
            "Two ET funds share one MFAPI code. For each pair: **Confirm** the correct fund, "
            "set **No link** or a different **Correction** for the other, then **Save all changes**."
        )
        st.dataframe(
            dup_detail,
            use_container_width=True,
            hide_index=True,
            height=min(320, 60 + len(dup_detail) * 38),
        )

    open_detail = build_open_review_detail(nr)
    if not open_detail.empty:
        st.subheader("Open matcher review")
        st.caption("Matcher could not auto-link these — pick Confirm, No link, or a Correction below.")
        st.dataframe(
            open_detail,
            use_container_width=True,
            hide_index=True,
            height=min(360, 60 + len(open_detail) * 38),
        )

    if n_pairs and n_dup_rows:
        st.warning(
            f"**{n_pairs}** MF codes are assigned to **{n_dup_rows}** ET funds "
            f"({n_open} open matcher review). Work through the grid below."
        )
    st.info("The two tables above are read-only summaries. Edit rows in **Decisions grid** below.")
    return nr


def render_needs_review_grid(
    report: pd.DataFrame,
    et_active: pd.DataFrame,
    mf_df: pd.DataFrame,
    decisions: pd.DataFrame,
    *,
    rank_fn,
    options_fn,
    scheme_map: pd.DataFrame | None = None,
) -> None:
    """Needs-review queue: open matcher rows + duplicate MF-code pairs in fund_scheme_map."""
    scheme_map = scheme_map if scheme_map is not None else load_scheme_map()
    nr_table = render_needs_review_panels(report, scheme_map, et_active, mf_df, decisions)
    n = len(nr_table)
    if n == 0:
        st.success("Nothing left in this queue.")
        return

    reason_by_id = dict(
        zip(nr_table["scheme_id"].astype(int), nr_table["review_reason"].astype(str))
    )
    map_mf_by_id: dict[int, int] = {}
    if not scheme_map.empty:
        for _, m in scheme_map.iterrows():
            code = m.get("mf_scheme_code")
            if pd.notna(code) and str(code).strip():
                map_mf_by_id[int(m["scheme_id"])] = int(float(code))

    st.subheader("Decisions grid")
    restrict_ids = set(nr_table["scheme_id"].astype(int))
    grid, label_to_code, label_to_score, prefixed_options = build_grid_dataframe(
        report,
        et_active,
        mf_df,
        decisions,
        rank_fn=rank_fn,
        options_fn=options_fn,
        filter_mode="All in scope",
        auto_ok_below_100_fn=lambda r: r,
        restrict_scheme_ids=restrict_ids,
        reason_by_id=reason_by_id,
        map_mf_by_id=map_mf_by_id,
    )
    if len(grid) != n:
        st.error(f"Grid row count ({len(grid)}) ≠ queue ({n}). Use Refresh data in sidebar.")

    _render_grid_editor(
        grid,
        label_to_code,
        label_to_score,
        prefixed_options,
        show_ids=True,
        queue_label=f"Funds to review ({n})",
        show_review_columns=True,
    )


def render_bulk_grid(
    report: pd.DataFrame,
    et_active: pd.DataFrame,
    mf_df: pd.DataFrame,
    *,
    rank_fn,
    options_fn,
    auto_ok_below_100_fn,
    default_filter: str = "All in scope (no index)",
) -> None:
    st.subheader("Bulk grid review")
    st.caption(
        "Scan all rows at once. Change **Decision** or **Correction** only where needed, then **Save all changes**. "
        "Rows left as **—** with unchanged correction are not written."
    )

    decisions = load_decisions()

    filter_choices = [
        "All in scope (no index)",
        "Auto-OK < 100%",
        "Review + ambiguous",
        "Auto-OK only",
    ]
    default_ix = (
        filter_choices.index(default_filter)
        if default_filter in filter_choices
        else 0
    )

    f1, f2 = st.columns([2, 1])
    with f1:
        filter_mode = st.selectbox(
            "Filter rows",
            filter_choices,
            index=default_ix,
        )
    with f2:
        show_ids = st.checkbox("Show scheme_id column", value=True)

    fm = filter_mode
    if fm == "All in scope (no index)":
        fm = "All in scope"

    grid, label_to_code, label_to_score, prefixed_options = build_grid_dataframe(
        report,
        et_active,
        mf_df,
        decisions,
        rank_fn=rank_fn,
        options_fn=options_fn,
        filter_mode=fm,
        auto_ok_below_100_fn=auto_ok_below_100_fn,
        restrict_scheme_ids=None,
    )

    if grid.empty:
        st.info("No rows for this filter.")
        return

    _render_grid_editor(
        grid,
        label_to_code,
        label_to_score,
        prefixed_options,
        show_ids=show_ids,
        queue_label=f"Rows in grid ({len(grid)})",
    )


def _render_grid_editor(
    grid: pd.DataFrame,
    label_to_code: dict[str, int],
    label_to_score: dict[str, float],
    prefixed_options: list[str],
    *,
    show_ids: bool,
    queue_label: str,
    show_review_columns: bool = False,
) -> None:
    st.metric(queue_label, len(grid))

    base_cols = [
        "scheme_id",
        "review_reason",
        "shared_mf_code",
        "et_fund_name",
        "mfapi_fund_name",
        "match_pct",
        "match_status",
        "decision",
        "correction",
    ]
    if not show_review_columns:
        base_cols = [c for c in base_cols if c not in ("review_reason", "shared_mf_code")]
    editor_input = grid[[c for c in base_cols if c in grid.columns]].copy()

    column_config = {
        "scheme_id": st.column_config.NumberColumn(
            "scheme_id",
            disabled=True,
            width="small",
        ),
        "review_reason": st.column_config.TextColumn("Why review", disabled=True, width="medium"),
        "shared_mf_code": st.column_config.NumberColumn(
            "Shared MF code",
            disabled=True,
            width="small",
            help="MFAPI code — two ET funds must not keep the same code.",
        ),
        "et_fund_name": st.column_config.TextColumn("ET fund name", disabled=True, width="large"),
        "mfapi_fund_name": st.column_config.TextColumn("MFAPI fund name", disabled=True, width="large"),
        "match_pct": st.column_config.TextColumn("Match %", disabled=True, width="small"),
        "match_status": st.column_config.TextColumn("Status", disabled=True, width="small"),
        "decision": st.column_config.SelectboxColumn(
            "Decision",
            options=["—", "Confirm", "No link"],
            width="small",
            help="Confirm = use correction MF code. No link = no NAV mapping.",
        ),
        "correction": st.column_config.SelectboxColumn(
            "Correction (MFAPI pick)",
            options=prefixed_options,
            width="large",
            help="Options start with scheme_id | — pick rows matching this fund's scheme_id.",
        ),
    }
    if not show_ids:
        editor_input = editor_input.drop(columns=["scheme_id"])

    edited = st.data_editor(
        editor_input,
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        height=min(700, 80 + len(editor_input) * 35),
        key=f"mfapi_bulk_grid_{queue_label}",
    )

    st.markdown(
        "**Decision:** `—` = no change · `Confirm` = approve **Correction** · `No link` = blank. "
        "Change **Correction** only (starts with `scheme_id |`) to override MFAPI code. "
        "Enable **Show scheme_id** if save fails."
    )

    if st.button("Save all changes", type="primary"):
        full = edited.copy()
        if "scheme_id" not in full.columns:
            full = full.reset_index(drop=True)
            full["scheme_id"] = grid["scheme_id"].values
        merged = full.merge(
            grid[["scheme_id", "_original_correction", "_original_decision", "et_fund_name"]],
            on="scheme_id",
            how="left",
        )
        _, saved, skipped = apply_grid_save(merged, grid, label_to_code, label_to_score)
        st.success(f"Saved **{saved}** decision(s). Unchanged rows skipped: **{skipped}**.")
        st.rerun()

    st.divider()
    if st.button("Export overrides CSV (Batch 4)"):
        n = export_overrides_from_decisions(load_decisions())
        st.success(f"Wrote {n} approved rows → {OVERRIDES_CSV}")
