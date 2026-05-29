"""
Streamlit UI to approve/reject ET ↔ MFAPI matches (Batch 3 review).

Does not modify app.py. Run from repo root:

  streamlit run scripts/review_et_mfapi_app.py

Decisions saved to data/et_mfapi_decisions.csv (only your Approve/Reject clicks).
Export writes data/mfapi_et_manual_overrides.csv for Batch 4 apply.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from et_mfapi_decisions import (
    DECISIONS_CSV,
    OVERRIDES_CSV,
    decisions_as_override_map,
    export_overrides_from_decisions,
    load_decisions,
    save_decisions,
    upsert_decision,
)
from match_et_mfapi import (
    ET_MASTER,
    REPORT_OUT,
    _house_boost,
    _load_mf_universe,
    _nfkc_house,
    _rank_candidates,
)
from mfapi_scheme_name import normalize_match_key
from review_et_mfapi_grid import (
    render_bulk_grid,
    render_needs_review_grid,
    render_needs_review_panels,
)
from review_queue import build_needs_review_table, load_scheme_map, needs_review_counts

ROOT = Path(__file__).resolve().parents[1]
NAV_DB = ROOT / "data" / "nav" / "nav.db"
MF_UNIVERSE = ROOT / "data" / "raw" / "mfapi" / "nav_universe_schemes.csv"
NO_LINK_LABEL = "— No MFAPI link (leave blank) —"
NO_LINK_CODE = 0


@st.cache_data
def _load_report() -> pd.DataFrame:
    if not REPORT_OUT.is_file():
        raise FileNotFoundError(
            f"Missing {REPORT_OUT}. Run: python scripts/match_et_mfapi.py"
        )
    return pd.read_csv(REPORT_OUT)


@st.cache_data
def _load_et_active() -> pd.DataFrame:
    et = pd.read_csv(ET_MASTER)
    return et[et["status"].astype(str).str.upper() == "ACTIVE"].copy()


@st.cache_data
def _load_mf() -> pd.DataFrame:
    return _load_mf_universe(MF_UNIVERSE, NAV_DB)


def _parse_alts(alt_str: str) -> list[tuple[int, float]]:
    if not alt_str or not isinstance(alt_str, str):
        return []
    out: list[tuple[int, float]] = []
    for part in alt_str.split(";"):
        part = part.strip()
        if ":" not in part:
            continue
        code_s, score_s = part.split(":", 1)
        try:
            out.append((int(code_s.strip()), float(score_s.strip())))
        except ValueError:
            continue
    return out


def _candidate_options(row: pd.Series, mf_df: pd.DataFrame, et_row: pd.Series) -> list[dict]:
    """Build selectbox options: top match + alts + full re-rank top 8."""
    seen: set[int] = set()
    options: list[dict] = []

    def add(code: int, score: float, label: str) -> None:
        if code in seen:
            return
        seen.add(code)
        m = mf_df[mf_df["mf_scheme_code"].astype(int) == code]
        name = label
        cat = ""
        house = ""
        if not m.empty:
            mr = m.iloc[0]
            name = str(mr.get("scheme_name_raw") or label)
            cat = str(mr.get("scheme_category") or "")
            house = str(mr.get("fund_house") or "")
        options.append(
            {
                "code": code,
                "score": score,
                "label": f"{code} — {score:.1f}% — {name[:72]}",
                "name": name,
                "category": cat,
                "fund_house": house,
            }
        )

    code0 = row.get("mf_scheme_code")
    score0 = pd.to_numeric(row.get("match_score"), errors="coerce")
    if pd.notna(code0) and str(code0).strip() != "":
        add(int(float(code0)), float(score0) if pd.notna(score0) else 0.0, str(row.get("mf_scheme_name") or ""))

    for code, sc in _parse_alts(str(row.get("alt_candidates") or "")):
        add(code, sc, "")

    scored = _rank_candidates(et_row, mf_df)
    for code, sc, name, _ in scored[:8]:
        add(code, sc, name)

    return options


def _auto_ok_below_100(report: pd.DataFrame) -> pd.DataFrame:
    scores = pd.to_numeric(report["match_score"], errors="coerce")
    sub = report[(report["match_status"] == "auto_ok") & (scores < 100)].copy()
    return sub.sort_values("match_score", kind="mergesort")


def _house_warning(et_house: str, mf_house: str) -> str | None:
    eh, mh = _nfkc_house(et_house), _nfkc_house(mf_house)
    if not eh or not mh:
        return None
    if eh == mh or eh in mh or mh in eh:
        return None
    boost = _house_boost(et_house, mf_house)
    if boost >= 3:
        return None
    return f"Fund house mismatch: ET **{et_house}** vs MF **{mf_house}**"


def main() -> None:
    st.set_page_config(page_title="ET ↔ MFAPI Match Review", layout="wide")
    st.title("ET Money ↔ MFAPI match review")
    st.caption(
        "Approve or reject links for Batch 3. "
        f"Decisions → `{DECISIONS_CSV.name}`. "
        "Does not change the FundLens app."
    )

    try:
        report = _load_report()
        et_active = _load_et_active()
        mf_df = _load_mf()
    except FileNotFoundError as exc:
        st.error(str(exc))
        return

    scheme_map = load_scheme_map()
    decisions = load_decisions()
    nr_counts = needs_review_counts(report, scheme_map)
    n_review = nr_counts["unique_needs_review"]

    tab_needs, tab_grid, tab_card = st.tabs(
        [
            f"Needs my review ({n_review})",
            "Grid (all funds)",
            "Card (one fund)",
        ]
    )

    with tab_needs:
        render_needs_review_grid(
            report,
            et_active,
            mf_df,
            decisions,
            rank_fn=_rank_candidates,
            options_fn=_candidate_options,
            scheme_map=scheme_map,
        )

    with tab_grid:
        render_bulk_grid(
            report,
            et_active,
            mf_df,
            rank_fn=_rank_candidates,
            options_fn=_candidate_options,
            auto_ok_below_100_fn=_auto_ok_below_100,
            default_filter="All in scope (no index)",
        )

    with tab_card:
        _render_card_mode(report, et_active, mf_df, scheme_map, nr_counts)


def _render_card_mode(
    report: pd.DataFrame,
    et_active: pd.DataFrame,
    mf_df: pd.DataFrame,
    scheme_map: pd.DataFrame,
    nr_counts: dict,
) -> None:
    decisions = load_decisions()
    decided_ids = set(decisions["scheme_id"].astype(int).tolist()) if not decisions.empty else set()

    excluded = report[report["match_status"] == "excluded_index"].copy()
    auto_ok = report[report["match_status"] == "auto_ok"].copy()
    auto_ok_lo = _auto_ok_below_100(report)
    auto_ok_lo_pending = auto_ok_lo[
        ~auto_ok_lo["scheme_id"].astype(int).isin(decided_ids)
    ].copy()
    needs = report[
        ~report["match_status"].isin(("auto_ok", "excluded_index", "approved"))
    ].copy()
    pending = needs[~needs["scheme_id"].astype(int).isin(decided_ids)].copy()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Auto-OK (skip)", len(auto_ok))
    c2.metric("Auto-OK < 100%", len(auto_ok_lo))
    c3.metric("< 100% pending", len(auto_ok_lo_pending))
    c4.metric("Needs decision", len(pending))
    c5.metric("Excluded index", len(excluded))

    with st.sidebar:
        st.header("Queue")
        st.metric("Needs review (total)", nr_counts["unique_needs_review"])

        view = st.radio(
            "Show",
            [
                "Needs my review (review + dup pairs)",
                "Auto-OK < 100% (spot check)",
                "Pending",
                "Review + ambiguous",
                "No match",
                "All needs review",
                "Decided",
                "Auto-OK (read-only)",
                "Excluded index (read-only)",
            ],
            index=0,
        )
        show_decided_spot = False
        if view == "Auto-OK < 100% (spot check)":
            show_decided_spot = st.checkbox("Include already decided", value=False)
        if st.button("Refresh data"):
            st.cache_data.clear()
            st.rerun()

        st.divider()
        st.header("Export")
        n_ap = len(decisions[decisions["decision"] == "approved"]) if not decisions.empty else 0
        st.write(f"Approved: **{n_ap}**")
        if st.button("Export overrides CSV (Batch 4)"):
            n = export_overrides_from_decisions(decisions)
            st.success(f"Wrote {n} rows → {OVERRIDES_CSV}")

        if DECISIONS_CSV.is_file() and st.button("Clear all decisions", type="secondary"):
            DECISIONS_CSV.unlink()
            st.cache_data.clear()
            st.rerun()

        st.divider()
        st.markdown(
            "**Tips**\n"
            "- Pick the correct fund from **close matches**, or choose **No link**.\n"
            "- **Save decision** stores your dropdown choice.\n"
            "- Wrong auto-suggestion → pick another row, then Save.\n"
            "- Check fund house when score < 100%."
        )

    if view == "Auto-OK (read-only)":
        st.info(f"{len(auto_ok)} funds are auto_ok (≥95% or 100% rule). No action needed unless you disagree.")
        st.dataframe(
            auto_ok[
                ["scheme_id", "et_fund_name", "mf_scheme_code", "match_score", "et_fund_house", "mf_scheme_name"]
            ],
            use_container_width=True,
            height=600,
        )
        return

    if view == "Excluded index (read-only)":
        st.info(
            f"{len(excluded)} index funds are out of scope (not in MFAPI 881 NAV universe). "
            "No MFAPI link; ET holdings still work for Analyze."
        )
        st.dataframe(
            excluded[["scheme_id", "et_fund_name", "et_category", "et_fund_house"]],
            use_container_width=True,
            height=600,
        )
        return

    if view == "Decided":
        st.dataframe(decisions, use_container_width=True, height=600)
        return

    if view == "Needs my review (review + dup pairs)":
        nr = render_needs_review_panels(report, scheme_map, et_active, mf_df, decisions)
        st.caption("After saving, run: `python scripts/apply_et_mfapi_map.py`")
        nr_ids = set(nr["scheme_id"].astype(int)) if not nr.empty else set()
        queue = report[report["scheme_id"].astype(int).isin(nr_ids)].copy()
        if not nr.empty:
            reasons = nr.set_index("scheme_id")["review_reason"].astype(str)
            queue["review_reason"] = queue["scheme_id"].astype(int).map(reasons)
    elif view == "Auto-OK < 100% (spot check)":
        st.warning(
            f"**{len(auto_ok_lo)}** funds were auto-linked at **95–99.99%** (not a perfect name match). "
            "Confirm the MFAPI scheme below or pick another / no link."
        )
        table_cols = [
            "scheme_id",
            "et_fund_name",
            "mf_scheme_code",
            "match_score",
            "score_gap",
            "et_fund_house",
            "mf_scheme_name",
        ]
        st.dataframe(auto_ok_lo[table_cols], use_container_width=True, height=220)
        queue = auto_ok_lo.copy()
        if not show_decided_spot:
            queue = queue[~queue["scheme_id"].astype(int).isin(decided_ids)]
    elif view == "Pending":
        queue = pending
    elif view == "Review + ambiguous":
        queue = pending[pending["match_status"].isin(("review", "ambiguous", "manual"))]
    elif view == "No match":
        queue = pending[pending["match_status"] == "no_match"]
    else:
        queue = pending

    if st.session_state.get("last_view") != view:
        st.session_state.qi = 0
        st.session_state.last_view = view

    if queue.empty:
        st.success("No pending funds in this queue. Export overrides when ready.")
        if not decisions.empty:
            st.dataframe(decisions, use_container_width=True)
        return

    # Navigate by index in session
    if "qi" not in st.session_state:
        st.session_state.qi = 0
    st.session_state.qi = min(st.session_state.qi, len(queue) - 1)
    st.session_state.qi = max(0, st.session_state.qi)

    nav1, nav2, nav3 = st.columns([1, 2, 1])
    with nav1:
        if st.button("← Previous") and st.session_state.qi > 0:
            st.session_state.qi -= 1
            st.rerun()
    with nav3:
        if st.button("Next →") and st.session_state.qi < len(queue) - 1:
            st.session_state.qi += 1
            st.rerun()
    with nav2:
        pick_i = st.number_input(
            f"Fund {st.session_state.qi + 1} of {len(queue)}",
            min_value=1,
            max_value=len(queue),
            value=st.session_state.qi + 1,
            step=1,
        )
        if int(pick_i) - 1 != st.session_state.qi:
            st.session_state.qi = int(pick_i) - 1
            st.rerun()

    row = queue.iloc[st.session_state.qi]
    sid = int(row["scheme_id"])
    et_row = et_active[et_active["scheme_id"].astype(int) == sid]
    if et_row.empty:
        st.error(f"scheme_id {sid} not in ET ACTIVE master")
        return
    et_row = et_row.iloc[0]

    st.subheader(row["et_fund_name"])
    reason = row.get("review_reason", "")
    st.write(
        f"**scheme_id** `{sid}` · **ET category** {row.get('et_category')} · "
        f"**ET house** {row.get('et_fund_house')} · **status** `{row.get('match_status')}` · "
        f"**score** {row.get('match_score')} · **gap** {row.get('score_gap')}"
        + (f" · **reason** `{reason}`" if reason and str(reason) != "nan" else "")
    )
    if str(reason) == "duplicate_mf_code":
        st.error(
            "This fund shares an MFAPI code with another ET fund in `fund_scheme_map.csv`. "
            "Pick the correct unique MF scheme or **No link** for one of the pair."
        )

    if view == "Auto-OK < 100% (spot check)":
        st.markdown(
            "Auto-linked below 100%. Confirm the suggested MF scheme or choose another / **No link**."
        )
    else:
        st.markdown(
            "If the suggested match is wrong, pick the correct fund from **close matches** below. "
            "If none fit, choose **No MFAPI link**."
        )

    options = _candidate_options(row, mf_df, et_row)
    no_link_option = {
        "code": NO_LINK_CODE,
        "score": 0.0,
        "label": NO_LINK_LABEL,
        "name": "",
        "category": "",
        "fund_house": "",
    }
    chosen: dict = no_link_option.copy()

    if not options:
        st.warning("No close matches from the matcher. Enter a code or leave blank.")
        manual_entry = int(
            st.number_input(
                "MF scheme code (optional; 0 = no link)",
                min_value=0,
                step=1,
                value=0,
                key=f"manual_{sid}",
            )
        )
        if manual_entry > 0:
            m = mf_df[mf_df["mf_scheme_code"].astype(int) == manual_entry]
            chosen = {
                "code": manual_entry,
                "score": 0.0,
                "name": str(m.iloc[0]["scheme_name_raw"]) if not m.empty else "",
                "category": str(m.iloc[0].get("scheme_category", "")) if not m.empty else "",
                "fund_house": str(m.iloc[0].get("fund_house", "")) if not m.empty else "",
            }
    else:
        pick_list = [no_link_option] + options
        labels = [o["label"] for o in pick_list]
        default_ix = 1 if len(pick_list) > 1 else 0
        sel = st.selectbox(
            "Close matches (MFAPI Direct–Growth)",
            labels,
            index=default_ix,
            key=f"pick_{sid}",
        )
        chosen = pick_list[labels.index(sel)]
        if chosen["code"] != NO_LINK_CODE:
            st.write(f"**Category:** {chosen.get('category', '')}")
            warn = _house_warning(
                str(row.get("et_fund_house") or ""), str(chosen.get("fund_house") or "")
            )
            if warn:
                st.warning(warn)
            if float(chosen.get("score") or 0) < 95:
                st.info(f"Match score for this pick: **{float(chosen['score']):.1f}%**")
        else:
            st.info("No NAV link will be saved for this fund (ET holdings only).")

    manual_code = int(chosen.get("code") or 0)

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Save decision", type="primary", use_container_width=True):
            if manual_code == NO_LINK_CODE:
                decisions = upsert_decision(
                    decisions,
                    scheme_id=sid,
                    decision="rejected",
                    mf_scheme_code=None,
                    computed_score=None,
                    et_fund_name=str(row["et_fund_name"]),
                    mf_scheme_name="",
                    notes="no MFAPI link",
                )
            else:
                note = (
                    "spot_check auto_ok<100"
                    if view == "Auto-OK < 100% (spot check)"
                    else ""
                )
                decisions = upsert_decision(
                    decisions,
                    scheme_id=sid,
                    decision="approved",
                    mf_scheme_code=manual_code,
                    computed_score=float(chosen.get("score") or 0),
                    et_fund_name=str(row["et_fund_name"]),
                    mf_scheme_name=str(chosen.get("name") or ""),
                    notes=note,
                )
            save_decisions(decisions)
            if st.session_state.qi < len(queue) - 1:
                st.session_state.qi += 1
            st.rerun()
    with col_b:
        if st.button("Skip (decide later)", use_container_width=True):
            if st.session_state.qi < len(queue) - 1:
                st.session_state.qi += 1
            st.rerun()

    with st.expander("ET vs MF name keys"):
        mf_name = str(chosen.get("name") or "") if manual_code else ""
        st.code(
            f"ET: {normalize_match_key(str(row['et_fund_name']))}\n"
            f"MF: {normalize_match_key(mf_name)}"
        )


if __name__ == "__main__":
    main()
