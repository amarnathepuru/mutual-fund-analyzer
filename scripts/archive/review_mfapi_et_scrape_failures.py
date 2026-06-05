"""
Review batch scrape failures and add ET hints for retry.

  streamlit run scripts/review_mfapi_et_scrape_failures.py --server.port 8504
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from et_mfapi_scrape_lib import SCRAPE_HINTS  # noqa: E402

PROGRESS_CSV = ROOT / "data" / "reports" / "mfapi_et_scrape_batch_progress.csv"
FAILURES_CSV = ROOT / "data" / "reports" / "mfapi_et_scrape_failures.csv"
HINT_COLS = ["mf_scheme_code", "et_slug", "et_scheme_id", "notes"]

ET_URL_RE = re.compile(
    r"etmoney\.com/mutual-funds/([a-z0-9\-]+)/(\d+)",
    re.IGNORECASE,
)


def parse_et_money_url(text: str) -> tuple[str, int] | None:
    m = ET_URL_RE.search(str(text or "").strip())
    if not m:
        return None
    return m.group(1), int(m.group(2))


def _read_hints() -> pd.DataFrame:
    if not SCRAPE_HINTS.is_file():
        return pd.DataFrame(columns=HINT_COLS)
    h = pd.read_csv(SCRAPE_HINTS, encoding="utf-8-sig")
    for c in HINT_COLS:
        if c not in h.columns:
            h[c] = ""
    return h[HINT_COLS]


def _save_hint(mf_code: int, slug: str, scheme_id: int, notes: str) -> None:
    h = _read_hints()
    if not h.empty:
        h = h[h["mf_scheme_code"].astype(int) != int(mf_code)]
    row = pd.DataFrame(
        [
            {
                "mf_scheme_code": int(mf_code),
                "et_slug": slug.strip(),
                "et_scheme_id": int(scheme_id),
                "notes": (notes or "review UI").strip(),
            }
        ]
    )
    h = pd.concat([h, row], ignore_index=True)
    SCRAPE_HINTS.parent.mkdir(parents=True, exist_ok=True)
    h.to_csv(SCRAPE_HINTS, index=False, encoding="utf-8-sig")
    import et_mfapi_scrape_lib as lib

    lib._HINTS_CACHE = None


@st.cache_data
def _load_failures() -> pd.DataFrame:
    df = pd.read_csv(PROGRESS_CSV, encoding="utf-8-sig")
    fail = df[df["status"].astype(str).str.lower() == "lookup_failed"].copy()
    fail = fail.sort_values(["mf_category", "mfapi_name_cleaned"]).reset_index(drop=True)
    fail["etmoney_search"] = fail["mfapi_name_cleaned"].map(
        lambda n: f"https://www.google.com/search?q={quote_plus('site:etmoney.com ' + str(n) + ' direct growth')}"
    )
    FAILURES_CSV.parent.mkdir(parents=True, exist_ok=True)
    fail[
        [
            "mf_scheme_code",
            "mfapi_name_cleaned",
            "mf_category",
            "error",
            "scraped_at",
            "etmoney_search",
        ]
    ].to_csv(FAILURES_CSV, index=False, encoding="utf-8-sig")
    return fail


def main() -> None:
    st.set_page_config(page_title="Scrape failures review", layout="wide")
    st.title("MFAPI → ET batch scrape failures")

    if not PROGRESS_CSV.is_file():
        st.error(f"Missing {PROGRESS_CSV}. Run the batch scrape first.")
        return

    if "hint_msg" not in st.session_state:
        st.session_state.hint_msg = ""
    if "hint_err" not in st.session_state:
        st.session_state.hint_err = ""

    fail = _load_failures()
    hints = _read_hints()
    hinted_codes = (
        set(hints["mf_scheme_code"].astype(int).tolist()) if not hints.empty else set()
    )

    if st.session_state.hint_msg:
        st.success(st.session_state.hint_msg)
        st.session_state.hint_msg = ""
    if st.session_state.hint_err:
        st.error(st.session_state.hint_err)
        st.session_state.hint_err = ""

    st.caption(
        f"**{len(fail)}** failures · hints file: `{SCRAPE_HINTS}` · "
        "retry: `python scripts/scrape_mfapi_et_batch.py --delay 2`"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Failures", len(fail))
    c2.metric("Hints saved", len(hinted_codes))
    c3.metric("Categories", fail["mf_category"].nunique())
    c4.metric("Liquid failures", len(fail[fail["mf_category"] == "Debt Scheme - Liquid Fund"]))

    with st.sidebar:
        st.header("Filter")
        cats = ["(all)"] + sorted(fail["mf_category"].dropna().astype(str).unique().tolist())
        cat_pick = st.selectbox("MFAPI category", cats, index=0)
        q = st.text_input("Search fund name", "")
        only_no_hint = st.checkbox("Only without hint", value=False)
        if FAILURES_CSV.is_file():
            st.download_button(
                "Download failures CSV",
                data=FAILURES_CSV.read_bytes(),
                file_name=FAILURES_CSV.name,
                mime="text/csv",
            )
        if not hints.empty:
            st.markdown("**Saved hints**")
            st.dataframe(hints, hide_index=True, use_container_width=True)

    view = fail.copy()
    if cat_pick != "(all)":
        view = view[view["mf_category"] == cat_pick]
    if q.strip():
        view = view[
            view["mfapi_name_cleaned"].str.contains(q.strip(), case=False, na=False)
        ]
    if only_no_hint:
        view = view[~view["mf_scheme_code"].astype(int).isin(hinted_codes)]

    st.subheader(f"Showing {len(view)} of {len(fail)} failures")

    st.dataframe(
        view[
            ["mf_scheme_code", "mfapi_name_cleaned", "mf_category", "etmoney_search"]
        ],
        column_config={
            "mf_scheme_code": st.column_config.NumberColumn("MF code", format="%d"),
            "mfapi_name_cleaned": st.column_config.TextColumn("MFAPI name", width="large"),
            "mf_category": st.column_config.TextColumn("Category", width="medium"),
            "etmoney_search": st.column_config.LinkColumn(
                "Search ET",
                display_text="Google",
            ),
        },
        hide_index=True,
        width="stretch",
        height=min(400, 80 + len(view) * 35),
    )

    st.markdown("### Save ET hint")
    st.info(
        "Paste the full **ET Money Direct-Growth** URL, e.g. "
        "`https://www.etmoney.com/mutual-funds/quantum-liquid-fund-direct-growth/3196` "
        "— or enter slug + scheme id separately. **Scheme id must be > 0.**"
    )

    options = view["mf_scheme_code"].astype(int).tolist()
    if not options:
        st.warning("No rows match the filter.")
        return

    name_by_code = dict(
        zip(view["mf_scheme_code"].astype(int), view["mfapi_name_cleaned"], strict=False)
    )

    pick = st.selectbox(
        "MFAPI fund",
        options,
        format_func=lambda c: f"{c} — {name_by_code.get(int(c), '')}",
    )
    pick = int(pick)
    row = view.loc[view["mf_scheme_code"].astype(int) == pick].iloc[0]
    prior = hints[hints["mf_scheme_code"].astype(int) == pick] if not hints.empty else hints
    default_slug = str(prior.iloc[0]["et_slug"]) if not prior.empty else ""
    default_sid = int(float(prior.iloc[0]["et_scheme_id"])) if not prior.empty else 1

    st.write(f"**Category:** {row['mf_category']}")
    st.link_button("Search on ET Money (Google)", row["etmoney_search"])

    with st.form("hint_form", clear_on_submit=False):
        et_url = st.text_input(
            "ET Money URL (easiest)",
            placeholder="https://www.etmoney.com/mutual-funds/.../12345",
        )
        slug = st.text_input("ET slug (if not using URL)", value=default_slug)
        sid = st.number_input(
            "ET scheme_id (if not using URL)",
            min_value=1,
            step=1,
            value=max(1, default_sid),
        )
        notes = st.text_input("Notes", value="review UI")
        submitted = st.form_submit_button("Save hint", type="primary")

    if submitted:
        try:
            final_slug, final_sid = slug.strip(), int(sid)
            parsed = parse_et_money_url(et_url)
            if parsed:
                final_slug, final_sid = parsed
            elif et_url.strip():
                st.session_state.hint_err = (
                    "Could not parse URL. Use format: "
                    "https://www.etmoney.com/mutual-funds/{slug}/{scheme_id}"
                )
                st.rerun()
            if not final_slug or final_sid < 1:
                st.session_state.hint_err = (
                    "Provide a valid ET Money URL, or both slug and scheme_id (scheme_id ≥ 1)."
                )
                st.rerun()
            _save_hint(pick, final_slug, final_sid, notes)
            st.session_state.hint_msg = (
                f"Saved MFAPI **{pick}** → ET **{final_sid}** (`{final_slug}`). "
                f"File: `{SCRAPE_HINTS}`"
            )
            st.session_state.hint_err = ""
            st.rerun()
        except Exception as exc:
            st.session_state.hint_err = f"Save failed: {exc}"
            st.rerun()

    with st.expander("Failures by category"):
        st.dataframe(
            fail.groupby("mf_category", dropna=False)
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False),
            hide_index=True,
            width="stretch",
        )


if __name__ == "__main__":
    main()
