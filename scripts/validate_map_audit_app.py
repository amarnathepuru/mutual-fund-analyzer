"""
Browse fund_scheme_map audit issues + per-fund scrape validation.

  python -m streamlit run scripts/validate_map_audit_app.py --server.port 8505

Regenerate audit:
  python scripts/audit_fund_scheme_map.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from match_mfapi_et import REPORT_OUT  # noqa: E402
from review_mfapi_et_validation import render_row_validation_panel  # noqa: E402

ROOT = SCRIPTS.parent
REVIEW_CSV = ROOT / "data/reports/fund_scheme_map_audit_review.csv"
FULL_AUDIT = ROOT / "data/reports/fund_scheme_map_audit.csv"


@st.cache_data(ttl=60)
def _load_review() -> pd.DataFrame:
    if not REVIEW_CSV.is_file():
        raise FileNotFoundError(
            f"Missing {REVIEW_CSV}. Run: python scripts/audit_fund_scheme_map.py"
        )
    return pd.read_csv(REVIEW_CSV, encoding="utf-8-sig")


@st.cache_data
def _load_report() -> pd.DataFrame:
    if REPORT_OUT.is_file():
        return pd.read_csv(REPORT_OUT)
    return pd.DataFrame()


def main() -> None:
    st.set_page_config(page_title="Map audit review", layout="wide")
    st.title("Fund scheme map — audit review")
    st.caption(
        "Review discrepancies from `audit_fund_scheme_map.py`. "
        "Select a row to open scrape validation for that MFAPI code."
    )

    try:
        review = _load_review()
    except FileNotFoundError as exc:
        st.error(str(exc))
        return

    report = _load_report()

    with st.sidebar:
        st.metric("Review queue", len(review))
        types = ["All"] + sorted(review["issue_type"].dropna().unique().tolist())
        issue_filter = st.selectbox("Issue type", types)
        sev = st.multiselect(
            "Severity",
            ["error", "warn", "info"],
            default=["error", "warn"],
        )
        search = st.text_input("Filter name / MF code", "")
        if st.button("Refresh audit"):
            st.cache_data.clear()
            st.rerun()
        if st.button("Re-run audit script"):
            import subprocess

            r = subprocess.run(
                [sys.executable, str(SCRIPTS / "audit_fund_scheme_map.py")],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            st.code(r.stdout or r.stderr or "(no output)")
            st.cache_data.clear()
            st.rerun()

        st.divider()
        st.markdown("**Counts by issue**")
        st.dataframe(
            review.groupby(["severity", "issue_type"]).size().reset_index(name="n"),
            hide_index=True,
            height=220,
        )

    show = review.copy()
    if issue_filter != "All":
        show = show[show["issue_type"] == issue_filter]
    if sev:
        show = show[show["severity"].isin(sev)]
    if search.strip():
        q = search.strip().lower()
        show = show[
            show["mfapi_name"].astype(str).str.lower().str.contains(q, na=False)
            | show["et_fund_name"].astype(str).str.lower().str.contains(q, na=False)
            | show["mf_scheme_code"].astype(str).str.contains(q, na=False)
            | show["detail"].astype(str).str.lower().str.contains(q, na=False)
        ]

    st.subheader(f"{len(show)} issues")
    st.dataframe(
        show[
            [
                "severity",
                "issue_type",
                "mf_scheme_code",
                "scheme_id",
                "name_match_pct",
                "mfapi_name",
                "et_fund_name",
                "detail",
                "notes",
            ]
        ],
        use_container_width=True,
        height=min(520, 80 + len(show) * 32),
        hide_index=True,
    )

    codes = show["mf_scheme_code"].dropna().astype(str).unique().tolist()
    pick = st.selectbox(
        "Inspect MFAPI fund (scrape validation)",
        options=[""] + codes,
        format_func=lambda x: x if x else "— pick a row —",
    )
    if pick and str(pick).strip().isdigit():
        mf = int(float(pick))
        st.divider()
        render_row_validation_panel(mf, report, show_scrape_button=True)


if __name__ == "__main__":
    main()
