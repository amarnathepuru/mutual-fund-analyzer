"""
Review all batch-scrape auto-mappings in one table (~206 funds).

  python -m streamlit run scripts/archive/review_mfapi_batch_scrape.py --server.port 8503

Saves to data/mfapi_et_decisions.csv → apply with python scripts/apply_mfapi_et_map.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from match_mfapi_et import ET_MASTER  # noqa: E402
from mfapi_et_decisions import export_approved_for_apply, load_decisions  # noqa: E402
from review_mfapi_batch_grid import load_batch_queue, render_batch_bulk_table  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCHEME_MAP = ROOT / "data/fund_scheme_map.csv"


@st.cache_data
def _load_et_active() -> pd.DataFrame:
    et = pd.read_csv(ET_MASTER)
    return et[et["status"].astype(str).str.upper() == "ACTIVE"].copy()


def main() -> None:
    st.set_page_config(page_title="Batch scrape review", layout="wide")
    st.title("Batch scrape — confirm all mappings")
    st.caption(
        "Review **every** auto-scraped fund in one scrollable table. "
        "154 manual mappings are already in `fund_scheme_map.csv` and are not listed here."
    )

    try:
        queue = load_batch_queue()
        et_active = _load_et_active()
    except FileNotFoundError as exc:
        st.error(str(exc))
        return

    scheme_map = pd.read_csv(SCHEME_MAP) if SCHEME_MAP.is_file() else pd.DataFrame()
    decisions = load_decisions()

    batch_decided: set[int] = set()
    if not decisions.empty:
        mask = decisions["notes"].astype(str).str.contains("batch_scrape", case=False, na=False)
        batch_decided = set(decisions.loc[mask, "mf_scheme_code"].astype(int))

    with st.sidebar:
        st.metric("Batch funds", len(queue))
        st.metric("Saved in decisions", len(batch_decided))
        st.metric("Pending", len(queue) - len(batch_decided))

        search = st.text_input("Filter by name", "")
        hide_done = st.checkbox("Hide already saved", value=False)
        sort_by = st.selectbox(
            "Sort",
            ["MFAPI name (A–Z)", "Name match % (low first)", "Name match % (high first)"],
        )

        if st.button("Refresh data"):
            load_batch_queue.clear()
            _load_et_active.clear()
            if "batch_grid_df" in st.session_state:
                del st.session_state["batch_grid_df"]
            st.rerun()

        if st.button("Export approved CSV"):
            n = export_approved_for_apply(decisions)
            st.success(f"Wrote {n} approved rows")

    show = queue.copy()
    if hide_done:
        show = show[~show["mf_scheme_code"].astype(int).isin(batch_decided)]
    if search.strip():
        q = search.strip().lower()
        mask = (
            show["mfapi_cleaned"].astype(str).str.lower().str.contains(q, na=False)
            | show["scraped_et_fund_name"].astype(str).str.lower().str.contains(q, na=False)
        )
        show = show[mask]

    if sort_by == "Name match % (low first)":
        show = show.sort_values("name_match_pct", ascending=True)
    elif sort_by == "Name match % (high first)":
        show = show.sort_values("name_match_pct", ascending=False)
    else:
        show = show.sort_values("mfapi_cleaned")

    show = show.reset_index(drop=True)
    st.subheader(f"{len(show)} funds", anchor=False)

    render_batch_bulk_table(show, et_active, scheme_map, batch_decided=batch_decided)


if __name__ == "__main__":
    main()
