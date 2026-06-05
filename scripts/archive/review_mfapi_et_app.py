"""
Streamlit review: MFAPI-only funds → ET Money (4-column grid).

  streamlit run scripts/review_mfapi_et_app.py --server.port 8502
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from match_mfapi_et import ET_MASTER, REPORT_OUT  # noqa: E402
from mfapi_et_decisions import (  # noqa: E402
    DECISIONS_CSV,
    EXPORT_CSV,
    export_approved_for_apply,
    load_decisions,
)
from review_mfapi_et_grid import render_mfapi_bulk_grid  # noqa: E402
from review_mfapi_et_validation import SAMPLE_MF_CODE, render_row_validation_panel  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCHEME_MAP = ROOT / "data" / "fund_scheme_map.csv"


@st.cache_data
def _load_report() -> pd.DataFrame:
    if not REPORT_OUT.is_file():
        raise FileNotFoundError(f"Missing {REPORT_OUT}. Run: python scripts/match_mfapi_et.py")
    return pd.read_csv(REPORT_OUT)


@st.cache_data
def _load_et_active() -> pd.DataFrame:
    et = pd.read_csv(ET_MASTER)
    return et[et["status"].astype(str).str.upper() == "ACTIVE"].copy()


@st.cache_data
def _load_scheme_map() -> pd.DataFrame:
    if not SCHEME_MAP.is_file():
        return pd.DataFrame()
    return pd.read_csv(SCHEME_MAP)


def _build_queue(
    report: pd.DataFrame,
    filter_mode: str,
    decided_codes: set[int],
    hide_decided: bool,
) -> pd.DataFrame:
    if filter_mode == "Decided":
        return report.iloc[0:0]
    queue = report.copy()
    if filter_mode == "Pending only":
        queue = queue[~queue["mf_scheme_code"].astype(int).isin(decided_codes)]
    elif filter_mode == "Review + ambiguous":
        queue = queue[queue["match_status"].isin(("review", "ambiguous"))]
    elif filter_mode == "No match (algo)":
        queue = queue[queue["match_status"] == "no_match"]
    elif filter_mode == "Auto-OK":
        queue = queue[queue["match_status"] == "auto_ok"]
    elif filter_mode.startswith("Sample:"):
        queue = queue[queue["mf_scheme_code"].astype(int) == SAMPLE_MF_CODE]
    if hide_decided and filter_mode not in ("Decided",) and not filter_mode.startswith("Sample:"):
        queue = queue[~queue["mf_scheme_code"].astype(int).isin(decided_codes)]
    return queue


def main() -> None:
    st.set_page_config(page_title="MFAPI → ET Match Review", layout="wide")
    st.title("MFAPI → ET Money match review")

    try:
        report = _load_report()
        et_active = _load_et_active()
        scheme_map = _load_scheme_map()
    except FileNotFoundError as exc:
        st.error(str(exc))
        return

    decisions = load_decisions()
    decided_codes = (
        set(decisions["mf_scheme_code"].astype(int).tolist()) if not decisions.empty else set()
    )

    with st.sidebar:
        st.header("Queue")
        st.metric("MFAPI-only", len(report))
        st.metric("Pending", len(report) - len(decided_codes))

        filter_mode = st.selectbox(
            "Filter",
            [
                "Pending only",
                "All 490",
                "Review + ambiguous",
                "No match (algo)",
                "Auto-OK",
                f"Sample: Quantum Value ({SAMPLE_MF_CODE})",
                "Decided",
            ],
            index=0,
        )
        hide_decided = st.checkbox(
            "Hide decided",
            value=True,
            disabled=filter_mode.startswith("Sample:"),
        )
        if st.button("Refresh"):
            st.cache_data.clear()
            st.rerun()
        if st.button("Export approved"):
            n = export_approved_for_apply(decisions)
            st.success(f"{n} rows → {EXPORT_CSV.name}")

        with st.expander("Scrape validation (sample)"):
            render_row_validation_panel(SAMPLE_MF_CODE, report, show_scrape_button=True)

    if filter_mode == "Decided":
        st.dataframe(decisions, use_container_width=True, height=700)
        return

    queue = _build_queue(report, filter_mode, decided_codes, hide_decided)
    if queue.empty:
        st.success("Nothing in this queue.")
        return

    render_mfapi_bulk_grid(
        queue,
        et_active,
        scheme_map,
        queue_label=filter_mode,
    )


if __name__ == "__main__":
    main()
