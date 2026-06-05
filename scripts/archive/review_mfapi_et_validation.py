"""Scrape validation panel — shared by match review + validate apps."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from et_mfapi_scrape_lib import (  # noqa: E402
    ET_MASTER,
    HOLDINGS,
    SCHEME_MAP,
    fund_name_match_score,
    load_mfapi_row,
    resolve_et_for_mfapi,
    run_one_fund_scrape,
)
from mfapi_scheme_name import mf_fund_name_cleaned  # noqa: E402

SAMPLE_MF_CODE = 103490


def validation_status(mf_code: int, report_row: pd.Series | None = None) -> dict:
    """Live status from CSVs for one MFAPI code."""
    master = pd.read_csv(ET_MASTER) if ET_MASTER.is_file() else pd.DataFrame()
    scheme_map = pd.read_csv(SCHEME_MAP) if SCHEME_MAP.is_file() else pd.DataFrame()
    holdings = pd.read_csv(HOLDINGS) if HOLDINGS.is_file() else pd.DataFrame()

    et_sid: int | None = None
    et_name = ""
    if not scheme_map.empty:
        m = scheme_map[scheme_map["mf_scheme_code"].astype(int) == int(mf_code)]
        if not m.empty:
            et_sid = int(m.iloc[0]["scheme_id"])
            et_name = str(m.iloc[0].get("et_fund_name") or "")

    if et_sid is None and report_row is not None:
        raw = report_row.get("scheme_id")
        if pd.notna(raw) and str(raw).strip():
            et_sid = int(float(raw))
            et_name = str(report_row.get("et_fund_name") or "")

    in_master = False
    master_status = ""
    if et_sid and not master.empty:
        hit = master[master["scheme_id"].astype(int) == et_sid]
        if not hit.empty:
            in_master = True
            master_status = str(hit.iloc[0].get("status") or "")

    n_holdings = 0
    if et_sid and not holdings.empty:
        n_holdings = len(holdings[holdings["scheme_id"].astype(int) == et_sid])

    return {
        "mf_scheme_code": int(mf_code),
        "et_scheme_id": et_sid or "",
        "et_fund_name": et_name,
        "in_fund_scheme_map": not scheme_map.empty
        and int(mf_code) in set(scheme_map["mf_scheme_code"].astype(int)),
        "in_fund_master_auto": in_master,
        "et_master_status": master_status,
        "holdings_rows": n_holdings,
    }


def report_row_for_mf(report: pd.DataFrame, mf_code: int) -> pd.Series | None:
    m = report[report["mf_scheme_code"].astype(int) == int(mf_code)]
    if m.empty:
        return None
    return m.iloc[0]


def enrich_report_with_validation(report: pd.DataFrame) -> pd.DataFrame:
    """Add scrape validation columns for grid display."""
    rows = []
    for _, r in report.iterrows():
        mf = int(r["mf_scheme_code"])
        st_ = validation_status(mf, r)
        rows.append({**r.to_dict(), **st_})
    return pd.DataFrame(rows)


def render_row_validation_panel(
    mf_code: int,
    report: pd.DataFrame,
    *,
    show_scrape_button: bool = True,
) -> None:
    """Full validation UI for one MFAPI fund."""
    try:
        mf_row = load_mfapi_row(int(mf_code))
    except (ValueError, FileNotFoundError) as exc:
        st.error(str(exc))
        return

    rep = report_row_for_mf(report, mf_code)
    cleaned = mf_fund_name_cleaned(str(mf_row.get("scheme_name_raw") or ""))
    st_ = validation_status(mf_code, rep)

    st.subheader(f"MFAPI {mf_code} · {cleaned}")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("In scheme_map", "Yes" if st_["in_fund_scheme_map"] else "No")
    c2.metric("In ET master", "Yes" if st_["in_fund_master_auto"] else "No")
    c3.metric("ET status", st_["et_master_status"] or "—")
    c4.metric("Holdings rows", st_["holdings_rows"])
    c5.metric("Report match %", rep.get("match_score") if rep is not None else "—")

    with st.expander("MFAPI row", expanded=False):
        st.write(f"**Raw:** {mf_row.get('scheme_name_raw')}")
        st.write(f"**Category:** {mf_row.get('scheme_category')}")
        if rep is not None:
            rep_view = pd.DataFrame([rep.to_dict()]).T.rename(columns={0: "value"})
            rep_view["value"] = rep_view["value"].map(
                lambda v: "" if pd.isna(v) else str(v)
            )
            st.dataframe(rep_view, use_container_width=True)

    st.markdown("**ET lookup** (live listing search)")
    try:
        et_hit = resolve_et_for_mfapi(mf_row)
        st.success(
            f"ET **{et_hit['et_fund_name']}** · id **{et_hit['scheme_id']}** · "
            f"match **{et_hit['match_score']}%**"
        )
        if st_["et_scheme_id"] and int(st_["et_scheme_id"]) != int(et_hit["scheme_id"]):
            st.warning(
                f"Mapped ET id **{st_['et_scheme_id']}** differs from fresh lookup **{et_hit['scheme_id']}**"
            )
    except LookupError as exc:
        st.error(str(exc))
        et_hit = None

    if st_["et_scheme_id"]:
        sid = int(st_["et_scheme_id"])
        master = pd.read_csv(ET_MASTER) if ET_MASTER.is_file() else pd.DataFrame()
        if not master.empty:
            m = master[master["scheme_id"].astype(int) == sid]
            if not m.empty:
                st.markdown("**fund_master_auto**")
                st.dataframe(m, use_container_width=True)
        if HOLDINGS.is_file():
            h = pd.read_csv(HOLDINGS)
            h = h[h["scheme_id"].astype(int) == sid]
            if not h.empty:
                st.markdown("**Holdings (top 15)**")
                st.dataframe(
                    h[["stock_name", "sector", "allocation_percent"]].head(15),
                    use_container_width=True,
                )

    if show_scrape_button:
        st.markdown("**Run scrape**")
        dry = st.checkbox("Dry run", value=False, key=f"dry_{mf_code}")
        if st.button("Scrape this fund", type="primary", key=f"scrape_{mf_code}"):
            with st.spinner("Scraping…"):
                try:
                    result = run_one_fund_scrape(int(mf_code), dry_run=dry)
                    st.cache_data.clear()
                    st.success(
                        f"Done · holdings **{result['holdings_rows']}** · "
                        f"ET **{result['et_lookup']['scheme_id']}**"
                    )
                    st.rerun()
                except Exception as exc:
                    st.exception(exc)
