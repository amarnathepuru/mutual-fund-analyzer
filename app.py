import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import urllib.parse
import json as _json
import pathlib as _pathlib

# ── PORTFOLIO PERSISTENCE ─────────────────────────────────────────────────────

_PORTFOLIO_SAVE_PATH = _pathlib.Path("saved_portfolio.json")

def _save_portfolio(df: pd.DataFrame) -> None:
    """Save portfolio DataFrame to a local JSON file for cross-session persistence."""
    try:
        _PORTFOLIO_SAVE_PATH.write_text(
            _json.dumps({
                "saved_at": pd.Timestamp.now().isoformat(timespec="seconds"),
                "records":  df.to_dict(orient="records"),
                "columns":  list(df.columns),
            }, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except Exception:
        pass  # best-effort — never crash the app

def _load_saved_portfolio() -> "pd.DataFrame | None":
    """Load portfolio from the local JSON file; returns None if not found."""
    try:
        if not _PORTFOLIO_SAVE_PATH.exists():
            return None
        data   = _json.loads(_PORTFOLIO_SAVE_PATH.read_text(encoding="utf-8"))
        df     = pd.DataFrame(data["records"], columns=data.get("columns"))
        return df if not df.empty else None
    except Exception:
        return None

def _saved_portfolio_meta() -> "tuple[int,str] | None":
    """Return (n_funds, human_date) for the saved portfolio, or None."""
    try:
        if not _PORTFOLIO_SAVE_PATH.exists():
            return None
        data     = _json.loads(_PORTFOLIO_SAVE_PATH.read_text(encoding="utf-8"))
        n        = len(data.get("records", []))
        saved_at = data.get("saved_at", "")
        ts       = pd.to_datetime(saved_at)
        try:
            human = ts.strftime("%-d %b %Y, %-I:%M %p")
        except ValueError:
            human = ts.strftime("%d %b %Y, %I:%M %p")
        return n, human
    except Exception:
        return None

def _saved_portfolio_funds() -> list:
    """Return list of fund names from the saved portfolio."""
    df = _load_saved_portfolio()
    if df is None or df.empty:
        return []
    fund_col = next((c for c in df.columns if "fund" in c.lower()), None)
    return df[fund_col].dropna().tolist() if fund_col else []

def _prefill_manual_entry_state(df: pd.DataFrame) -> None:
    """Pre-populate Streamlit session-state keys for the manual entry widgets."""
    fund_col = next((c for c in df.columns if "fund" in c.lower()), None)
    if fund_col is None:
        return
    funds = df[fund_col].dropna().tolist()
    st.session_state["manual_fund_select"] = funds
    for _, row in df.iterrows():
        fname = str(row.get(fund_col, ""))
        if not fname:
            continue
        safe  = fname.replace(" ", "_").replace("/", "_")
        amt   = row.get("invested_amount", 0)
        units = row.get("units", 0.0)
        st.session_state[f"m_amt_{safe}"]   = int(float(amt))   if pd.notna(amt)   else 0
        st.session_state[f"m_units_{safe}"] = float(units) if pd.notna(units) else 0.0

def _clear_manual_entry_state() -> None:
    """Remove all manual-entry widget keys from session state."""
    for key in list(st.session_state.keys()):
        if key in ("manual_fund_select", "portfolio_entry_mode") or \
           key.startswith("m_amt_") or key.startswith("m_units_"):
            del st.session_state[key]

st.set_page_config(
    page_title="FundLens — Investment Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── GLOBAL CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── DARK PREMIUM BASE ───────────────────────────────────────────────────── */

[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main { background: #0A0F1E !important; }
[data-testid="stHeader"] { display: none; }
footer { display: none; }
.block-container {
    padding: 2.5rem 3rem !important;
    max-width: 1140px !important;
    margin: 0 auto;
    background: #0A0F1E;
}

/* ── SIDEBAR ─────────────────────────────────────────────────────────────── */

[data-testid="stSidebar"] {
    background: #0D1426 !important;
    border-right: 1px solid rgba(255,255,255,0.07) !important;
    min-width: 220px !important;
    max-width: 240px !important;
    overflow: visible !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 1.75rem 0.85rem 1rem; overflow: visible !important; }
[data-testid="stSidebarCollapseButton"] { display: none; }

/* ── TYPOGRAPHY ──────────────────────────────────────────────────────────── */

body, p, div, input, textarea, select, button, label, td, th, li, a {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
h1, h2, h3, h4 { color: #F1F5F9 !important; font-weight: 700 !important; }
h1 { font-size: 1.8rem !important; letter-spacing: -0.02em; }
h2 { font-size: 1.35rem !important; letter-spacing: -0.01em; }
h3 { font-size: 1.1rem !important; }
p, li { color: #CBD5E1 !important; }
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li { color: #CBD5E1 !important; }

/* ── WIDGET THEMING ──────────────────────────────────────────────────────── */

.stTextInput input, .stNumberInput input, .stTextArea textarea {
    background: #1C2540 !important;
    border: 1.5px solid rgba(255,255,255,0.28) !important;
    color: #F1F5F9 !important;
    border-radius: 8px !important;
}
.stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
    border-color: #7C3AED !important;
    box-shadow: 0 0 0 3px rgba(124,58,237,0.22) !important;
    outline: none !important;
}
.stTextInput input::placeholder, .stNumberInput input::placeholder, .stTextArea textarea::placeholder {
    color: rgba(255,255,255,0.35) !important;
}
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {
    background: #1C2540 !important;
    border: 1.5px solid rgba(255,255,255,0.28) !important;
    color: #F1F5F9 !important;
    border-radius: 8px !important;
}
[data-testid="stCheckbox"] label { color: #94A3B8 !important; }
[data-testid="stRadio"] label span { color: #CBD5E1 !important; }

/* Buttons */
.stButton > button {
    background: #1A2340 !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    color: #CBD5E1 !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.18s ease !important;
}
.stButton > button:hover {
    background: #222D4A !important;
    border-color: rgba(124,58,237,0.5) !important;
    color: #F1F5F9 !important;
}
.stButton > button[kind="primaryFormSubmit"],
.stButton > button[kind="primary"],
button[data-testid="baseButton-primary"] {
    background: #7C3AED !important;
    border-color: #7C3AED !important;
    color: #fff !important;
}
.stButton > button[kind="primary"]:hover,
button[data-testid="baseButton-primary"]:hover {
    background: #6D28D9 !important;
    border-color: #6D28D9 !important;
}

/* Tabs */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: transparent !important;
    gap: 2px;
    border-bottom: 1px solid rgba(255,255,255,0.08) !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    background: transparent !important;
    color: #475569 !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    font-size: 0.84rem !important;
    font-weight: 500 !important;
    padding: 0.6rem 1.1rem !important;
    transition: color 0.15s, border-color 0.15s !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
    color: #A78BFA !important;
    border-bottom-color: #7C3AED !important;
    background: transparent !important;
}
[data-testid="stTabs"] [data-baseweb="tab"]:hover { color: #94A3B8 !important; }
[data-testid="stTabs"] [data-baseweb="tab-panel"] {
    background: transparent !important;
    padding-top: 1.5rem !important;
}

/* Expander */
[data-testid="stExpander"] {
    background: #141B2E !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span,
[data-testid="stExpander"] details[open] summary,
[data-testid="stExpander"] details[open] summary p,
[data-testid="stExpander"] details[open] summary span,
[data-testid="stExpander"] summary:hover,
[data-testid="stExpander"] summary:hover p,
[data-testid="stExpander"] summary:focus,
[data-testid="stExpander"] summary:focus p,
[data-testid="stExpander"] summary:active,
[data-testid="stExpander"] summary:active p { color: #94A3B8 !important; font-weight: 500 !important; }

/* Dataframe */
[data-testid="stDataFrame"] iframe,
.stDataFrame { border-radius: 10px !important; overflow: hidden !important; }

/* Info/alert boxes */
[data-testid="stAlert"] {
    background: rgba(124,58,237,0.1) !important;
    border-color: rgba(124,58,237,0.25) !important;
    color: #CBD5E1 !important;
    border-radius: 10px !important;
}

/* ── APP BAR ─────────────────────────────────────────────────────────────── */

.app-bar {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 2.5rem; padding-bottom: 1.25rem;
    border-bottom: 1px solid rgba(255,255,255,0.08);
}
.app-logo { font-size: 20px; font-weight: 800; color: #A78BFA; }

/* ── CARDS ───────────────────────────────────────────────────────────────── */

.card {
    background: #141B2E;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 1.75rem 2rem;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}

/* ── METRIC CARDS ────────────────────────────────────────────────────────── */

.metric-card {
    background: #141B2E;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 1.5rem;
    text-align: center;
    transition: border-color 0.18s ease, background 0.18s ease,
                box-shadow 0.18s ease, transform 0.18s ease;
}
a.metric-card-link { all: unset; display: block; cursor: pointer; }
a.metric-card-link:hover .metric-card,
.metric-card:hover {
    border-color: rgba(124,58,237,0.55);
    background: rgba(124,58,237,0.1);
    box-shadow: 0 8px 32px rgba(124,58,237,0.22);
    transform: translateY(-3px);
}
.metric-value {
    font-size: 2.5rem; font-weight: 800; color: #A78BFA !important;
    line-height: 1; font-feature-settings: "tnum";
}
.metric-label {
    font-size: 0.72rem; color: #475569 !important; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.8px; margin-top: 6px;
}
.metric-sub { font-size: 0.7rem; color: #334155 !important; margin-top: 4px; }

/* ── JOURNEY CARDS ───────────────────────────────────────────────────────── */

.journey-card {
    background: #141B2E;
    border: 1.5px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 2rem; height: 100%; transition: all 0.2s;
}
.journey-card:hover {
    border-color: rgba(124,58,237,0.4);
    box-shadow: 0 8px 32px rgba(0,0,0,0.45);
}

/* ── STATS BANNER ────────────────────────────────────────────────────────── */

.stats-banner {
    background: linear-gradient(135deg, #1E1060 0%, #312E81 50%, #1E3A5F 100%);
    border: 1px solid rgba(124,58,237,0.3);
    border-radius: 16px; padding: 1.75rem 2rem; color: white;
    display: flex; gap: 0; align-items: center; margin-bottom: 2.5rem;
    flex-wrap: wrap;
}
.stat-item { text-align: center; flex: 1; min-width: 100px; }
.stat-value { font-size: 1.85rem; font-weight: 800; font-feature-settings: "tnum"; }
.stat-label { font-size: 0.7rem; opacity: 0.55; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.6px; }
.stat-divider { width: 1px; background: rgba(255,255,255,0.12); height: 40px; flex-shrink: 0; }

/* ── CATEGORY CARDS ──────────────────────────────────────────────────────── */

.cat-name { font-size: 0.9rem; font-weight: 700; color: #E2E8F0; margin-bottom: 4px; margin-top: 8px; }
.cat-desc { font-size: 0.75rem; color: #475569; line-height: 1.5; }

.cat-card-inner {
    background: #141B2E;
    border: 1.5px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: .9rem .9rem .85rem; min-height: 120px; position: relative;
    transition: border-color .15s, box-shadow .15s;
}
.cat-card-inner.selected {
    background: rgba(124,58,237,0.12);
    border: 2px solid rgba(124,58,237,0.55);
    box-shadow: 0 0 0 3px rgba(124,58,237,.1);
}
.cat-card-col [data-testid="stCheckbox"] { margin-top: .3rem; }
.cat-card-col [data-testid="stCheckbox"] label {
    font-size: .78rem !important; color: #475569 !important; font-weight: 500;
}
.cat-card-col [data-testid="stCheckbox"] label span { color: #475569 !important; }

/* ── NAV PILLS ───────────────────────────────────────────────────────────── */

a.nav-pill {
    display: inline-flex; align-items: center; gap: .3rem;
    padding: .3rem .9rem; border-radius: 9999px;
    border: 1px solid rgba(255,255,255,0.1);
    background: rgba(255,255,255,0.04);
    color: #64748B; font-size: .78rem; font-weight: 600;
    text-decoration: none; cursor: pointer;
    transition: border-color .15s, color .15s, background .15s;
    white-space: nowrap;
}
a.nav-pill:hover {
    border-color: rgba(124,58,237,0.5);
    color: #A78BFA;
    background: rgba(124,58,237,0.1);
}
.nav-pill-row { display: flex; gap: .5rem; align-items: center; margin-bottom: .85rem; }

/* ── SIDEBAR TOOLTIP ─────────────────────────────────────────────────────── */

.nav-tooltip-wrap { position: relative; display: block; }
.nav-tooltip {
    visibility: hidden; opacity: 0;
    position: absolute;
    left: calc(100% + 12px); top: 50%;
    transform: translateY(-50%) translateX(-4px);
    transition: opacity .18s ease, transform .18s ease, visibility .18s;
    background: #0D1426;
    border: 1px solid rgba(255,255,255,0.12);
    color: #CBD5E1;
    border-radius: 10px; padding: .75rem 1rem;
    font-size: .75rem; line-height: 1.55;
    width: 210px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.55);
    z-index: 9999; pointer-events: none; white-space: normal;
}
.nav-tooltip-wrap:hover .nav-tooltip {
    visibility: visible; opacity: 1;
    transform: translateY(-50%) translateX(0);
}
.nav-tooltip-title { font-weight: 700; margin-bottom: .4rem; color: #A78BFA; font-size: .78rem; }
.nav-tooltip-item { display: flex; gap: .35rem; margin-bottom: .22rem; opacity: .85; align-items: flex-start; }

/* ── BADGES ──────────────────────────────────────────────────────────────── */

.badge { display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 0.65rem; font-weight: 700; }
.badge-live   { background: rgba(16,185,129,0.15); color: #6EE7B7; }
.badge-soon   { background: rgba(100,116,139,0.15); color: #94A3B8; }
.badge-high   { background: rgba(239,68,68,0.15); color: #FCA5A5; }
.badge-medium { background: rgba(245,158,11,0.15); color: #FDE68A; }
.badge-low    { background: rgba(16,185,129,0.15); color: #6EE7B7; }

/* ── INSIGHT CARDS ───────────────────────────────────────────────────────── */

.insight-card {
    border-radius: 12px; padding: 1rem 1.125rem;
    margin-bottom: 0.75rem;
    display: flex; align-items: flex-start; gap: 0.875rem;
    transition: transform 0.15s ease;
}
.insight-card:hover { transform: translateX(2px); }
.insight-alert   { background: linear-gradient(135deg, rgba(239,68,68,0.13), rgba(239,68,68,0.05)); border-left: 3px solid #EF4444; }
.insight-warning { background: linear-gradient(135deg, rgba(245,158,11,0.13), rgba(245,158,11,0.05)); border-left: 3px solid #F59E0B; }
.insight-info    { background: linear-gradient(135deg, rgba(124,58,237,0.15), rgba(124,58,237,0.05)); border-left: 3px solid #7C3AED; }
.insight-success { background: linear-gradient(135deg, rgba(16,185,129,0.13), rgba(16,185,129,0.05)); border-left: 3px solid #10B981; }
.insight-icon { font-size: 1.2rem; flex-shrink: 0; margin-top: 1px; }
.insight-text { font-size: 0.8rem; color: #94A3B8; line-height: 1.65; }

/* ── SECTION HEADERS ─────────────────────────────────────────────────────── */

.section-title { font-size: 1.05rem; font-weight: 700; color: #E2E8F0; margin-bottom: 2px; letter-spacing: -0.01em; }
.section-sub   { font-size: 0.78rem; color: #475569; margin-bottom: 1rem; }

/* ── DISCLAIMER ──────────────────────────────────────────────────────────── */

.disclaimer {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px; padding: 0.875rem 1.25rem;
    font-size: 0.7rem; color: #334155;
    margin-top: 2rem; text-align: center; line-height: 1.6;
}

/* ── OVERLAP BARS ────────────────────────────────────────────────────────── */

.overlap-row {
    background: #141B2E;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 1.125rem 1.5rem; margin-bottom: 0.75rem;
    transition: border-color 0.15s;
}
.overlap-row:hover { border-color: rgba(124,58,237,0.35); }
.overlap-bar-bg { background: rgba(255,255,255,0.07); border-radius: 4px; height: 6px; overflow: hidden; margin-top: 8px; }
.overlap-bar-fill { background: linear-gradient(90deg, #7C3AED, #A78BFA); height: 100%; border-radius: 4px; }

/* ── RESPONSIVE ──────────────────────────────────────────────────────────── */

@media (max-width: 1024px) {
    .block-container { padding: 1.5rem 1.5rem !important; }
}

@media (max-width: 768px) {
    .block-container { padding: 0.75rem !important; max-width: 100% !important; }
    [data-testid="stSidebarCollapseButton"] { display: flex !important; }
    [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: 0.5rem !important; }
    [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        width: 100% !important; flex: 0 0 100% !important; min-width: 100% !important;
    }
    h1 { font-size: 1.4rem !important; }
    h2 { font-size: 1.2rem !important; }
    h3 { font-size: 1rem !important; }
    .card, .metric-card, .journey-card { padding: 1.125rem !important; }
    .insight-card { padding: 0.75rem 0.875rem !important; }
    .overlap-row { padding: 0.75rem !important; }
    .hide-mobile { display: none !important; }
}

@media (max-width: 480px) {
    .block-container { padding: 0.5rem !important; }
    .card, .metric-card { padding: 0.875rem !important; }
}
</style>
""", unsafe_allow_html=True)


# ── DARK CHART THEME ─────────────────────────────────────────────────────────

_CHART_FONT   = dict(family="Inter, sans-serif", color="#94A3B8", size=12)
_CHART_GRID   = "rgba(255,255,255,0.06)"
_CHART_ZERO   = "rgba(255,255,255,0.14)"
_CHART_TICK   = dict(color="#475569", size=11)
_CHART_BG     = "rgba(0,0,0,0)"

def _dark_layout(**extra):
    base = dict(
        paper_bgcolor=_CHART_BG,
        plot_bgcolor=_CHART_BG,
        font=_CHART_FONT,
        margin=dict(t=30, b=10, l=10, r=10),
    )
    base.update(extra)
    return base

def _dark_xaxis(**kw):
    d = dict(showgrid=False, showline=False, tickfont=_CHART_TICK, title="", zeroline=False)
    d.update(kw); return d

def _dark_yaxis(**kw):
    d = dict(showgrid=True, gridcolor=_CHART_GRID, zeroline=True,
             zerolinecolor=_CHART_ZERO, zerolinewidth=1, tickfont=_CHART_TICK, title="")
    d.update(kw); return d

_PALETTE = ["#7C3AED", "#F59E0B", "#06B6D4", "#10B981", "#EF4444",
            "#8B5CF6", "#F472B6", "#34D399", "#FB923C", "#60A5FA"]

# ── DATA LOADING ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_holdings():
    try:
        return pd.read_csv("data/processed/normalized_holdings.csv")
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_master():
    try:
        return pd.read_csv("data/fund_master_auto.csv")
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_similarity():
    try:
        df = pd.read_csv("data/processed/fund_similarity.csv")
        # Backfill normalized_score if loading an older CSV that predates the column
        if "normalized_score" not in df.columns and "similarity_score" in df.columns:
            df["normalized_score"] = df["similarity_score"]
        return df
    except Exception:
        return pd.DataFrame()



@st.cache_data
def compute_fund_enriched(holdings_df, master_df):
    if holdings_df.empty or master_df.empty:
        return master_df.copy()

    hold_counts = (
        holdings_df.groupby("fund_name")["stock_name"]
        .nunique()
        .reset_index()
        .rename(columns={"stock_name": "holding_count"})
    )

    top_sector = (
        holdings_df.groupby(["fund_name", "sector"])["allocation_percent"]
        .sum()
        .reset_index()
        .sort_values("allocation_percent", ascending=False)
        .groupby("fund_name")
        .first()
        .reset_index()
        .rename(columns={"sector": "top_sector", "allocation_percent": "top_sector_pct"})
    )

    result = master_df.merge(hold_counts, on="fund_name", how="left")
    result = result.merge(top_sector[["fund_name", "top_sector"]], on="fund_name", how="left")
    return result


@st.cache_data
def get_sector_breakdown(holdings_df):
    return (
        holdings_df.groupby(["fund_name", "sector"])["allocation_percent"]
        .sum()
        .reset_index()
    )



# ── HELPERS ───────────────────────────────────────────────────────────────────

def sim_badge(score):
    if score >= 60:
        return "Very High", "badge-high"
    if score >= 45:
        return "High", "badge-high"
    if score >= 30:
        return "Moderate", "badge-medium"
    if score >= 15:
        return "Good", "badge-low"
    return "Excellent", "badge-low"


def short_name(name):
    return (
        name.replace("Aditya Birla Sun Life ", "ABSL ")
            .replace(" Large Cap Fund", "")
            .replace(" Largecap Fund", "")
            .replace(" Fund", "")
    )


def display_name(name, max_len=32):
    """Abbreviated but unique fund name — keeps category, only shortens house names."""
    n = (
        name.replace("Aditya Birla Sun Life ", "ABSL ")
            .replace("ICICI Prudential ", "ICICI Pru ")
            .replace("Mirae Asset ", "Mirae ")
            .replace("Franklin Templeton ", "Franklin ")
            .replace("Kotak Mahindra ", "Kotak ")
    )
    return n if len(n) <= max_len else n[:max_len - 1] + "…"


def format_aum(val):
    try:
        v = float(val)
        return f"₹{v/1000:.1f}K Cr" if v >= 10000 else f"₹{v:,.0f} Cr"
    except Exception:
        return "—"


def render_risk_metric_explainer(key_suffix=""):
    """Plain-English explainer panel for the 4 risk/efficiency metrics."""
    _, t = _fl_get_theme()
    _hd = t["head"]; _bd = t["body"]; _a = t["a"]; _al = t["al"]; _cd = t["card"]; _bdr = t["bdr"]
    with st.expander("ℹ️ What do these numbers mean?", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        for col, emoji, term, plain, good in [
            (
                c1, "📊", "Std Dev %",
                "Measures how much the fund's returns jump around year to year. "
                "A fund with 10% std dev might return anywhere from −10% to +30% in a given year. "
                "Lower means a steadier, more predictable ride.",
                "Lower = steadier",
            ),
            (
                c2, "⚖️", "Sharpe Ratio",
                "Tells you how much return you're getting for the risk you're taking. "
                "Think of it as 'is the bumpy ride worth it?' "
                "A score above 1.0 is generally considered good.",
                "Higher = better reward for risk",
            ),
            (
                c3, "🎯", "Alpha %",
                "How much extra return the fund manager generated beyond what the market "
                "naturally gave. +2% alpha means the manager added 2% on top of the benchmark. "
                "Negative means they lagged the market.",
                "Positive = manager added value",
            ),
            (
                c4, "📡", "Beta",
                "How much the fund swings when the market swings. "
                "Beta 1.2 means if the market falls 10%, this fund typically falls 12%. "
                "Beta 0.8 means it only falls 8%. Higher beta = bumpier ride in market swings.",
                "< 1 = less market-sensitive",
            ),
        ]:
            with col:
                st.markdown(
                    f'<div style="background:{_al};border-radius:8px;padding:0.75rem 0.8rem;'
                    f'border-left:3px solid {_a};height:100%;border:1px solid {_bdr};border-left:3px solid {_a};">'
                    f'<div style="font-size:1.3rem;margin-bottom:4px;">{emoji}</div>'
                    f'<div style="font-weight:700;font-size:0.82rem;color:{_hd};margin-bottom:5px;">{term}</div>'
                    f'<div style="font-size:0.73rem;color:{_bd};line-height:1.45;margin-bottom:8px;">{plain}</div>'
                    f'<div style="font-size:0.68rem;font-weight:700;color:{_a};">{good}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


INSIGHT_CATEGORIES = [
    (
        "overlap",
        "🔗 Do your funds repeat the same stocks?",
        "Checks whether several funds own the same companies underneath.",
    ),
    (
        "sector",
        "🏗️ Are you tilted toward one industry?",
        "Looks at how much of your funds sit in sectors like banks, IT, or pharma.",
    ),
    (
        "unique",
        "🔬 What does each fund add on its own?",
        "Stocks only one of your funds holds — the extra variety that fund brings.",
    ),
    (
        "momentum",
        "📈 What are managers buying or selling lately?",
        "Recent 3-month changes in how much funds hold certain stocks.",
    ),
    (
        "cost_risk",
        "💰 Fees and bumpiness",
        "Yearly fund charges and how much returns tend to swing up and down.",
    ),
]


def _render_categorized_insights(
    insights: list,
    *,
    hd: str, sb: str, bd: str, al: str, bdr: str,
    page_key: str = "ins",
    empty_msg: str = "No clear patterns stood out. Try adding more funds or check the other tabs.",
) -> None:
    """Render insights grouped in collapsible sections to keep the page scannable."""
    cls_map = {
        "alert": "insight-alert",
        "warning": "insight-warning",
        "info": "insight-info",
        "success": "insight-success",
    }
    if not insights:
        st.info(empty_msg)
        return

    n_notes = len(insights)
    n_watch = sum(1 for i in insights if i["type"] in ("alert", "warning"))
    n_good  = sum(1 for i in insights if i["type"] == "success")
    st.markdown(
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:1rem;">'
        f'<span style="font-size:0.72rem;font-weight:600;color:{sb};background:{al};'
        f'border:1px solid {bdr};border-radius:999px;padding:4px 10px;">'
        f'{n_notes} note{"s" if n_notes != 1 else ""} total</span>'
        + (f'<span style="font-size:0.72rem;font-weight:600;color:{sb};background:rgba(245,158,11,0.12);'
           f'border:1px solid {bdr};border-radius:999px;padding:4px 10px;">'
           f'{n_watch} worth a closer look</span>' if n_watch else "")
        + (f'<span style="font-size:0.72rem;font-weight:600;color:{sb};background:rgba(16,185,129,0.12);'
           f'border:1px solid {bdr};border-radius:999px;padding:4px 10px;">'
           f'{n_good} positive</span>' if n_good else "")
        + f'</div>',
        unsafe_allow_html=True,
    )

    _open_cat = None
    for cat_key, _, _ in INSIGHT_CATEGORIES:
        cat_ins = [i for i in insights if i.get("category") == cat_key]
        if cat_ins and any(i["type"] in ("alert", "warning") for i in cat_ins):
            _open_cat = cat_key
            break
    if _open_cat is None:
        for cat_key, _, _ in INSIGHT_CATEGORIES:
            if any(i.get("category") == cat_key for i in insights):
                _open_cat = cat_key
                break

    for cat_key, cat_title, cat_sub in INSIGHT_CATEGORIES:
        cat_ins = [i for i in insights if i.get("category") == cat_key]
        if not cat_ins:
            continue
        with st.expander(
            f"{cat_title} — {len(cat_ins)} note{'s' if len(cat_ins) != 1 else ''}",
            expanded=(cat_key == _open_cat),
            key=f"{page_key}_ins_{cat_key}",
        ):
            st.markdown(
                f'<div style="font-size:0.78rem;color:{bd};line-height:1.5;margin-bottom:0.75rem;">'
                f'{cat_sub}</div>',
                unsafe_allow_html=True,
            )
            for ins in cat_ins:
                st.markdown(
                    f'<div class="insight-card {cls_map[ins["type"]]}">'
                    f'<div class="insight-icon">{ins["icon"]}</div>'
                    f'<div class="insight-text">{ins["text"]}</div></div>',
                    unsafe_allow_html=True,
                )


def _render_concentration_flags(
    *,
    matched_funds: list,
    sel_sim: pd.DataFrame,
    sel_h: pd.DataFrame,
    sel_sector: pd.DataFrame,
    sel_master: pd.DataFrame,
    master: pd.DataFrame,
    weight_map: dict,
    hd: str,
    bd: str,
    al: str,
    bdr: str,
) -> bool:
    """Strict warning checks (overlap ≥65%, stock >5%, sector >40%, etc.). Returns True if any flag fired."""
    st.markdown(
        f'<div style="margin:0 0 0.5rem;">'
        f'<div style="font-size:0.95rem;font-weight:700;color:{hd};">'
        f'⚡ Priority concentration flags</div>'
        f'<div style="font-size:0.72rem;color:{bd};margin-top:2px;">'
        f'Only shows up when your portfolio crosses a strict warning level</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="font-size:0.82rem;color:{bd};line-height:1.65;margin-bottom:0.75rem;'
        f'padding:0.75rem 1rem;background:{al};border:1px solid {bdr};border-radius:10px;">'
        f'<strong style="color:{hd};">Concentration</strong> means too much of your money depends on the '
        f'same stocks, industries, fund types, or high fees. These flags are the first things to check.</div>',
        unsafe_allow_html=True,
    )

    flags_found = False

    if not sel_sim.empty:
        high_ol = sel_sim[sel_sim["normalized_score"] >= 65]
        for _, row in high_ol.iterrows():
            flags_found = True
            _fa = display_name(row["fund_a"])
            _fb = display_name(row["fund_b"])
            _ol_pct = row["normalized_score"]
            _common = int(row["common_stocks"])
            st.markdown(f"""<div class="insight-card insight-alert">
                <div class="insight-icon">🔁</div>
                <div class="insight-text"><strong>Two funds that largely own the same stocks</strong><br>
                <strong>{_fa}</strong> and <strong>{_fb}</strong> share about <strong>{_ol_pct:.0f}%</strong>
                of their holdings — roughly <strong>{_common}</strong> companies appear in both.
                In plain terms: money in both funds often ends up in the same place, so you are not
                getting much extra safety from holding two. It is a bit like buying two similar baskets.
                Open the <strong>Fund Overlap</strong> tab to see the shared company names.</div></div>""",
                unsafe_allow_html=True,
            )

    sel_h_wt2 = sel_h.copy()
    sel_h_wt2["weight"]    = sel_h_wt2["fund_name"].map(weight_map).fillna(0)
    sel_h_wt2["eff_alloc"] = sel_h_wt2["allocation_percent"] * sel_h_wt2["weight"]
    eff_exp = sel_h_wt2.groupby("stock_name")["eff_alloc"].sum()
    heavy_stocks = eff_exp[eff_exp > 5].sort_values(ascending=False)
    if not heavy_stocks.empty:
        flags_found = True
        stocks_txt = ", ".join(
            f"<strong>{s}</strong> ({v:.1f}% of your total holdings)" for s, v in heavy_stocks.items()
        )
        st.markdown(f"""<div class="insight-card insight-warning">
            <div class="insight-icon">📌</div>
            <div class="insight-text"><strong>Too much riding on a few companies</strong><br>
            When we combine all your funds, these stocks make up more than 5% each of what you
            actually own: {stocks_txt}.
            If one of these companies has a bad quarter, legal trouble, or a big price fall,
            your whole portfolio can feel it — not just one fund.</div></div>""",
            unsafe_allow_html=True,
        )

    if not sel_sector.empty:
        avg_by_sec = sel_sector.groupby("sector")["allocation_percent"].mean()
        heavy_secs = avg_by_sec[avg_by_sec > 40].sort_values(ascending=False)
        for sec, pct in heavy_secs.items():
            flags_found = True
            _sec_name = sec.title()
            if sec.upper() == "FINANCIAL":
                _sec_bench = (
                    " Even a typical broad Indian market index only has about 30–35% in financial "
                    "companies, so your funds are tilted more than usual toward banks and finance."
                )
            else:
                _sec_bench = (
                    " Many well-spread equity funds keep any one industry below about 25%, "
                    "so this is a noticeable lean in one direction."
                )
            st.markdown(f"""<div class="insight-card insight-warning">
                <div class="insight-icon">🏗️</div>
                <div class="insight-text"><strong>Heavy tilt toward one industry ({_sec_name})</strong><br>
                A <em>sector</em> is a group of similar businesses — for example banks, IT, or pharma.
                On average, your funds have about <strong>{pct:.1f}%</strong> in <strong>{_sec_name}</strong>.{_sec_bench}
                If that whole industry struggles (for example rate changes hitting banks, or a tech slowdown),
                most of your funds can drop together because they all lean the same way.</div></div>""",
                unsafe_allow_html=True,
            )

    if not master.empty and "category" in master.columns:
        cat_map2  = dict(zip(master["fund_name"], master["category"]))
        fund_cats = list({cat_map2.get(f, "Other") for f in matched_funds})
        if len(fund_cats) == 1:
            flags_found = True
            _only_cat = fund_cats[0]
            _cap_plain = {
                "Large Cap": "big, well-known companies (think large Nifty names)",
                "Mid Cap": "medium-sized companies — often faster growth, but bumpier rides",
                "Small Cap": "smaller companies — can grow quickly, but usually swing more in bad markets",
                "Large & Mid Cap": "a mix of large and medium-sized companies",
                "Multi Cap": "companies of all sizes, chosen by the fund manager",
                "Flexi Cap": "flexible mix across company sizes",
                "ELSS": "tax-saving funds (with a 3-year lock-in)",
            }
            _cat_desc = _cap_plain.get(_only_cat, "similar types of companies")
            _all_caps = ["Large Cap", "Mid Cap", "Small Cap"]
            if _only_cat in _all_caps:
                _missing = [c for c in _all_caps if c != _only_cat]
                _missing_str = ", ".join(f"<strong>{c}</strong>" for c in _missing)
                _missing_tail = (
                    f" You do not hold separate {_missing_str} funds, "
                    f"so your portfolio mainly tracks {_only_cat.lower()} stocks."
                )
            else:
                _missing_tail = ""
            st.markdown(f"""<div class="insight-card insight-info">
                <div class="insight-icon">📊</div>
                <div class="insight-text"><strong>All your funds are the same type ({_only_cat})</strong><br>
                Fund categories describe <em>which size of company</em> they mainly buy:
                large-cap funds focus on {_cap_plain.get("Large Cap", "big companies")},
                mid-cap on {_cap_plain.get("Mid Cap", "medium ones")},
                and small-cap on {_cap_plain.get("Small Cap", "smaller ones")}.
                Every fund you hold is <strong>{_only_cat}</strong> — {_cat_desc}.{_missing_tail}
                Different sizes do not always move together in a market crash or rally, so using only one
                category can mean your whole portfolio rises and falls in a similar way.</div></div>""",
                unsafe_allow_html=True,
            )

    if not sel_master.empty and "expense_ratio" in sel_master.columns:
        er_vals = pd.to_numeric(sel_master["expense_ratio"], errors="coerce").dropna()
        if len(er_vals) > 1 and er_vals.min() > 0:
            most_exp = sel_master.loc[er_vals.idxmax()]
            cheapest = sel_master.loc[er_vals.idxmin()]
            if er_vals.max() > er_vals.min() * 2:
                flags_found = True
                _er_gap_pf   = float(most_exp["expense_ratio"]) - float(cheapest["expense_ratio"])
                _10yr_pf     = int(100_000 * ((1.12 ** 10) - ((1.12 - _er_gap_pf / 100) ** 10)))
                _exp_fn = display_name(most_exp["fund_name"])
                _cheap_fn = display_name(cheapest["fund_name"])
                _exp_er = float(most_exp["expense_ratio"])
                _cheap_er = float(cheapest["expense_ratio"])
                st.markdown(f"""<div class="insight-card insight-info">
                    <div class="insight-icon">💸</div>
                    <div class="insight-text"><strong>One fund charges much higher yearly fees</strong><br>
                    The <em>expense ratio</em> is the annual fee the fund house takes from your money.
                    <strong>{_exp_fn}</strong> charges <strong>{_exp_er:.2f}% per year</strong>, while
                    <strong>{_cheap_fn}</strong> charges <strong>{_cheap_er:.2f}%</strong> — more than double.
                    That extra <strong>{_er_gap_pf:.2f}%</strong> each year adds up: on ₹1 lakh, kept for
                    10 years (if returns were around 12% before fees), you could pay roughly
                    <strong>₹{_10yr_pf:,} more</strong> in fees on the pricier fund. Lower fees do not
                    guarantee better returns, but they leave more of any gains in your pocket.</div></div>""",
                    unsafe_allow_html=True,
                )

    if not flags_found:
        st.success(
            "✅ No priority concentration flags — overlap, single stocks, sectors, cap types, "
            "and fees did not cross our strict warning levels."
        )
    return flags_found


def generate_insights(fund_list, similarity_df, holdings_df, sector_df, master_df=None):
    insights = []
    sel_sim = similarity_df[
        similarity_df["fund_a"].isin(fund_list) & similarity_df["fund_b"].isin(fund_list)
    ]
    sel_h = holdings_df[holdings_df["fund_name"].isin(fund_list)]

    # 1. Highest-overlap pair
    if not sel_sim.empty:
        worst    = sel_sim.loc[sel_sim["normalized_score"].idxmax()]
        fa, fb   = worst["fund_a"], worst["fund_b"]
        wscore   = worst["normalized_score"]
        wcommon  = int(worst["common_stocks"])
        h_a_set  = set(sel_h[sel_h["fund_name"] == fa]["stock_name"])
        h_b_set  = set(sel_h[sel_h["fund_name"] == fb]["stock_name"])
        shared   = h_a_set & h_b_set
        top3     = (
            sel_h[sel_h["stock_name"].isin(shared)]
            .groupby("stock_name")["allocation_percent"].mean()
            .nlargest(3).index.tolist()
        )
        top3_txt = ", ".join(f"<strong>{s}</strong>" for s in top3)
        stype    = "alert" if wscore >= 60 else "warning"
        icon     = "⚠️"   if wscore >= 60 else "📊"
        if wscore >= 60:
            tail = (
                "That is a lot of overlap — both funds will usually move up or down together, "
                "so holding both does not spread your risk much. "
                "See <strong>Fund Overlap</strong> or <strong>What You Actually Own</strong> for the shared names."
            )
        else:
            tail = (
                "A fair chunk of your money lands in the same companies through both funds. "
                "Open the <strong>What each fund adds on its own</strong> section below to see what is different."
            )
        insights.append({
            "category": "overlap", "type": stype, "icon": icon,
            "text": (
                f"<strong>Most overlapping pair:</strong> "
                f"<strong>{display_name(fa)}</strong> and <strong>{display_name(fb)}</strong> "
                f"both hold about <strong>{wcommon}</strong> of the same companies "
                f"(<strong>{wscore:.0f}% overlap</strong>). "
                f"As a rough guide, overlap below 30% usually means more variety. "
                f"Largest shared names: {top3_txt}. {tail}"
            ),
        })

    # 2. Best diversification pair
    if not sel_sim.empty and len(sel_sim) > 1:
        best   = sel_sim.loc[sel_sim["normalized_score"].idxmin()]
        bscore = best["normalized_score"]
        if bscore < 50:
            insights.append({
                "category": "overlap", "type": "success", "icon": "✅",
                "text": (
                    f"<strong>Best variety between two funds:</strong> "
                    f"<strong>{display_name(best['fund_a'])}</strong> and "
                    f"<strong>{display_name(best['fund_b'])}</strong> overlap only "
                    f"<strong>{bscore:.0f}%</strong> — most of their stock lists are different. "
                    f"This pair does the most to spread your money across different companies."
                ),
            })

    # 3. Stocks held by ALL funds
    if not sel_h.empty:
        counts        = sel_h.groupby("stock_name")["fund_name"].nunique()
        unani_stocks  = counts[counts == len(fund_list)].index.tolist()
        if unani_stocks:
            top5u = (
                sel_h[sel_h["stock_name"].isin(unani_stocks)]
                .groupby("stock_name")["allocation_percent"].mean()
                .nlargest(5).index.tolist()
            )
            top5_txt = ", ".join(f"<strong>{s}</strong>" for s in top5u)
            insights.append({
                "category": "overlap", "type": "info", "icon": "📌",
                "text": (
                    f"<strong>Stocks every fund owns:</strong> "
                    f"{len(unani_stocks)} "
                    f"{'companies show up' if len(unani_stocks) > 1 else 'company shows up'} "
                    f"in all {len(fund_list)} funds — including {top5_txt}. "
                    f"No matter how you split money across these funds, you always end up owning these names."
                ),
            })

    # 4. Sector dominance
    sel_sector = sector_df[sector_df["fund_name"].isin(fund_list)]
    if not sel_sector.empty:
        avg_by_sec = sel_sector.groupby("sector")["allocation_percent"].mean()
        top_s      = avg_by_sec.idxmax()
        top_pct    = avg_by_sec.max()
        if top_pct > 25:
            by_fund  = (
                sel_sector[sel_sector["sector"] == top_s]
                .sort_values("allocation_percent", ascending=False)
            )
            hi_fund  = display_name(by_fund.iloc[0]["fund_name"])
            hi_pct   = by_fund.iloc[0]["allocation_percent"]
            lo_txt   = ""
            if len(by_fund) > 1:
                lo_fund = display_name(by_fund.iloc[-1]["fund_name"])
                lo_pct  = by_fund.iloc[-1]["allocation_percent"]
                lo_txt  = (
                    f" <strong>{lo_fund}</strong> is lightest here at <strong>{lo_pct:.0f}%</strong>."
                )
            if top_s.upper() == "FINANCIAL":
                bench_note = (
                    " Broad Indian market funds often have 30–35% in financial companies, "
                    "so this is common — but still a big slice of your money."
                )
            elif top_pct > 30:
                bench_note = (
                    " Many spread-out equity funds keep any one non-bank industry below about 25%."
                )
            else:
                bench_note = ""
            insights.append({
                "category": "sector", "type": "warning", "icon": "🏦",
                "text": (
                    f"<strong>Top industry tilt:</strong> on average about "
                    f"<strong>{top_pct:.0f}%</strong> of each fund is in "
                    f"<strong>{top_s.title()}</strong> companies. "
                    f"<strong>{hi_fund}</strong> leans most ({hi_pct:.0f}%).{lo_txt}{bench_note} "
                    f"If that whole industry struggles, several of your funds can fall together. "
                    f"See <strong>Sector & Cap Size</strong> for a full breakdown."
                ),
            })

        if len(avg_by_sec) > 1:
            sec_s   = avg_by_sec.drop(top_s).idxmax()
            sec_pct = avg_by_sec.drop(top_s).max()
            if sec_pct > 15:
                insights.append({
                    "category": "sector", "type": "info", "icon": "🏗️",
                    "text": (
                        f"<strong>Second-biggest industry:</strong> "
                        f"<strong>{sec_s.title()}</strong> at about <strong>{sec_pct:.0f}%</strong> on average. "
                        f"Together, <strong>{top_s.title()}</strong> and <strong>{sec_s.title()}</strong> "
                        f"make up roughly <strong>{int(top_pct + sec_pct)}%</strong> — "
                        f"the rest is spread across other industries."
                    ),
                })

    # 5. Unique holdings — one combined note (avoids one card per fund)
    if not sel_h.empty and len(fund_list) >= 2:
        unique_rows = []
        for fund in fund_list:
            fund_stocks   = set(sel_h[sel_h["fund_name"] == fund]["stock_name"])
            others_stocks = set(sel_h[sel_h["fund_name"] != fund]["stock_name"])
            unique        = fund_stocks - others_stocks
            if len(unique) >= 3:
                top_unique = (
                    sel_h[(sel_h["fund_name"] == fund) & (sel_h["stock_name"].isin(unique))]
                    .nlargest(3, "allocation_percent")["stock_name"].tolist()
                )
                unique_rows.append({
                    "fund": fund,
                    "n": len(unique),
                    "examples": top_unique,
                })
        if unique_rows:
            unique_rows.sort(key=lambda r: r["n"], reverse=True)
            show_rows = unique_rows[:4]
            lines = []
            for row in show_rows:
                ex = ", ".join(f"<strong>{s}</strong>" for s in row["examples"])
                lines.append(
                    f"<strong>{display_name(row['fund'])}</strong> — "
                    f"{row['n']} stocks only it holds (e.g. {ex})"
                )
            extra = ""
            if len(unique_rows) > len(show_rows):
                extra = (
                    f" …and <strong>{len(unique_rows) - len(show_rows)}</strong> more fund"
                    f"{'s' if len(unique_rows) - len(show_rows) != 1 else ''} "
                    f"with their own picks."
                )
            insights.append({
                "category": "unique", "type": "info", "icon": "🔬",
                "text": (
                    "<strong>What only one fund owns:</strong><br>"
                    + "<br>".join(lines)
                    + extra
                    + " See <strong>What You Actually Own</strong> for the full stock list."
                ),
            })

    # 6. Allocation momentum (3-month changes)
    if not sel_h.empty:
        trend_df  = sel_h.groupby("stock_name").agg(
            funds=("fund_name", "nunique"),
            avg_3m=("change_3m_percent", "mean"),
        ).reset_index()
        multi    = trend_df[trend_df["funds"] >= min(2, len(fund_list))]
        growing  = multi[multi["avg_3m"] > 0.8].nlargest(2, "avg_3m")
        declining = multi[multi["avg_3m"] < -0.8].nsmallest(2, "avg_3m")
        if not growing.empty:
            g_txt = ", ".join(
                f"<strong>{r['stock_name']}</strong> (managers added ~{r['avg_3m']:.1f}% on average)"
                for _, r in growing.iterrows()
            )
            insights.append({
                "category": "momentum", "type": "success", "icon": "📈",
                "text": (
                    f"<strong>Managers have been buying more of:</strong> {g_txt} "
                    f"over the last 3 months (across at least two of your funds). "
                    f"That can mean they liked recent results or outlook — not a guarantee of future gains."
                ),
            })
        if not declining.empty:
            d_txt = ", ".join(
                f"<strong>{r['stock_name']}</strong> (trimmed ~{abs(r['avg_3m']):.1f}% on average)"
                for _, r in declining.iterrows()
            )
            insights.append({
                "category": "momentum", "type": "warning", "icon": "📉",
                "text": (
                    f"<strong>Managers have been cutting back on:</strong> {d_txt} "
                    f"over the last 3 months. Several funds moving the same way can mean "
                    f"less enthusiasm for those companies right now."
                ),
            })

    # 7. Fees and volatility
    if master_df is not None and not master_df.empty:
        sel_master = master_df[master_df["fund_name"].isin(fund_list)].copy()

        er_df = sel_master.dropna(subset=["expense_ratio"]).copy()
        er_df["expense_ratio"] = pd.to_numeric(er_df["expense_ratio"], errors="coerce")
        er_df = er_df.dropna(subset=["expense_ratio"])
        if not er_df.empty:
            cheapest  = er_df.loc[er_df["expense_ratio"].idxmin()]
            costliest = er_df.loc[er_df["expense_ratio"].idxmax()]
            er_gap    = costliest["expense_ratio"] - cheapest["expense_ratio"]

            if er_gap > 0.3:
                worst_overlap = sel_sim["normalized_score"].max() if not sel_sim.empty else 0
                overlap_note  = (
                    f" They also share about <strong>{worst_overlap:.0f}%</strong> of the same stocks, "
                    f"so the pricier fund is not giving you much extra variety."
                    if worst_overlap >= 50 else ""
                )
                _10yr_impact = int(100_000 * ((1.12 ** 10) - ((1.12 - er_gap / 100) ** 10)))
                insights.append({
                    "category": "cost_risk", "type": "warning", "icon": "💸",
                    "text": (
                        f"<strong>Fee gap between funds:</strong> "
                        f"<strong>{display_name(costliest['fund_name'])}</strong> charges "
                        f"<strong>{costliest['expense_ratio']:.2f}%</strong> per year vs "
                        f"<strong>{display_name(cheapest['fund_name'])}</strong> at "
                        f"<strong>{cheapest['expense_ratio']:.2f}%</strong>. "
                        f"The <strong>{er_gap:.2f}%</strong> yearly difference adds up — on ₹1 lakh over "
                        f"10 years (if returns were ~12% before fees), that is roughly "
                        f"<strong>₹{_10yr_impact:,}</strong> more in charges on the expensive fund.{overlap_note}"
                    ),
                })
            elif len(er_df) > 1:
                avg_er = er_df["expense_ratio"].mean()
                insights.append({
                    "category": "cost_risk", "type": "success", "icon": "✅",
                    "text": (
                        f"<strong>Similar yearly fees:</strong> your funds charge about "
                        f"<strong>{avg_er:.2f}%</strong> on average — only "
                        f"<strong>{er_gap:.2f}%</strong> between the cheapest and priciest. "
                        f"Fees are not the main difference here; compare holdings and how bumpy returns are."
                    ),
                })

        sd_df = sel_master.dropna(subset=["std_dev"]).copy()
        sd_df["std_dev"] = pd.to_numeric(sd_df["std_dev"], errors="coerce")
        sd_df = sd_df.dropna(subset=["std_dev"])
        if not sd_df.empty:
            def _risk_label(v):
                if v < 13:   return "calmer"
                if v < 18:   return "moderately bumpy"
                return "quite bumpy"

            sd_df["_risk"] = sd_df["std_dev"].apply(_risk_label)
            riskiest  = sd_df.loc[sd_df["std_dev"].idxmax()]
            steadiest = sd_df.loc[sd_df["std_dev"].idxmin()]
            sd_gap    = riskiest["std_dev"] - steadiest["std_dev"]

            r_sd = float(riskiest["std_dev"])
            s_sd = float(steadiest["std_dev"])
            if sd_gap > 3:
                insights.append({
                    "category": "cost_risk", "type": "info", "icon": "📊",
                    "text": (
                        f"<strong>Some funds swing more than others:</strong> "
                        f"<strong>{display_name(riskiest['fund_name'])}</strong> has been "
                        f"<strong>{_risk_label(r_sd)}</strong> (typical yearly move around "
                        f"<strong>{r_sd:.1f}%</strong> vs its own average). "
                        f"<strong>{display_name(steadiest['fund_name'])}</strong> has been steadier "
                        f"(<strong>{s_sd:.1f}%</strong>). Mixing a calmer and a bumpier fund can "
                        f"smooth your overall ride a little."
                    ),
                })
            else:
                risk_labels = sd_df["_risk"].unique().tolist()
                label_str   = risk_labels[0] if len(risk_labels) == 1 else "similar"
                avg_sd      = sd_df["std_dev"].mean()
                insights.append({
                    "category": "cost_risk", "type": "info", "icon": "📊",
                    "text": (
                        f"<strong>Similar ups and downs:</strong> your funds have "
                        f"<strong>{label_str}</strong> year-to-year swings "
                        f"(around <strong>{avg_sd:.1f}%</strong> on average). "
                        f"Adding more funds like these may not calm your portfolio much. "
                        f"See <strong>Fund Performance</strong> for return and risk numbers."
                    ),
                })

    return insights


# ── NAV HEADER ────────────────────────────────────────────────────────────────

def nav_header(back_page=None, back_label="Back"):
    _t = st.session_state.get("fl_theme", "warm_light")
    back_pill = ""
    if back_page and back_page != "home":
        href = f"?nav={back_page}&theme={_t}"
        # Preserve selected_categories in URL so the explorer isn't empty after a reload
        if back_page == "explorer":
            cats = st.session_state.get("selected_categories", [])
            if cats:
                cats_enc = "|".join(urllib.parse.quote_plus(c) for c in cats)
                href = f"?nav={back_page}&cats={cats_enc}&theme={_t}"
        back_pill = f'<a href="{href}" target="_self" class="nav-pill">← {back_label}</a>'

    st.markdown(
        f'<div class="nav-pill-row">'
        f'<a href="?nav=home&theme={_t}" target="_self" class="nav-pill">🏠 Home</a>'
        f'{back_pill}'
        f'</div>'
        f'<div style="height:1px;background:rgba(255,255,255,0.08);margin:0 0 1.25rem;"></div>',
        unsafe_allow_html=True,
    )


# ── SIDEBAR ───────────────────────────────────────────────────────────────────

def render_sidebar():
    page = st.session_state.get("page", "home")

    with st.sidebar:
        st.markdown(
            '<div style="font-size:1.1rem;font-weight:800;color:#6C3CE1;'
            'display:flex;align-items:center;gap:.4rem;padding:.25rem 0 1.5rem;">'
            '<span style="font-size:1.25rem;">📊</span> FundLens</div>',
            unsafe_allow_html=True,
        )

        nav_items = [
            ("category",          ["category", "explorer", "compare"],
             "🔍", "Compare funds",   "Overlap · sector · holdings", "#EDE9FE", "#6C3CE1",
             "Compare up to 5 funds",
             ["Pairwise portfolio overlap (0–100%)", "Sector & holdings breakdown", "Common stocks with allocation trends"]),
            ("stock_explorer",    ["stock_explorer"],
             "📈", "Analyse a stock", "Which funds hold it",          "#DBEAFE", "#2563EB",
             "Stock-level intelligence",
             ["Search any stock by name", "See all funds holding it", "Allocation % + 3M/6M/1Y change"]),
            ("overlap_drilldown", ["overlap_drilldown"],
             "⊞",  "Overlap matrix",  "Full category view",           "#D1FAE5", "#059669",
             "Full category overlap matrix",
             ["Every fund-pair scored 0–100%", "Spot near-identical funds instantly", "Works across all 7 categories"]),
            ("portfolio_upload",  ["portfolio_upload", "portfolio_xray"],
             "📋", "Analyse Your Portfolio", "Upload your holdings",         "#FEF3C7", "#D97706",
             "X-Ray your portfolio",
             ["CSV / XLSX upload or manual entry", "Hidden stock & sector exposure", "Detect duplicate fund holdings"]),
        ]

        for target, active_pages, icon, title, sub, ic_bg, ic_color, tip_title, tip_bullets in nav_items:
            is_active   = page in active_pages
            card_bg     = "#F5F3FF"      if is_active else "#FAFAFA"
            card_border = "#7C3AED"      if is_active else "rgba(255,255,255,0.1)"
            title_color = "#6C3CE1"      if is_active else "#1A1A2E"
            arrow_color = "#6C3CE1"      if is_active else "#D1D5DB"
            shadow      = "0 2px 8px rgba(108,60,225,.10)" if is_active else "none"
            bullets_html = "".join(
                f'<div class="nav-tooltip-item"><span>▸</span>{b}</div>' for b in tip_bullets
            )
            st.markdown(
                f'<div class="nav-tooltip-wrap">'
                f'<a href="?nav={target}&theme={st.session_state.get("fl_theme","warm_light")}" target="_self" style="all:unset;display:block;cursor:pointer;">'
                f'<div style="background:{card_bg};border:1.5px solid {card_border};border-radius:12px;'
                f'padding:.75rem .85rem;margin-bottom:.5rem;box-shadow:{shadow};transition:all .15s;">'
                f'<div style="display:flex;align-items:center;gap:.7rem;">'
                f'<div style="width:2.25rem;height:2.25rem;border-radius:9px;background:{ic_bg};'
                f'display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0;">'
                f'{icon}</div>'
                f'<div style="flex:1;min-width:0;">'
                f'<div style="font-size:.85rem;font-weight:700;color:{title_color};">{title}</div>'
                f'<div style="font-size:.7rem;color:#9CA3AF;margin-top:2px;">{sub}</div>'
                f'</div>'
                f'<div style="font-size:.8rem;color:{arrow_color};font-weight:600;">→</div>'
                f'</div></div></a>'
                f'<div class="nav-tooltip">'
                f'<div class="nav-tooltip-title">{tip_title}</div>'
                f'{bullets_html}'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Stats at bottom
        st.markdown('<div style="height:2rem;"></div>', unsafe_allow_html=True)
        holdings = load_holdings()
        master   = load_master()
        n_funds  = master["fund_name"].nunique()    if not master.empty   else 0
        n_stocks = holdings["stock_name"].nunique() if not holdings.empty else 0
        n_cats   = master["category"].nunique()     if not master.empty   else 0
        st.markdown(
            f'<div style="font-size:.72rem;color:#9CA3AF;line-height:2;padding:.25rem 0;">'
            f'{n_funds} funds · <strong style="color:#6C3CE1;">{n_stocks} stocks</strong><br>'
            f'{n_cats} categories</div>',
            unsafe_allow_html=True,
        )


# ── WELCOME SCREEN ────────────────────────────────────────────────────────────

def render_welcome():
    st.markdown(
        '<div style="font-size:2rem;font-weight:900;color:#E2E8F0;line-height:1.2;margin-bottom:.75rem;">'
        'Invest with <span style="color:#6C3CE1;">clarity.</span><br>'
        'Backed by <span style="color:#6C3CE1;">data.</span></div>'
        '<p style="font-size:.95rem;color:#94A3B8;line-height:1.75;max-width:560px;margin:0 0 1.5rem;">'
        'Most mutual fund apps show NAV charts and SIP calculators. '
        'FundLens goes deeper — it reveals what\'s actually <em>inside</em> your funds.'
        '</p>',
        unsafe_allow_html=True,
    )

    features = [
        ("🔍", "Compare funds side-by-side",
         "Pick up to 5 funds and instantly see portfolio overlap, sector exposure, common holdings and redundancy across 231 funds in 7 categories."),
        ("📌", "Hidden stock exposure",
         "You might think you own 5 funds. But you actually own 12% HDFC Bank — sitting inside every single one of them. We surface that."),
        ("⊞", "Overlap matrix",
         "See the full overlap heatmap across every fund pair in a category. Instantly spot which funds are practically identical."),
        ("📋", "Analyse Your Portfolio",
         "Upload your existing holdings (CSV/XLSX) and get a full breakdown of true diversification, hidden concentration and duplicate funds."),
        ("📈", "Stock-level intelligence",
         "Pick any stock and see every fund that holds it, with allocation % and 3-month change — useful for tracking institutional conviction."),
    ]

    for icon, title, desc in features:
        st.markdown(
            f'<div style="display:flex;gap:1rem;align-items:flex-start;padding:1rem 1.25rem;'
            f'background:#141B2E;border:1px solid rgba(255,255,255,0.1);border-radius:12px;margin-bottom:.65rem;">'
            f'<div style="width:2.25rem;height:2.25rem;border-radius:9px;background:rgba(124,58,237,0.2);'
            f'display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0;">{icon}</div>'
            f'<div><div style="font-size:.9rem;font-weight:700;color:#E2E8F0;margin-bottom:.25rem;">{title}</div>'
            f'<div style="font-size:.82rem;color:#94A3B8;line-height:1.6;">{desc}</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<p style="font-size:.78rem;color:#9CA3AF;margin-top:1.5rem;text-align:center;">'
        'Select a feature from the sidebar to get started.</p>',
        unsafe_allow_html=True,
    )


# ── FL DESIGN SYSTEM ─────────────────────────────────────────────────────────

_FL_THEMES = {
    "warm_light":   dict(bg="#F5F4F0", nav="#FFFFFF", bdr="#E8E6DE", a="#2563EB",
                         al="rgba(37,99,235,0.08)",   body="#6B6965", head="#1A1A18",
                         card="#FFFFFF", sub="#ABA9A3"),
    "dark_premium": dict(bg="#0C0C0E", nav="#111113",  bdr="rgba(255,255,255,0.1)", a="#60A5FA",
                         al="rgba(96,165,250,0.12)",   body="#9CA3AF", head="#F9FAFB",
                         card="#141417", sub="#6B7280"),
    "ocean_blue":   dict(bg="#EFF6FF", nav="#FFFFFF",  bdr="#BFDBFE", a="#1D4ED8",
                         al="rgba(29,78,216,0.1)",     body="#4B5563", head="#1E3A5F",
                         card="#FFFFFF", sub="#93C5FD"),
    "forest_green": dict(bg="#F0FDF4", nav="#FFFFFF",  bdr="#BBF7D0", a="#16A34A",
                         al="rgba(22,163,74,0.1)",     body="#4B5563", head="#14532D",
                         card="#FFFFFF", sub="#86EFAC"),
    "soft_rose":    dict(bg="#FFF1F2", nav="#FFFFFF",  bdr="#FECDD3", a="#E11D48",
                         al="rgba(225,29,72,0.1)",     body="#4B5563", head="#881337",
                         card="#FFFFFF", sub="#FDA4AF"),
}
_FL_THEME_META = {
    "warm_light":   ("#EDE8D8", "Warm light"),
    "dark_premium": ("#1C1C20", "Dark premium"),
    "ocean_blue":   ("#93C5FD", "Ocean blue"),
    "forest_green": ("#86EFAC", "Forest green"),
    "soft_rose":    ("#FDA4AF", "Soft rose"),
}


def _fl_get_theme():
    if "fl_theme" not in st.session_state:
        st.session_state.fl_theme = "warm_light"
    t_name = st.session_state.fl_theme
    return t_name, _FL_THEMES.get(t_name, _FL_THEMES["warm_light"])


def _fl_inject_css(t, t_name):
    a=t["a"]; al=t["al"]; bg=t["bg"]; nb=t["nav"]; bdr=t["bdr"]
    cd=t["card"]; bd=t["body"]; hd=t["head"]; sb=t["sub"]
    a50=a+"80"  # 50% opacity accent
    a20=a+"33"  # 20% opacity accent (focus rings, subtle hovers)
    _dark = t_name == "dark_premium"
    if _dark:
        badge_css = (
            ".badge-high{background:rgba(239,68,68,0.15)!important;color:#FCA5A5!important;}"
            ".badge-medium{background:rgba(245,158,11,0.15)!important;color:#FDE68A!important;}"
            ".badge-low{background:rgba(16,185,129,0.15)!important;color:#6EE7B7!important;}"
        )
    else:
        badge_css = (
            ".badge-high{background:#FEE2E2!important;color:#DC2626!important;}"
            ".badge-medium{background:#FEF3C7!important;color:#D97706!important;}"
            ".badge-low{background:#D1FAE5!important;color:#059669!important;}"
        )
    st.markdown(f"""<style>
/* FundLens Design System — {t_name} */
html,html body{{background:{bg}!important;}}
html body [data-testid="stAppViewContainer"],
html body [data-testid="stMain"],
html body section[data-testid="stMain"],
html body .main{{background:{bg}!important;}}
html body .block-container{{
  padding:0!important;max-width:1280px!important;margin:0 auto!important;
  background:{bg}!important;min-height:100vh!important;}}
[data-testid="stSidebar"],[data-testid="stSidebarCollapseButton"]{{display:none!important;}}
html body section[data-testid="stMain"]{{margin-left:0!important;width:100%!important;}}
[data-testid="stMarkdownContainer"] p,[data-testid="stMarkdownContainer"] li{{color:{bd}!important;}}
/* ── Full theme override for all sub-pages ───────────────────────────────── */
html body h1,html body h2,html body h3,html body h4{{color:{hd}!important;}}
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4{{color:{hd}!important;}}
html body p,html body li{{color:{bd}!important;}}
/* Inputs */
.stTextInput input,.stNumberInput input,.stTextArea textarea{{
  background:{cd}!important;border:1.5px solid {bdr}!important;color:{hd}!important;}}
.stTextInput input::placeholder,.stTextArea textarea::placeholder{{color:{sb}!important;}}
/* Selectbox / multiselect (general) */
[data-testid="stSelectbox"]>div>div,
[data-testid="stMultiSelect"]>div>div{{
  background:{cd}!important;border:1.5px solid {bdr}!important;color:{hd}!important;}}
/* Checkbox / radio */
[data-testid="stCheckbox"] label,[data-testid="stCheckbox"] label span{{color:{bd}!important;}}
[data-testid="stRadio"] label,[data-testid="stRadio"] label span{{color:{bd}!important;}}
/* Buttons */
.stButton>button{{
  background:{cd}!important;border:1px solid {bdr}!important;color:{hd}!important;}}
.stButton>button p,.stButton>button span,.stButton>button div{{color:{hd}!important;}}
.stButton>button:hover{{border-color:{a}!important;color:{a}!important;background:{cd}!important;}}
.stButton>button[kind="primaryFormSubmit"],
.stButton>button[kind="primary"],
button[data-testid="baseButton-primary"]{{
  background:{a}!important;border-color:{a}!important;color:#fff!important;}}
button[data-testid="baseButton-primary"] p,
button[data-testid="baseButton-primary"] span,
button[data-testid="baseButton-primary"] div,
.stButton>button[kind="primary"] p,
.stButton>button[kind="primary"] span{{color:#fff!important;}}
.stButton>button[kind="primary"]:hover,
button[data-testid="baseButton-primary"]:hover{{background:{a}!important;opacity:.9!important;}}
/* Tabs */
[data-testid="stTabs"] [data-baseweb="tab-list"]{{border-bottom:1px solid {bdr}!important;}}
[data-testid="stTabs"] [data-baseweb="tab"]{{color:{sb}!important;}}
[data-testid="stTabs"] [aria-selected="true"]{{color:{a}!important;border-bottom-color:{a}!important;}}
[data-testid="stTabs"] [data-baseweb="tab"]:hover{{color:{bd}!important;}}
/* Expanders */
[data-testid="stExpander"]{{background:{cd}!important;border:1px solid {bdr}!important;}}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span{{color:{bd}!important;}}
/* Generic cards */
.card,.metric-card{{background:{cd}!important;border:1px solid {bdr}!important;}}
/* Category-select cards */
.cat-card-inner{{background:{cd}!important;border:1.5px solid {bdr}!important;}}
.cat-card-inner.selected{{background:{al}!important;border:1.5px solid {a50}!important;box-shadow:0 0 0 3px {a20}!important;}}
.section-title{{color:{hd}!important;}}
.section-sub{{color:{sb}!important;}}
.cat-card-col [data-testid="stCheckbox"] label,
.cat-card-col [data-testid="stCheckbox"] label span{{color:{bd}!important;}}
/* Streamlit metrics */
[data-testid="stMetricLabel"]>div{{color:{bd}!important;}}
[data-testid="stMetricValue"]{{color:{hd}!important;}}
[data-testid="stMetricDelta"]{{color:{bd}!important;}}
/* Alerts */
[data-testid="stAlert"]{{background:{al}!important;border-color:{a}!important;color:{hd}!important;}}
/* Navbar — built with st.columns so theme picker is a native selectbox (single-click) */
.block-container>[data-testid="stVerticalBlock"]>[data-testid="stHorizontalBlock"]:first-child{{
  background:{nb}!important;border-bottom:1px solid {bdr}!important;
  padding:0 1rem!important;position:sticky!important;top:0!important;
  z-index:999!important;box-shadow:0 1px 4px rgba(0,0,0,.06)!important;
  min-height:58px!important;align-items:center!important;
  gap:0!important;margin:0!important;}}
.block-container>[data-testid="stVerticalBlock"]>[data-testid="stHorizontalBlock"]:first-child>[data-testid="stColumn"]{{
  display:flex!important;align-items:center!important;
  padding:.4rem .6rem!important;min-height:58px!important;}}
.fl-theme-picker{{position:relative;display:inline-block;}}
.fl-theme-picker summary{{
  display:inline-flex;align-items:center;gap:6px;padding:4px 12px;
  border:1px solid {bdr};border-radius:20px;font-size:0.72rem;font-weight:500;
  color:{bd};background:transparent;cursor:pointer;list-style:none;
  user-select:none;white-space:nowrap;}}
.fl-theme-picker summary::-webkit-details-marker{{display:none;}}
.fl-theme-picker[open] summary{{border-color:{a};color:{a};}}
.fl-theme-picker summary:hover{{background:{bdr};border-color:{a};color:{a};}}
.fl-theme-dropdown{{
  position:absolute;right:0;top:calc(100% + 6px);background:{cd};
  border:1px solid {bdr};border-radius:10px;padding:8px 6px;min-width:168px;
  z-index:9999;box-shadow:0 4px 16px rgba(0,0,0,0.10);}}
.fl-logo{{font-size:1.05rem;font-weight:800;color:{a};text-decoration:none!important;
  letter-spacing:-.02em;display:flex;align-items:center;gap:.4rem;}}
.fl-nav-links{{display:flex;height:100%;align-items:center;gap:.05rem;}}
.fl-nav-link{{display:flex;align-items:center;height:100%;padding:0 .9rem;
  font-size:.82rem;font-weight:500;color:{bd};text-decoration:none!important;
  border-bottom:2px solid transparent;transition:color .15s,border-color .15s;
  white-space:nowrap;}}
.fl-nav-link:hover{{color:{a};}}
.fl-nav-link.active{{color:{a}!important;font-weight:600;border-bottom-color:{a};}}
.fl-body{{max-width:1180px;margin:0 auto;padding:3.5rem 2.5rem 3rem;
  display:grid;grid-template-columns:1fr 360px;gap:4rem;align-items:start;}}
.fl-pg-body{{max-width:1180px;margin:0 auto;padding:3.5rem 2.5rem 3rem;}}
.fl-tag{{display:inline-flex;align-items:center;gap:.4rem;font-size:.67rem;font-weight:700;
  letter-spacing:2px;text-transform:uppercase;color:{a};background:{al};
  border-radius:9999px;padding:.28rem 1rem;margin-bottom:1.5rem;}}
.fl-tag-dot{{width:6px;height:6px;border-radius:50%;background:{a};}}
.fl-h1{{font-size:2.85rem;font-weight:900;color:{hd};line-height:1.15;
  letter-spacing:-.04em;margin-bottom:.65rem;}}
.fl-h1 em{{font-style:normal;color:{a};}}
.fl-sub{{font-size:.93rem;color:{bd};line-height:1.72;margin-bottom:2.25rem;}}
.fl-feat{{display:flex;align-items:flex-start;gap:1rem;padding:1.05rem 0;border-bottom:1px solid {bdr};}}
.fl-feat:last-child{{border-bottom:none;padding-bottom:0;}}
.fl-feat-ico{{width:36px;height:36px;border-radius:9px;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;font-size:.95rem;}}
.fl-feat-t{{font-size:.87rem;font-weight:700;color:{hd};margin-bottom:.2rem;}}
.fl-feat-d{{font-size:.78rem;color:{bd};line-height:1.6;}}
.fl-stats{{display:flex;margin-top:2rem;border:1px solid {bdr};border-radius:12px;overflow:hidden;}}
.fl-stat{{flex:1;text-align:center;padding:.85rem .5rem;background:{cd};border-right:1px solid {bdr};}}
.fl-stat:last-child{{border-right:none;}}
.fl-stat-v{{font-size:1.4rem;font-weight:800;color:{a};font-feature-settings:"tnum";line-height:1;}}
.fl-stat-l{{font-size:.6rem;text-transform:uppercase;letter-spacing:.6px;color:{sb};font-weight:600;margin-top:4px;}}
.fl-ask{{background:{cd};border:1px solid {bdr};border-radius:14px;padding:.9rem 1rem;}}
.fl-ask-hdr{{display:flex;align-items:center;gap:.55rem;margin-bottom:.7rem;}}
.fl-ask-label{{font-size:.62rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:{sb};}}
.fl-ask-badge{{font-size:.56rem;font-weight:700;letter-spacing:.8px;text-transform:uppercase;
  background:{al};color:{a};padding:.18rem .6rem;border-radius:9999px;}}
.fl-ask-q{{background:{bg};border:1px solid {bdr};border-radius:8px;
  padding:.4rem .7rem;font-size:.72rem;color:{hd};margin-bottom:.35rem;}}
.fl-ask-input-area{{margin-top:.65rem;border:1px solid {bdr};border-radius:8px;
  background:{bg};display:flex;align-items:center;gap:.5rem;padding:.45rem .7rem;}}
.fl-ask-ico{{font-size:.78rem;color:{sb};}}
.fl-ask-inp{{flex:1;border:none;background:transparent;font-size:.72rem;color:{hd};outline:none;}}
.fl-ask-inp::placeholder{{color:{sb};}}
.fl-ask-foot{{font-size:.63rem;color:{sb};text-align:center;margin-top:.45rem;}}
.fl-pg-h1{{font-size:1.85rem;font-weight:800;color:{hd};margin-bottom:.3rem;letter-spacing:-.02em;}}
.fl-pg-sub{{font-size:.88rem;color:{bd};line-height:1.6;}}
.fl-af-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:1.25rem;margin-top:2.25rem;}}
.fl-af-card{{background:{cd};border:1px solid {bdr};border-radius:16px;
  padding:1.6rem 1.4rem;display:block;text-decoration:none!important;
  transition:border-color .15s,box-shadow .15s;position:relative;}}
.fl-af-card *{{text-decoration:none!important;}}
.fl-af-card:hover{{border-color:{a};box-shadow:0 6px 24px {al};}}
.fl-af-arr{{position:absolute;top:1.5rem;right:1.4rem;font-size:1rem;color:{sb};}}
.fl-af-ico{{width:42px;height:42px;border-radius:11px;margin-bottom:1.1rem;
  display:flex;align-items:center;justify-content:center;font-size:1.15rem;}}
.fl-af-title{{font-size:.95rem;font-weight:700;color:{hd};margin-bottom:.4rem;}}
.fl-af-desc{{font-size:.79rem;color:{bd};line-height:1.65;margin-bottom:1.25rem;}}
.fl-af-foot{{font-size:.71rem;color:{sb};}}
.fl-disc{{text-align:center;font-size:.7rem;color:{sb};
  border-top:1px solid {bdr};padding:1.25rem 2.5rem;line-height:1.65;}}
.fl-breadcrumb{{display:flex;align-items:center;gap:.4rem;padding:.6rem 2.5rem;
  font-size:.76rem;border-bottom:1px solid {bdr};background:{nb};}}
.fl-bc-link{{color:{a};text-decoration:none!important;font-weight:500;opacity:.8;}}
.fl-bc-link:hover{{opacity:1;}}
.fl-bc-sep{{color:{sb};}}
.fl-bc-cur{{color:{hd};font-weight:600;}}
/* ── Override global hardcoded purples ─────────────────────────────────── */
.stTextInput input:focus,.stNumberInput input:focus,.stTextArea textarea:focus{{
  border-color:{a}!important;box-shadow:0 0 0 3px {a20}!important;}}
.metric-value{{color:{a}!important;}}
.metric-card{{background:{cd}!important;border-color:{bdr}!important;color:{hd}!important;}}
.metric-card:hover,.metric-card-link:hover .metric-card{{
  border-color:{a50}!important;background:{al}!important;
  box-shadow:0 8px 32px {a20}!important;}}
.metric-label{{color:{bd}!important;}}
.metric-sub{{color:{sb}!important;}}
.app-logo{{color:{a}!important;}}
.insight-info{{background:{al}!important;border-left-color:{a}!important;}}
.overlap-bar-fill{{background:linear-gradient(90deg,{a},{a50})!important;}}
.overlap-row{{background:{cd}!important;border-color:{bdr}!important;}}
.overlap-row:hover{{border-color:{a50}!important;}}
.overlap-bar-bg{{background:{bdr}!important;}}
.section-title{{color:{hd}!important;}}
.section-sub{{color:{sb}!important;}}
.insight-text{{color:{bd}!important;}}
.disclaimer{{background:{al}!important;border-color:{bdr}!important;color:{sb}!important;}}
.nav-pill:hover{{border-color:{a50}!important;color:{a}!important;background:{al}!important;}}
.journey-card:hover{{border-color:{a50}!important;}}
/* Dataframe containers */
[data-testid="stDataFrame"]>div{{border:1px solid {bdr}!important;border-radius:0 0 12px 12px!important;overflow:hidden!important;}}
.tbl-hdr{{background:{a};color:#fff;font-size:0.8rem;font-weight:700;
  padding:0.6rem 1rem;border-radius:12px 12px 0 0;margin-bottom:0;line-height:1.3;}}
.tbl-sub-hdr{{font-size:0.65rem;color:rgba(255,255,255,0.78);margin-top:2px;}}
{badge_css}
</style>""", unsafe_allow_html=True)


def _fl_render_navbar(t, t_name, active_page):
    links_html = ""
    for key, label in [("home", "Home"), ("analyse_funds", "Analyse funds"), ("portfolio_upload", "Analyse your portfolio")]:
        active_cls = " active" if key == active_page else ""
        links_html += f'<a href="?nav={key}&theme={t_name}" target="_self" class="fl-nav-link{active_cls}">{label}</a>'

    _current_page = st.session_state.get("page", active_page)
    _theme_rows = ""
    for tk, (tc, tname) in _FL_THEME_META.items():
        _is_sel   = tk == t_name
        _row_bg   = t["al"] if _is_sel else "transparent"
        _name_col = t["a"] if _is_sel else t["body"]
        _name_wt  = "700" if _is_sel else "500"
        _check    = f'<span style="margin-left:auto;color:{t["a"]};font-size:0.65rem;">✓</span>' if _is_sel else ""
        _theme_rows += (
            f'<a href="?nav={_current_page}&theme={tk}" target="_self" '
            f'style="display:flex;align-items:center;gap:9px;padding:6px 8px;'
            f'border-radius:7px;text-decoration:none;background:{_row_bg};margin-bottom:1px;">'
            f'<div style="width:12px;height:12px;border-radius:50%;background:{tc};'
            f'box-shadow:0 0 0 1.5px {t["bdr"]};flex-shrink:0;"></div>'
            f'<span style="font-size:0.75rem;font-weight:{_name_wt};color:{_name_col};">{tname}</span>'
            f'{_check}</a>'
        )
    _theme_picker = (
        f'<details class="fl-theme-picker">'
        f'<summary>🎨&nbsp;&nbsp;Theme</summary>'
        f'<div class="fl-theme-dropdown">'
        f'<div style="font-size:0.6rem;font-weight:700;color:{t["sub"]};text-transform:uppercase;'
        f'letter-spacing:0.6px;padding:2px 8px 8px;">Select theme</div>'
        f'{_theme_rows}</div></details>'
    )

    col_l, col_c, col_r = st.columns([2, 10, 1.2])
    with col_l:
        st.markdown(
            f'<a href="?nav=home&theme={t_name}" target="_self" class="fl-logo">📊 FundLens</a>',
            unsafe_allow_html=True,
        )
    with col_c:
        st.markdown(
            f'<div class="fl-nav-links">{links_html}</div>',
            unsafe_allow_html=True,
        )
    with col_r:
        st.markdown(_theme_picker, unsafe_allow_html=True)


def _fl_render_breadcrumb(crumbs):
    """crumbs = list of (label, nav_key_or_None); last item = current page (no link)."""
    _t = st.session_state.get("fl_theme", "warm_light")
    parts = []
    for i, (label, nav_key) in enumerate(crumbs):
        if nav_key:
            parts.append(f'<a href="?nav={nav_key}&theme={_t}" target="_self" class="fl-bc-link">{label}</a>')
        else:
            parts.append(f'<span class="fl-bc-cur">{label}</span>')
        if i < len(crumbs) - 1:
            parts.append('<span class="fl-bc-sep">›</span>')
    st.markdown(f'<div class="fl-breadcrumb">{"".join(parts)}</div>', unsafe_allow_html=True)


# ── PAGE: HOME ────────────────────────────────────────────────────────────────

def page_home():
    t_name, t = _fl_get_theme()
    _fl_inject_css(t, t_name)
    _fl_render_navbar(t, t_name, "home")

    holdings   = load_holdings()
    similarity = load_similarity()
    master     = load_master()
    n_funds  = master["fund_name"].nunique()    if not master.empty   else 0
    n_cats   = master["category"].nunique()     if not master.empty   else 0
    n_unique = holdings["stock_name"].nunique() if not holdings.empty else 0
    max_sim  = similarity["normalized_score"].max() if not similarity.empty else 0

    _feats = [
        ("rgba(83,74,183,0.12)",  "🔀", "Find out how much your funds actually overlap",
         "Pick any two funds and see the percentage of holdings they share, the common stocks, "
         "and whether holding both is adding any real diversification."),
        ("rgba(16,185,129,0.12)", "🏦", "Track how funds are betting on individual stocks",
         "Search any stock — HDFC Bank, Infosys, Reliance — and see which funds hold it, "
         "how heavily they're positioned, and how that's changed recently."),
        ("rgba(249,115,22,0.12)", "🔗", "See which funds in a category are just copies of each other",
         f"The overlap matrix maps every fund pair in a category. We found two large cap funds "
         f"sharing {int(max_sim)}% of holdings — charging different expense ratios."),
    ]
    feats_html = "".join(
        f'<div class="fl-feat">'
        f'<div class="fl-feat-ico" style="background:{ib};">{ic}</div>'
        f'<div><div class="fl-feat-t">{ti}</div><div class="fl-feat-d">{de}</div></div>'
        f'</div>'
        for ib, ic, ti, de in _feats
    )

    st.markdown(
        f'<div class="fl-body">'
        f'<div>'
        f'<div class="fl-tag"><span class="fl-tag-dot"></span>Mutual fund transparency</div>'
        f'<div class="fl-h1">Do your funds <em>actually</em> diversify your portfolio?</div>'
        f'<div class="fl-sub">Most investors hold 4–6 mutual funds thinking they\'re diversified. '
        f'FundLens checks that assumption — by looking inside every fund and showing you what you '
        f'really own.</div>'
        f'{feats_html}'
        f'</div>'
        f'<div>'
        f'<div class="fl-ask">'
        f'<div class="fl-ask-hdr">'
        f'<span class="fl-ask-label">Ask FundLens</span>'
        f'<span class="fl-ask-badge">Coming Soon</span>'
        f'</div>'
        f'<div class="fl-ask-q">"Which large cap funds overlap the least?"</div>'
        f'<div class="fl-ask-q">"Am I diversified with HDFC and Mirae?"</div>'
        f'<div class="fl-ask-q">"Which funds cut Reliance this quarter?"</div>'
        f'<div class="fl-ask-input-area">'
        f'<span class="fl-ask-ico">💬</span>'
        f'<input class="fl-ask-inp" placeholder="Ask anything about funds…" disabled />'
        f'</div>'
        f'<div class="fl-ask-foot">Conversational analysis — coming soon</div>'
        f'</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="fl-disc">Portfolio analytics and transparency — not investment advice</div>',
        unsafe_allow_html=True,
    )


# ── PAGE: ANALYSE FUNDS ───────────────────────────────────────────────────────

def page_analyse_funds():
    t_name, t = _fl_get_theme()
    _fl_inject_css(t, t_name)
    _fl_render_navbar(t, t_name, "analyse_funds")

    holdings   = load_holdings()
    similarity = load_similarity()
    master     = load_master()
    n_funds  = master["fund_name"].nunique()    if not master.empty   else 0
    n_cats   = master["category"].nunique()     if not master.empty   else 0
    n_unique = holdings["stock_name"].nunique() if not holdings.empty else 0
    max_sim  = int(similarity["normalized_score"].max()) if not similarity.empty else 0

    _cards = [
        (f"?nav=category&theme={t_name}",          "rgba(83,74,183,0.15)",  "🔍",
         "Compare funds",
         "Pick up to 5 funds and see their overlap, sector exposure, and common holdings side by side.",
         f"{n_funds} funds · {n_cats} categories"),
        (f"?nav=stock_explorer&theme={t_name}",    "rgba(16,185,129,0.15)", "🏦",
         "Inspect a stock",
         "Pick any stock and see every fund holding it, at what weight, and how conviction is shifting.",
         f"{n_unique} unique stocks tracked"),
        (f"?nav=overlap_drilldown&theme={t_name}", "rgba(249,115,22,0.15)", "🔗",
         "Overlap matrix",
         "Full pairwise overlap across every fund in a category — spot which pairs are nearly identical.",
         f"Highest overlap found: {max_sim}%"),
    ]
    cards_html = "".join(
        f'<a href="{hr}" target="_self" class="fl-af-card">'
        f'<span class="fl-af-arr">→</span>'
        f'<div class="fl-af-ico" style="background:{ib};">{ic}</div>'
        f'<div class="fl-af-title">{ti}</div>'
        f'<div class="fl-af-desc">{de}</div>'
        f'<div class="fl-af-foot">{ft}</div>'
        f'</a>'
        for hr, ib, ic, ti, de, ft in _cards
    )

    st.markdown(
        f'<div class="fl-pg-body">'
        f'<div class="fl-pg-h1">Analyse funds</div>'
        f'<div class="fl-pg-sub">Choose what you want to explore</div>'
        f'<div class="fl-af-grid">{cards_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="fl-disc">Portfolio analytics and transparency — not investment advice</div>',
        unsafe_allow_html=True,
    )


# ── PAGE: CATEGORY SELECT ─────────────────────────────────────────────────────

def page_category_select():
    t_name, t = _fl_get_theme()
    _fl_inject_css(t, t_name)
    _fl_render_navbar(t, t_name, "analyse_funds")
    _fl_render_breadcrumb([("Home", "home"), ("Analyse Funds", "analyse_funds"), ("Compare Funds", None)])
    holdings = load_holdings()
    fund_counts = {}
    if not holdings.empty:
        fund_counts = holdings.groupby("category")["fund_name"].nunique().to_dict()

    if "selected_categories" not in st.session_state:
        st.session_state.selected_categories = []

    n_sel = len(st.session_state.selected_categories)

    # ── Header row: title left, Explore CTA right ────────────────────────────
    h1, h2 = st.columns([3, 2], gap="medium")
    with h1:
        st.markdown(
            f'<div style="font-size:1.3rem;font-weight:800;color:{t["head"]};margin-bottom:.2rem;">'
            f'Choose Fund Category</div>'
            f'<div style="font-size:.8rem;color:{t["body"]};">'
            f'Tap a category to select · mix multiple for cross-category comparison</div>',
            unsafe_allow_html=True,
        )
    with h2:
        if n_sel > 0:
            sel_labels = " + ".join(st.session_state.selected_categories)
            if st.button(f"Explore {sel_labels} →", type="primary",
                         use_container_width=True, key="cat_explore_top"):
                st.session_state.selected_funds = []
                st.session_state.page = "explorer"
                st.rerun()
        else:
            st.markdown(
                f'<div style="text-align:right;font-size:.8rem;color:{t["body"]};padding-top:.6rem;">'
                f'Select a category to continue →</div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div style="height:.6rem;"></div>', unsafe_allow_html=True)

    # ── Category cards ────────────────────────────────────────────────────────
    categories = [
        ("Large Cap",       "🏛️", "Top 100 companies by market cap"),
        ("Mid Cap",         "📈", "Ranked 101–250, moderate risk"),
        ("Small Cap",       "🚀", "Ranked 251+, higher volatility"),
        ("Large & Mid Cap", "⚖️", "Blend of top 250 companies"),
        ("Multi Cap",       "🔀", "Mandatory across all cap sizes"),
        ("Flexi Cap",       "🔄", "Flexible across all caps"),
        ("ELSS",            "💰", "Tax saving, 3-year lock-in"),
    ]

    def cat_card(name, icon, desc, row_key):
        count  = fund_counts.get(name, 0)
        is_sel = name in st.session_state.selected_categories
        sel_cls = " selected" if is_sel else ""
        tc      = t["a"] if is_sel else t["head"]

        st.markdown(
            f'<div class="cat-card-inner{sel_cls}">'
            f'<div style="font-size:1.5rem;margin-bottom:.35rem;">{icon}</div>'
            f'<div style="font-size:.88rem;font-weight:700;color:{tc};margin-bottom:.2rem;">{name}</div>'
            f'<div style="font-size:.7rem;color:{t["sub"]};margin-bottom:.5rem;line-height:1.4;">{desc}</div>'
            f'<span style="background:{t["al"]};color:{t["a"]};border-radius:9999px;'
            f'font-size:.62rem;font-weight:700;padding:2px 8px;">{count} funds</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        checked = st.checkbox("Select", value=is_sel, key=f"chk_{name}_{row_key}")
        if checked != is_sel:
            cats = list(st.session_state.selected_categories)
            if checked:
                cats.append(name)
            else:
                cats = [c for c in cats if c != name]
            st.session_state.selected_categories = cats
            st.rerun()

    # Row 1: first 4
    r1 = st.columns(4, gap="small")
    for i, (name, icon, desc) in enumerate(categories[:4]):
        with r1[i]:
            cat_card(name, icon, desc, "r1")

    st.markdown('<div style="height:.4rem;"></div>', unsafe_allow_html=True)

    # Row 2: remaining 3 (last column intentionally empty)
    r2 = st.columns(4, gap="small")
    for i, (name, icon, desc) in enumerate(categories[4:]):
        with r2[i]:
            cat_card(name, icon, desc, "r2")

    if n_sel == 0:
        st.markdown(
            '<div style="text-align:center;font-size:.8rem;color:#D1D5DB;margin-top:.5rem;">'
            'Select one or more categories above to continue</div>',
            unsafe_allow_html=True,
        )


# ── PAGE: FUND EXPLORER ───────────────────────────────────────────────────────

def page_fund_explorer():
    t_name, t = _fl_get_theme()
    _fl_inject_css(t, t_name)
    _fl_render_navbar(t, t_name, "analyse_funds")
    _fl_render_breadcrumb([("Home", "home"), ("Analyse Funds", "analyse_funds"), ("Compare Funds", "category"), ("Fund Explorer", None)])
    _hd = t["head"]; _bd = t["body"]; _sb = t["sub"]
    _cd = t["card"]; _bdr = t["bdr"]; _a = t["a"]; _al = t["al"]
    _a50 = _a + "80"  # 50% opacity accent for subtle borders

    selected_cats = st.session_state.get("selected_categories", ["Large Cap"])
    holdings      = load_holdings()
    master_df     = load_master()
    similarity    = load_similarity()
    enriched      = compute_fund_enriched(holdings, master_df)
    cat_funds     = enriched[enriched["category"].isin(selected_cats)].copy()

    if "selected_funds"  not in st.session_state: st.session_state.selected_funds  = []
    if "explorer_layout" not in st.session_state: st.session_state.explorer_layout = "D"

    show_cat_filter = len(selected_cats) > 1
    title  = " + ".join(selected_cats) if selected_cats else "All Funds"
    layout = st.session_state.explorer_layout

    # ── Header + layout switcher ──────────────────────────────────────────────
    ht, hs = st.columns([3, 2])
    with ht:
        st.markdown(f"## {title}")
        st.markdown(
            f"<p style='color:{_bd};margin-top:-0.5rem;margin-bottom:0.5rem;'>"
            "Browse funds and add up to 5 to compare portfolios side by side.</p>",
            unsafe_allow_html=True,
        )
    with hs:
        st.markdown(
            f'<div style="text-align:right;font-size:0.72rem;color:{_sb};'
            f'font-weight:600;margin-bottom:4px;">Choose layout</div>',
            unsafe_allow_html=True,
        )
        la, lb, lc, ld = st.columns(4)
        for code, label, col in [("A","Cards",la),("B","Split",lb),("C","Table",lc),("D","Search",ld)]:
            with col:
                if st.button(label, key=f"lsw_{code}",
                             type="primary" if layout == code else "secondary",
                             use_container_width=True):
                    if layout != code:
                        st.session_state.explorer_layout = code
                        st.rerun()

    selected = list(st.session_state.selected_funds)
    n_sel    = len(selected)
    amcs_list = ["All AMCs"] + sorted(cat_funds["fund_house"].dropna().unique().tolist())

    # ── Shared helpers ────────────────────────────────────────────────────────
    def apply_filters(df, search, amc, cat, sort):
        f = df.copy()
        if search:
            mask = (f["fund_name"].str.contains(search, case=False, na=False) |
                    f["fund_house"].str.contains(search, case=False, na=False))
            f = f[mask]
        if amc != "All AMCs":
            f = f[f["fund_house"] == amc]
        if cat != "All Categories":
            f = f[f["category"] == cat]
        sm = {
            "Star Rating (High→Low)":             ("star_rating",             False),
            "3Y Return (High→Low)":               ("return_3y",               False),
            "1Y Return (High→Low)":               ("return_1y",               False),
            "5Y Return (High→Low)":               ("return_5y",               False),
            "Returns Since Inception (High→Low)": ("return_since_inception",   False),
            "Consistency (High→Low)":             ("consistency_score",        False),
            "AUM (High→Low)":                     ("aum_cr",                  False),
            "AUM (Low→High)":                     ("aum_cr",                  True),
            "Expense Ratio (Low→High)":           ("expense_ratio",           True),
            "Holdings Count":                     ("holding_count",           False),
        }
        if sort in sm:
            sc, sa = sm[sort]
            if sc in f.columns:
                f = f.sort_values(sc, ascending=sa, na_position="last")
        return f

    def overlap_warns(sel):
        if len(sel) < 2 or similarity.empty:
            return ""
        sim = similarity[similarity["fund_a"].isin(sel) & similarity["fund_b"].isin(sel)]
        parts = [
            f'<span style="background:rgba(245,158,11,0.12);color:#92400E;border-radius:9999px;'
            f'border:1px solid rgba(245,158,11,0.35);padding:3px 10px;font-size:0.72rem;font-weight:600;">'
            f'⚠ {short_name(r["fund_a"])} ↔ {short_name(r["fund_b"])}: '
            f'{r["normalized_score"]:.0f}% overlap</span>'
            for _, r in sim[sim["normalized_score"] >= 60]
                          .sort_values("normalized_score", ascending=False).head(2).iterrows()
        ]
        return ('<div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;">'
                + " ".join(parts) + "</div>") if parts else ""

    def stars_html(rating):
        if rating is None or (isinstance(rating, float) and np.isnan(rating)):
            return f'<span style="color:{_sb};font-size:0.75rem;">Not rated</span>'
        r = int(rating)
        filled = "★" * r
        empty  = "☆" * (5 - r)
        colour = {5:"#F59E0B", 4:"#F59E0B", 3:"#6B7280", 2:"#EF4444", 1:"#EF4444"}.get(r, "#6B7280")
        return (f'<span style="color:{colour};font-size:0.95rem;letter-spacing:1px;">{filled}</span>'
                f'<span style="color:{_sb};font-size:0.95rem;letter-spacing:1px;">{empty}</span>')

    def fund_info(fund):
        aum_str = format_aum(fund.get("aum_cr", ""))
        er_val  = fund.get("expense_ratio")
        er_str  = f"{float(er_val):.2f}%" if pd.notna(er_val) else "—"
        hc_val  = fund.get("holding_count")
        hc_str  = str(int(hc_val)) if pd.notna(hc_val) else "—"
        top_sec = str(fund.get("top_sector") or "—").title()
        amc_str = str(fund.get("fund_house") or "—")
        cat_str = str(fund.get("category") or "")
        r1y = fund.get("return_1y");  r1y_str = f"{r1y:+.1f}%" if pd.notna(r1y) else "—"
        r3y = fund.get("return_3y");  r3y_str = f"{r3y:+.1f}%" if pd.notna(r3y) else "—"
        r5y = fund.get("return_5y");  r5y_str = f"{r5y:+.1f}%" if pd.notna(r5y) else "—"
        rsi = fund.get("return_since_inception"); rsi_str = f"{rsi:+.1f}%" if pd.notna(rsi) else "—"
        star = fund.get("star_rating")
        return aum_str, er_str, hc_str, top_sec, amc_str, cat_str, r1y_str, r3y_str, r5y_str, rsi_str, star

    def chips_html(sel):
        return "".join(
            f'<span style="background:{_al};color:{_a};border-radius:9999px;'
            f'padding:4px 12px;font-size:0.78rem;font-weight:600;white-space:nowrap;">'
            f'{short_name(fn)}</span>'
            for fn in sel
        )

    def selection_tray(sel, n, cmp_key, clr_key):
        if n == 0:
            st.markdown(
                f'<div style="background:{_al};border:1.5px dashed {_bdr};border-radius:10px;'
                f'padding:0.75rem 1rem;font-size:0.82rem;color:{_sb};text-align:center;">'
                f'Add 2–5 funds below to compare.</div>',
                unsafe_allow_html=True,
            )
        else:
            tc, cc = st.columns([5, 1])
            with tc:
                st.markdown(
                    f'<div style="background:{_al};border:1.5px solid {_a50};'
                    f'border-radius:10px;padding:0.75rem 1rem;">'
                    f'<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">'
                    f'<span style="font-size:0.72rem;color:{_a};font-weight:700;'
                    f'white-space:nowrap;">{n} of 5 selected:</span>'
                    f'{chips_html(sel)}</div>{overlap_warns(sel)}</div>',
                    unsafe_allow_html=True,
                )
            with cc:
                if st.button("Compare →", type="primary", disabled=(n < 2),
                             use_container_width=True, key=cmp_key):
                    st.session_state.page = "compare"
                    st.rerun()
            if st.button("Clear selection", key=clr_key):
                st.session_state.selected_funds = []
                st.rerun()

    # ─── LAYOUT A: Card Grid ─────────────────────────────────────────────────
    if layout == "A":
        fc = st.columns([3, 2, 2, 2] if show_cat_filter else [3, 2, 2])
        search     = fc[0].text_input("Search", placeholder="Fund name or AMC…",
                                       label_visibility="collapsed", key="a_srch")
        amc_filter = fc[1].selectbox("AMC", amcs_list,
                                      label_visibility="collapsed", key="a_amc")
        sort_by    = fc[2].selectbox(
            "Sort", ["Star Rating (High→Low)", "3Y Return (High→Low)", "1Y Return (High→Low)", "5Y Return (High→Low)", "Returns Since Inception (High→Low)", "Consistency (High→Low)", "AUM (High→Low)", "AUM (Low→High)", "Expense Ratio (Low→High)", "Holdings Count"],
            label_visibility="collapsed", key="a_sort",
        )
        cat_filter = "All Categories"
        if show_cat_filter:
            cat_filter = fc[3].selectbox("Category",
                                          ["All Categories"] + sorted(selected_cats),
                                          label_visibility="collapsed", key="a_cat")
        filtered = apply_filters(cat_funds, search, amc_filter, cat_filter, sort_by)

        st.markdown("<br>", unsafe_allow_html=True)
        selection_tray(selected, n_sel, "a_cmp", "a_clr")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-sub">{len(filtered)} fund{"s" if len(filtered)!=1 else ""}'
            f' — click a card to add it to your comparison</div>',
            unsafe_allow_html=True,
        )
        fund_list = list(filtered.iterrows())
        for row_start in range(0, len(fund_list), 3):
            chunk = fund_list[row_start:row_start + 3]
            cols  = st.columns(3, gap="medium")
            for ci, (_, fund) in enumerate(chunk):
                fn     = fund["fund_name"]
                is_sel = fn in selected
                at_max = n_sel >= 5 and not is_sel
                aum_str, er_str, hc_str, top_sec, amc_str, cat_str, r1y_str, r3y_str, r5y_str, rsi_str, star = fund_info(fund)
                border = f"1.5px solid {_a50}" if is_sel else f"1px solid {_bdr}"
                bg     = _al                  if is_sel else _cd
                shadow = "none"
                name_c = _a                   if is_sel else _hd
                badge  = (
                    f'<div style="margin-top:8px;"><span style="background:{_al};color:{_a};'
                    f'border-radius:9999px;padding:2px 8px;font-size:0.65rem;font-weight:700;">'
                    f'✓ In comparison</span></div>'
                ) if is_sel else ""
                with cols[ci]:
                    st.markdown(f"""
                    <div style="background:{bg};border:{border};border-radius:14px 14px 6px 6px;
                                padding:1.25rem 1.25rem 0.75rem;box-shadow:{shadow};">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:2px;">
                            <div style="font-size:0.85rem;font-weight:700;color:{name_c};
                                        line-height:1.4;flex:1;">{fn}</div>
                        </div>
                        <div style="margin-bottom:6px;">{stars_html(star)}</div>
                        <div style="font-size:0.72rem;color:{_bd};margin-bottom:10px;">
                            {amc_str}{(' &nbsp;·&nbsp; '+cat_str) if show_cat_filter else ''}
                        </div>
                        <div style="display:flex;gap:10px;margin-bottom:8px;flex-wrap:wrap;">
                            <div>
                                <div style="font-size:0.6rem;color:{_sb};text-transform:uppercase;letter-spacing:0.4px;">1Y Ret</div>
                                <div style="font-size:0.8rem;font-weight:600;color:{_hd};">{r1y_str}</div>
                            </div>
                            <div>
                                <div style="font-size:0.6rem;color:{_sb};text-transform:uppercase;letter-spacing:0.4px;">3Y Ret</div>
                                <div style="font-size:0.8rem;font-weight:600;color:{_hd};">{r3y_str}</div>
                            </div>
                            <div>
                                <div style="font-size:0.6rem;color:{_sb};text-transform:uppercase;letter-spacing:0.4px;">5Y Ret</div>
                                <div style="font-size:0.8rem;font-weight:600;color:{_hd};">{r5y_str}</div>
                            </div>
                            <div>
                                <div style="font-size:0.6rem;color:{_sb};text-transform:uppercase;letter-spacing:0.4px;">Since Inc.</div>
                                <div style="font-size:0.8rem;font-weight:600;color:{_hd};">{rsi_str}</div>
                            </div>
                            <div>
                                <div style="font-size:0.6rem;color:{_sb};text-transform:uppercase;letter-spacing:0.4px;">Exp.</div>
                                <div style="font-size:0.8rem;font-weight:600;color:{_hd};">{er_str}</div>
                            </div>
                            <div>
                                <div style="font-size:0.6rem;color:{_sb};text-transform:uppercase;letter-spacing:0.4px;">AUM</div>
                                <div style="font-size:0.8rem;font-weight:600;color:{_hd};">{aum_str}</div>
                            </div>
                        </div>
                        <div style="font-size:0.7rem;color:{_bd};">
                            Top sector: <strong style="color:{_bd};">{top_sec}</strong>
                        </div>
                        {badge}
                    </div>""", unsafe_allow_html=True)
                    if is_sel:
                        bl, bt = "✓ Added — click to remove", "primary"
                    elif at_max:
                        bl, bt = "Max 5 reached", "secondary"
                    else:
                        bl, bt = "+ Add to Compare", "secondary"
                    if st.button(bl, key=f"a_{row_start}_{ci}",
                                 use_container_width=True, type=bt, disabled=at_max):
                        if is_sel:
                            st.session_state.selected_funds = [f for f in selected if f != fn]
                        else:
                            st.session_state.selected_funds = selected + [fn]
                        st.rerun()

    # ─── LAYOUT B: Two-Panel Split ───────────────────────────────────────────
    elif layout == "B":
        b_search = st.text_input("Search", placeholder="Fund name or AMC…",
                                  label_visibility="collapsed", key="b_srch")
        bc1, bc2 = st.columns(2)
        b_amc  = bc1.selectbox("AMC", amcs_list, label_visibility="collapsed", key="b_amc")
        b_sort = bc2.selectbox(
            "Sort", ["Star Rating (High→Low)", "3Y Return (High→Low)", "1Y Return (High→Low)", "5Y Return (High→Low)", "Returns Since Inception (High→Low)", "Consistency (High→Low)", "AUM (High→Low)", "AUM (Low→High)", "Expense Ratio (Low→High)", "Holdings Count"],
            label_visibility="collapsed", key="b_sort",
        )
        filtered = apply_filters(cat_funds, b_search, b_amc, "All Categories", b_sort)

        left_col, right_col = st.columns([3, 2], gap="large")
        with left_col:
            st.markdown(
                f'<div class="section-sub">{len(filtered)} funds — click Add to build your comparison</div>',
                unsafe_allow_html=True,
            )
            for i, (_, fund) in enumerate(filtered.iterrows()):
                fn     = fund["fund_name"]
                is_b   = fn in selected
                at_b   = n_sel >= 5 and not is_b
                aum_str, er_str, _, _, amc_str, _, r1y_str, r3y_str, r5y_str, rsi_str, star = fund_info(fund)
                row_bg  = _al if is_b else _cd
                row_bdr = f"1.5px solid {_a50}" if is_b else f"1px solid {_bdr}"
                r1, r2  = st.columns([4, 1])
                with r1:
                    st.markdown(f"""
                    <div style="background:{row_bg};border:{row_bdr};border-radius:10px;
                                padding:0.75rem 1rem;">
                        <div style="font-size:0.85rem;font-weight:700;color:{_hd};
                                    margin-bottom:2px;">{fn}</div>
                        <div style="margin-bottom:2px;">{stars_html(star)}</div>
                        <div style="font-size:0.72rem;color:{_bd};">
                            {amc_str} &nbsp;·&nbsp; 1Y {r1y_str} &nbsp;·&nbsp; 3Y {r3y_str} &nbsp;·&nbsp; 5Y {r5y_str} &nbsp;·&nbsp; Since Inc. {rsi_str} &nbsp;·&nbsp; ER {er_str} &nbsp;·&nbsp; AUM {aum_str}
                        </div>
                    </div>""", unsafe_allow_html=True)
                with r2:
                    bl, bt = ("✓ Remove", "primary") if is_b else ("+ Add", "secondary")
                    if st.button(bl, key=f"b_{i}", use_container_width=True, type=bt, disabled=at_b):
                        if is_b:
                            st.session_state.selected_funds = [f for f in selected if f != fn]
                        else:
                            st.session_state.selected_funds = selected + [fn]
                        st.rerun()

        with right_col:
            tray_bg  = _al if n_sel > 0 else _cd
            tray_bdr = _a50 if n_sel > 0 else _bdr
            st.markdown(f"""
            <div style="background:{tray_bg};border:1.5px solid {tray_bdr};
                        border-radius:12px;padding:1.25rem;">
                <div style="font-size:0.85rem;font-weight:700;color:{_hd};margin-bottom:0.75rem;">
                    Your Comparison &nbsp;
                    <span style="font-size:0.72rem;color:{_a};font-weight:600;">{n_sel} / 5</span>
                </div>""", unsafe_allow_html=True)
            if n_sel == 0:
                st.markdown(
                    f'<div style="font-size:0.8rem;color:{_sb};text-align:center;padding:1rem 0;">'
                    f'Add funds from the left to build your comparison</div>',
                    unsafe_allow_html=True,
                )
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                for idx, fn in enumerate(selected):
                    rc1, rc2 = st.columns([4, 1])
                    with rc1:
                        st.markdown(
                            f'<div style="font-size:0.82rem;font-weight:600;color:{_hd};'
                            f'padding:4px 0;">{short_name(fn)}</div>',
                            unsafe_allow_html=True,
                        )
                    with rc2:
                        if st.button("✕", key=f"b_rm_{idx}", use_container_width=True):
                            st.session_state.selected_funds = [f for f in selected if f != fn]
                            st.rerun()
                warns = overlap_warns(selected)
                if warns:
                    st.markdown(warns, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Compare Now →", type="primary", use_container_width=True,
                             key="b_cmp", disabled=(n_sel < 2)):
                    st.session_state.page = "compare"
                    st.rerun()

    # ─── LAYOUT C: Selectable Table ──────────────────────────────────────────
    elif layout == "C":
        cc = st.columns([3, 2, 2])
        c_search = cc[0].text_input("Search", placeholder="Fund name or AMC…",
                                     label_visibility="collapsed", key="c_srch")
        c_amc    = cc[1].selectbox("AMC", amcs_list, label_visibility="collapsed", key="c_amc")
        c_sort   = cc[2].selectbox(
            "Sort", ["Star Rating (High→Low)", "3Y Return (High→Low)", "1Y Return (High→Low)", "5Y Return (High→Low)", "Returns Since Inception (High→Low)", "Consistency (High→Low)", "AUM (High→Low)", "AUM (Low→High)", "Expense Ratio (Low→High)", "Holdings Count"],
            label_visibility="collapsed", key="c_sort",
        )
        filtered = apply_filters(cat_funds, c_search, c_amc, "All Categories", c_sort)

        c_tbl = filtered[["fund_name", "fund_house", "star_rating", "return_1y", "return_3y",
                           "return_5y", "return_since_inception", "aum_cr",
                           "expense_ratio", "holding_count", "top_sector"]].copy()
        c_tbl = c_tbl.rename(columns={
            "fund_name": "Fund", "fund_house": "AMC", "star_rating": "★",
            "return_1y": "1Y %", "return_3y": "3Y %", "return_5y": "5Y %",
            "return_since_inception": "Since Inc. %",
            "aum_cr": "AUM (₹ Cr)", "expense_ratio": "Exp Ratio %",
            "holding_count": "Holdings", "top_sector": "Top Sector",
        })
        c_tbl["AUM (₹ Cr)"]     = pd.to_numeric(c_tbl["AUM (₹ Cr)"],     errors="coerce")
        c_tbl["Exp Ratio %"]    = pd.to_numeric(c_tbl["Exp Ratio %"],    errors="coerce")
        c_tbl["Holdings"]       = pd.to_numeric(c_tbl["Holdings"],       errors="coerce").astype("Int64")
        c_tbl["★"]              = pd.to_numeric(c_tbl["★"],              errors="coerce").astype("Int64")
        c_tbl["1Y %"]           = pd.to_numeric(c_tbl["1Y %"],           errors="coerce")
        c_tbl["3Y %"]           = pd.to_numeric(c_tbl["3Y %"],           errors="coerce")
        c_tbl["5Y %"]           = pd.to_numeric(c_tbl["5Y %"],           errors="coerce")
        c_tbl["Since Inc. %"]   = pd.to_numeric(c_tbl["Since Inc. %"],   errors="coerce")
        c_tbl["Select"]         = c_tbl["Fund"].isin(selected)

        edited = st.data_editor(
            c_tbl[["Select", "Fund", "AMC", "★", "1Y %", "3Y %", "5Y %", "Since Inc. %",
                   "AUM (₹ Cr)", "Exp Ratio %", "Holdings", "Top Sector"]].reset_index(drop=True),
            use_container_width=True, height=440,
            column_config={
                "Select":        st.column_config.CheckboxColumn("Select", width="small"),
                "Fund":          st.column_config.TextColumn("Fund Name", width="large"),
                "AMC":           st.column_config.TextColumn("AMC"),
                "★":             st.column_config.NumberColumn("★ Rating", format="%d ★"),
                "1Y %":          st.column_config.NumberColumn("1Y %",    format="%.1f%%"),
                "3Y %":          st.column_config.NumberColumn("3Y %",    format="%.1f%%"),
                "5Y %":          st.column_config.NumberColumn("5Y %",    format="%.1f%%"),
                "Since Inc. %":  st.column_config.NumberColumn("Since Inc.", format="%.1f%%"),
                "AUM (₹ Cr)":   st.column_config.NumberColumn("AUM (₹ Cr)", format="₹%,.0f Cr"),
                "Exp Ratio %":   st.column_config.NumberColumn("Exp Ratio",  format="%.2f%%"),
                "Holdings":      st.column_config.NumberColumn("Holdings",   format="%d"),
                "Top Sector":    st.column_config.TextColumn("Top Sector"),
            },
            hide_index=True, key="c_editor",
        )
        new_sel_c = edited[edited["Select"] == True]["Fund"].tolist()[:5]
        if set(new_sel_c) != set(selected):
            st.session_state.selected_funds = new_sel_c
            st.rerun()

        n_c = len(new_sel_c)
        if n_c == 0:
            st.info("Tick checkboxes in the Select column to build your comparison.")
        else:
            cbot1, _, cbot3 = st.columns([4, 1, 1])
            with cbot1:
                st.markdown(
                    f'<div style="padding:0.5rem 0;display:flex;gap:6px;align-items:center;flex-wrap:wrap;">'
                    f'<span style="font-size:0.75rem;color:{_sb};font-weight:600;">{n_c} selected:</span>'
                    f'{chips_html(new_sel_c)}{overlap_warns(new_sel_c)}</div>',
                    unsafe_allow_html=True,
                )
            with cbot3:
                if st.button("Compare →", type="primary", use_container_width=True,
                             key="c_cmp", disabled=(n_c < 2)):
                    st.session_state.selected_funds = new_sel_c
                    st.session_state.page = "compare"
                    st.rerun()

    # ─── LAYOUT D: Search-First Chips (default) ──────────────────────────────
    else:
        if n_sel > 0:
            d_chips = "".join(
                f'<span style="background:{_al};color:{_a};border-radius:9999px;'
                'padding:5px 14px;font-size:0.82rem;font-weight:600;white-space:nowrap;">'
                f'{short_name(fn)}</span> '
                for fn in selected
            )
            dc, db = st.columns([5, 1])
            with dc:
                st.markdown(
                    f'<div style="background:{_al};border:1.5px solid {_a50};'
                    f'border-radius:10px;padding:0.75rem 1rem;">'
                    f'<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">'
                    f'<span style="font-size:0.72rem;color:{_a};font-weight:700;'
                    f'white-space:nowrap;">{n_sel} of 5:</span>'
                    f'{d_chips}</div>{overlap_warns(selected)}</div>',
                    unsafe_allow_html=True,
                )
            with db:
                if st.button("Compare →", type="primary", use_container_width=True,
                             key="d_cmp", disabled=(n_sel < 2)):
                    st.session_state.page = "compare"
                    st.rerun()
            if st.button("Clear selection", key="d_clr"):
                st.session_state.selected_funds = []
                st.rerun()

        d_search = st.text_input("", placeholder="Search by fund name or AMC…", key="d_srch")
        da1, da2 = st.columns(2)
        d_amc  = da1.selectbox("AMC", amcs_list, label_visibility="collapsed", key="d_amc")
        d_sort = da2.selectbox(
            "Sort", ["Star Rating (High→Low)", "3Y Return (High→Low)", "1Y Return (High→Low)", "5Y Return (High→Low)", "Returns Since Inception (High→Low)", "Consistency (High→Low)", "AUM (High→Low)", "AUM (Low→High)", "Expense Ratio (Low→High)", "Holdings Count"],
            label_visibility="collapsed", key="d_sort",
        )
        filtered = apply_filters(cat_funds, d_search, d_amc, "All Categories", d_sort)

        st.markdown(
            f'<div class="section-sub" style="margin-bottom:0.5rem;">'
            f'{len(filtered)} result{"s" if len(filtered)!=1 else ""}</div>',
            unsafe_allow_html=True,
        )
        for i, (_, fund) in enumerate(filtered.iterrows()):
            fn     = fund["fund_name"]
            is_d   = fn in selected
            at_d   = n_sel >= 5 and not is_d
            aum_str, er_str, hc_str, _, amc_str, _, r1y_str, r3y_str, r5y_str, rsi_str, star = fund_info(fund)
            row_bg  = _al                               if is_d else _cd
            row_bdr = f"1.5px solid {_a50}"            if is_d else f"1px solid {_bdr}"
            dot_c   = _a                                if is_d else _sb
            dr1, dr2 = st.columns([5, 1])
            with dr1:
                st.markdown(f"""
                <div style="background:{row_bg};border:{row_bdr};border-radius:8px;
                            padding:0.6rem 1rem;display:flex;align-items:center;gap:10px;">
                    <div style="width:8px;height:8px;border-radius:50%;background:{dot_c};
                                flex-shrink:0;margin-top:2px;"></div>
                    <div style="flex:1;">
                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:1px;">
                            <span style="font-size:0.85rem;font-weight:700;color:{_hd};">{fn}</span>
                            <span>{stars_html(star)}</span>
                        </div>
                        <div style="font-size:0.7rem;color:{_bd};">
                            {amc_str} &nbsp;·&nbsp; 1Y {r1y_str} &nbsp;·&nbsp; 3Y {r3y_str} &nbsp;·&nbsp; 5Y {r5y_str} &nbsp;·&nbsp; Since Inc. {rsi_str} &nbsp;·&nbsp; ER {er_str} &nbsp;·&nbsp; AUM {aum_str}
                        </div>
                    </div>
                </div>""", unsafe_allow_html=True)
            with dr2:
                dl, dt = ("✓ Remove", "primary") if is_d else ("+ Add", "secondary")
                if st.button(dl, key=f"d_{i}", use_container_width=True, type=dt, disabled=at_d):
                    if is_d:
                        st.session_state.selected_funds = [f for f in selected if f != fn]
                    else:
                        st.session_state.selected_funds = selected + [fn]
                    st.rerun()


# ── PAGE: COMPARE ─────────────────────────────────────────────────────────────

def page_compare():
    t_name, t = _fl_get_theme()
    _fl_inject_css(t, t_name)
    _fl_render_navbar(t, t_name, "analyse_funds")
    _fl_render_breadcrumb([("Home", "home"), ("Analyse Funds", "analyse_funds"), ("Compare Funds", "category"), ("Fund Explorer", "explorer"), ("Compare", None)])
    _hd = t["head"]; _bd = t["body"]; _sb = t["sub"]
    _cd = t["card"]; _bdr = t["bdr"]; _a = t["a"]; _al = t["al"]
    _a50 = _a + "80"; _a20 = _a + "33"
    _is_dark = t_name == "dark_premium"
    # Semantic status colors — readable on both light and dark card backgrounds
    _col_green = "#34D399" if _is_dark else "#059669"
    _col_amber = "#FDE68A" if _is_dark else "#D97706"
    _col_red   = "#FCA5A5" if _is_dark else "#DC2626"
    # Plotly chart theming
    _cf = dict(family="Inter, sans-serif", color=_bd, size=12)
    _ct = dict(color=_bd, size=11)
    _cg = _bdr  # grid / zero-line color
    PERF_COLORS = [_a, "#F59E0B", "#06B6D4", "#10B981", "#EF4444"]

    selected = st.session_state.get("selected_funds", [])
    if len(selected) < 2:
        st.warning("Please select at least 2 funds to compare.")
        return

    if st.session_state.get("overlap_matrix_return"):
        _cmp_ret_src = st.session_state.get("overlap_return_source", "overlap_drilldown")
        _cmp_back_lbl = (
            "← Back to Fund Overlap"
            if _cmp_ret_src == "portfolio_xray"
            else "← Back to Overlap Matrix"
        )
        if st.button(_cmp_back_lbl, type="secondary", key="compare_back_overlap"):
            st.session_state.overlap_matrix_return = False
            if _cmp_ret_src == "portfolio_xray":
                st.session_state["_pf_xray_return_hint"] = True
            st.session_state.page = _cmp_ret_src
            st.rerun()

    holdings   = load_holdings()
    similarity = load_similarity()
    master     = load_master()
    sector_df  = get_sector_breakdown(holdings)

    sel_h   = holdings[holdings["fund_name"].isin(selected)].copy()
    sel_sim = similarity[
        similarity["fund_a"].isin(selected) & similarity["fund_b"].isin(selected)
    ]

    st.markdown("## Fund Comparison")
    fund_labels = ", ".join(display_name(f) for f in selected)
    st.markdown(
        f"<p style='color:{_bd};margin-top:-0.5rem;margin-bottom:1.5rem;'>"
        f"{len(selected)} funds selected — {fund_labels}</p>",
        unsafe_allow_html=True,
    )

    # ── Top metrics ──
    avg_sim  = sel_sim["normalized_score"].mean()  if not sel_sim.empty else 0
    max_sim  = sel_sim["normalized_score"].max()   if not sel_sim.empty else 0
    n_unique = sel_h["stock_name"].nunique()

    stock_counts = sel_h.groupby("stock_name")["fund_name"].nunique()
    n_common_all = int((stock_counts == len(selected)).sum())
    common_all_stocks = list(stock_counts[stock_counts == len(selected)].index)

    slabel, scls = sim_badge(avg_sim)
    _avg_level = "Low" if avg_sim < 15 else "Good" if avg_sim < 30 else "Moderate" if avg_sim < 45 else "High" if avg_sim < 60 else "Very High"
    _max_level = "Low" if max_sim < 15 else "Good" if max_sim < 30 else "Moderate" if max_sim < 45 else "High" if max_sim < 60 else "Very High"

    c1, c2, c3, c4 = st.columns(4)

    # shared tooltip CSS (once) — themed
    st.markdown(
        f'<style>'
        f'.mc-wrap{{position:relative;cursor:default;}}'
        f'.mc-pop{{'
        f'  display:none;position:absolute;bottom:calc(100% + 10px);left:50%;'
        f'  transform:translateX(-50%);background:{_cd};'
        f'  border:1px solid {_bdr};border-radius:14px;'
        f'  padding:0.9rem 1rem;width:270px;z-index:9999;text-align:left;'
        f'  box-shadow:0 12px 40px rgba(0,0,0,0.18);pointer-events:none;}}'
        f'.mc-wrap:hover .mc-pop{{display:block;}}'
        f'.mc-pop::before{{'
        f'  content:"";position:absolute;top:100%;left:50%;transform:translateX(-50%);'
        f'  border:7px solid transparent;border-top-color:{_cd};}}'
        f'.mc-pop-title{{font-size:0.73rem;font-weight:700;color:{_a};margin-bottom:5px;}}'
        f'.mc-pop-body{{font-size:0.72rem;color:{_bd};line-height:1.6;}}'
        f'.mc-pop-tag{{display:inline-block;margin-top:7px;font-size:0.68rem;font-weight:700;'
        f'  background:{_al};border-radius:9999px;padding:2px 9px;color:{_hd};}}'
        f'</style>',
        unsafe_allow_html=True,
    )

    with c1:
        st.markdown(
            f'<div class="metric-card mc-wrap">'
            f'<div class="metric-value">{avg_sim:.0f}%</div>'
                f'<div class="metric-label">Avg Portfolio Similarity</div>'
                f'<div class="metric-sub"><span class="badge {scls}">{slabel}</span></div>'
                f'<div class="mc-pop">'
                f'<div class="mc-pop-title">What does this mean?</div>'
                f'<div class="mc-pop-body">This is the <strong style="color:{_hd};">average overlap %</strong> between all pairs of your funds. '
                f'{avg_sim:.0f}% means each pair shares roughly {avg_sim:.0f}% of their stocks on average.<br><br>'
            f'<strong style="color:{_hd};">Lower is better</strong> — it means your funds invest in more different companies, spreading your risk wider.</div>'
            f'<span class="mc-pop-tag">Level: {_avg_level} &nbsp;·&nbsp; Target: below 30%</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with c2:
        if n_common_all == 0:
            _c2_popup_body = (
                f'No stock appears in all {len(selected)} funds — each fund has at least some unique holdings. '
                f'Good sign for diversification.'
            )
            _c2_chips_html = ""
            _c2_clickable  = False
        else:
            _c2_popup_body = (
                f'These {n_common_all} stocks appear in every one of your {len(selected)} funds — '
                f'typically large blue-chip names all managers agree on.<br><br>'
                f'<strong style="color:{_a};">👆 Click the card</strong> to see the full list.'
            )
            _chips = "".join(
                f'<span style="background:{_al};border:1px solid {_bdr};'
                f'border-radius:9999px;padding:2px 9px;font-size:0.68rem;color:{_hd};white-space:nowrap;">{s}</span>'
                for s in common_all_stocks
            )
            _c2_chips_html = (
                f'<div style="display:flex;flex-wrap:wrap;gap:4px;padding:0.75rem 0 0.25rem;">{_chips}</div>'
            )
            _c2_clickable = True

        if _c2_clickable:
            # Wrap the whole card in <details> so clicking anywhere on it toggles the list
            st.markdown(
                f'<style>'
                f'.sc-details{{width:100%;}}'
                f'.sc-details>summary{{list-style:none;outline:none;cursor:pointer;}}'
                f'.sc-details>summary::-webkit-details-marker{{display:none;}}'
                f'.sc-details>summary .sc-hint{{font-size:0.65rem;color:{_sb};margin-top:4px;}}'
                f'.sc-details[open]>summary .sc-hint{{color:{_a};}}'
                f'.sc-details[open]>summary .metric-card{{border-color:{_a50};background:{_al};}}'
                f'</style>'

                f'<details class="sc-details">'
                f'<summary>'
                f'<div class="metric-card mc-wrap" style="cursor:pointer;">'
                f'<div class="metric-value">{n_common_all}</div>'
                f'<div class="metric-label">Stocks in All {len(selected)} Funds</div>'
                f'<div class="metric-sub">Held by every selected fund</div>'
                f'<div class="mc-pop">'
                f'<div class="mc-pop-title">Stocks common to all your funds</div>'
                f'<div class="mc-pop-body">{_c2_popup_body}</div>'
                f'<span class="mc-pop-tag">Lower = more unique holdings per fund</span>'
                f'</div>'
                f'</div>'
                f'</summary>'
                f'{_c2_chips_html}'
                f'</details>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="metric-card mc-wrap">'
                f'<div class="metric-value">{n_common_all}</div>'
                f'<div class="metric-label">Stocks in All {len(selected)} Funds</div>'
                f'<div class="metric-sub">Held by every selected fund</div>'
                f'<div class="mc-pop">'
                f'<div class="mc-pop-title">What does this mean?</div>'
                f'<div class="mc-pop-body">{_c2_popup_body}</div>'
                f'<span class="mc-pop-tag">Lower = more unique holdings per fund</span>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with c3:
        st.markdown(
            f'<div class="metric-card mc-wrap">'
            f'<div class="metric-value">{int(max_sim)}%</div>'
            f'<div class="metric-label">Highest Pair Similarity</div>'
            f'<div class="metric-sub">Most overlapping pair</div>'
            f'<div class="mc-pop">'
            f'<div class="mc-pop-title">Your most redundant fund pair</div>'
            f'<div class="mc-pop-body">Your <strong style="color:{_hd};">most similar pair</strong> of funds shares {int(max_sim)}% of stocks. '
            f'This is the pair giving you the least diversification benefit — you may be paying two managers to make nearly identical bets.<br><br>'
            f'Scroll down to the pair analysis to identify and review this pair.</div>'
            f'<span class="mc-pop-tag">Level: {_max_level} &nbsp;·&nbsp; Target: below 30%</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with c4:
        st.markdown(
            f'<div class="metric-card mc-wrap">'
            f'<div class="metric-value">{n_unique}</div>'
            f'<div class="metric-label">Total Unique Stocks</div>'
            f'<div class="metric-sub">Across all selected funds</div>'
            f'<div class="mc-pop">'
            f'<div class="mc-pop-title">Unique companies in your portfolio</div>'
            f'<div class="mc-pop-body">Combined, your {len(selected)} funds invest in <strong style="color:{_hd};">{n_unique} different companies</strong>. '
            f'A single fund typically holds 50–80 stocks, so multiple funds can broaden your exposure — '
            f'but only if they don\'t overlap too much.<br><br>'
            f'<strong style="color:{_hd};">More unique stocks = your money works in more places.</strong></div>'
            f'<span class="mc-pop-tag">~{n_unique // len(selected)} unique stocks per fund on average</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    tab_ov, tab_perf, tab_ol, tab_sec, tab_hold, tab_ins = st.tabs([
        "📊 Overview",
        "📉 Fund Performance",
        "🔬 Holdings Deep Dive",
        "🏗️ Sector Analysis",
        "📈 Holdings Timeline",
        "💡 Key Insights",
    ])

    # ── Tab 1: Overview ──────────────────────────────────────────────────────
    with tab_ov:
        # ── pre-compute lookups ───────────────────────────────────────────────
        score_lk  = {}
        common_lk = {}
        for _, _row in sel_sim.iterrows():
            for _key in [(_row["fund_a"], _row["fund_b"]), (_row["fund_b"], _row["fund_a"])]:
                score_lk[_key]  = _row["normalized_score"]
                common_lk[_key] = int(_row["common_stocks"])
        cat_lk = dict(zip(master["fund_name"], master["category"])) if not master.empty else {}

        # ── portfolio overlap summary (direct bucket mapping, no inversion) ────
        # Bucket thresholds identical to OVERLAP_BUCKETS in overlap_journey_viz.py
        if avg_sim < 15:
            zone_label, zone_color, zone_icon = "Excellent",       "#34D399",   "🟢"
            zone_msg = "Your funds cover very different companies — great diversification!"
        elif avg_sim < 30:
            zone_label, zone_color, zone_icon = "Good",            "#059669",   "🟢"
            zone_msg = "Healthy diversification with limited overlap — generally fine."
        elif avg_sim < 45:
            zone_label, zone_color, zone_icon = "Moderate",        "#6366F1",   "🔵"
            zone_msg = "Noticeable overlap — worth monitoring. Consider swapping one fund."
        elif avg_sim < 60:
            zone_label, zone_color, zone_icon = "High Overlap",    _col_amber,  "🟡"
            zone_msg = "Significant overlap — you may be paying two managers for similar results."
        else:
            zone_label, zone_color, zone_icon = "Very High Overlap", _col_red,  "🔴"
            zone_msg = "Funds are nearly identical — you're likely paying for the same stocks twice."

        # Effective fund count: how many truly independent funds does this portfolio behave like?
        # Formula: 1 + (n − 1) × (1 − avg_overlap/100)  [standard linear approximation]
        _n_funds  = len(selected)
        _eff_n    = 1 + (_n_funds - 1) * (1 - avg_sim / 100) if _n_funds > 1 else 1.0
        _eff_n    = round(_eff_n, 1)

        n_high_pairs = int((sel_sim["normalized_score"] >= 50).sum()) if not sel_sim.empty else 0
        gauge_w = int(avg_sim)   # gauge now shows overlap % (higher fill = more overlap = worse)

        # ── What is overlap? banner ───────────────────────────────────────────
        st.markdown(f"""
        <div style="background:{_al};border:1px solid {_a50};
                    border-radius:12px;padding:1rem 1.25rem;margin-bottom:1.25rem;
                    display:flex;align-items:flex-start;gap:0.75rem;">
            <div style="font-size:1.25rem;flex-shrink:0;">💡</div>
            <div>
                <div style="font-size:0.85rem;font-weight:700;color:{_a};margin-bottom:3px;">
                    New to mutual funds? Here's what this page tells you.
                </div>
                <div style="font-size:0.82rem;color:{_bd};line-height:1.65;">
                    When two funds buy the <strong style="color:{_hd};">same stocks</strong>, they "overlap."
                    High overlap means you're paying <strong style="color:{_hd};">two fund managers to make identical bets</strong>
                    — so you're not spreading your risk as much as you think.
                    <strong style="color:{_hd};">Low overlap = your money is working in more places.</strong>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

        # ── Score card + Key Findings ─────────────────────────────────────────
        col_score, col_finds = st.columns([1, 2], gap="large")

        with col_score:
            st.markdown(
                f'<style>'
                f'.hs-info{{position:relative;display:inline-block;cursor:help;}}'
                f'.hs-tip{{'
                f'  display:none;position:absolute;bottom:calc(100% + 10px);left:50%;'
                f'  transform:translateX(-50%);background:{_cd};'
                f'  border:1px solid {_bdr};border-radius:14px;'
                f'  padding:1rem 1.1rem;width:300px;z-index:9999;text-align:left;'
                f'  box-shadow:0 12px 40px rgba(0,0,0,0.18);pointer-events:none;}}'
                f'.hs-info:hover .hs-tip{{display:block;}}'
                f'.hs-tip::after{{'
                f'  content:"";position:absolute;top:100%;left:50%;transform:translateX(-50%);'
                f'  border:7px solid transparent;border-top-color:{_cd};}}'
                f'</style>'

                # ── Main card ──────────────────────────────────────────────────
                f'<div class="card" style="text-align:center;padding:1.25rem 1.1rem;">'

                f'<div style="font-size:0.65rem;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:1px;color:{_sb};margin-bottom:0.5rem;">Avg Portfolio Overlap</div>'

                # Big overlap number
                f'<div style="font-size:3rem;font-weight:900;color:{zone_color};'
                f'line-height:1;margin-bottom:0.15rem;">{avg_sim:.0f}%</div>'

                # Gauge — left fill = overlap amount (higher fill = more overlap = worse)
                f'<div style="background:{_bdr};border-radius:999px;height:7px;'
                f'margin:0 0.2rem 0.7rem;overflow:hidden;">'
                f'<div style="background:{zone_color};height:100%;width:{gauge_w}%;'
                f'border-radius:999px;transition:width 0.4s;"></div>'
                f'</div>'

                # Bucket badge
                f'<div style="display:inline-flex;align-items:center;gap:6px;background:{_al};'
                f'border-radius:9999px;padding:4px 14px;font-size:0.8rem;font-weight:700;'
                f'color:{zone_color};">{zone_icon} {zone_label}</div>'

                # Message
                f'<div style="font-size:0.73rem;color:{_bd};margin-top:0.65rem;'
                f'line-height:1.5;margin-bottom:0.9rem;">{zone_msg}</div>'

                # Divider
                f'<div style="height:1px;background:{_bdr};margin:0 0 0.9rem;"></div>'

                # Effective fund count
                f'<div style="display:flex;align-items:center;justify-content:center;'
                f'gap:0.5rem;margin-bottom:0.2rem;">'
                f'<span style="font-size:1.55rem;font-weight:900;color:{_hd};">{_eff_n}</span>'
                f'<span style="font-size:0.72rem;color:{_sb};text-align:left;line-height:1.4;">'
                f'effective funds<br>out of {_n_funds}</span>'
                f'</div>'
                f'<div style="font-size:0.7rem;color:{_sb};margin-bottom:0.85rem;line-height:1.4;">'
                f'Your {_n_funds} funds behave like '
                f'<strong style="color:{_hd};">~{_eff_n} truly independent funds</strong>'
                f'</div>'

                # Tooltip
                f'<div class="hs-info">'
                f'<span style="font-size:0.7rem;color:{_sb};border-bottom:1px dashed {_bdr};'
                f'padding-bottom:1px;">ⓘ How are these calculated?</span>'
                f'<div class="hs-tip">'
                f'<div style="font-size:0.75rem;font-weight:700;color:{_a};margin-bottom:0.5rem;">'
                f'Avg Portfolio Overlap</div>'
                f'<div style="font-size:0.73rem;color:{_bd};line-height:1.6;margin-bottom:0.85rem;">'
                f'Mean of pairwise overlap % across all your fund pairs. '
                f'Your current average is <strong style="color:{zone_color};">{avg_sim:.0f}%</strong>.'
                f'</div>'
                f'<div style="font-size:0.75rem;font-weight:700;color:{_a};margin-bottom:0.4rem;">'
                f'Effective Fund Count</div>'
                f'<div style="font-size:0.73rem;color:{_bd};line-height:1.6;margin-bottom:0.85rem;">'
                f'= 1 + (N − 1) × (1 − overlap/100)<br>'
                f'= 1 + {_n_funds - 1} × {1 - avg_sim/100:.2f} '
                f'= <strong style="color:{_hd};">{_eff_n}</strong>. '
                f'At 0% overlap all {_n_funds} funds would be fully independent. '
                f'At 100% they would all be identical (= 1 fund).'
                f'</div>'
                f'<div style="font-size:0.67rem;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:0.6px;color:{_sb};margin-bottom:5px;">Overlap levels</div>'
                f'<div style="display:flex;flex-direction:column;gap:3px;">'
                f'<div style="display:flex;gap:8px;font-size:0.72rem;">'
                f'<span style="color:#34D399;font-weight:700;min-width:52px;">&lt; 15%</span>'
                f'<span style="color:{_sb};">🟢 Excellent</span></div>'
                f'<div style="display:flex;gap:8px;font-size:0.72rem;">'
                f'<span style="color:#059669;font-weight:700;min-width:52px;">15–29%</span>'
                f'<span style="color:{_sb};">🟢 Good</span></div>'
                f'<div style="display:flex;gap:8px;font-size:0.72rem;">'
                f'<span style="color:#6366F1;font-weight:700;min-width:52px;">30–44%</span>'
                f'<span style="color:{_sb};">🔵 Moderate</span></div>'
                f'<div style="display:flex;gap:8px;font-size:0.72rem;">'
                f'<span style="color:{_col_amber};font-weight:700;min-width:52px;">45–59%</span>'
                f'<span style="color:{_sb};">🟡 High</span></div>'
                f'<div style="display:flex;gap:8px;font-size:0.72rem;">'
                f'<span style="color:{_col_red};font-weight:700;min-width:52px;">≥ 60%</span>'
                f'<span style="color:{_sb};">🔴 Very High</span></div>'
                f'</div>'
                f'</div>'
                f'</div>'

                f'</div>',
                unsafe_allow_html=True,
            )

        with col_finds:
            # Finding 1 – unique companies
            f1_icon, f1_color = "🏢", _col_green
            f1_bg  = "rgba(16,185,129,0.12)" if _is_dark else "#D1FAE5"
            f1_bdr = "rgba(16,185,129,0.35)" if _is_dark else "#6EE7B7"
            f1_title = f"Your funds invest in <strong>{n_unique} different companies</strong> in total"
            f1_desc  = (f"Across all {len(selected)} funds combined. "
                        "More unique companies = your money is working in more places.")

            # Finding 2 – worst pair or all-clear
            if n_high_pairs > 0 and not sel_sim.empty:
                _worst = sel_sim.loc[sel_sim["normalized_score"].idxmax()]
                _wa, _wb = display_name(_worst["fund_a"]), display_name(_worst["fund_b"])
                _ws, _wc = int(_worst["normalized_score"]), int(_worst["common_stocks"])
                f2_icon, f2_color = "⚠️", _col_amber
                f2_bg  = "rgba(245,158,11,0.12)" if _is_dark else "#FEF3C7"
                f2_bdr = "rgba(245,158,11,0.35)" if _is_dark else "#FCD34D"
                f2_title = f"<strong>{_wa}</strong> and <strong>{_wb}</strong> share {_wc} stocks ({_ws}% similar)"
                f2_desc  = ("These two funds are quite alike. You may want to swap one for a fund "
                            "from a different category — like Mid Cap or Flexi Cap — to get better spread.")
            else:
                f2_icon, f2_color = "✅", _col_green
                f2_bg  = "rgba(16,185,129,0.12)" if _is_dark else "#D1FAE5"
                f2_bdr = "rgba(16,185,129,0.35)" if _is_dark else "#6EE7B7"
                f2_title = "No fund pair has dangerously high overlap"
                f2_desc  = "All your fund pairings look healthy — you're well diversified."

            # Finding 3 – stocks in all funds
            if n_common_all > 0:
                f3_icon, f3_color = "📌", _a
                f3_bg, f3_bdr = _al, _a50
                f3_title = f"<strong>{n_common_all} companies</strong> appear in every one of your funds"
                f3_desc  = ("These are widely held blue-chip stocks — all your fund managers chose them. "
                            "Normal for Large Cap funds, but good to be aware of.")
            else:
                f3_icon, f3_color = "✅", _col_green
                f3_bg  = "rgba(16,185,129,0.12)" if _is_dark else "#D1FAE5"
                f3_bdr = "rgba(16,185,129,0.35)" if _is_dark else "#6EE7B7"
                f3_title = "No single company is held by all your funds"
                f3_desc  = "Your fund managers are making genuinely different picks — a healthy sign."

            for icon, color, bg, bdr, title, desc in [
                (f1_icon, f1_color, f1_bg, f1_bdr, f1_title, f1_desc),
                (f2_icon, f2_color, f2_bg, f2_bdr, f2_title, f2_desc),
                (f3_icon, f3_color, f3_bg, f3_bdr, f3_title, f3_desc),
            ]:
                st.markdown(f"""
                <div style="background:{bg};border:1px solid {bdr};border-radius:12px;
                            padding:0.9rem 1.1rem;margin-bottom:0.65rem;
                            display:flex;gap:0.85rem;align-items:flex-start;">
                    <div style="font-size:1.2rem;flex-shrink:0;margin-top:1px;">{icon}</div>
                    <div>
                        <div style="font-size:0.85rem;font-weight:600;color:{_hd};
                                    line-height:1.4;margin-bottom:3px;">{title}</div>
                        <div style="font-size:0.78rem;color:{_bd};line-height:1.55;">{desc}</div>
                    </div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Fund pair cards ───────────────────────────────────────────────────
        st.markdown(
            f'<div style="font-size:1rem;font-weight:800;color:{_hd};margin-bottom:3px;">Ranked Fund Pairings</div>'
            f'<div style="font-size:0.8rem;color:{_bd};margin-bottom:0.9rem;">'
            f'Ranked from best diversification (top) to most overlap (bottom). '
            f'Click <strong style="color:{_a};">›</strong> on any pair, then open <strong style="color:{_a};">View Detailed Overlap</strong> for label definitions.</div>',
            unsafe_allow_html=True,
        )

        # default detail panel to worst pair
        _worst_key = ""
        if not sel_sim.empty:
            _wrow = sel_sim.loc[sel_sim["normalized_score"].idxmax()]
            _worst_key = f"{_wrow['fund_a']}___{_wrow['fund_b']}"
        if "ov_detail_pair" not in st.session_state or st.session_state.ov_detail_pair == "":
            st.session_state.ov_detail_pair = _worst_key
        if "ov_detail_expanded" not in st.session_state:
            st.session_state.ov_detail_expanded = False

        FUND_COLORS_OV = ["#F97316", "#6366F1", "#8B5CF6", "#10B981", "#EF4444"]
        fund_color_map_ov = {fn: FUND_COLORS_OV[i % len(FUND_COLORS_OV)] for i, fn in enumerate(selected)}

        col_pairs, col_detail = st.columns([3, 2], gap="large")

        # ── Left: ranked pair list ────────────────────────────────────────────
        with col_pairs:
          if not sel_sim.empty:
            for _pi, (_pidx, _p) in enumerate(
                sel_sim.sort_values("normalized_score", ascending=True).iterrows()
            ):
                _sc   = int(_p["normalized_score"])
                _co   = int(_p["common_stocks"])
                _fa   = display_name(_p["fund_a"])
                _fb   = display_name(_p["fund_b"])
                _fak  = _p["fund_a"]
                _fbk  = _p["fund_b"]
                _ca   = cat_lk.get(_fak, "")
                _cb   = cat_lk.get(_fbk, "")
                _pkey = f"{_fak}___{_fbk}"
                _sel  = st.session_state.ov_detail_pair == _pkey
                _fc_a = fund_color_map_ov.get(_fak, "#94A3B8")
                _fc_b = fund_color_map_ov.get(_fbk, "#94A3B8")

                if _sc >= 60:
                    _badge, _bc_text, _desc = "Very High", _col_red, "Very high redundancy — these funds hold largely the same stocks."
                    _num_bg, _card_bdr = "#EF4444", "rgba(239,68,68,0.4)" if _sel else "rgba(239,68,68,0.18)"
                elif _sc >= 45:
                    _badge, _bc_text, _desc = "High", _col_amber, "High overlap — significant common holdings, consider diversifying."
                    _num_bg, _card_bdr = "#F59E0B", "rgba(245,158,11,0.4)" if _sel else "rgba(245,158,11,0.18)"
                elif _sc >= 30:
                    _badge, _bc_text, _desc = "Moderate", _a, "Some common holdings — generally acceptable but worth watching."
                    _num_bg, _card_bdr = _a, (_a50 if _sel else _a20)
                elif _sc >= 15:
                    _badge, _bc_text, _desc = "Good", _col_green, "Balanced combination with healthy diversification."
                    _num_bg, _card_bdr = "#10B981", "rgba(16,185,129,0.4)" if _sel else "rgba(16,185,129,0.18)"
                else:
                    _badge, _bc_text, _desc = "Excellent", _col_green, "Strong diversification with minimal overlap."
                    _num_bg, _card_bdr = "#10B981", "rgba(16,185,129,0.4)" if _sel else "rgba(16,185,129,0.18)"

                _card_bg  = _al if _sel else _cd
                _card_bdr_width = "2px" if _sel else "1px"

                _pc, _ac = st.columns([10, 1])
                with _pc:
                    st.markdown(
                        f'<div style="background:{_card_bg};border:{_card_bdr_width} solid {_card_bdr};'
                        f'border-radius:14px;padding:0.8rem 1rem;display:flex;align-items:center;gap:0.75rem;">'

                        f'<div style="min-width:28px;height:28px;border-radius:50%;background:{_num_bg};'
                        f'color:#fff;font-size:0.78rem;font-weight:800;display:flex;align-items:center;'
                        f'justify-content:center;flex-shrink:0;">{_pi+1}</div>'

                        f'<div style="flex:1;min-width:0;">'
                        f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">'
                        f'<span style="width:9px;height:9px;border-radius:50%;background:{_fc_a};flex-shrink:0;display:inline-block;"></span>'
                        f'<span style="font-size:0.82rem;font-weight:700;color:{_hd};'
                        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_fa}</span>'
                        f'</div>'
                        f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:5px;">'
                        f'<span style="width:9px;height:9px;border-radius:50%;background:{_fc_b};flex-shrink:0;display:inline-block;"></span>'
                        f'<span style="font-size:0.82rem;font-weight:700;color:{_hd};'
                        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_fb}</span>'
                        f'</div>'
                        f'<div style="display:flex;align-items:center;gap:6px;">'
                        f'<span style="font-size:0.68rem;color:{_sb};">{_ca}</span>'
                        f'<span style="background:{_al};border:1px solid {_bdr};'
                        f'border-radius:9999px;padding:1px 8px;font-size:0.67rem;font-weight:700;'
                        f'color:{_bc_text};white-space:nowrap;">{_badge}</span>'
                        f'</div>'
                        f'</div>'

                        f'<div style="text-align:right;flex-shrink:0;">'
                        f'<div style="font-size:1.5rem;font-weight:900;color:{_bc_text};line-height:1;">{_sc}%</div>'
                        f'<div style="font-size:0.6rem;color:{_sb};margin-top:1px;">Overlap</div>'
                        f'</div>'

                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with _ac:
                    st.markdown("<div style='height:0.45rem'></div>", unsafe_allow_html=True)
                    if st.button("›" if not _sel else "‹", key=f"ov_pair_{_pi}",
                                 use_container_width=True,
                                 type="primary" if _sel else "secondary"):
                        if _pkey != st.session_state.ov_detail_pair:
                            st.session_state.ov_detail_expanded = False
                        st.session_state.ov_detail_pair = _pkey
                        st.rerun()
                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # ── Right: detail panel ───────────────────────────────────────────────
        with col_detail:
          if not sel_sim.empty and st.session_state.ov_detail_pair:
            _dpk = st.session_state.ov_detail_pair
            _dp_parts = _dpk.split("___")
            if len(_dp_parts) == 2:
                _dp_fak, _dp_fbk = _dp_parts[0], _dp_parts[1]
                _dp_row = sel_sim[
                    ((sel_sim["fund_a"] == _dp_fak) & (sel_sim["fund_b"] == _dp_fbk)) |
                    ((sel_sim["fund_a"] == _dp_fbk) & (sel_sim["fund_b"] == _dp_fak))
                ]
                if not _dp_row.empty:
                    _dp_row = _dp_row.iloc[0]
                    _dp_sc  = int(_dp_row["normalized_score"])
                    _dp_co  = int(_dp_row["common_stocks"])
                    _dp_fa  = display_name(_dp_fak)
                    _dp_fb  = display_name(_dp_fbk)

                    # common stocks
                    _dh_a = sel_h[sel_h["fund_name"] == _dp_fak][["stock_name","sector","allocation_percent"]].copy()
                    _dh_b = sel_h[sel_h["fund_name"] == _dp_fbk][["stock_name","sector","allocation_percent"]].copy()
                    _dh_a.columns = ["stock_name","sector","alloc_a"]
                    _dh_b.columns = ["stock_name","sector_b","alloc_b"]
                    _dcommon = _dh_a.merge(_dh_b, on="stock_name").sort_values("alloc_a", ascending=False).head(8)

                    # shared sectors
                    _dsec = (
                        _dcommon.groupby("sector").agg(cnt=("stock_name","count"), avg=("alloc_a","mean"))
                        .reset_index().sort_values("avg", ascending=False).head(4)
                    ) if not _dcommon.empty else pd.DataFrame()

                    # alert config by overlap level
                    if _dp_sc >= 60:
                        _dh_icon, _dh_color = "⚠️", _col_red
                        _dh_hbg  = "rgba(239,68,68,0.18)" if _is_dark else "#FEE2E2"
                        _dh_bdr  = "rgba(239,68,68,0.40)"
                        _dh_title = "Very High Overlap"
                        _dp_adv = f"These funds share <strong>{_dp_co} stocks</strong>. You're paying two managers for nearly identical bets. Consider replacing one with a fund from a different category."
                        _sec_intro = "Both funds are heavily concentrated in:"
                    elif _dp_sc >= 45:
                        _dh_icon, _dh_color = "⚠️", _col_amber
                        _dh_hbg  = "rgba(245,158,11,0.15)" if _is_dark else "#FEF3C7"
                        _dh_bdr  = "rgba(245,158,11,0.40)"
                        _dh_title = "High Overlap"
                        _dp_adv = f"These funds share <strong>{_dp_co} stocks</strong>. Significant common holdings — you may be getting less diversification than you think."
                        _sec_intro = "Both funds have high exposure to:"
                    elif _dp_sc >= 30:
                        _dh_icon, _dh_color, _dh_hbg, _dh_bdr = "💡", _a, _al, _a50
                        _dh_title = "Moderate Overlap"
                        _dp_adv = f"These funds share <strong>{_dp_co} stocks</strong> — meaningful but manageable. Worth watching as you grow your portfolio."
                        _sec_intro = "Both funds have notable exposure to:"
                    elif _dp_sc >= 15:
                        _dh_icon, _dh_color = "✅", _col_green
                        _dh_hbg  = "rgba(16,185,129,0.12)" if _is_dark else "#D1FAE5"
                        _dh_bdr  = "rgba(16,185,129,0.35)"
                        _dh_title = "Good Pairing"
                        _dp_adv = f"Only <strong>{_dp_co} stocks</strong> in common — these funds complement each other well with healthy diversification."
                        _sec_intro = "Both funds also invest in:"
                    else:
                        _dh_icon, _dh_color = "✅", _col_green
                        _dh_hbg  = "rgba(16,185,129,0.12)" if _is_dark else "#D1FAE5"
                        _dh_bdr  = "rgba(16,185,129,0.35)"
                        _dh_title = "Excellent Pairing"
                        _dp_adv = f"Only <strong>{_dp_co} stocks</strong> in common — your money is genuinely spread across very different companies."
                        _sec_intro = "Some shared sectors:"

                    # sector icon map
                    _SECTOR_ICONS = {
                        "Financial Services": "🏦", "Banking": "🏦", "Insurance": "🛡️",
                        "Information Technology": "💻", "Technology": "💻",
                        "Automobile": "🚗", "Auto": "🚗",
                        "Consumer Goods": "🛒", "FMCG": "🛍️",
                        "Healthcare": "🏥", "Pharma": "💊", "Pharmaceuticals": "💊",
                        "Energy": "⚡", "Power": "⚡", "Oil & Gas": "🛢️",
                        "Metals": "⚙️", "Materials": "🧱", "Chemicals": "🧪",
                        "Real Estate": "🏢", "Construction": "🏗️", "Cement": "🧱",
                        "Capital Goods": "🏭", "Industrials": "🏭",
                        "Telecom": "📡", "Communication": "📡",
                        "Media": "📺", "Services": "🤝", "Utilities": "💡",
                    }

                    # sector rows (reference card style)
                    _dsec_rows_html = "".join(
                        f'<div style="display:flex;align-items:center;padding:0.45rem 0;border-bottom:1px solid {_bdr};">'
                        f'<span style="font-size:1rem;margin-right:0.6rem;width:1.4rem;text-align:center;">'
                        f'{_SECTOR_ICONS.get(r["sector"], "📌")}</span>'
                        f'<span style="flex:1;font-size:0.8rem;color:{_bd};">{r["sector"]}</span>'
                        f'<span style="font-size:0.82rem;font-weight:800;color:{_dh_color};">{r["avg"]:.0f}%</span>'
                        f'</div>'
                        for _, r in _dsec.iterrows()
                    ) if not _dsec.empty else (
                        f'<div style="font-size:0.75rem;color:{_sb};padding:0.4rem 0;">No sector data available</div>'
                    )

                    # stock rows (for expander)
                    _dp_fc_a = fund_color_map_ov.get(_dp_fak, "#A78BFA")
                    _dp_fc_b = fund_color_map_ov.get(_dp_fbk, "#F59E0B")
                    _dstock_rows = "".join(
                        f'<tr>'
                        f'<td style="padding:5px 6px;font-size:0.75rem;color:{_hd};font-weight:600;">{r["stock_name"]}</td>'
                        f'<td style="padding:5px 6px;font-size:0.75rem;color:{_dp_fc_a};font-weight:700;text-align:right;">{r["alloc_a"]:.1f}%</td>'
                        f'<td style="padding:5px 6px;font-size:0.75rem;color:{_dp_fc_b};font-weight:700;text-align:right;">{r["alloc_b"]:.1f}%</td>'
                        f'</tr>'
                        for _, r in _dcommon.iterrows()
                    ) if not _dcommon.empty else (
                        f'<tr><td colspan="3" style="padding:10px;text-align:center;color:{_sb};font-size:0.75rem;">No data</td></tr>'
                    )

                    # ── Reference-style summary card ──────────────────────────
                    _summary_html = (
                        f'<div style="background:{_cd};border:1.5px solid {_dh_bdr};border-radius:14px;overflow:hidden;">'
                        f'<div style="background:{_dh_hbg};padding:0.7rem 1rem;border-bottom:1px solid {_bdr};">'
                        f'<div style="font-size:0.88rem;font-weight:800;color:{_dh_color};">{_dh_icon} {_dh_title}</div>'
                        f'</div>'
                        f'<div style="padding:0.85rem 1rem;">'
                        f'<div style="font-size:0.82rem;color:{_hd};margin-bottom:0.6rem;line-height:1.5;">'
                        f'<strong>{_dp_fa}</strong> and <strong>{_dp_fb}</strong><br>'
                        f'have <strong style="color:{_dh_color};">{_dp_sc}% overlap</strong> — {_dp_co} shared stocks.</div>'
                        f'<div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.7px;color:{_sb};margin-bottom:0.35rem;">{_sec_intro}</div>'
                        f'{_dsec_rows_html}'
                        f'</div>'
                        f'</div>'
                    )
                    st.markdown(_summary_html, unsafe_allow_html=True)

                    # ── Detailed overlap in native expander ───────────────────
                    with st.expander("View Detailed Overlap"):
                        _full_html = (
                            f'<div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;'
                            f'color:{_sb};margin-bottom:8px;">All stocks held by both funds</div>'
                            f'<table style="width:100%;border-collapse:collapse;">'
                            f'<thead><tr style="border-bottom:1px solid {_bdr};">'
                            f'<th style="padding:4px 6px;font-size:0.65rem;color:{_sb};font-weight:600;text-align:left;">Stock</th>'
                            f'<th style="padding:4px 6px;font-size:0.65rem;color:{_dp_fc_a};font-weight:700;text-align:right;">{_dp_fa[:14]}</th>'
                            f'<th style="padding:4px 6px;font-size:0.65rem;color:{_dp_fc_b};font-weight:700;text-align:right;">{_dp_fb[:14]}</th>'
                            f'</tr></thead><tbody>{_dstock_rows}</tbody></table>'
                            f'<div style="font-size:0.62rem;color:{_sb};margin-top:5px;margin-bottom:1rem;">'
                            f'% = allocation within each fund\'s portfolio</div>'

                            f'<div style="border-top:1px solid {_bdr};padding-top:0.75rem;">'
                            f'<div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.7px;color:{_sb};margin-bottom:7px;">What do these labels mean?</div>'
                            f'<div style="display:flex;flex-direction:column;gap:5px;">'
                            + (
                            f'<div style="display:flex;align-items:baseline;gap:8px;">'
                            f'<span style="font-size:0.72rem;font-weight:700;color:{"#34D399" if _is_dark else "#059669"};min-width:82px;flex-shrink:0;">🟢 Excellent<br><span style="font-weight:400;color:{_sb};font-size:0.65rem;">&lt;15%</span></span>'
                            f'<span style="font-size:0.72rem;color:{_bd};line-height:1.5;">Very different portfolios — ideal combination.</span></div>'
                            f'<div style="display:flex;align-items:baseline;gap:8px;">'
                            f'<span style="font-size:0.72rem;font-weight:700;color:{"#34D399" if _is_dark else "#059669"};min-width:82px;flex-shrink:0;">🟢 Good<br><span style="font-weight:400;color:{_sb};font-size:0.65rem;">15–29%</span></span>'
                            f'<span style="font-size:0.72rem;color:{_bd};line-height:1.5;">Healthy diversification — generally fine.</span></div>'
                            f'<div style="display:flex;align-items:baseline;gap:8px;">'
                            f'<span style="font-size:0.72rem;font-weight:700;color:{_a};min-width:82px;flex-shrink:0;">🔵 Moderate<br><span style="font-weight:400;color:{_sb};font-size:0.65rem;">30–44%</span></span>'
                            f'<span style="font-size:0.72rem;color:{_bd};line-height:1.5;">Noticeable overlap — worth monitoring.</span></div>'
                            f'<div style="display:flex;align-items:baseline;gap:8px;">'
                            f'<span style="font-size:0.72rem;font-weight:700;color:{"#FDE68A" if _is_dark else "#D97706"};min-width:82px;flex-shrink:0;">🟡 High<br><span style="font-weight:400;color:{_sb};font-size:0.65rem;">45–59%</span></span>'
                            f'<span style="font-size:0.72rem;color:{_bd};line-height:1.5;">Significant overlap — paying two managers for similar results.</span></div>'
                            f'<div style="display:flex;align-items:baseline;gap:8px;">'
                            f'<span style="font-size:0.72rem;font-weight:700;color:{"#FCA5A5" if _is_dark else "#DC2626"};min-width:82px;flex-shrink:0;">🔴 Very High<br><span style="font-weight:400;color:{_sb};font-size:0.65rem;">60%+</span></span>'
                            f'<span style="font-size:0.72rem;color:{_bd};line-height:1.5;">Nearly identical — consider replacing one fund.</span></div>'
                            )
                            + f'</div>'
                            f'<div style="font-size:0.65rem;color:{_sb};margin-top:8px;padding-top:6px;border-top:1px solid {_bdr};">'
                            f'💡 Aim to keep all pairs below 30% for a well-diversified portfolio.</div>'
                            f'</div>'
                        )
                        st.markdown(_full_html, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Advanced: overlap matrix (collapsible) ────────────────────────────
        with st.expander("🔬 Advanced view — See the full overlap matrix"):
            display_mode = st.radio(
                "Show numbers as:",
                ["% overlap", "plain words", "both"],
                index=2,
                horizontal=True,
            )

            col_matrix, col_top = st.columns([3, 2], gap="large")

        with col_matrix:
            cats = [cat_lk.get(f, "Large Cap") for f in selected]

            # Responsive sizing — scale everything down as fund count grows
            n_sel    = len(selected)
            cell_h   = 86 if n_sel <= 3 else 74 if n_sel == 4 else 64
            pct_fs   = 20 if n_sel <= 3 else 17 if n_sel == 4 else 14
            hdr_fs   = 11 if n_sel <= 3 else 10
            lbl_fs   = 9  if n_sel <= 3 else 8
            pad      = 3  if n_sel <= 3 else 2

            # Matrix uses short_name so headers are compact enough to fit
            def _mx_name(name):
                n = short_name(name)
                return (n[:16] + "…") if len(n) > 16 else n

            m_names = [_mx_name(f) for f in selected]

            def _cell_cfg(score, common):
                if common == 0 and score == 0:
                    return {"bg": _bdr, "txt": _sb,
                            "label": "No data",
                            "bdg_bg": _bdr, "bdg_txt": _sb}
                if score >= 60:
                    if _is_dark:
                        return {"bg": "rgba(239,68,68,0.30)", "txt": "#FCA5A5",
                                "label": "Very High",
                                "bdg_bg": "rgba(239,68,68,0.20)", "bdg_txt": "#FCA5A5"}
                    return {"bg": "#FEE2E2", "txt": "#991B1B",
                            "label": "Very High",
                            "bdg_bg": "#FECACA", "bdg_txt": "#991B1B"}
                if score >= 45:
                    if _is_dark:
                        return {"bg": "rgba(245,158,11,0.30)", "txt": "#FDE68A",
                                "label": "High",
                                "bdg_bg": "rgba(245,158,11,0.20)", "bdg_txt": "#FDE68A"}
                    return {"bg": "#FEF9C3", "txt": "#854D0E",
                            "label": "High",
                            "bdg_bg": "#FDE68A", "bdg_txt": "#854D0E"}
                if score >= 30:
                    return {"bg": _al, "txt": _a,
                            "label": "Moderate",
                            "bdg_bg": _al, "bdg_txt": _a}
                if score >= 15:
                    if _is_dark:
                        return {"bg": "rgba(16,185,129,0.25)", "txt": "#6EE7B7",
                                "label": "Good",
                                "bdg_bg": "rgba(16,185,129,0.20)", "bdg_txt": "#6EE7B7"}
                    return {"bg": "#D1FAE5", "txt": "#065F46",
                            "label": "Good",
                            "bdg_bg": "#A7F3D0", "bdg_txt": "#065F46"}
                if _is_dark:
                    return {"bg": "rgba(16,185,129,0.15)", "txt": "#34D399",
                            "label": "Excellent",
                            "bdg_bg": "rgba(16,185,129,0.10)", "bdg_txt": "#34D399"}
                return {"bg": "#ECFDF5", "txt": "#064E3B",
                        "label": "Excellent",
                        "bdg_bg": "#D1FAE5", "bdg_txt": "#064E3B"}

            # Column headers — no fixed widths, table fills container
            hdr = '<td style="width:18%;"></td>'
            for mn, cat in zip(m_names, cats):
                hdr += (
                    f'<td style="text-align:center;padding:0 2px {pad*3}px;vertical-align:bottom;">'
                    f'<div style="font-weight:700;font-size:{hdr_fs}px;color:{_hd};'
                    f'line-height:1.3;word-break:break-word;">{mn}</div>'
                    f'<div style="font-size:{lbl_fs}px;color:{_sb};">{cat}</div>'
                    f'</td>'
                )

            # Matrix rows
            rows = ""
            for fa, mn, fa_cat in zip(selected, m_names, cats):
                cells = ""
                for fb in selected:
                    if fa == fb:
                        cells += (
                            f'<td style="padding:{pad}px;">'
                            f'<div style="background:{_bdr};border-radius:8px;'
                            f'width:100%;height:{cell_h}px;display:flex;align-items:center;justify-content:center;">'
                            f'<span style="font-size:{lbl_fs}px;color:{_sb};font-style:italic;">—</span>'
                            f'</div></td>'
                        )
                    else:
                        sc  = score_lk.get((fa, fb), 0)
                        co  = common_lk.get((fa, fb), 0)
                        cfg = _cell_cfg(sc, co)
                        pct = (
                            f'<div style="font-size:{pct_fs}px;font-weight:800;'
                            f'color:{cfg["txt"]};line-height:1;">{sc:.0f}%</div>'
                            if display_mode in ("% overlap", "both") else ""
                        )
                        lbl = (
                            f'<div style="background:{cfg["bdg_bg"]};color:{cfg["bdg_txt"]};'
                            f'font-size:{lbl_fs}px;font-weight:700;border-radius:9999px;'
                            f'padding:2px 5px;margin-top:4px;white-space:nowrap;text-align:center;">'
                            f'{cfg["label"]}</div>'
                            if display_mode in ("plain words", "both") else ""
                        )
                        cells += (
                            f'<td style="padding:{pad}px;">'
                            f'<div style="background:{cfg["bg"]};border-radius:8px;width:100%;'
                            f'height:{cell_h}px;display:flex;flex-direction:column;'
                            f'align-items:center;justify-content:center;padding:0 4px;">'
                            f'{pct}{lbl}</div></td>'
                        )

                rows += (
                    f'<tr>'
                    f'<td style="padding:{pad}px 8px {pad}px 0;text-align:right;vertical-align:middle;">'
                    f'<div style="font-weight:700;font-size:{hdr_fs}px;color:{_hd};'
                    f'word-break:break-word;line-height:1.3;">{mn}</div>'
                    f'<div style="font-size:{lbl_fs}px;color:{_sb};">{fa_cat}</div>'
                    f'</td>{cells}</tr>'
                )

            st.markdown(
                f'<table style="border-collapse:separate;border-spacing:0;'
                f'width:100%;table-layout:fixed;">'
                f'<thead><tr>{hdr}</tr></thead>'
                f'<tbody>{rows}</tbody>'
                f'</table>',
                unsafe_allow_html=True,
            )

            # Colour legend — swatches match _cell_cfg colours for the active theme
            if _is_dark:
                _sw = [
                    ("rgba(16,185,129,0.15)", "rgba(16,185,129,0.25)"),
                    ("rgba(16,185,129,0.25)", "rgba(16,185,129,0.40)"),
                    (_al, _a50),
                    ("rgba(245,158,11,0.30)", "rgba(245,158,11,0.50)"),
                    ("rgba(239,68,68,0.30)",  "rgba(239,68,68,0.50)"),
                ]
            else:
                _sw = [
                    ("#ECFDF5", "#A7F3D0"),
                    ("#D1FAE5", "#6EE7B7"),
                    (_al, _a50),
                    ("#FEF9C3", "#FDE68A"),
                    ("#FEE2E2", "#FECACA"),
                ]
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:8px;margin-top:14px;'
                f'font-size:11px;color:{_sb};flex-wrap:wrap;">'
                f'<span style="font-weight:600;">Low overlap</span>'
                f'<div style="display:flex;gap:3px;align-items:center;">'
                + "".join(
                    f'<div style="width:14px;height:14px;background:{bg};border:1px solid {bdr};border-radius:3px;"></div>'
                    for bg, bdr in _sw
                )
                + f'</div>'
                f'<span style="font-weight:600;">High overlap</span>'
                f'<span style="color:{_sb};">· Higher = more redundant</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        with col_top:
            st.markdown('<div class="section-title">Top Common Holdings</div>', unsafe_allow_html=True)
            st.markdown('<div class="section-sub">Stocks held across the most selected funds, ranked by avg allocation</div>', unsafe_allow_html=True)

            top_com = (
                sel_h.groupby("stock_name")
                .agg(
                    funds_holding=("fund_name",         "nunique"),
                    avg_alloc    =("allocation_percent", "mean"),
                    sector       =("sector",             "first"),
                )
                .reset_index()
                .sort_values(["funds_holding", "avg_alloc"], ascending=[False, False])
                .head(12)
            )
            top_com["stock_name"] = top_com["stock_name"].str.strip()
            top_com["avg_alloc"]  = top_com["avg_alloc"].round(2)

            # Which funds hold each stock (for per-fund dot coloring)
            stock_to_funds = (
                sel_h.groupby("stock_name")["fund_name"]
                .apply(set)
                .to_dict()
            )

            FUND_COLORS = [_a, "#F97316", "#0891B2", "#16A34A", "#E11D48"]

            max_alloc_top = float(top_com["avg_alloc"].max()) if not top_com.empty else 1.0
            n_sel         = len(selected)

            def _ch_row(stock, alloc, sector_val):
                bar_w = min(100.0, alloc / max_alloc_top * 100) if max_alloc_top else 0
                sec_str = str(sector_val).strip() if pd.notna(sector_val) and str(sector_val).strip() not in ("", "nan") else ""
                sec_tag = (
                    f'<span style="font-size:0.58rem;background:{_al};color:{_sb};'
                    f'border-radius:4px;padding:1px 5px;margin-left:4px;">'
                    + sec_str.title() + '</span>'
                ) if sec_str else ""
                holding_funds = stock_to_funds.get(stock, set())
                dots = ""
                for idx, fund_name in enumerate(selected):
                    if fund_name in holding_funds:
                        bg = FUND_COLORS[idx % len(FUND_COLORS)]
                    else:
                        bg = _bdr
                    dots += (
                        '<span style="display:inline-block;width:9px;height:9px;'
                        'border-radius:50%;background:' + bg + ';margin-right:2px;"></span>'
                    )
                return (
                    f'<div style="display:flex;align-items:center;padding:8px 0;'
                    f'border-bottom:1px solid {_bdr};gap:10px;">'
                    f'<div style="flex:1;min-width:0;">'
                    f'<div style="font-size:0.78rem;font-weight:700;color:{_hd};'
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                    + stock + sec_tag +
                    f'</div>'
                    f'<div style="background:{_al};border-radius:3px;height:5px;'
                    f'margin-top:5px;overflow:hidden;">'
                    '<div style="background:' + _a + ';width:' + f"{bar_w:.1f}" + '%;'
                    f'height:100%;border-radius:3px;"></div>'
                    f'</div></div>'
                    f'<div style="flex-shrink:0;">' + dots + f'</div>'
                    f'<div style="font-size:0.78rem;font-weight:800;color:{_a};'
                    f'width:38px;text-align:right;flex-shrink:0;">'
                    + f"{alloc:.1f}%" +
                    f'</div></div>'
                )

            rows_html = "".join(
                _ch_row(r["stock_name"], r["avg_alloc"], r["sector"])
                for _, r in top_com.iterrows()
            )

            legend_parts = []
            for i, fund_name in enumerate(selected):
                dot_color = FUND_COLORS[i % len(FUND_COLORS)]
                legend_parts.append(
                    '<div style="display:flex;align-items:center;gap:4px;margin-right:10px;">'
                    '<div style="width:9px;height:9px;border-radius:50%;background:' + dot_color + ';"></div>'
                    f'<span style="font-size:0.65rem;color:{_sb};">' + display_name(fund_name) + '</span>'
                    '</div>'
                )
            legend_html = "".join(legend_parts)

            st.markdown(
                f'<div style="background:{_cd};border:1px solid {_bdr};border-radius:12px;padding:0.75rem 1rem;">'
                f'<div style="display:flex;flex-wrap:wrap;gap:2px;margin-bottom:8px;'
                f'padding-bottom:8px;border-bottom:1px solid {_bdr};">'
                + legend_html +
                '</div>'
                + rows_html +
                f'<div style="font-size:0.62rem;color:{_sb};margin-top:8px;text-align:right;">'
                'Filled dots = fund holds stock &nbsp;·&nbsp; bar = avg allocation weight'
                '</div></div>',
                unsafe_allow_html=True,
            )

    # ── Tab 2: Fund Performance ──────────────────────────────────────────────
    with tab_perf:
        st.markdown('<div class="section-title">Fund Performance Comparison</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Returns, risk, and efficiency metrics side by side across selected funds</div>', unsafe_allow_html=True)
        _render_fund_performance_tab(
            master[master["fund_name"].isin(selected)].copy(),
            selected,
            hd=_hd, sb=_sb, bd=_bd, a=_a, cd=_cd, bdr=_bdr, al=_al,
            col_amber=_col_amber, col_green=_col_green, col_red=_col_red,
            cf=_cf, cg=_cg, ct=_ct, is_dark=_is_dark,
            explainer_key="cmp",
        )

    # ── Tab 3: Holdings Deep Dive ────────────────────────────────────────────
    with tab_ol:
        # ── Data computation ─────────────────────────────────────────────────
        _n_funds = len(selected)
        _eff = (
            sel_h.assign(stock_name=sel_h["stock_name"].str.strip())
            .groupby("stock_name")
            .agg(
                funds_holding=("fund_name",          "nunique"),
                avg_alloc    =("allocation_percent",  "mean"),
                sector       =("sector",              "first"),
            )
            .reset_index()
        )
        _eff["eff_weight"] = _eff["avg_alloc"] * (_eff["funds_holding"] / _n_funds)
        _eff = _eff.sort_values(["funds_holding", "eff_weight"], ascending=[False, False]).reset_index(drop=True)

        _HIGH_THRESH = 8.0
        _max_eff = float(_eff["eff_weight"].max()) if not _eff.empty else 1.0

        # ── Insights metrics ─────────────────────────────────────────────────
        _total_stocks = len(_eff)
        _all_shared   = _eff[_eff["funds_holding"] == _n_funds]
        _exclusive    = _eff[_eff["funds_holding"] == 1]
        _shared_2p    = _eff[_eff["funds_holding"] >= 2]

        # Allocation-weighted overlap: % of average fund weight that sits in shared stocks.
        # More meaningful than a raw stock count — answers "how much of my money is duplicated?"
        _total_alloc  = _eff["avg_alloc"].sum()
        _shared_alloc = _eff.loc[_eff["funds_holding"] >= 2, "avg_alloc"].sum()
        _overlap_pct  = (_shared_alloc / _total_alloc * 100) if _total_alloc > 0 else 0

        _fund_excl = {}
        for _fn_ex in selected:
            _fn_stocks = set(sel_h[sel_h["fund_name"] == _fn_ex]["stock_name"].str.strip())
            _fn_excl_df = _eff[(_eff["funds_holding"] == 1) & (_eff["stock_name"].isin(_fn_stocks))]
            _fund_excl[_fn_ex] = len(_fn_excl_df)

        # Thresholds mirror the app-wide overlap buckets exactly:
        # Excellent <15%, Good 15-29%, Moderate 30-44%, High 45-59%, Very High ≥60%
        if _overlap_pct >= 60:
            _v_icon, _v_label, _v_col = "🔴", "Very High Allocation Overlap", _col_red
            _v_desc = (
                f"{_overlap_pct:.0f}% of the average fund's weight is in stocks also held "
                f"by at least one other fund. You're effectively paying multiple managers "
                f"to make nearly identical bets. Consider swapping a fund for a different "
                f"category to get genuine diversification."
            )
            _v_bg  = "rgba(239,68,68,0.12)" if _is_dark else "#FEF2F2"
            _v_bdr = "rgba(239,68,68,0.30)" if _is_dark else "#FECACA"
        elif _overlap_pct >= 45:
            _v_icon, _v_label, _v_col = "🟡", "High Allocation Overlap", _col_amber
            _v_desc = (
                f"{_overlap_pct:.0f}% of the average fund's weight sits in stocks shared "
                f"with at least one other fund. Significant duplication — you may be paying "
                f"two managers for similar results."
            )
            _v_bg  = "rgba(245,158,11,0.12)" if _is_dark else "#FFFBEB"
            _v_bdr = "rgba(245,158,11,0.30)" if _is_dark else "#FDE68A"
        elif _overlap_pct >= 30:
            _v_icon, _v_label, _v_col = "🔵", "Moderate Allocation Overlap", "#6366F1"
            _v_desc = (
                f"{_overlap_pct:.0f}% of the average fund's weight is in stocks shared "
                f"with at least one other fund. Noticeable duplication — worth monitoring. "
                f"Consider whether any fund could be swapped for better spread."
            )
            _v_bg  = "rgba(99,102,241,0.10)" if _is_dark else "#EEF2FF"
            _v_bdr = "rgba(99,102,241,0.30)" if _is_dark else "#C7D2FE"
        elif _overlap_pct >= 15:
            _v_icon, _v_label, _v_col = "🟢", "Good — Low Allocation Overlap", "#059669"
            _v_desc = (
                f"Only {_overlap_pct:.0f}% of the average fund's weight is in shared stocks. "
                f"Healthy diversification — your funds are largely investing in different companies."
            )
            _v_bg  = "rgba(16,185,129,0.12)" if _is_dark else "#ECFDF5"
            _v_bdr = "rgba(16,185,129,0.30)" if _is_dark else "#A7F3D0"
        else:
            _v_icon, _v_label, _v_col = "🟢", "Excellent — Minimal Allocation Overlap", "#34D399"
            _v_desc = (
                f"Only {_overlap_pct:.0f}% of the average fund's weight is in stocks also "
                f"held by another fund. Your funds cover very different companies — great diversification!"
            )
            _v_bg  = "rgba(16,185,129,0.12)" if _is_dark else "#ECFDF5"
            _v_bdr = "rgba(16,185,129,0.30)" if _is_dark else "#A7F3D0"

        # ── Insights: stat cards ──────────────────────────────────────────────
        _ins_data = [
            ("📦", "Total Unique Stocks",  str(_total_stocks),    f"across all {_n_funds} funds",  _hd),
            ("🔗", "Shared by All Funds",  str(len(_all_shared)), f"held by all {_n_funds} funds", _col_amber if len(_all_shared) > 10 else _bd),
            ("🔍", "Exclusive Holdings",   str(len(_exclusive)),  "held by exactly 1 fund",        _col_green if len(_exclusive) > 0 else _sb),
        ]
        _ic1, _ic2, _ic3, _ic4 = st.columns(4)
        for _icol, (ico, title, val, sub, vc) in zip([_ic1, _ic2, _ic3], _ins_data):
            with _icol:
                st.markdown(
                    f'<div style="background:{_cd};border:1px solid {_bdr};border-radius:12px;padding:0.9rem 1rem;">'
                    f'<div style="font-size:1rem;margin-bottom:4px;">{ico}</div>'
                    f'<div style="font-size:0.62rem;color:{_sb};font-weight:600;text-transform:uppercase;'
                    f'letter-spacing:0.4px;margin-bottom:6px;">{title}</div>'
                    f'<div style="font-size:1.5rem;font-weight:800;color:{vc};line-height:1;">{val}</div>'
                    f'<div style="font-size:0.62rem;color:{_sb};margin-top:3px;">{sub}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ── 4th card: Allocation in Shared Stocks — with explanation popup ────
        with _ic4:
            st.markdown(
                f'<style>'
                f'.dd-info{{position:relative;display:block;cursor:help;}}'
                f'.dd-tip{{'
                f'  display:none;position:absolute;left:calc(100% + 12px);top:0;'
                f'  background:{_cd};border:1px solid {_bdr};border-radius:14px;'
                f'  padding:1rem 1.1rem;width:310px;z-index:9999;text-align:left;'
                f'  box-shadow:0 12px 40px rgba(0,0,0,0.18);pointer-events:none;}}'
                f'.dd-info:hover .dd-tip{{display:block;}}'
                f'.dd-tip::before{{'
                f'  content:"";position:absolute;top:18px;right:100%;'
                f'  border:7px solid transparent;border-right-color:{_cd};}}'
                f'</style>'

                f'<div class="dd-info">'
                f'<div style="background:{_cd};border:1px solid {_bdr};border-radius:12px;padding:0.9rem 1rem;">'
                f'<div style="font-size:1rem;margin-bottom:4px;">📊</div>'
                f'<div style="font-size:0.62rem;color:{_sb};font-weight:600;text-transform:uppercase;'
                f'letter-spacing:0.4px;margin-bottom:6px;">Allocation in Shared Stocks</div>'
                f'<div style="font-size:1.5rem;font-weight:800;color:{_v_col};line-height:1;">{_overlap_pct:.0f}%</div>'
                f'<div style="font-size:0.62rem;color:{_sb};margin-top:3px;">of avg fund weight duplicated</div>'
                f'<div style="font-size:0.6rem;color:{_sb};margin-top:5px;border-top:1px dashed {_bdr};'
                f'padding-top:5px;">ⓘ Hover to understand</div>'
                f'</div>'

                # ── Popup content ──────────────────────────────────────────
                f'<div class="dd-tip">'
                f'<div style="font-size:0.78rem;font-weight:700;color:{_a};margin-bottom:0.55rem;">'
                f'What does this mean?</div>'
                f'<div style="font-size:0.73rem;color:{_bd};line-height:1.65;margin-bottom:0.85rem;">'
                f'<strong style="color:{_hd};">{_overlap_pct:.0f}%</strong> of the average fund\'s '
                f'weight is invested in stocks that are <em>also held by at least one other fund</em> '
                f'in your selection. In other words, ₹{_overlap_pct:.0f} out of every ₹100 you invest '
                f'goes into positions duplicated across funds.'
                f'</div>'

                f'<div style="font-size:0.75rem;font-weight:700;color:{_a};margin-bottom:0.4rem;">'
                f'How is it different from Avg Portfolio Similarity ({avg_sim:.0f}%)?</div>'
                f'<div style="font-size:0.73rem;color:{_bd};line-height:1.65;margin-bottom:0.85rem;">'
                f'<strong style="color:{_hd};">Avg Portfolio Similarity</strong> counts how many '
                f'stock <em>names</em> overlap between each pair of funds and averages that across '
                f'all pairs — every stock counts equally, regardless of weight.<br><br>'
                f'<strong style="color:{_hd};">Allocation in Shared Stocks</strong> is '
                f'<em>weight-aware</em>: a stock that eats 8% of a fund\'s portfolio counts far more '
                f'than one at 0.2%. So if your funds all pile into the same top 5 mega-caps, this '
                f'number will be much higher than the pairwise similarity.'
                f'</div>'

                f'<div style="background:{_al};border-radius:8px;padding:0.55rem 0.7rem;">'
                f'<div style="font-size:0.7rem;font-weight:700;color:{_a};margin-bottom:3px;">Example</div>'
                f'<div style="font-size:0.7rem;color:{_bd};line-height:1.55;">'
                f'Fund A and Fund B each hold 50 stocks, sharing 15 names (30% pairwise similarity). '
                f'But those 15 shared stocks are the top holdings — 60% of each fund\'s weight. '
                f'Pairwise similarity = 30%, Allocation overlap = 60%. '
                f'<strong style="color:{_hd};">The second number is the real story.</strong>'
                f'</div>'
                f'</div>'
                f'</div>'  # end dd-tip

                f'</div>',  # end dd-info
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # Per-fund exclusive chips
        if _n_funds > 1:
            _chips_html = (
                f'<div style="margin-bottom:0.5rem;">'
                f'<div style="font-size:0.7rem;font-weight:700;color:{_sb};text-transform:uppercase;'
                f'letter-spacing:0.4px;margin-bottom:8px;">What each fund brings uniquely</div>'
                f'<div style="display:flex;flex-wrap:wrap;gap:8px;">'
            )
            for _fi_ch, _fn_ch in enumerate(selected):
                _fc_ch  = PERF_COLORS[_fi_ch % len(PERF_COLORS)]
                _ex_cnt = _fund_excl.get(_fn_ch, 0)
                _ex_col = _col_green if _ex_cnt >= 10 else (_col_amber if _ex_cnt >= 3 else _sb)
                _chips_html += (
                    f'<div style="background:{_cd};border:1px solid {_bdr};border-left:3px solid {_fc_ch};'
                    f'border-radius:8px;padding:0.5rem 0.75rem;display:flex;align-items:center;gap:10px;">'
                    f'<div style="font-size:0.78rem;font-weight:700;color:{_hd};">{display_name(_fn_ch)}</div>'
                    f'<div style="font-size:0.72rem;font-weight:700;color:{_ex_col};">'
                    f'{_ex_cnt} exclusive stock{"s" if _ex_cnt != 1 else ""}</div>'
                    f'</div>'
                )
            _chips_html += '</div></div>'
            st.markdown(_chips_html, unsafe_allow_html=True)

        # Verdict card
        st.markdown(
            f'<div style="background:{_v_bg};border:1px solid {_v_bdr};border-left:3px solid {_v_col};'
            f'border-radius:10px;padding:0.75rem 1rem;margin-bottom:0.5rem;">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
            f'<span style="font-size:1rem;">{_v_icon}</span>'
            f'<span style="font-size:0.88rem;font-weight:700;color:{_v_col};">{_v_label}</span>'
            f'</div>'
            f'<div style="font-size:0.82rem;color:{_bd};line-height:1.6;">{_v_desc}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Effective Portfolio expander ──────────────────────────────────────
        _conc_stocks = _eff[_eff["eff_weight"] >= _HIGH_THRESH]
        _ep_html = ""
        if not _conc_stocks.empty:
            _conc_names = ", ".join(f"<strong>{s}</strong>" for s in _conc_stocks["stock_name"].tolist())
            _ep_html += (
                f'<div style="background:{"rgba(245,158,11,0.15)" if _is_dark else "#FEF3C7"};'
                f'border:1px solid {"rgba(245,158,11,0.35)" if _is_dark else "#FCD34D"};'
                f'border-left:3px solid {_col_amber};border-radius:10px;'
                f'padding:0.75rem 1rem;margin-bottom:1rem;font-size:0.82rem;color:{_hd};line-height:1.55;">'
                f'⚠️ <strong style="color:{_col_amber};">Concentration alert:</strong> '
                f'{_conc_names} each make up ≥{_HIGH_THRESH:.0f}% of your effective portfolio. '
                f'These positions dominate your combined exposure.</div>'
            )
        _ep_html += (
            f'<div style="display:grid;grid-template-columns:1fr 80px 80px 120px 100px;'
            f'gap:0;background:{_bdr};border-radius:10px 10px 0 0;padding:0.45rem 0.75rem;">'
            f'<div style="font-size:0.68rem;font-weight:700;color:{_sb};text-transform:uppercase;letter-spacing:0.5px;">Stock · Sector</div>'
            f'<div style="font-size:0.68rem;font-weight:700;color:{_sb};text-align:center;text-transform:uppercase;letter-spacing:0.5px;"># Funds</div>'
            f'<div style="font-size:0.68rem;font-weight:700;color:{_sb};text-align:right;text-transform:uppercase;letter-spacing:0.5px;">Avg Alloc</div>'
            f'<div style="font-size:0.68rem;font-weight:700;color:{_sb};text-align:center;text-transform:uppercase;letter-spacing:0.5px;">Coverage</div>'
            f'<div style="font-size:0.68rem;font-weight:700;color:{_sb};text-align:right;text-transform:uppercase;letter-spacing:0.5px;">Eff. Weight</div>'
            f'</div>'
        )
        _eff_rows_html = ""
        for _ei, _er in _eff.head(30).iterrows():
            _sec_str = str(_er.get("sector", "")).strip()
            _sec_str = _sec_str if _sec_str and _sec_str != "nan" else ""
            _bar_w   = min(100, _er["eff_weight"] / _max_eff * 100)
            _is_high = _er["eff_weight"] >= _HIGH_THRESH
            _wt_col  = _col_amber if _is_high else _a
            _cov_pct = int(_er["funds_holding"] / _n_funds * 100)
            _cov_col = _col_green if _cov_pct == 100 else (_col_amber if _cov_pct >= 50 else _sb)
            _row_bg  = f"{'rgba(245,158,11,0.06)' if _is_dark else '#FFFBEB'}" if _is_high else _cd
            _eff_rows_html += (
                f'<div style="display:grid;grid-template-columns:1fr 80px 80px 120px 100px;'
                f'gap:0;background:{_row_bg};padding:0.5rem 0.75rem;'
                f'border-bottom:1px solid {_bdr};align-items:center;">'
                f'<div>'
                f'<div style="font-size:0.82rem;font-weight:600;color:{_hd};">{_er["stock_name"]}'
                + (f' <span style="font-size:0.6rem;color:{_col_amber};font-weight:700;">▲ HIGH</span>' if _is_high else '')
                + f'</div>'
                + (f'<div style="font-size:0.62rem;color:{_sb};margin-top:1px;">{_sec_str}</div>' if _sec_str else '')
                + f'</div>'
                f'<div style="text-align:center;font-size:0.8rem;font-weight:700;color:{_hd};">{int(_er["funds_holding"])}/{_n_funds}</div>'
                f'<div style="text-align:right;font-size:0.8rem;font-weight:600;color:{_bd};">{_er["avg_alloc"]:.2f}%</div>'
                f'<div style="padding:0 12px;">'
                f'<div style="background:{_bdr};border-radius:3px;height:6px;overflow:hidden;">'
                f'<div style="background:{_cov_col};width:{_cov_pct}%;height:100%;border-radius:3px;"></div></div>'
                f'<div style="font-size:0.6rem;color:{_cov_col};margin-top:2px;text-align:center;">{_cov_pct}% of funds</div></div>'
                f'<div style="text-align:right;">'
                f'<div style="font-size:0.88rem;font-weight:800;color:{_wt_col};">{_er["eff_weight"]:.2f}%</div>'
                f'<div style="background:{_bdr};border-radius:3px;height:4px;overflow:hidden;margin-top:3px;">'
                f'<div style="background:{_wt_col};width:{_bar_w:.1f}%;height:100%;border-radius:3px;"></div></div></div>'
                f'</div>'
            )
        _ep_html += (
            f'<div style="border:1px solid {_bdr};border-top:none;border-radius:0 0 10px 10px;overflow:hidden;">'
            + _eff_rows_html + f'</div>'
            f'<div style="font-size:0.62rem;color:{_sb};margin-top:6px;text-align:right;">'
            f'Top 30 stocks · Eff. Weight = avg allocation × (funds holding ÷ total funds selected)</div>'
        )
        with st.expander("🗂️ Effective Portfolio — blended stock exposure across all funds", expanded=False):
            st.markdown(
                f'<div class="section-sub">Equal-weighted blend of all selected funds — '
                f'your actual combined stock exposure if you invest equally in each fund</div>',
                unsafe_allow_html=True,
            )
            st.markdown(_ep_html, unsafe_allow_html=True)

        # ── Stock-Level Allocation Comparison expander ────────────────────────
        with st.expander("📊 Stock-Level Allocation Comparison — per-fund breakdown", expanded=False):
            hold_filter = st.radio(
            "Show",
            options=["Shared (held by 2+ funds)", "All holdings", "Exclusive (held by 1 fund only)"],
            index=0,
            horizontal=True,
            key="hold_filter_radio",
            help=(
                "'Shared' shows overlap stocks · "
                "'All holdings' shows every stock including unique ones · "
                "'Exclusive' shows only stocks held by exactly one fund"
            ),
        )

            pivot = (
                sel_h.pivot_table(index="stock_name", columns="fund_name", values="allocation_percent", aggfunc="sum")
                .fillna(0)
            )
            pivot.index = pivot.index.str.strip()
            pivot.columns = [display_name(c) for c in pivot.columns]
            pivot["_n"] = (pivot > 0).sum(axis=1)

            if hold_filter == "Shared (held by 2+ funds)":
                pivot = pivot[pivot["_n"] > 1]
                sub_text = "Stocks held by 2+ funds — bar width shows allocation weight per fund"
                empty_msg = "No stocks are held by more than one selected fund."
            elif hold_filter == "Exclusive (held by 1 fund only)":
                pivot = pivot[pivot["_n"] == 1]
                sub_text = "Stocks held exclusively by a single fund — these drive differentiation between funds"
                empty_msg = "No exclusive holdings found — all stocks are shared across 2+ selected funds."
            else:
                sub_text = "All holdings across selected funds — stocks with 0% are not held by that fund"
                empty_msg = "No holdings data found for the selected funds."

            pivot = pivot.drop(columns=["_n"])
            st.markdown(f'<div class="section-sub">{sub_text}</div>', unsafe_allow_html=True)

            if pivot.empty:
                st.info(empty_msg)
            else:
                fund_cols = pivot.columns.tolist()
                if hold_filter == "All holdings":
                    pivot["_sort_n"] = (pivot > 0).sum(axis=1)
                    pivot = pivot.sort_values(["_sort_n", fund_cols[0]], ascending=[False, False]).drop(columns=["_sort_n"])
                elif hold_filter == "Exclusive (held by 1 fund only)":
                    pivot["_max_alloc"] = pivot[fund_cols].max(axis=1)
                    pivot = pivot.sort_values("_max_alloc", ascending=False).drop(columns=["_max_alloc"])
                else:
                    pivot = pivot.sort_values(fund_cols[0], ascending=False)

                sector_map = (
                    sel_h.assign(stock_name=sel_h["stock_name"].str.strip())
                    .dropna(subset=["sector"])
                    .groupby("stock_name")["sector"]
                    .first()
                    .to_dict()
                )
                pivot_tbl = pivot.reset_index()
                pivot_tbl.rename(columns={"stock_name": "Stock"}, inplace=True)
                pivot_tbl.insert(1, "Sector",  pivot_tbl["Stock"].map(sector_map).fillna("—"))
                pivot_tbl.insert(2, "# Funds", (pivot_tbl[fund_cols] > 0).sum(axis=1))

                _max_pv    = float(pivot_tbl[fund_cols].values.max()) if pivot_tbl[fund_cols].values.max() > 0 else 1.0
                _dn_color  = {display_name(fn): PERF_COLORS[i % len(PERF_COLORS)] for i, fn in enumerate(selected)}
                _n_fc      = len(fund_cols)
                _col_w_sl  = f"minmax(160px,2fr) {''.join(['minmax(100px,1fr) ' for _ in fund_cols])}"

                _hdr_sl = (
                    f'<div style="display:grid;grid-template-columns:{_col_w_sl};">'
                    f'<div style="background:{_bdr};padding:0.6rem 0.75rem;display:flex;flex-direction:column;justify-content:center;">'
                    f'<span style="font-size:0.65rem;font-weight:700;color:{_sb};text-transform:uppercase;letter-spacing:0.5px;">Stock · Sector</span>'
                    f'<span style="font-size:0.58rem;color:{_sb};margin-top:1px;">{len(pivot_tbl)} stocks · {_n_fc} funds</span>'
                    f'</div>'
                )
                for _fci, _fc in enumerate(fund_cols):
                    _fcc = _dn_color.get(_fc, _a)
                    _hdr_sl += (
                        f'<div style="background:{_fcc};padding:0.55rem 0.6rem;text-align:center;'
                        f'border-left:1px solid rgba(255,255,255,0.15);">'
                        f'<div style="font-size:0.68rem;font-weight:700;color:#fff;'
                        f'line-height:1.3;word-break:break-word;">{_fc}</div>'
                        f'</div>'
                    )
                _hdr_sl += '</div>'

                _rows_sl = ""
                for _si, (_, _srow) in enumerate(pivot_tbl.iterrows()):
                    _stock  = _srow["Stock"]
                    _sector = str(_srow.get("Sector", "")).strip()
                    _sector = _sector if _sector and _sector not in ("—", "nan") else ""
                    _n_hold = int(_srow["# Funds"])
                    _row_bg = _cd if _si % 2 == 0 else (f"{'rgba(255,255,255,0.02)' if _is_dark else '#F9FAFB'}")
                    _fund_chip_col = _col_green if _n_hold == _n_fc else (_col_amber if _n_hold > 1 else _sb)
                    _rows_sl += (
                        f'<div style="display:grid;grid-template-columns:{_col_w_sl};'
                        f'background:{_row_bg};border-bottom:1px solid {_bdr};">'
                        f'<div style="padding:0.5rem 0.75rem;border-right:1px solid {_bdr};">'
                        f'<div style="font-size:0.82rem;font-weight:600;color:{_hd};line-height:1.3;">{_stock}</div>'
                        + (f'<div style="font-size:0.62rem;color:{_sb};margin-top:1px;">{_sector}</div>' if _sector else '')
                        + f'<div style="font-size:0.58rem;font-weight:700;color:{_fund_chip_col};margin-top:3px;">'
                        f'{_n_hold}/{_n_fc} funds</div></div>'
                    )
                    for _fci, _fc in enumerate(fund_cols):
                        _alloc = float(_srow.get(_fc, 0))
                        _fcc   = _dn_color.get(_fc, _a)
                        _bar_w = min(100, _alloc / _max_pv * 100)
                        if _alloc > 0:
                            _rows_sl += (
                                f'<div style="padding:0.5rem 0.6rem;border-left:1px solid {_bdr};'
                                f'display:flex;flex-direction:column;justify-content:center;gap:4px;">'
                                f'<div style="display:flex;align-items:center;gap:5px;">'
                                f'<div style="flex:1;background:{_bdr};border-radius:3px;height:7px;overflow:hidden;">'
                                f'<div style="background:{_fcc};width:{_bar_w:.1f}%;height:100%;border-radius:3px;opacity:0.85;"></div></div>'
                                f'<div style="font-size:0.75rem;font-weight:700;color:{_hd};min-width:36px;text-align:right;">{_alloc:.2f}%</div>'
                                f'</div></div>'
                            )
                        else:
                            _rows_sl += (
                                f'<div style="border-left:1px solid {_bdr};display:flex;align-items:center;justify-content:center;">'
                                f'<span style="font-size:0.75rem;color:{_bdr};font-weight:500;">—</span></div>'
                            )
                    _rows_sl += '</div>'

                st.markdown(
                    f'<div style="border:1px solid {_bdr};border-radius:12px;overflow:hidden;overflow-x:auto;">'
                    f'{_hdr_sl}{_rows_sl}</div>'
                    f'<div style="font-size:0.62rem;color:{_sb};margin-top:6px;text-align:right;">'
                    f'Bar width = allocation % relative to highest allocation · — = not held by that fund</div>',
                    unsafe_allow_html=True,
                )

    # ── Tab 4: Sector Analysis ───────────────────────────────────────────────
    with tab_sec:
        sel_sector = sector_df[sector_df["fund_name"].isin(selected)].copy()
        sel_sector["fund_short"] = sel_sector["fund_name"].apply(display_name)

        SECTOR_COLORS = {
            "FINANCIAL": "#3B82F6", "TECHNOLOGY": "#8B5CF6", "ENERGY": "#F97316",
            "HEALTHCARE": "#10B981", "CONSUMER DISCRETIONARY": "#F59E0B",
            "CONSUMER STAPLES": "#84CC16", "AUTOMOBILE": "#EC4899",
            "COMMUNICATION": "#06B6D4", "CAPITAL GOODS": "#6366F1",
            "MATERIALS": "#A78BFA", "SERVICES": "#F472B6",
        }

        # ── Insights metrics ─────────────────────────────────────────────────
        _sec_avg    = sel_sector.groupby("sector")["allocation_percent"].mean().sort_values(ascending=False)
        _top_sec    = _sec_avg.index[0] if len(_sec_avg) else "—"
        _top_sec_pct = float(_sec_avg.iloc[0]) if len(_sec_avg) else 0
        _n_sectors  = len(_sec_avg[_sec_avg > 1])
        _sec_color  = SECTOR_COLORS.get(_top_sec.upper(), _a)

        # Most concentrated fund (single highest sector allocation)
        _fund_max   = sel_sector.groupby("fund_name")["allocation_percent"].max()
        _conc_fn    = _fund_max.idxmax() if not _fund_max.empty else None
        _conc_sec   = sel_sector[sel_sector["fund_name"] == _conc_fn].sort_values("allocation_percent", ascending=False).iloc[0] if _conc_fn else None
        _conc_fi    = selected.index(_conc_fn) if _conc_fn and _conc_fn in selected else 0

        # Common top sector: how many funds have same top sector?
        _fund_top_sec = {}
        for _fts in selected:
            _rows = sel_sector[sel_sector["fund_name"] == _fts].sort_values("allocation_percent", ascending=False)
            if not _rows.empty:
                _fund_top_sec[_fts] = _rows.iloc[0]["sector"]
        _common_top = max(set(_fund_top_sec.values()), key=list(_fund_top_sec.values()).count) if _fund_top_sec else "—"
        _common_count = list(_fund_top_sec.values()).count(_common_top)

        # Verdict
        if _top_sec_pct >= 40:
            _sv_icon, _sv_label, _sv_col = "🔴", "Heavily Concentrated", _col_red
            _sv_bg  = "rgba(239,68,68,0.10)" if _is_dark else "#FEF2F2"
            _sv_bdr = "rgba(239,68,68,0.25)" if _is_dark else "#FECACA"
            _sv_desc = (f"{_top_sec} dominates with ~{_top_sec_pct:.0f}% average allocation across your funds. "
                        f"Your combined portfolio is heavily exposed to this one sector — its performance will "
                        f"significantly drive your overall returns. Consider adding a fund from a different sector focus to balance.")
        elif _top_sec_pct >= 25:
            _sv_icon, _sv_label, _sv_col = "🟡", "Moderate Sector Bias", _col_amber
            _sv_bg  = "rgba(245,158,11,0.10)" if _is_dark else "#FFFBEB"
            _sv_bdr = "rgba(245,158,11,0.25)" if _is_dark else "#FDE68A"
            _sv_desc = (f"{_top_sec} leads with ~{_top_sec_pct:.0f}% — a meaningful tilt, but other sectors "
                        f"provide some balance. Watch for sector-specific downturns that could disproportionately affect you.")
        else:
            _sv_icon, _sv_label, _sv_col = "🟢", "Well Diversified Across Sectors", _col_green
            _sv_bg  = "rgba(16,185,129,0.10)" if _is_dark else "#ECFDF5"
            _sv_bdr = "rgba(16,185,129,0.25)" if _is_dark else "#A7F3D0"
            _sv_desc = (f"No single sector dominates — {_top_sec} leads at just ~{_top_sec_pct:.0f}%. "
                        f"Your combined holdings are spread across {_n_sectors} meaningful sectors, reducing sector-specific risk.")

        # ── Insights: stat cards ──────────────────────────────────────────────
        _si4 = st.columns(4)
        _si_data = [
            ("🏆", "Top Sector",         _top_sec.title(),              f"~{_top_sec_pct:.0f}% avg across funds",         _sv_col),
            ("📊", "Sectors Covered",    str(_n_sectors),               "sectors with >1% allocation",                    _bd),
            ("🔗", "Shared Top Sector",  f"{_common_count}/{len(selected)} funds", f"all lean on {_common_top.title()}", _col_amber if _common_count == len(selected) else _bd),
            ("⚠️", "Most Concentrated",  display_name(_conc_fn) if _conc_fn else "—",
             f"{_conc_sec['sector'].title()} @ {_conc_sec['allocation_percent']:.0f}%" if _conc_sec is not None else "—",
             PERF_COLORS[_conc_fi % len(PERF_COLORS)]),
        ]
        for _sii, (ico, title, val, sub, vc) in enumerate(_si_data):
            with _si4[_sii]:
                st.markdown(
                    f'<div style="background:{_cd};border:1px solid {_bdr};border-radius:12px;padding:0.9rem 1rem;">'
                    f'<div style="font-size:1rem;margin-bottom:4px;">{ico}</div>'
                    f'<div style="font-size:0.62rem;color:{_sb};font-weight:600;text-transform:uppercase;'
                    f'letter-spacing:0.4px;margin-bottom:6px;">{title}</div>'
                    f'<div style="font-size:1rem;font-weight:800;color:{vc};line-height:1.2;">{val}</div>'
                    f'<div style="font-size:0.62rem;color:{_sb};margin-top:3px;">{sub}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)

        # Verdict
        st.markdown(
            f'<div style="background:{_sv_bg};border:1px solid {_sv_bdr};border-left:3px solid {_sv_col};'
            f'border-radius:10px;padding:0.75rem 1rem;margin-bottom:1rem;">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
            f'<span style="font-size:1rem;">{_sv_icon}</span>'
            f'<span style="font-size:0.88rem;font-weight:700;color:{_sv_col};">{_sv_label}</span>'
            f'</div>'
            f'<div style="font-size:0.82rem;color:{_bd};line-height:1.6;">{_sv_desc}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Combined Sector View (toggle: Chart ↔ Heatmap) ──────────────────────
        top_sectors  = _sec_avg.nlargest(10).index.tolist()
        plot_df      = sel_sector[sel_sector["sector"].isin(top_sectors)]
        sec_pivot    = (
            sel_sector.pivot_table(index="sector", columns="fund_short",
                                   values="allocation_percent", aggfunc="sum").fillna(0)
        )
        sec_pivot["_avg"] = sec_pivot.mean(axis=1)
        sec_pivot    = sec_pivot.sort_values("_avg", ascending=False).drop(columns=["_avg"])
        sec_tbl      = sec_pivot.reset_index()
        _sec_fcols   = [c for c in sec_tbl.columns if c != "sector"]
        _dn_color_s  = {display_name(fn): PERF_COLORS[i % len(PERF_COLORS)] for i, fn in enumerate(selected)}

        _sv_hdr = st.columns([5, 2])
        with _sv_hdr[1]:
            _sec_view = st.radio(
                "sec_view_lbl", ["📊 Chart", "🗺️ Heatmap"],
                horizontal=True, label_visibility="collapsed", key="sec_view_mode",
            )

        if _sec_view == "📊 Chart":
            _pdf = plot_df.copy()
            _totals = _pdf.groupby("fund_short")["allocation_percent"].transform("sum")
            _pdf["alloc_val"] = _pdf["allocation_percent"] / _totals * 100
            # Sort sectors by avg allocation descending → largest segment leftmost in each bar
            _sec_order = (
                _pdf.groupby("sector")["alloc_val"].mean()
                .sort_values(ascending=False).index.tolist()
            )
            fig_sec = px.bar(
                _pdf, y="fund_short", x="alloc_val", color="sector",
                orientation="h", barmode="stack", color_discrete_map=SECTOR_COLORS,
                labels={"fund_short": "", "alloc_val": "Allocation", "sector": "Sector"},
                text=_pdf["alloc_val"].apply(lambda v: f"{v:.1f}%" if v >= 4 else ""),
                category_orders={"sector": _sec_order},
            )
            fig_sec.update_layout(**_dark_layout(
                height=max(300, len(selected) * 90),
                font=_cf,
                margin=dict(l=0, r=10, t=55, b=10),
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02,
                    xanchor="left", x=0, font=dict(size=11, color=_bd),
                ),
                xaxis=_dark_xaxis(
                    ticksuffix="%", tickfont=_ct, gridcolor=_cg,
                    zerolinecolor=_cg, range=[0, 100],
                ),
                yaxis=_dark_yaxis(tickfont=dict(size=12, color=_bd), automargin=True),
                bargap=0.3,
            ))
            fig_sec.update_traces(
                marker_line_width=0,
                textposition="inside",
                insidetextanchor="middle",
                textfont=dict(size=10, color="#ffffff"),
            )
            st.plotly_chart(fig_sec, use_container_width=True, config={"displayModeBar": False})

        else:  # Heatmap
            _col_w_hm = f"minmax(155px,2fr) {''.join([f'minmax(105px,1fr) ' for _ in _sec_fcols])}"

            # Fund avatar header row
            _hm_hdr = (
                f'<div style="display:grid;grid-template-columns:{_col_w_hm};'
                f'background:{_bdr};border-radius:10px 10px 0 0;">'
                f'<div style="padding:0.65rem 0.75rem;">'
                f'<span style="font-size:0.65rem;font-weight:700;color:{_sb};'
                f'text-transform:uppercase;letter-spacing:0.4px;">Sector</span></div>'
            )
            for _hfi, _hfc in enumerate(_sec_fcols):
                _hfc_color  = _dn_color_s.get(_hfc, _a)
                _hfc_letter = _hfc[0].upper()
                _hfc_full   = next((fn for fn in selected if display_name(fn) == _hfc), None)
                _hfc_cat    = ""
                if _hfc_full:
                    _hm_mrow = master[master["fund_name"] == _hfc_full]
                    if not _hm_mrow.empty:
                        _hfc_cat = str(_hm_mrow.iloc[0].get("category", "")).strip()
                _hm_hdr += (
                    f'<div style="padding:0.65rem 0.5rem;text-align:center;'
                    f'border-left:1px solid rgba(255,255,255,0.1);">'
                    f'<div style="width:34px;height:34px;border-radius:50%;background:{_hfc_color};'
                    f'display:flex;align-items:center;justify-content:center;margin:0 auto 5px;">'
                    f'<span style="font-size:0.85rem;font-weight:800;color:#fff;">{_hfc_letter}</span></div>'
                    f'<div style="font-size:0.68rem;font-weight:700;color:{_hd};line-height:1.3;">{_hfc}</div>'
                    f'<div style="font-size:0.58rem;color:{_sb};margin-top:1px;">{_hfc_cat}</div>'
                    f'</div>'
                )
            _hm_hdr += '</div>'

            # Sector rows
            _hm_rows = ""
            for _sri, (_, _srow) in enumerate(sec_tbl.iterrows()):
                _sec_name = str(_srow["sector"]).title()
                _row_vals = [float(_srow.get(_sfc, 0)) for _sfc in _sec_fcols]
                _row_max  = max(_row_vals) if max(_row_vals) > 0 else 1.0
                _sec_base = SECTOR_COLORS.get(_srow["sector"].upper(), _sb)
                _row_bg   = _cd if _sri % 2 == 0 else (
                    "rgba(255,255,255,0.02)" if _is_dark else "#F9FAFB"
                )
                # parse hex sector color to rgb for rgba cells
                _hx = _sec_base.lstrip("#")
                _hr_c = int(_hx[0:2], 16)
                _hg_c = int(_hx[2:4], 16)
                _hb_c = int(_hx[4:6], 16)

                _hm_rows += (
                    f'<div style="display:grid;grid-template-columns:{_col_w_hm};'
                    f'border-bottom:1px solid {_bdr};">'
                    f'<div style="padding:0.55rem 0.75rem;background:{_row_bg};'
                    f'border-right:1px solid {_bdr};display:flex;align-items:center;gap:8px;">'
                    f'<div style="width:8px;height:8px;border-radius:50%;background:{_sec_base};flex-shrink:0;"></div>'
                    f'<div style="font-size:0.82rem;font-weight:600;color:{_hd};">{_sec_name}</div>'
                    f'</div>'
                )
                for _sfc, _sv in zip(_sec_fcols, _row_vals):
                    _alpha   = (0.08 + (_sv / _row_max) * 0.60) if _sv > 0 else 0
                    _cell_bg = f"rgba({_hr_c},{_hg_c},{_hb_c},{_alpha:.2f})" if _sv > 0 else _row_bg
                    _fw      = "800" if _sv >= _row_max * 0.95 else "600"
                    _tc      = _hd if _sv > 0 else _sb
                    _hm_rows += (
                        f'<div style="padding:0.55rem 0.5rem;background:{_cell_bg};'
                        f'border-left:1px solid {_bdr};text-align:center;">'
                        + (f'<span style="font-size:0.82rem;font-weight:{_fw};color:{_tc};">{_sv:.1f}%</span>'
                           if _sv > 0 else
                           f'<span style="font-size:0.75rem;color:{_bdr};">—</span>')
                        + f'</div>'
                    )
                _hm_rows += '</div>'

            st.markdown(
                f'<div style="font-size:0.72rem;color:{_sb};margin-bottom:8px;">'
                f'Darker color indicates higher allocation within each sector row</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="border:1px solid {_bdr};border-radius:12px;overflow:hidden;overflow-x:auto;">'
                f'{_hm_hdr}{_hm_rows}</div>',
                unsafe_allow_html=True,
            )

    # ── Tab 5: Holdings Timeline ─────────────────────────────────────────────
    with tab_hold:
        def _trend(v3m, v6m, v1y):
            try:
                v3, v6, v1 = float(v3m), float(v6m), float(v1y)
                if v3 >= v6 >= v1: return "↑"
                elif v3 <= v6 <= v1: return "↓"
                else: return "→"
            except Exception:
                return "→"

        shared_counts = sel_h.assign(stock_name=sel_h["stock_name"].str.strip()).groupby("stock_name")["fund_name"].nunique()
        shared_stocks = shared_counts[shared_counts > 1].index

        # Compute aggregated view for insights
        _ht_agg = (
            sel_h.assign(stock_name=sel_h["stock_name"].str.strip())
            .groupby("stock_name")
            .agg(
                funds_holding=("fund_name",         "nunique"),
                avg_alloc    =("allocation_percent", "mean"),
                avg_3m       =("change_3m_percent",  "mean"),
                avg_6m       =("change_6m_percent",  "mean"),
                avg_1y       =("change_1y_percent",  "mean"),
                sector       =("sector",             "first"),
            )
            .reset_index()
        )
        _ht_shared = (
            _ht_agg[_ht_agg["funds_holding"] > 1]
            .sort_values(["funds_holding", "avg_alloc"], ascending=[False, False])
            .reset_index(drop=True)
        )
        _ht_shared["Trend"] = _ht_shared.apply(lambda r: _trend(r["avg_3m"], r["avg_6m"], r["avg_1y"]), axis=1)

        # ── Insights metrics ─────────────────────────────────────────────────
        _ht_n_shared  = len(_ht_shared)
        _ht_gaining   = _ht_shared[_ht_shared["Trend"] == "↑"]
        _ht_losing    = _ht_shared[_ht_shared["Trend"] == "↓"]
        _ht_top_stock = _ht_shared.iloc[0]["stock_name"] if not _ht_shared.empty else "—"
        _ht_top_funds = int(_ht_shared.iloc[0]["funds_holding"]) if not _ht_shared.empty else 0

        if len(_ht_gaining) > len(_ht_losing):
            _htv_icon, _htv_label, _htv_col = "🟢", "Positive Momentum", _col_green
            _htv_bg  = "rgba(16,185,129,0.10)" if _is_dark else "#ECFDF5"
            _htv_bdr = "rgba(16,185,129,0.25)" if _is_dark else "#A7F3D0"
            _htv_desc = (f"{len(_ht_gaining)} of {_ht_n_shared} shared stocks are on an accelerating allocation trend — "
                         f"fund managers across your selection are collectively increasing exposure to these positions. "
                         f"Momentum stocks: {', '.join(_ht_gaining.head(3)['stock_name'].tolist())}.")
        elif len(_ht_losing) > len(_ht_gaining):
            _htv_icon, _htv_label, _htv_col = "🔴", "Declining Momentum", _col_red
            _htv_bg  = "rgba(239,68,68,0.10)" if _is_dark else "#FEF2F2"
            _htv_bdr = "rgba(239,68,68,0.25)" if _is_dark else "#FECACA"
            _htv_desc = (f"{len(_ht_losing)} of {_ht_n_shared} shared stocks are on a decelerating allocation trend — "
                         f"fund managers are collectively trimming these positions. "
                         f"Stocks being reduced: {', '.join(_ht_losing.head(3)['stock_name'].tolist())}.")
        else:
            _htv_icon, _htv_label, _htv_col = "🟡", "Mixed Signals", _col_amber
            _htv_bg  = "rgba(245,158,11,0.10)" if _is_dark else "#FFFBEB"
            _htv_bdr = "rgba(245,158,11,0.25)" if _is_dark else "#FDE68A"
            _htv_desc = (f"Allocation trends are mixed across your shared holdings — "
                         f"{len(_ht_gaining)} stocks gaining momentum, {len(_ht_losing)} declining, {len(_ht_shared) - len(_ht_gaining) - len(_ht_losing)} stable.")

        # Stat cards
        _ht4 = st.columns(4)
        _ht_ins = [
            ("🔗", "Shared Holdings", str(_ht_n_shared),       "stocks held by 2+ funds",                  _bd),
            ("📈", "Gaining Momentum", str(len(_ht_gaining)),  "↑ allocation trend",                       _col_green),
            ("📉", "Losing Momentum",  str(len(_ht_losing)),   "↓ allocation trend",                       _col_red),
            ("🏆", "Most Held Stock",  _ht_top_stock,          f"in {_ht_top_funds}/{len(selected)} funds", _a),
        ]
        for _hti, (ico, title, val, sub, vc) in enumerate(_ht_ins):
            with _ht4[_hti]:
                st.markdown(
                    f'<div style="background:{_cd};border:1px solid {_bdr};border-radius:12px;padding:0.9rem 1rem;">'
                    f'<div style="font-size:1rem;margin-bottom:4px;">{ico}</div>'
                    f'<div style="font-size:0.62rem;color:{_sb};font-weight:600;text-transform:uppercase;'
                    f'letter-spacing:0.4px;margin-bottom:6px;">{title}</div>'
                    f'<div style="font-size:1rem;font-weight:800;color:{vc};line-height:1.2;">{val}</div>'
                    f'<div style="font-size:0.62rem;color:{_sb};margin-top:3px;">{sub}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)

        # Momentum strips
        if not _ht_gaining.empty or not _ht_losing.empty:
            _mom_cols = st.columns(2)
            with _mom_cols[0]:
                _g_chips = "".join(
                    f'<div style="background:{"rgba(16,185,129,0.15)" if _is_dark else "#D1FAE5"};'
                    f'border:1px solid {"rgba(16,185,129,0.3)" if _is_dark else "#6EE7B7"};'
                    f'border-radius:6px;padding:0.3rem 0.6rem;font-size:0.72rem;font-weight:700;color:{_col_green};">'
                    f'↑ {r["stock_name"]} <span style="font-weight:400;color:{_sb};">{r["avg_3m"]:+.1f}% 3M</span></div>'
                    for _, r in _ht_gaining.head(5).iterrows() if pd.notna(r["avg_3m"])
                )
                if _g_chips:
                    st.markdown(
                        f'<div style="font-size:0.7rem;font-weight:700;color:{_col_green};'
                        f'text-transform:uppercase;letter-spacing:0.4px;margin-bottom:6px;">Top gainers</div>'
                        f'<div style="display:flex;flex-wrap:wrap;gap:6px;">{_g_chips}</div>',
                        unsafe_allow_html=True,
                    )
            with _mom_cols[1]:
                _l_chips = "".join(
                    f'<div style="background:{"rgba(239,68,68,0.15)" if _is_dark else "#FEE2E2"};'
                    f'border:1px solid {"rgba(239,68,68,0.3)" if _is_dark else "#FCA5A5"};'
                    f'border-radius:6px;padding:0.3rem 0.6rem;font-size:0.72rem;font-weight:700;color:{_col_red};">'
                    f'↓ {r["stock_name"]} <span style="font-weight:400;color:{_sb};">{r["avg_3m"]:+.1f}% 3M</span></div>'
                    for _, r in _ht_losing.head(5).iterrows() if pd.notna(r["avg_3m"])
                )
                if _l_chips:
                    st.markdown(
                        f'<div style="font-size:0.7rem;font-weight:700;color:{_col_red};'
                        f'text-transform:uppercase;letter-spacing:0.4px;margin-bottom:6px;">Top decliners</div>'
                        f'<div style="display:flex;flex-wrap:wrap;gap:6px;">{_l_chips}</div>',
                        unsafe_allow_html=True,
                    )

        st.markdown("<br>", unsafe_allow_html=True)

        # Verdict
        st.markdown(
            f'<div style="background:{_htv_bg};border:1px solid {_htv_bdr};border-left:3px solid {_htv_col};'
            f'border-radius:10px;padding:0.75rem 1rem;margin-bottom:1rem;">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
            f'<span style="font-size:1rem;">{_htv_icon}</span>'
            f'<span style="font-size:0.88rem;font-weight:700;color:{_htv_col};">{_htv_label}</span>'
            f'</div>'
            f'<div style="font-size:0.82rem;color:{_bd};line-height:1.6;">{_htv_desc}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Holdings Timeline table expander ──────────────────────────────────
        def _delta_cell(val, na_str="—"):
            try:
                v = float(val)
                col = _col_green if v > 0 else (_col_red if v < 0 else _sb)
                return f'<span style="font-weight:700;color:{col};">{v:+.2f}%</span>'
            except Exception:
                return f'<span style="color:{_sb};">{na_str}</span>'

        def _trend_chip(t):
            if t == "↑":
                return (f'<span style="background:{"rgba(16,185,129,0.18)" if _is_dark else "#D1FAE5"};'
                        f'color:{_col_green};border-radius:4px;padding:2px 6px;font-size:0.7rem;font-weight:700;">↑ Up</span>')
            if t == "↓":
                return (f'<span style="background:{"rgba(239,68,68,0.18)" if _is_dark else "#FEE2E2"};'
                        f'color:{_col_red};border-radius:4px;padding:2px 6px;font-size:0.7rem;font-weight:700;">↓ Down</span>')
            return (f'<span style="background:{_bdr};color:{_sb};border-radius:4px;'
                    f'padding:2px 6px;font-size:0.7rem;font-weight:700;">→ Mixed</span>')

        with st.expander("📈 Holdings Timeline — allocation trends across shared stocks", expanded=False):
            ht_view = st.radio(
                "View",
                options=["Average across funds", "Per fund"],
                horizontal=True,
                key="ht_view_radio",
                help="'Average' rolls up each stock · 'Per Fund' shows one row per fund per stock",
            )

            if ht_view == "Average across funds":
                ht_search = st.text_input(
                    "Search stock", placeholder="Type to filter stocks…",
                    key="ht_avg_search", label_visibility="collapsed"
                )
                _disp = _ht_shared.copy()
                if ht_search:
                    _disp = _disp[_disp["stock_name"].str.contains(ht_search.strip(), case=False, na=False)].reset_index(drop=True)

                _max_ha = float(_disp["avg_alloc"].max()) if not _disp.empty else 1.0
                _col_w_ht = "minmax(160px,2fr) 60px 70px 110px 72px 72px 72px"
                _hdr_ht = (
                    f'<div style="display:grid;grid-template-columns:{_col_w_ht};background:{_bdr};border-radius:10px 10px 0 0;">'
                    f'<div style="padding:0.5rem 0.75rem;font-size:0.65rem;font-weight:700;color:{_sb};text-transform:uppercase;letter-spacing:0.4px;">Stock · Sector</div>'
                    f'<div style="padding:0.5rem 0.4rem;font-size:0.65rem;font-weight:700;color:{_sb};text-align:center;text-transform:uppercase;"># Funds</div>'
                    f'<div style="padding:0.5rem 0.4rem;font-size:0.65rem;font-weight:700;color:{_sb};text-align:center;text-transform:uppercase;">Trend</div>'
                    f'<div style="padding:0.5rem 0.6rem;font-size:0.65rem;font-weight:700;color:{_sb};text-transform:uppercase;">Avg Alloc</div>'
                    f'<div style="padding:0.5rem 0.4rem;font-size:0.65rem;font-weight:700;color:{_sb};text-align:right;text-transform:uppercase;">3M Δ</div>'
                    f'<div style="padding:0.5rem 0.4rem;font-size:0.65rem;font-weight:700;color:{_sb};text-align:right;text-transform:uppercase;">6M Δ</div>'
                    f'<div style="padding:0.5rem 0.4rem;font-size:0.65rem;font-weight:700;color:{_sb};text-align:right;text-transform:uppercase;">1Y Δ</div>'
                    f'</div>'
                )
                _rows_ht = ""
                for _hri, (_, _hr) in enumerate(_disp.iterrows()):
                    _row_bg = _cd if _hri % 2 == 0 else (f"{'rgba(255,255,255,0.02)' if _is_dark else '#F9FAFB'}")
                    _sec_s  = str(_hr.get("sector", "")).strip()
                    _sec_s  = _sec_s if _sec_s and _sec_s != "nan" else ""
                    _bw_ha  = min(100, float(_hr["avg_alloc"]) / _max_ha * 100)
                    _rows_ht += (
                        f'<div style="display:grid;grid-template-columns:{_col_w_ht};'
                        f'background:{_row_bg};border-bottom:1px solid {_bdr};align-items:center;">'
                        f'<div style="padding:0.5rem 0.75rem;">'
                        f'<div style="font-size:0.82rem;font-weight:600;color:{_hd};">{_hr["stock_name"]}</div>'
                        + (f'<div style="font-size:0.62rem;color:{_sb};margin-top:1px;">{_sec_s}</div>' if _sec_s else '')
                        + f'</div>'
                        f'<div style="padding:0.5rem 0.4rem;text-align:center;font-size:0.78rem;font-weight:700;color:{_hd};">'
                        f'{int(_hr["funds_holding"])}/{len(selected)}</div>'
                        f'<div style="padding:0.5rem 0.4rem;text-align:center;">{_trend_chip(_hr["Trend"])}</div>'
                        f'<div style="padding:0.5rem 0.6rem;">'
                        f'<div style="display:flex;align-items:center;gap:5px;">'
                        f'<div style="flex:1;background:{_bdr};border-radius:3px;height:7px;overflow:hidden;">'
                        f'<div style="background:{_a};width:{_bw_ha:.1f}%;height:100%;border-radius:3px;opacity:0.85;"></div></div>'
                        f'<div style="font-size:0.72rem;font-weight:700;color:{_hd};min-width:34px;text-align:right;">{_hr["avg_alloc"]:.2f}%</div>'
                        f'</div></div>'
                        f'<div style="padding:0.5rem 0.4rem;text-align:right;font-size:0.75rem;">{_delta_cell(_hr["avg_3m"])}</div>'
                        f'<div style="padding:0.5rem 0.4rem;text-align:right;font-size:0.75rem;">{_delta_cell(_hr["avg_6m"])}</div>'
                        f'<div style="padding:0.5rem 0.4rem;text-align:right;font-size:0.75rem;">{_delta_cell(_hr["avg_1y"])}</div>'
                        f'</div>'
                    )
                st.markdown(
                    f'<div style="border:1px solid {_bdr};border-radius:12px;overflow:hidden;">'
                    f'{_hdr_ht}{_rows_ht}</div>'
                    f'<div style="font-size:0.62rem;color:{_sb};margin-top:6px;text-align:right;">'
                    f'Trend: ↑ Up = 3M &gt; 6M &gt; 1Y (accelerating) · ↓ Down = decelerating · → Mixed</div>',
                    unsafe_allow_html=True,
                )

            else:  # Per fund
                per_fund = (
                    sel_h.assign(stock_name=sel_h["stock_name"].str.strip())
                    [lambda df: df["stock_name"].isin(shared_stocks)]
                    [["stock_name", "fund_name", "sector", "allocation_percent",
                      "change_3m_percent", "change_6m_percent", "change_1y_percent"]]
                    .copy()
                )
                per_fund["fund_dn"]  = per_fund["fund_name"].apply(display_name)
                per_fund["fund_idx"] = per_fund["fund_name"].apply(lambda f: selected.index(f) if f in selected else 0)
                per_fund["Trend"]    = per_fund.apply(
                    lambda r: _trend(r["change_3m_percent"], r["change_6m_percent"], r["change_1y_percent"]), axis=1
                )
                per_fund = per_fund.sort_values(["stock_name", "allocation_percent"], ascending=[True, False]).reset_index(drop=True)

                all_stocks_pf = sorted(per_fund["stock_name"].unique().tolist())
                picked_stocks = st.multiselect(
                    "Filter by stock",
                    options=all_stocks_pf,
                    placeholder="Select stocks to focus on (leave blank for all)…",
                    key="ht_pf_stock_pick",
                    label_visibility="collapsed",
                )
                if picked_stocks:
                    per_fund = per_fund[per_fund["stock_name"].isin(picked_stocks)].reset_index(drop=True)

                _max_pf   = float(per_fund["allocation_percent"].max()) if not per_fund.empty else 1.0
                _col_w_pf = "minmax(140px,2fr) minmax(120px,1.5fr) 60px 100px 70px 70px 70px"
                _hdr_pf = (
                    f'<div style="display:grid;grid-template-columns:{_col_w_pf};background:{_bdr};border-radius:10px 10px 0 0;">'
                    f'<div style="padding:0.5rem 0.75rem;font-size:0.65rem;font-weight:700;color:{_sb};text-transform:uppercase;letter-spacing:0.4px;">Stock · Sector</div>'
                    f'<div style="padding:0.5rem 0.6rem;font-size:0.65rem;font-weight:700;color:{_sb};text-transform:uppercase;">Fund</div>'
                    f'<div style="padding:0.5rem 0.4rem;font-size:0.65rem;font-weight:700;color:{_sb};text-align:center;text-transform:uppercase;">Trend</div>'
                    f'<div style="padding:0.5rem 0.6rem;font-size:0.65rem;font-weight:700;color:{_sb};text-transform:uppercase;">Alloc %</div>'
                    f'<div style="padding:0.5rem 0.4rem;font-size:0.65rem;font-weight:700;color:{_sb};text-align:right;text-transform:uppercase;">3M Δ</div>'
                    f'<div style="padding:0.5rem 0.4rem;font-size:0.65rem;font-weight:700;color:{_sb};text-align:right;text-transform:uppercase;">6M Δ</div>'
                    f'<div style="padding:0.5rem 0.4rem;font-size:0.65rem;font-weight:700;color:{_sb};text-align:right;text-transform:uppercase;">1Y Δ</div>'
                    f'</div>'
                )
                _rows_pf = ""
                _prev_stock = None
                for _pri, (_, _pr) in enumerate(per_fund.iterrows()):
                    _row_bg   = _cd if _pri % 2 == 0 else (f"{'rgba(255,255,255,0.02)' if _is_dark else '#F9FAFB'}")
                    _fc_pf    = PERF_COLORS[int(_pr["fund_idx"]) % len(PERF_COLORS)]
                    _sec_pf   = str(_pr.get("sector", "")).strip()
                    _sec_pf   = _sec_pf if _sec_pf and _sec_pf != "nan" else ""
                    _bw_pf    = min(100, float(_pr["allocation_percent"]) / _max_pf * 100)
                    _is_new   = _pr["stock_name"] != _prev_stock
                    _prev_stock = _pr["stock_name"]
                    _rows_pf += (
                        f'<div style="display:grid;grid-template-columns:{_col_w_pf};'
                        f'background:{_row_bg};border-bottom:1px solid {_bdr};align-items:center;">'
                        + (
                            f'<div style="padding:0.5rem 0.75rem;">'
                            f'<div style="font-size:0.82rem;font-weight:600;color:{_hd};">{_pr["stock_name"]}</div>'
                            + (f'<div style="font-size:0.62rem;color:{_sb};margin-top:1px;">{_sec_pf}</div>' if _sec_pf else '')
                            + f'</div>'
                            if _is_new else
                            f'<div style="padding:0.5rem 0.75rem;border-left:2px solid {_bdr};"></div>'
                        )
                        + f'<div style="padding:0.5rem 0.6rem;">'
                        f'<span style="background:{_fc_pf};color:#fff;border-radius:5px;'
                        f'padding:2px 7px;font-size:0.68rem;font-weight:700;">{_pr["fund_dn"]}</span></div>'
                        f'<div style="padding:0.5rem 0.4rem;text-align:center;">{_trend_chip(_pr["Trend"])}</div>'
                        f'<div style="padding:0.5rem 0.6rem;">'
                        f'<div style="display:flex;align-items:center;gap:5px;">'
                        f'<div style="flex:1;background:{_bdr};border-radius:3px;height:7px;overflow:hidden;">'
                        f'<div style="background:{_fc_pf};width:{_bw_pf:.1f}%;height:100%;border-radius:3px;opacity:0.85;"></div></div>'
                        f'<div style="font-size:0.72rem;font-weight:700;color:{_hd};min-width:34px;text-align:right;">{float(_pr["allocation_percent"]):.2f}%</div>'
                        f'</div></div>'
                        f'<div style="padding:0.5rem 0.4rem;text-align:right;font-size:0.75rem;">{_delta_cell(_pr["change_3m_percent"])}</div>'
                        f'<div style="padding:0.5rem 0.4rem;text-align:right;font-size:0.75rem;">{_delta_cell(_pr["change_6m_percent"])}</div>'
                        f'<div style="padding:0.5rem 0.4rem;text-align:right;font-size:0.75rem;">{_delta_cell(_pr["change_1y_percent"])}</div>'
                        f'</div>'
                    )
                st.markdown(
                    f'<div style="border:1px solid {_bdr};border-radius:12px;overflow:hidden;overflow-x:auto;">'
                    f'{_hdr_pf}{_rows_pf}</div>'
                    f'<div style="font-size:0.62rem;color:{_sb};margin-top:6px;text-align:right;">'
                    f'One row per fund per stock · Colored fund badge matches fund color throughout the page</div>',
                    unsafe_allow_html=True,
                )

    # ── Tab 6: Insights ──────────────────────────────────────────────────────
    with tab_ins:
        st.markdown('<div class="section-title">Key Insights</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-sub">Plain-English notes on your selected funds — '
            'grouped by topic, for learning only</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="font-size:0.82rem;color:{_bd};line-height:1.65;margin-bottom:1rem;'
            f'padding:0.75rem 1rem;background:{_al};border:1px solid {_bdr};border-radius:10px;">'
            f'Open each section below to read one topic at a time. '
            f'Sections with warnings start open. Numbers come from latest holdings data — '
            f'they describe how funds are built, not whether you should buy or sell.</div>',
            unsafe_allow_html=True,
        )

        insights = generate_insights(selected, similarity, holdings, sector_df, master)
        _render_categorized_insights(
            insights,
            hd=_hd, sb=_sb, bd=_bd, al=_al, bdr=_bdr,
            page_key="cmp",
            empty_msg="No clear patterns stood out for these funds. Try different picks or use the other tabs.",
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-title">Diversification Summary</div>', unsafe_allow_html=True)

        sel_sec = sector_df[sector_df["fund_name"].isin(selected)]
        n_secs  = sel_sec["sector"].nunique()
        fin_pct = sel_sec[sel_sec["sector"] == "FINANCIAL"]["allocation_percent"].mean()
        avg_s   = sel_sim["normalized_score"].mean() if not sel_sim.empty else 0

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Sectors Covered",       n_secs)
        with c2:
            st.metric("Avg Financial Exposure", f"{fin_pct:.1f}%" if not np.isnan(fin_pct) else "—")
        with c3:
            st.metric("Portfolio Overlap Score", f"{int(avg_s)}%")

        st.markdown("""
        <div class="disclaimer">
            Insights are generated from portfolio data for informational purposes only.
            They do not constitute investment advice, buy/sell recommendations, or financial planning guidance.
        </div>
        """, unsafe_allow_html=True)


# ── PAGE: PORTFOLIO UPLOAD ────────────────────────────────────────────────────

def page_portfolio_upload():
    import difflib
    t_name, t = _fl_get_theme()
    _fl_inject_css(t, t_name)
    _fl_render_navbar(t, t_name, "portfolio_upload")
    _fl_render_breadcrumb([("Home", "home"), ("Analyse Your Portfolio", None)])

    st.markdown(
        f'<h2 style="font-size:1.6rem;font-weight:800;color:{t["head"]};'
        f'margin-bottom:0.25rem;">Analyse Your MF Portfolio</h2>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='color:{t['body']};margin-top:0;margin-bottom:1.5rem;'>"
        "Upload your portfolio or build it manually — then get hidden exposure, overlap and concentration insights.</p>",
        unsafe_allow_html=True,
    )

    holdings  = load_holdings()
    all_funds = sorted(holdings["fund_name"].unique().tolist())
    fund_set  = set(all_funds)

    # ── Page mode: "view" shows saved portfolio, "entry" shows upload form ──
    _sv_meta   = _saved_portfolio_meta()
    _pmode     = st.session_state.get(
        "portfolio_page_mode",
        "view" if _sv_meta is not None else "entry",
    )

    # ════════════════════════════════════════════════════════════════════════
    # VIEW MODE — show saved portfolio with Analyse / Edit options
    # ════════════════════════════════════════════════════════════════════════
    if _pmode == "view" and _sv_meta is not None:
        _sv_n, _sv_ts = _sv_meta
        _sv_funds     = _saved_portfolio_funds()

        fund_chips = "".join(
            f'<span style="display:inline-block;background:{t["al"]};color:{t["a"]};'
            f'border:1px solid {t["a"]}44;border-radius:9999px;padding:5px 13px;'
            f'font-size:0.78rem;font-weight:600;margin:3px 5px 3px 0;">'
            f'{display_name(f)}</span>'
            for f in _sv_funds
        )

        st.markdown(
            f'<div style="background:{t["card"]};border:1px solid {t["bdr"]};'
            f'border-radius:16px;padding:1.5rem 1.75rem;margin-bottom:1.5rem;">'
            # Header
            f'<div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.5rem;">'
            f'<span style="font-size:1.15rem;">📋</span>'
            f'<span style="font-size:1rem;font-weight:800;color:{t["head"]};">Your Saved Portfolio</span>'
            f'</div>'
            f'<div style="font-size:0.75rem;color:{t["sub"]};margin-bottom:1rem;">'
            f'{_sv_n} fund{"s" if _sv_n != 1 else ""} &nbsp;·&nbsp; Last saved {_sv_ts}</div>'
            # Divider
            f'<div style="height:1px;background:{t["bdr"]};margin-bottom:1rem;"></div>'
            # Fund chips
            f'<div style="line-height:2.2;margin-bottom:1rem;">{fund_chips}</div>'
            f'<div style="height:1px;background:{t["bdr"]};margin-top:0.5rem;"></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        _ca, _cb = st.columns(2, gap="medium")
        with _ca:
            if st.button("▶  Analyse My Portfolio", type="primary",
                         use_container_width=True, key="sv_analyse"):
                _sv_df = _load_saved_portfolio()
                if _sv_df is not None:
                    st.session_state.portfolio_df = _sv_df
                st.session_state.page = "portfolio_xray"
                st.rerun()
        with _cb:
            if st.button("✏️  Edit / Change Portfolio",
                         use_container_width=True, key="sv_edit"):
                _sv_df_edit = _load_saved_portfolio()
                if _sv_df_edit is not None:
                    _prefill_manual_entry_state(_sv_df_edit)
                st.session_state["_portfolio_edit_type"] = "edit"
                st.session_state.portfolio_page_mode = "entry"
                st.rerun()

        st.markdown(
            f"<div style='text-align:center;font-size:0.7rem;color:{t['sub']};margin-top:1.25rem;'>"
            "💾 Saved locally on this device · Never uploaded to any server</div>",
            unsafe_allow_html=True,
        )
        return  # ← stop here; don't render the entry form

    # ════════════════════════════════════════════════════════════════════════
    # ENTRY MODE — upload or manually enter portfolio
    # ════════════════════════════════════════════════════════════════════════

    # Back link (always shown when a saved portfolio exists)
    if _sv_meta is not None:
        if st.button("← Back to saved portfolio", key="back_to_saved"):
            st.session_state.portfolio_page_mode = "view"
            st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)

    # Edit type: "edit" = pre-populated editing, "fresh" = blank start
    _edit_type = st.session_state.get("_portfolio_edit_type", "fresh")

    col_up, col_info = st.columns([3, 2], gap="large")

    with col_up:

        # ── When a saved portfolio exists, offer Edit vs Start-fresh choice ──
        if _sv_meta is not None:
            st.markdown(
                f'<div style="font-size:0.78rem;font-weight:700;color:{t["sub"]};'
                f'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:0.6rem;">'
                f'How do you want to proceed?</div>',
                unsafe_allow_html=True,
            )
            _ec1, _ec2 = st.columns(2, gap="small")
            with _ec1:
                if st.button(
                    "✏️  Edit existing portfolio",
                    type="primary" if _edit_type == "edit" else "secondary",
                    use_container_width=True, key="btn_edit_existing",
                ):
                    if _edit_type != "edit":
                        _sv_df_re = _load_saved_portfolio()
                        if _sv_df_re is not None:
                            _prefill_manual_entry_state(_sv_df_re)
                        st.session_state["_portfolio_edit_type"] = "edit"
                        st.rerun()
            with _ec2:
                if st.button(
                    "🔄  Clear & start fresh",
                    type="primary" if _edit_type == "fresh" else "secondary",
                    use_container_width=True, key="btn_fresh",
                ):
                    if _edit_type != "fresh":
                        _clear_manual_entry_state()
                        st.session_state["_portfolio_edit_type"] = "fresh"
                        st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)

        # ════════════════════════════════════════════════════════════════════
        # SUB-MODE A: Edit existing — manual form pre-populated from saved data
        # ════════════════════════════════════════════════════════════════════
        if _edit_type == "edit" and _sv_meta is not None:
            st.markdown(
                f'<div style="font-size:0.85rem;font-weight:600;color:{t["head"]};'
                f'margin-bottom:4px;">Your portfolio — add, remove or update funds and amounts</div>',
                unsafe_allow_html=True,
            )
            selected_manual = st.multiselect(
                "Funds",
                options=all_funds,
                key="manual_fund_select",
                label_visibility="collapsed",
                placeholder="Start typing to add a fund…",
            )
            if selected_manual:
                st.markdown("<br>", unsafe_allow_html=True)
                h1, h2, h3 = st.columns([4, 3, 2])
                h1.markdown(f"<div style='font-size:0.78rem;font-weight:700;color:{t['sub']};'>FUND</div>", unsafe_allow_html=True)
                h2.markdown(f"<div style='font-size:0.78rem;font-weight:700;color:{t['sub']};'>INVESTED AMOUNT (₹)</div>", unsafe_allow_html=True)
                h3.markdown(f"<div style='font-size:0.78rem;font-weight:700;color:{t['sub']};'>UNITS (optional)</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='height:1px;background:{t['bdr']};margin-bottom:4px;'></div>", unsafe_allow_html=True)

                manual_rows = []
                for fund in selected_manual:
                    safe_key = fund.replace(" ", "_").replace("/", "_")
                    c1, c2, c3 = st.columns([4, 3, 2])
                    with c1:
                        st.markdown(
                            f'<div style="font-size:0.82rem;color:{t["head"]};padding-top:6px;'
                            f'line-height:1.3;">{display_name(fund)}</div>',
                            unsafe_allow_html=True,
                        )
                    with c2:
                        amt = st.number_input(
                            "amt", min_value=0, step=1000,
                            key=f"m_amt_{safe_key}",
                            label_visibility="collapsed",
                        )
                    with c3:
                        units = st.number_input(
                            "units", min_value=0.0, step=1.0, format="%.2f",
                            key=f"m_units_{safe_key}",
                            label_visibility="collapsed",
                        )
                    manual_rows.append({"fund_name": fund, "invested_amount": amt, "units": units})

                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("💾  Save Changes", type="primary",
                             use_container_width=True, key="edit_save"):
                    _pf = pd.DataFrame(manual_rows)
                    st.session_state.portfolio_df = _pf
                    _save_portfolio(_pf)
                    st.session_state.portfolio_page_mode = "view"
                    st.session_state.pop("_portfolio_edit_type", None)
                    st.rerun()
            else:
                st.info("All funds removed. Add funds above or switch to 'Clear & start fresh' to upload a new CSV.")

        # ════════════════════════════════════════════════════════════════════
        # SUB-MODE B: Start fresh — normal upload / manual entry
        # ════════════════════════════════════════════════════════════════════
        else:
            # ── Entry mode selector ───────────────────────────────────────
            entry_mode = st.radio(
                "How would you like to add your portfolio?",
                ["📁  Upload CSV / XLSX", "✏️  Enter Manually"],
                horizontal=True,
                key="portfolio_entry_mode",
            )
            st.markdown("<br>", unsafe_allow_html=True)

            # ── Manual entry ──────────────────────────────────────────────
            if entry_mode == "✏️  Enter Manually":
                st.markdown(
                    f"<div style='font-size:0.85rem;font-weight:600;color:{t['head']};margin-bottom:4px;'>"
                    "Select your funds (search by name or AMC)</div>",
                    unsafe_allow_html=True,
                )
                selected_manual = st.multiselect(
                    "Funds",
                    options=all_funds,
                    key="manual_fund_select",
                    label_visibility="collapsed",
                    placeholder="Start typing a fund name…",
                )
                if selected_manual:
                    st.markdown("<br>", unsafe_allow_html=True)
                    h1, h2, h3 = st.columns([4, 3, 2])
                    h1.markdown(f"<div style='font-size:0.78rem;font-weight:700;color:{t['sub']};'>FUND</div>", unsafe_allow_html=True)
                    h2.markdown(f"<div style='font-size:0.78rem;font-weight:700;color:{t['sub']};'>INVESTED AMOUNT (₹)</div>", unsafe_allow_html=True)
                    h3.markdown(f"<div style='font-size:0.78rem;font-weight:700;color:{t['sub']};'>UNITS (optional)</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='height:1px;background:{t['bdr']};margin-bottom:4px;'></div>", unsafe_allow_html=True)

                    manual_rows = []
                    for fund in selected_manual:
                        safe_key = fund.replace(" ", "_").replace("/", "_")
                        c1, c2, c3 = st.columns([4, 3, 2])
                        with c1:
                            st.markdown(
                                f'<div style="font-size:0.82rem;color:{t["head"]};padding-top:6px;'
                                f'line-height:1.3;">{display_name(fund)}</div>',
                                unsafe_allow_html=True,
                            )
                        with c2:
                            amt = st.number_input(
                                "amt", min_value=0, step=1000,
                                key=f"m_amt_{safe_key}",
                                label_visibility="collapsed",
                            )
                        with c3:
                            units = st.number_input(
                                "units", min_value=0.0, step=1.0, format="%.2f",
                                key=f"m_units_{safe_key}",
                                label_visibility="collapsed",
                            )
                        manual_rows.append({"fund_name": fund, "invested_amount": amt, "units": units})

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("💾  Save Portfolio", type="primary",
                                 use_container_width=True, key="manual_go"):
                        _pf = pd.DataFrame(manual_rows)
                        st.session_state.portfolio_df = _pf
                        _save_portfolio(_pf)
                        st.session_state.portfolio_page_mode = "view"
                        st.session_state.pop("_portfolio_edit_type", None)
                        st.rerun()
                else:
                    st.info("Start typing above to search and add funds from our database.")

            # ── File upload ───────────────────────────────────────────────
            else:
                template = pd.DataFrame({
                    "fund_name":       ["HDFC Large Cap Fund", "ICICI Prudential Bluechip Fund"],
                    "invested_amount": [50000, 30000],
                    "units":           [100.50, 80.20],
                })
                st.download_button(
                    "⬇️  Download CSV Template",
                    template.to_csv(index=False),
                    file_name="portfolio_template.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
                st.markdown("<br>", unsafe_allow_html=True)

                uploaded = st.file_uploader(
                    "Drop your portfolio CSV or XLSX here",
                    type=["csv", "xlsx"],
                    help="Expected columns: fund_name, invested_amount (optional), units (optional)",
                )

                if uploaded:
                    try:
                        portfolio_df = (
                            pd.read_csv(uploaded)
                            if uploaded.name.endswith(".csv")
                            else pd.read_excel(uploaded)
                        )
                        fund_col = next(
                            (c for c in portfolio_df.columns if "fund" in c.lower()), None
                        )
                        if not fund_col:
                            st.error("Could not find a 'fund_name' column in your file.")
                        else:
                            portfolio_df[fund_col] = portfolio_df[fund_col].astype(str).str.strip()
                            user_funds = portfolio_df[fund_col].dropna().unique().tolist()
                            matched   = [f for f in user_funds if f in fund_set]
                            unmatched = [f for f in user_funds if f not in fund_set]

                            # ── Matched funds summary ─────────────────────────
                            st.markdown(
                                f"<div style='font-size:1rem;font-weight:700;color:{t['head']};"
                                f"margin-bottom:0.5rem;'>Validation Results</div>",
                                unsafe_allow_html=True,
                            )
                            if matched:
                                chips = "".join(
                                    f'<span style="display:inline-block;background:rgba(16,185,129,0.15);'
                                    f'color:#34D399;border-radius:6px;padding:3px 10px;'
                                    f'font-size:0.75rem;font-weight:600;margin:3px 4px 3px 0;">'
                                    f'✓ {f}</span>'
                                    for f in matched
                                )
                                st.markdown(
                                    f'<div style="margin-bottom:0.75rem;">{chips}</div>',
                                    unsafe_allow_html=True,
                                )

                            # ── Interactive correction for unmatched ──────────
                            corrections = {}
                            if unmatched:
                                st.markdown(
                                    f'<div style="background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);'
                                    f'border-radius:10px;padding:0.9rem 1rem;margin-bottom:0.75rem;">'
                                    f'<div style="font-weight:700;color:#FCA5A5;font-size:0.85rem;'
                                    f'margin-bottom:0.6rem;">❌ {len(unmatched)} fund(s) not recognised — '
                                    f'select the correct name or skip</div></div>',
                                    unsafe_allow_html=True,
                                )
                                for fund in unmatched:
                                    suggestions = difflib.get_close_matches(
                                        fund, all_funds, n=5, cutoff=0.35
                                    )
                                    ordered = suggestions + [f for f in all_funds if f not in suggestions]
                                    c_label, c_pick = st.columns([2, 3])
                                    with c_label:
                                        st.markdown(
                                            f'<div style="font-size:0.78rem;color:#DC2626;font-weight:600;'
                                            f'padding-top:8px;word-break:break-word;">✗ {fund}</div>',
                                            unsafe_allow_html=True,
                                        )
                                    with c_pick:
                                        skip_label = "— Skip (exclude from analysis) —"
                                        default_idx = 1 if suggestions else 0
                                        choice = st.selectbox(
                                            f"fix_{fund}",
                                            options=[skip_label] + ordered,
                                            index=default_idx,
                                            key=f"fix__{fund}",
                                            label_visibility="collapsed",
                                        )
                                        if choice != skip_label:
                                            corrections[fund] = choice
                                    st.markdown(
                                        "<div style='height:1px;background:rgba(239,68,68,0.2);margin:2px 0;'></div>",
                                        unsafe_allow_html=True,
                                    )

                            # ── Summary + save button ─────────────────────────
                            st.markdown("<br>", unsafe_allow_html=True)
                            n_corrected = len(corrections)
                            n_skipped   = len(unmatched) - n_corrected
                            total_ready = len(matched) + n_corrected

                            if total_ready > 0:
                                if unmatched:
                                    parts = []
                                    if matched:
                                        parts.append(f"{len(matched)} matched")
                                    if n_corrected:
                                        parts.append(f"{n_corrected} corrected")
                                    if n_skipped:
                                        parts.append(f"{n_skipped} skipped")
                                    st.caption(f"Ready to save: {' · '.join(parts)} → {total_ready} fund(s) will be used.")
                                if st.button("💾  Save Portfolio", type="primary",
                                             use_container_width=True, key="upload_go"):
                                    final_df = portfolio_df.copy()
                                    for orig, fixed in corrections.items():
                                        final_df.loc[final_df[fund_col] == orig, fund_col] = fixed
                                    skipped_funds = [f for f in unmatched if f not in corrections]
                                    final_df = final_df[~final_df[fund_col].isin(skipped_funds)]
                                    st.session_state.portfolio_df = final_df
                                    _save_portfolio(final_df)
                                    st.session_state.portfolio_page_mode = "view"
                                    st.session_state.pop("_portfolio_edit_type", None)
                                    st.rerun()
                            else:
                                st.error(
                                    "No funds are ready for analysis. "
                                    "Please correct the fund names above or use the CSV template as a reference."
                                )

                    except Exception as e:
                        st.error(f"Could not read file: {e}")

        st.markdown(
            f"<div style='text-align:center;font-size:0.72rem;color:{t['sub']};margin-top:1.5rem;'>"
            "💾 Portfolio is saved locally on this device for your next visit. "
            "Never uploaded to any server.</div>",
            unsafe_allow_html=True,
        )

    with col_info:
        st.markdown('<div class="section-title">What you\'ll discover</div>', unsafe_allow_html=True)
        for icon, title, desc in [
            ("🏦", "Hidden Stock Exposure",   "See exactly which stocks you indirectly own and in what proportions across all funds."),
            ("🔍", "Duplicate Fund Detection", "Identify funds with near-identical portfolios that add no real diversification."),
            ("📊", "Sector Concentration",    "Find if you're over-exposed to a single sector like BFSI or IT across your portfolio."),
            ("🔗", "Portfolio Overlap Score",  "A single score showing how truly diversified your combined fund portfolio is."),
            ("📈", "Allocation Trends",       "See how fund managers have been adjusting stock weights over 3M, 6M and 1Y periods."),
        ]:
            st.markdown(f"""
            <div style="display:flex;gap:0.75rem;margin-bottom:1rem;align-items:flex-start;">
                <div style="font-size:1.5rem;flex-shrink:0;">{icon}</div>
                <div>
                    <div style="font-weight:600;font-size:0.85rem;color:{t['head']};margin-bottom:2px;">{title}</div>
                    <div style="font-size:0.75rem;color:{t['body']};line-height:1.5;">{desc}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style="background:{t['al']};border:1px solid {t['bdr']};border-radius:10px;padding:1rem;margin-top:0.5rem;">
            <div style="font-size:0.8rem;font-weight:700;color:{t['a']};margin-bottom:0.5rem;">📌 Expected CSV Format</div>
            <div style="font-family:monospace;font-size:0.72rem;color:{t['body']};line-height:1.8;">
                fund_name, invested_amount, units<br>
                HDFC Large Cap Fund, 50000, 100.5<br>
                ICICI Prudential Bluechip Fund, 30000, 80.2
            </div>
        </div>
        """, unsafe_allow_html=True)



def _blended_exposure_table_html(
    df: pd.DataFrame,
    n_funds: int,
    *,
    hd: str, sb: str, bd: str, a: str, cd: str, bdr: str,
    col_amber: str, col_green: str, is_dark: bool,
    weight_col: str = "eff_alloc",
    weight_hdr: str = "Eff. Exp",
    high_thresh: float = 8.0,
) -> str:
    """HTML grid table matching Compare → Effective Portfolio design."""
    if df.empty or n_funds < 1:
        return ""

    max_wt = float(df[weight_col].max()) if weight_col in df.columns else 1.0
    grid = "display:grid;grid-template-columns:1fr 80px 80px 120px 100px;gap:0;"
    hdr = (
        f'<div style="{grid}background:{bdr};border-radius:10px 10px 0 0;padding:0.45rem 0.75rem;">'
        f'<div style="font-size:0.68rem;font-weight:700;color:{sb};text-transform:uppercase;letter-spacing:0.5px;">Stock · Sector</div>'
        f'<div style="font-size:0.68rem;font-weight:700;color:{sb};text-align:center;text-transform:uppercase;letter-spacing:0.5px;"># Funds</div>'
        f'<div style="font-size:0.68rem;font-weight:700;color:{sb};text-align:right;text-transform:uppercase;letter-spacing:0.5px;">Avg Alloc</div>'
        f'<div style="font-size:0.68rem;font-weight:700;color:{sb};text-align:center;text-transform:uppercase;letter-spacing:0.5px;">Coverage</div>'
        f'<div style="font-size:0.68rem;font-weight:700;color:{sb};text-align:right;text-transform:uppercase;letter-spacing:0.5px;">{weight_hdr}</div>'
        f"</div>"
    )

    rows = ""
    for _, er in df.iterrows():
        sec = str(er.get("sector", "")).strip()
        sec = sec if sec and sec.lower() != "nan" else ""
        wt = float(er[weight_col])
        bar_w = min(100, wt / max_wt * 100) if max_wt else 0
        is_high = wt >= high_thresh
        wt_col = col_amber if is_high else a
        cov_pct = int(int(er["funds_holding"]) / n_funds * 100)
        cov_col = col_green if cov_pct == 100 else (col_amber if cov_pct >= 50 else sb)
        row_bg = ("rgba(245,158,11,0.06)" if is_dark else "#FFFBEB") if is_high else cd
        high_badge = (
            f' <span style="font-size:0.6rem;color:{col_amber};font-weight:700;">▲ HIGH</span>'
            if is_high else ""
        )
        sec_line = (
            f'<div style="font-size:0.62rem;color:{sb};margin-top:1px;">{sec}</div>' if sec else ""
        )
        rows += (
            f'<div style="{grid}background:{row_bg};padding:0.5rem 0.75rem;'
            f'border-bottom:1px solid {bdr};align-items:center;">'
            f'<div>'
            f'<div style="font-size:0.82rem;font-weight:600;color:{hd};">{er["stock_name"]}{high_badge}</div>'
            f"{sec_line}"
            f"</div>"
            f'<div style="text-align:center;font-size:0.8rem;font-weight:700;color:{hd};">'
            f'{int(er["funds_holding"])}/{n_funds}</div>'
            f'<div style="text-align:right;font-size:0.8rem;font-weight:600;color:{bd};">'
            f'{float(er["avg_alloc"]):.2f}%</div>'
            f'<div style="padding:0 12px;">'
                f'<div style="background:{bdr};border-radius:3px;height:6px;overflow:hidden;">'
            f'<div style="background:{cov_col};width:{cov_pct}%;height:100%;border-radius:3px;"></div></div>'
            f'<div style="font-size:0.6rem;color:{cov_col};margin-top:2px;text-align:center;">'
            f"{cov_pct}% of funds</div></div>"
            f'<div style="text-align:right;">'
            f'<div style="font-size:0.88rem;font-weight:800;color:{wt_col};">{wt:.2f}%</div>'
            f'<div style="background:{bdr};border-radius:3px;height:4px;overflow:hidden;margin-top:3px;">'
            f'<div style="background:{wt_col};width:{bar_w:.1f}%;height:100%;border-radius:3px;"></div>'
            f"</div></div></div>"
        )

    return (
        hdr
        + f'<div style="border:1px solid {bdr};border-top:none;border-radius:0 0 10px 10px;overflow:hidden;'
        f'max-height:520px;overflow-y:auto;">'
        + rows
        + "</div>"
    )


def _sector_exposure_table_html(
    df: pd.DataFrame,
    *,
    hd: str, sb: str, bd: str, a: str, cd: str, bdr: str,
    col_amber: str, is_dark: bool,
    weight_hdr: str = "Eff. Exp",
    high_thresh: float = 25.0,
    scale_max: float | None = None,
    show_header: bool = True,
) -> str:
    """Sector-level effective exposure table (same visual language as holdings grid)."""
    if df.empty:
        return ""

    max_wt = (
        scale_max
        if scale_max is not None
        else (float(df["eff_alloc"].max()) if "eff_alloc" in df.columns else 1.0)
    )
    grid = "display:grid;grid-template-columns:1fr 90px 110px;gap:0;"
    hdr = (
        f'<div style="{grid}background:{bdr};border-radius:10px 10px 0 0;padding:0.45rem 0.75rem;">'
        f'<div style="font-size:0.68rem;font-weight:700;color:{sb};text-transform:uppercase;letter-spacing:0.5px;">Sector</div>'
        f'<div style="font-size:0.68rem;font-weight:700;color:{sb};text-align:center;text-transform:uppercase;letter-spacing:0.5px;"># Stocks</div>'
        f'<div style="font-size:0.68rem;font-weight:700;color:{sb};text-align:right;text-transform:uppercase;letter-spacing:0.5px;">{weight_hdr}</div>'
        f"</div>"
    ) if show_header else ""

    rows = ""
    for _, er in df.iterrows():
        wt = float(er["eff_alloc"])
        bar_w = min(100, wt / max_wt * 100) if max_wt else 0
        is_high = wt >= high_thresh
        wt_col = col_amber if is_high else a
        row_bg = ("rgba(245,158,11,0.06)" if is_dark else "#FFFBEB") if is_high else cd
        sec_lbl = str(er["sector"]).strip().title() if str(er["sector"]).strip() else "Other"
        high_badge = (
            f' <span style="font-size:0.6rem;color:{col_amber};font-weight:700;">▲ HIGH</span>'
            if is_high else ""
        )
        rows += (
            f'<div style="{grid}background:{row_bg};padding:0.5rem 0.75rem;'
            f'border-bottom:1px solid {bdr};align-items:center;">'
            f'<div style="font-size:0.82rem;font-weight:600;color:{hd};">{sec_lbl}{high_badge}</div>'
            f'<div style="text-align:center;font-size:0.8rem;font-weight:700;color:{hd};">'
            f'{int(er["n_stocks"])}</div>'
            f'<div style="text-align:right;">'
            f'<div style="font-size:0.88rem;font-weight:800;color:{wt_col};">{wt:.2f}%</div>'
            f'<div style="background:{bdr};border-radius:3px;height:4px;overflow:hidden;margin-top:3px;">'
            f'<div style="background:{wt_col};width:{bar_w:.1f}%;height:100%;border-radius:3px;"></div>'
            f"</div></div></div>"
        )

    _wrap_style = (
        f"border:1px solid {bdr};border-top:none;border-radius:0 0 10px 10px;overflow:hidden;"
        if show_header
        else f"border:1px solid {bdr};border-radius:10px;overflow:hidden;"
    )
    return hdr + f'<div style="{_wrap_style}">' + rows + "</div>"


def _render_fund_performance_tab(
    sel_master: pd.DataFrame,
    fund_order: list[str],
    *,
    hd: str, sb: str, bd: str, a: str, cd: str, bdr: str, al: str,
    col_amber: str, col_green: str, col_red: str,
    cf: dict, cg: str, ct: dict, is_dark: bool,
    explainer_key: str = "cmp",
    max_display: int = 8,
    amount_map: dict | None = None,
    matched_funds: list | None = None,
    has_amounts: bool = False,
) -> None:
    """Shared Fund Performance tab UI (Compare + Portfolio X-Ray)."""
    _hd, _sb, _bd, _a, _al, _cd, _bdr = hd, sb, bd, a, al, cd, bdr
    _col_amber, _col_green, _col_red = col_amber, col_green, col_red
    _is_dark, _cf, _cg = is_dark, cf, cg

    if sel_master.empty:
        st.info("Performance data not available for the selected funds.")
        return
    for _rc in ("std_dev", "sharpe_ratio", "alpha", "beta"):
        if _rc in sel_master.columns:
            sel_master[_rc] = pd.to_numeric(sel_master[_rc], errors="coerce")
    sel_master = sel_master.copy()
    sel_master["_order"] = sel_master["fund_name"].apply(
        lambda f: fund_order.index(f) if f in fund_order else 99)
    sel_master = sel_master.sort_values("_order").drop(columns=["_order"])
    _n_all = len(sel_master)
    if _n_all > max_display:
        st.info(
            f"Showing top {max_display} of {_n_all} funds by sort order — "
            "narrow filters to compare more side by side."
        )
        sel_master = sel_master.head(max_display)
    sel_master["short_name"] = sel_master["fund_name"].apply(display_name)
    PERF_COLORS = [a, "#F59E0B", "#06B6D4", "#10B981", "#EF4444"]

    # ── Fund Summary Cards ────────────────────────────────────────────
    _rank_col = "return_since_inception" if "return_since_inception" in sel_master.columns else (
                "return_3y" if "return_3y" in sel_master.columns else None)
    if _rank_col:
        sel_master["_rv"] = pd.to_numeric(sel_master[_rank_col], errors="coerce")
        sel_master["_rk"] = sel_master["_rv"].rank(ascending=False, method="min").fillna(99).astype(int)
    _rank_label = "Since Inception Return" if _rank_col == "return_since_inception" else "3Y Return"

    _cards_html = ""
    for _ci, (_, _crow) in enumerate(sel_master.iterrows()):
        _cc   = PERF_COLORS[_ci % len(PERF_COLORS)]
        _cfn  = display_name(_crow["fund_name"])
        _crk  = int(_crow.get("_rk", 99)) if _rank_col else None
        _crv  = _crow.get("_rv") if _rank_col else None
        _crs  = f"{float(_crv):+.1f}%" if _rank_col and pd.notna(_crv) else "—"
        _crc  = _col_green if _rank_col and pd.notna(_crv) and float(_crv) > 0 else _col_red
        _trophy = " 🏆" if _crk == 1 else ""
        # Inception date
        _cld = _crow.get("launch_date", "")
        _cld_str = ""
        if _cld and str(_cld) not in ("", "nan", "NaT", "None"):
            try:
                _cld_str = pd.to_datetime(str(_cld)).strftime("%d %b %Y")
            except Exception:
                pass
        _cards_html += (
            f'<div style="background:{_cd};border:1px solid {_bdr};border-top:3px solid {_cc};'
            f'border-radius:12px;padding:1rem 1.1rem;flex:1;min-width:170px;">'
            f'<div style="display:flex;align-items:center;gap:7px;margin-bottom:6px;">'
            f'<div style="width:9px;height:9px;border-radius:50%;background:{_cc};flex-shrink:0;"></div>'
            f'<div style="font-size:0.75rem;font-weight:600;color:{_bd};line-height:1.3;">{_cfn}</div></div>'
            f'<div style="font-size:0.6rem;color:{_sb};margin-bottom:6px;">{_rank_label}</div>'
            f'<div style="display:flex;align-items:flex-end;justify-content:space-between;">'
            f'<div style="font-size:1.55rem;font-weight:800;color:{_crc};line-height:1;">{_crs}</div>'
            f'<div style="font-size:0.85rem;font-weight:700;color:{_sb};">{"#"+str(_crk)+_trophy if _crk else ""}</div>'
            f'</div>'
            + (f'<div style="font-size:0.58rem;color:{_sb};margin-top:5px;">Since {_cld_str}</div>' if _cld_str else '')
            + f'</div>'
        )
    st.markdown(
        f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:1.5rem;">{_cards_html}</div>',
        unsafe_allow_html=True,
    )

    # ── Returns: 4 mini charts ────────────────────────────────────────
    _PERIODS = [
        ("return_1y",              "1 Year",         "Short term",   "📅"),
        ("return_3y",              "3 Year",         "Medium term",  "📅"),
        ("return_5y",              "5 Year",         "Long term",    "📅"),
        ("return_since_inception", "Since Inception","Overall",      "📅"),
    ]
    _avail_p = [(k, lbl, sub, ic) for k, lbl, sub, ic in _PERIODS if k in sel_master.columns]

    if _avail_p:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:0.5rem;">'
            f'<span style="font-size:1rem;">📈</span>'
            f'<span style="font-size:0.95rem;font-weight:700;color:{_hd};">Returns (%)</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        # Shared color legend — shown once above all charts
        _NA_COLOR = "rgba(156,163,175,0.35)" if _is_dark else "rgba(156,163,175,0.4)"
        _legend_items = ""
        for _lfi, (_, _lrow) in enumerate(sel_master.iterrows()):
            _lc  = PERF_COLORS[_lfi % len(PERF_COLORS)]
            _lfn = display_name(_lrow["fund_name"])
            _legend_items += (
                f'<div style="display:flex;align-items:center;gap:5px;">'
                f'<div style="width:10px;height:10px;border-radius:3px;background:{_lc};flex-shrink:0;"></div>'
                f'<span style="font-size:0.68rem;color:{_bd};white-space:nowrap;">{_lfn}</span>'
                f'</div>'
            )
        st.markdown(
            f'<div style="display:flex;gap:14px;flex-wrap:wrap;align-items:center;'
            f'margin-bottom:0.5rem;padding:0.5rem 0.75rem;background:{_cd};'
            f'border:1px solid {_bdr};border-radius:10px;">{_legend_items}</div>',
            unsafe_allow_html=True,
        )

        _pcols = st.columns(len(_avail_p))
        for _pi, (pk, plbl, psub, pic) in enumerate(_avail_p):
            with _pcols[_pi]:
                _pdata = []
                for _pfi, (_, _prow) in enumerate(sel_master.iterrows()):
                    _pv  = pd.to_numeric(_prow.get(pk), errors="coerce")
                    _has = pd.notna(_pv)
                    _pdata.append({
                        "fn":  display_name(_prow["fund_name"]),
                        "v":   float(_pv) if _has else 0.0,
                        "c":   PERF_COLORS[_pfi % len(PERF_COLORS)] if _has else _NA_COLOR,
                        "has": _has,
                    })
                _with_data = [d for d in _pdata if d["has"]]
                if _with_data:
                    _leader = max(_with_data, key=lambda x: x["v"])
                    st.markdown(
                        f'<div style="text-align:center;margin-bottom:2px;">'
                        f'<div style="font-size:0.78rem;font-weight:700;color:{_hd};">{pic} {plbl}</div>'
                        f'<div style="font-size:0.62rem;color:{_sb};">{psub} performance</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    _fig_m = go.Figure()
                    for _pd in _pdata:
                        _fig_m.add_trace(go.Bar(
                            x=[_pd["fn"]], y=[_pd["v"]],
                            marker_color=_pd["c"],
                            showlegend=False,
                            text=[f"{_pd['v']:.1f}%" if _pd["has"] else "N/A"],
                            textposition="outside" if _pd["has"] else "inside",
                        ))
                    _fig_m.update_traces(
                        textfont=dict(size=9, color=_bd, family="Inter, sans-serif"),
                        marker_line_width=0, opacity=0.92,
                    )
                    _fig_m.update_layout(**_dark_layout(
                        height=200, font=_cf,
                        margin=dict(t=28, b=5, l=5, r=5),
                        xaxis=_dark_xaxis(showticklabels=False, tickfont=dict(size=8, color=_bd)),
                        yaxis=_dark_yaxis(ticksuffix="%", tickfont=dict(size=8, color=_bd),
                                          gridcolor=_cg, zerolinecolor=_cg),
                    ))
                    st.plotly_chart(_fig_m, use_container_width=True, config={"displayModeBar": False})
                    # Callout: if not all funds have data, note which ones do
                    _missing = [d["fn"] for d in _pdata if not d["has"]]
                    if _missing:
                        _have_names = " & ".join(d["fn"] for d in _with_data)
                        _callout_line2 = f"{'has' if len(_with_data)==1 else 'have'} {plbl.lower()} track record"
                        _callout_fn    = _have_names
                    else:
                        _callout_fn    = _leader["fn"]
                        _callout_line2 = f"leads in {plbl.lower()} returns"
                    st.markdown(
                        f'<div style="background:{_al};border:1px solid {_bdr};border-radius:8px;'
                        f'padding:0.35rem 0.5rem;text-align:center;margin-top:-10px;margin-bottom:4px;">'
                        f'<div style="font-size:0.68rem;font-weight:700;color:{_leader["c"]};">{_callout_fn}</div>'
                        f'<div style="font-size:0.58rem;color:{_sb};">{_callout_line2}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div style="text-align:center;color:{_sb};font-size:0.75rem;padding:3rem 0;">'
                        f'No {plbl} data</div>',
                        unsafe_allow_html=True,
                    )

    # ── Performance Summary ───────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:0.75rem;">'
        f'<span style="font-size:1rem;">⭐</span>'
        f'<span style="font-size:0.95rem;font-weight:700;color:{_hd};">Performance Summary</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    def _best_in(col, higher_is_better=True):
        if col not in sel_master.columns: return None, None, None
        s = pd.to_numeric(sel_master[col], errors="coerce")
        if s.isna().all(): return None, None, None
        idx = s.idxmax() if higher_is_better else s.idxmin()
        row = sel_master.loc[idx]
        ci  = list(sel_master.index).index(idx) % len(PERF_COLORS)
        return display_name(row["fund_name"]), float(s[idx]), PERF_COLORS[ci]

    _bo_col  = "return_since_inception" if "return_since_inception" in sel_master.columns else "return_3y"
    _bo_fn,  _bo_v,  _bo_c  = _best_in(_bo_col)
    _mc_fn,  _mc_v,  _mc_c  = _best_in("std_dev", higher_is_better=False)
    _bra_fn, _bra_v, _bra_c = _best_in("sharpe_ratio")
    _hs_fn,  _hs_v,  _hs_c  = _best_in("return_1y")

    _sum_cards = [
        ("📈", "Best Overall Performer",   _bo_fn,  f"{_bo_v:+.1f}%"  if _bo_v  is not None else None, "Since Inception Return" if _bo_col=="return_since_inception" else "3Y Return", _bo_c),
        ("📊", "Most Consistent",           _mc_fn,  None,              "Lowest volatility",              _mc_c),
        ("🛡️", "Best Risk Adjusted",        _bra_fn, f"{_bra_v:.2f}"   if _bra_v is not None else None, "Highest Sharpe Ratio",   _bra_c),
        ("🚀", "Highest Short-Term Return", _hs_fn,  f"{_hs_v:+.1f}%"  if _hs_v  is not None else None, "1 Year Return",          _hs_c),
    ]

    _metric_cards_html = ""
    for ico, title, fn, val, sub, fc in _sum_cards:
        if fn:
            _metric_cards_html += (
                f'<div style="flex:3;min-width:150px;background:{_cd};border:1px solid {_bdr};'
                f'border-radius:12px;padding:0.9rem 1rem;">'
                f'<div style="font-size:1.1rem;margin-bottom:4px;">{ico}</div>'
                f'<div style="font-size:0.65rem;color:{_sb};font-weight:600;text-transform:uppercase;'
                f'letter-spacing:0.4px;margin-bottom:6px;">{title}</div>'
                f'<div style="font-size:0.88rem;font-weight:700;color:{fc};margin-bottom:2px;">{fn}</div>'
                + (f'<div style="font-size:1.2rem;font-weight:800;color:{fc};">{val}</div>' if val else "")
                + f'<div style="font-size:0.65rem;color:{_sb};margin-top:2px;">{sub}</div>'
                f'</div>'
            )
    _info_card_html = (
        f'<div style="flex:2;min-width:130px;background:{_al};border:1px solid {_bdr};'
        f'border-radius:12px;padding:0.9rem 1rem;">'
        f'<div style="font-size:0.68rem;font-weight:700;color:{_a};margin-bottom:8px;">ℹ️ How to read this?</div>'
        f'<div style="font-size:0.68rem;color:{_sb};line-height:1.6;">'
        f'Returns are annualised for periods &gt; 1 year.<br><br>'
        f'Past performance is not indicative of future results.<br><br>'
        f'<span style="color:{_a};font-weight:600;">Scroll down for deeper analysis ↓</span>'
        f'</div></div>'
    )
    st.markdown(
        f'<div style="display:flex;gap:10px;align-items:stretch;flex-wrap:wrap;">'
        f'{_metric_cards_html}{_info_card_html}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 2: Risk & Efficiency ────────────────────────────────
    risk_cols = {
        "std_dev":      "Std Dev (%)",
        "sharpe_ratio": "Sharpe Ratio",
        "alpha":        "Alpha (%)",
        "beta":         "Beta",
    }
    avail_risk = {k: v for k, v in risk_cols.items() if k in sel_master.columns}

    if avail_risk:
        _RISK_DEFS = [
            ("std_dev",      "Std Dev",    "%",  "Volatility of returns — below 13% = low, 13–18% = moderate, above 18% = high"),
            ("sharpe_ratio", "Sharpe",     "",   "Return per unit of risk — above 1.0 is good, above 1.5 is excellent"),
            ("alpha",        "Alpha",      "%",  "Excess return vs benchmark — positive means the manager beat the index"),
            ("beta",         "Beta",       "",   "Market sensitivity — below 1 = less volatile than market, above 1 = amplified swings"),
        ]
        _avail_defs = [(k, lbl, u, tip) for k, lbl, u, tip in _RISK_DEFS if k in sel_master.columns]

        def _risk_cell(col_key, raw):
            try:
                v = float(raw)
            except (TypeError, ValueError):
                return _cd, _sb, "—"
            _dk = _is_dark
            if col_key == "std_dev":
                if v < 13:  return ("rgba(16,185,129,0.18)" if _dk else "#D1FAE5"), _col_green, "Low ✓"
                if v < 18:  return ("rgba(245,158,11,0.18)" if _dk else "#FEF3C7"), _col_amber, "Moderate"
                return ("rgba(239,68,68,0.18)" if _dk else "#FEE2E2"), _col_red, "High ⚠"
            if col_key == "sharpe_ratio":
                if v >= 1.5: return ("rgba(16,185,129,0.18)" if _dk else "#D1FAE5"), _col_green, "Excellent ✓"
                if v >= 1.0: return ("rgba(16,185,129,0.10)" if _dk else "#ECFDF5"), _col_green, "Good ✓"
                if v >= 0.5: return ("rgba(245,158,11,0.18)" if _dk else "#FEF3C7"), _col_amber, "Fair"
                return ("rgba(239,68,68,0.18)" if _dk else "#FEE2E2"), _col_red, "Weak ⚠"
            if col_key == "alpha":
                if v > 2:   return ("rgba(16,185,129,0.18)" if _dk else "#D1FAE5"), _col_green, "Strong ✓"
                if v > 0:   return ("rgba(16,185,129,0.10)" if _dk else "#ECFDF5"), _col_green, "Positive ✓"
                if v > -2:  return ("rgba(245,158,11,0.15)" if _dk else "#FEF3C7"), _col_amber, "Slight lag"
                return ("rgba(239,68,68,0.18)" if _dk else "#FEE2E2"), _col_red, "Negative ⚠"
            if col_key == "beta":
                if v < 0.85: return ("rgba(16,185,129,0.18)" if _dk else "#D1FAE5"), _col_green, "Low β"
                if v <= 1.1: return _cd, _bd, "Market β"
                return ("rgba(245,158,11,0.18)" if _dk else "#FEF3C7"), _col_amber, "High β ⚠"
            return _cd, _sb, "—"

        _n_r = len(sel_master)
        _col_w_r = f"repeat({_n_r}, 1fr)"
        _chip_bg = "rgba(255,255,255,0.10)" if _is_dark else "rgba(0,0,0,0.07)"

        # Header row — fund names with PERF_COLORS
        _hdr_r = "".join(
            f'<div style="background:{PERF_COLORS[i % len(PERF_COLORS)]};'
            f'padding:0.65rem 0.5rem;text-align:center;'
            f'border-right:1px solid rgba(255,255,255,0.15);">'
            f'<div style="font-size:0.72rem;font-weight:700;color:#fff;'
            f'line-height:1.3;word-break:break-word;">{display_name(row["fund_name"])}</div>'
            f'</div>'
            for i, (_, row) in enumerate(sel_master.iterrows())
        )

        _rows_r = ""
        for col_key, lbl, unit, tip in _avail_defs:
            cells_r = ""
            for _, row in sel_master.iterrows():
                raw = row.get(col_key)
                try:
                    v = float(raw)
                    if col_key == "std_dev":   v_str = f"{v:.1f}{unit}"
                    elif col_key == "alpha":   v_str = f"{v:+.2f}{unit}"
                    else:                      v_str = f"{v:.2f}{unit}"
                except (TypeError, ValueError):
                    v_str = "—"
                cell_bg, cell_txt, chip = _risk_cell(col_key, raw)
                cells_r += (
                    f'<div style="padding:0.65rem 0.5rem;text-align:center;'
                    f'background:{cell_bg};border-right:1px solid {_bdr};border-bottom:1px solid {_bdr};">'
                    f'<div style="font-size:0.64rem;font-weight:700;color:{cell_txt};'
                    f'background:{_chip_bg};border-radius:4px;padding:1px 6px;'
                    f'display:inline-block;margin-bottom:4px;">{chip}</div>'
                    f'<div style="font-size:0.9rem;font-weight:800;color:{_hd};">{v_str}</div>'
                    f'</div>'
                )
            _rows_r += (
                f'<div style="display:grid;grid-template-columns:120px {_col_w_r};">'
                f'<div style="padding:0.6rem 0.75rem;border-right:1px solid {_bdr};'
                f'border-bottom:1px solid {_bdr};display:flex;flex-direction:column;justify-content:center;">'
                f'<div style="font-size:0.78rem;font-weight:700;color:{_bd};">{lbl}</div>'
                f'<div style="font-size:0.6rem;color:{_sb};margin-top:2px;line-height:1.3;">{tip}</div>'
                f'</div>{cells_r}</div>'
            )

        _risk_grid_html = (
            f'<div style="border:1px solid {_bdr};border-radius:12px;overflow:hidden;">'
            f'<div style="display:grid;grid-template-columns:120px {_col_w_r};">'
            f'<div style="background:{_bdr};padding:0.65rem 0.75rem;display:flex;align-items:center;">'
            f'<span style="font-size:0.7rem;font-weight:700;color:{_sb};'
            f'text-transform:uppercase;letter-spacing:0.5px;">Metric</span></div>'
            f'{_hdr_r}</div>'
            f'{_rows_r}'
            f'</div>'
        )
    else:
        _risk_grid_html = None

    with st.expander("📊 Risk & Efficiency — Sharpe, Alpha, Beta, Volatility", expanded=False):
        render_risk_metric_explainer(explainer_key)
        if _risk_grid_html:
            st.markdown(_risk_grid_html, unsafe_allow_html=True)

    # ── Section 3: Fund Profile ───────────────────────────────────────
    _CONS_LABEL = {4: "Very High", 3: "High", 2: "Moderate", 1: "Low", 0: "—"}
    _PROF_METRICS = [
        ("★ Rating",    "star_rating",       lambda v: "★ " * int(v) if pd.notna(v) else "—",                   "Star rating from value research / similar"),
        ("Expense",     "expense_ratio",     lambda v: f"{float(v):.2f}%" if pd.notna(v) else "—",              "Annual fee — lower is better"),
        ("AUM",         "aum_cr",            lambda v: (f"₹{float(v)/1000:.1f}K Cr" if float(v)>=10000 else f"₹{float(v):.0f} Cr") if pd.notna(v) else "—", "Assets under management"),
        ("Consistency", "consistency_score", lambda v: _CONS_LABEL.get(int(float(v)), "—") if pd.notna(v) else "—", "How often top-quartile across periods"),
        ("Cat. Rank",   "category_rank",     lambda v: f"#{int(float(v))}" if pd.notna(v) and float(v) != -1 else "—", "Rank within category"),
    ]
    n_funds = len(sel_master)
    col_w = f"repeat({n_funds}, 1fr)"
    hdr_cells = "".join(
        f'<div style="background:{PERF_COLORS[i%len(PERF_COLORS)]};'
        f'padding:0.65rem 0.5rem;text-align:center;border-right:1px solid rgba(255,255,255,0.15);">'
        f'<div style="font-size:0.72rem;font-weight:700;color:#fff;'
        f'line-height:1.3;word-break:break-word;">{display_name(row["fund_name"])}</div>'
        f'<div style="font-size:0.62rem;color:rgba(255,255,255,0.7);margin-top:2px;">{row.get("category","")}</div>'
        f'</div>'
        for i, (_, row) in enumerate(sel_master.iterrows())
    )
    metric_rows_html = ""
    for m_label, m_col, m_fmt, m_tip in _PROF_METRICS:
        if m_col not in sel_master.columns:
            continue
        cells = "".join(
            f'<div style="padding:0.55rem 0.5rem;text-align:center;'
            f'border-right:1px solid {_bdr};border-bottom:1px solid {_bdr};">'
            f'<span style="font-size:0.85rem;font-weight:700;color:{_hd};">'
            f'{m_fmt(row.get(m_col))}</span></div>'
            for _, row in sel_master.iterrows()
        )
        metric_rows_html += (
            f'<div style="display:grid;grid-template-columns:110px {col_w};">'
            f'<div style="padding:0.55rem 0.75rem;border-right:1px solid {_bdr};'
            f'border-bottom:1px solid {_bdr};display:flex;flex-direction:column;justify-content:center;">'
            f'<div style="font-size:0.75rem;font-weight:600;color:{_bd};">{m_label}</div>'
            f'<div style="font-size:0.6rem;color:{_sb};margin-top:1px;">{m_tip}</div></div>'
            f'{cells}</div>'
        )
    _prof_grid_html = (
        f'<div style="border:1px solid {_bdr};border-radius:12px;overflow:hidden;">'
        f'<div style="display:grid;grid-template-columns:110px {col_w};">'
        f'<div style="background:{_bdr};padding:0.65rem 0.75rem;display:flex;align-items:center;">'
        f'<span style="font-size:0.7rem;font-weight:700;color:{_sb};text-transform:uppercase;letter-spacing:0.5px;">Metric</span></div>'
        f'{hdr_cells}</div>'
        f'{metric_rows_html}'
        f'</div>'
    )
    with st.expander("🧾 Fund Profile — Rating, Expense, AUM, Consistency", expanded=False):
        if has_amounts and amount_map and matched_funds:
            _inv_hdr = "".join(
                f'<div style="background:{PERF_COLORS[i % len(PERF_COLORS)]};'
                f'padding:0.65rem 0.5rem;text-align:center;border-right:1px solid rgba(255,255,255,0.15);">'
                f'<div style="font-size:0.72rem;font-weight:700;color:#fff;line-height:1.3;">'
                f'{display_name(row["fund_name"])}</div></div>'
                for i, (_, row) in enumerate(sel_master.iterrows())
            )
            _inv_cells = "".join(
                f'<div style="padding:0.55rem 0.5rem;text-align:center;border-right:1px solid {_bdr};'
                f'border-bottom:1px solid {_bdr};">'
                f'<span style="font-size:0.85rem;font-weight:700;color:{_hd};">'
                f'₹{amount_map.get(row["fund_name"], 0):,.0f}</span></div>'
                for _, row in sel_master.iterrows()
            )
            st.markdown(
                f'<div style="border:1px solid {_bdr};border-radius:12px;overflow:hidden;margin-bottom:0.75rem;">'
                f'<div style="display:grid;grid-template-columns:110px {col_w};">'
                f'<div style="background:{_bdr};padding:0.65rem 0.75rem;">'
                f'<span style="font-size:0.7rem;font-weight:700;color:{_sb};">Metric</span></div>'
                f'{_inv_hdr}</div>'
                f'<div style="display:grid;grid-template-columns:110px {col_w};">'
                f'<div style="padding:0.55rem 0.75rem;border-right:1px solid {_bdr};'
                f'border-bottom:1px solid {_bdr};"><div style="font-size:0.75rem;font-weight:600;color:{_bd};">'
                f'Invested</div></div>{_inv_cells}</div></div>',
                unsafe_allow_html=True,
            )
        st.markdown(_prof_grid_html, unsafe_allow_html=True)

    # ── Section 4: Plain English Summary ────────────────────────────

    def _plain_bullets(frow):
        bullets = []  # (icon, bold_label, description)

        sd     = pd.to_numeric(frow.get("std_dev"),      errors="coerce")
        sharpe = pd.to_numeric(frow.get("sharpe_ratio"), errors="coerce")
        alpha  = pd.to_numeric(frow.get("alpha"),        errors="coerce")
        beta   = pd.to_numeric(frow.get("beta"),         errors="coerce")
        exp    = pd.to_numeric(frow.get("expense_ratio"),errors="coerce")
        r1y    = pd.to_numeric(frow.get("return_1y"),    errors="coerce")
        r3y    = pd.to_numeric(frow.get("return_3y"),    errors="coerce")
        r5y    = pd.to_numeric(frow.get("return_5y"),    errors="coerce")

        if pd.notna(sd):
            if sd < 13:
                bullets.append(("🟢", "Smooth ride",
                    f"Volatility is low at {sd:.1f}%. Returns stay relatively steady — "
                    f"less stressful to hold, especially during rough markets."))
            elif sd < 18:
                bullets.append(("🟡", "Moderate bumps",
                    f"Volatility of {sd:.1f}% means returns swing somewhat. Manageable "
                    f"for investors with a 3+ year horizon who won't panic at short-term dips."))
            else:
                bullets.append(("🔴", "Bumpy road",
                    f"High volatility at {sd:.1f}%. Expect sharp swings in value. Best suited "
                    f"for investors with a long time horizon who can hold through downturns."))

        if pd.notna(sharpe):
            if sharpe >= 1.5:
                bullets.append(("🟢", "Excellent risk-reward",
                    f"Sharpe ratio of {sharpe:.2f} — earning strong returns without taking "
                    f"excessive risk. Think of it as getting great value for the risk you're accepting."))
            elif sharpe >= 1.0:
                bullets.append(("🟢", "Good risk-reward",
                    f"Sharpe ratio of {sharpe:.2f} — the returns justify the risk taken. "
                    f"The fund is earning its keep and not just riding market luck."))
            elif sharpe >= 0.5:
                bullets.append(("🟡", "Fair risk-reward",
                    f"Sharpe ratio of {sharpe:.2f} — the fund delivers some return for its risk, "
                    f"but could be working harder. There may be better options for the same risk level."))
            else:
                bullets.append(("🔴", "Risk not rewarded",
                    f"Sharpe ratio of {sharpe:.2f} — taking meaningful risk but not earning "
                    f"enough return for it. Worth asking whether a safer fund would serve you better."))

        if pd.notna(alpha):
            if alpha > 2:
                bullets.append(("🟢", "Active management paying off",
                    f"Alpha of +{alpha:.2f}% — the fund manager is clearly beating the market "
                    f"index. You're paying higher fees for skill that's actually delivering results."))
            elif alpha > 0:
                bullets.append(("🟢", "Beating the benchmark",
                    f"Alpha of +{alpha:.2f}% — modestly ahead of a plain index fund. The manager "
                    f"is adding some value, though not dramatically."))
            elif alpha > -2:
                bullets.append(("🟡", "Roughly tracking the market",
                    f"Alpha of {alpha:+.2f}% — performance is close to a simple index fund. "
                    f"The active stock-picking isn't adding much beyond what the market gives for free."))
            else:
                bullets.append(("🔴", "Lagging the benchmark",
                    f"Alpha of {alpha:.2f}% — underperforming the market index. A low-cost index "
                    f"fund would have done better here. The active fees aren't being earned back."))

        if pd.notna(beta):
            if beta < 0.85:
                bullets.append(("🟢", "Less sensitive to market swings",
                    f"Beta of {beta:.2f} — when markets fall 10%, this fund typically falls only "
                    f"~{beta*10:.0f}%. It cushions downside, making it more defensive."))
            elif beta <= 1.1:
                bullets.append(("⚪", "Moves with the market",
                    f"Beta of {beta:.2f} — closely mirrors the Sensex/Nifty. Good market days "
                    f"are good days for this fund, and the same goes for bad days."))
            else:
                bullets.append(("🟡", "Amplifies market moves",
                    f"Beta of {beta:.2f} — this fund swings more than the overall market. "
                    f"Higher upside potential when markets rally, but steeper falls when they dip."))

        if pd.notna(exp):
            if exp < 0.5:
                bullets.append(("🟢", "Very low cost",
                    f"Just {exp:.2f}% per year — nearly free to hold. Low fees compound into "
                    f"a significant advantage over a 10–15 year period."))
            elif exp < 1.0:
                bullets.append(("🟢", "Low cost",
                    f"Annual fee of {exp:.2f}% — reasonable. Most of the returns stay in "
                    f"your hands rather than going to the fund house."))
            elif exp < 1.5:
                bullets.append(("🟡", "Moderate cost",
                    f"Fee of {exp:.2f}% per year — not cheap. The performance needs to justify "
                    f"this extra cost versus a similar but cheaper fund."))
            else:
                bullets.append(("🔴", "High fees",
                    f"Annual fee of {exp:.2f}% — on the expensive side. Over 15 years, high "
                    f"fees compound significantly against you. The alpha should more than offset it."))

        if pd.notna(r1y):
            parts = [f"1Y: {r1y:+.1f}%"]
            if pd.notna(r3y): parts.append(f"3Y: {r3y:+.1f}%")
            if pd.notna(r5y): parts.append(f"5Y: {r5y:+.1f}%")
            r_icon  = "🟢" if r1y >= 15 else ("🟡" if r1y >= 8 else "🔴")
            r_label = "Strong recent returns" if r1y >= 15 else ("Decent recent returns" if r1y >= 8 else "Weak recent returns")
            r_desc  = f"Historical track record — {' · '.join(parts)}."
            if pd.notna(r3y) and r1y < r3y - 5:
                r_desc += " Recent performance has dipped below the longer-term average — could be a short-term blip or an early sign of change."
            elif pd.notna(r3y) and r1y > r3y + 5:
                r_desc += " Recent returns are running well ahead of the long-term average — strong momentum, but don't bank on this pace continuing."
            bullets.append((r_icon, r_label, r_desc))

        return bullets

    _plain_all_html = ""
    for _fi, (_, _frow) in enumerate(sel_master.iterrows()):
        _fc   = PERF_COLORS[_fi % len(PERF_COLORS)]
        _fn   = display_name(_frow["fund_name"])
        _fcat = _frow.get("category", "")
        _fbullets = _plain_bullets(_frow)
        if not _fbullets:
            continue
        _bhtml = ""
        for _icon, _bold, _desc in _fbullets:
            _bhtml += (
                f'<div style="display:flex;gap:10px;padding:0.55rem 0;border-bottom:1px solid {_bdr};">'
                f'<div style="font-size:1rem;flex-shrink:0;width:22px;text-align:center;padding-top:1px;">{_icon}</div>'
                f'<div style="font-size:0.82rem;color:{_bd};line-height:1.6;">'
                f'<strong style="color:{_hd};">{_bold}:</strong> {_desc}'
                f'</div></div>'
            )
        _plain_all_html += (
            f'<div style="border:1px solid {_bdr};border-radius:12px;overflow:hidden;margin-bottom:1rem;">'
            f'<div style="background:{_fc};padding:0.65rem 1rem;display:flex;align-items:center;gap:10px;">'
            f'<div style="font-size:0.88rem;font-weight:700;color:#fff;">{_fn}</div>'
            f'<div style="font-size:0.72rem;color:rgba(255,255,255,0.72);">{_fcat}</div>'
            f'</div>'
            f'<div style="padding:0.15rem 1rem 0.6rem;">{_bhtml}</div>'
            f'</div>'
        )
    if _plain_all_html:
        with st.expander("💬 Plain English Summary — what these numbers mean for you", expanded=False):
            st.markdown(_plain_all_html, unsafe_allow_html=True)


# ── PAGE: PORTFOLIO X-RAY ─────────────────────────────────────────────────────

def page_portfolio_xray():
    t_name, t = _fl_get_theme()
    _fl_inject_css(t, t_name)
    _fl_render_navbar(t, t_name, "portfolio_upload")
    _fl_render_breadcrumb([("Home", "home"), ("Analyse Your Portfolio", "portfolio_upload"), ("Portfolio X-Ray", None)])
    _hd = t["head"]; _bd = t["body"]; _sb = t["sub"]
    _cd = t["card"]; _bdr = t["bdr"]; _a = t["a"]; _al = t["al"]
    _is_dark = t_name == "dark_premium"
    _a50       = _a + "80"
    _col_green = "#34D399" if _is_dark else "#059669"
    _col_amber = "#FDE68A" if _is_dark else "#D97706"
    _col_red   = "#FCA5A5" if _is_dark else "#DC2626"
    _cf = dict(family="Inter, sans-serif", color=_bd, size=12)
    _cg = _bdr
    _ct = dict(color=_sb, size=11)

    portfolio_df = st.session_state.get("portfolio_df", pd.DataFrame())
    if portfolio_df.empty:
        _sv = _load_saved_portfolio()
        if _sv is not None:
            st.session_state.portfolio_df = _sv
            portfolio_df = _sv
        else:
            st.warning("No portfolio data. Please upload your portfolio first.")
            t_name_up = st.session_state.get("fl_theme", "warm_light")
            if st.button("Go to upload page"):
                st.session_state.page = "portfolio_upload"
                st.rerun()
            return

    holdings   = load_holdings()
    similarity = load_similarity()
    master     = load_master()
    sector_df  = get_sector_breakdown(holdings)

    fund_col = next((c for c in portfolio_df.columns if "fund" in c.lower()), None)
    if not fund_col:
        st.error("Could not find a 'fund_name' column in your file.")
        return

    user_funds    = portfolio_df[fund_col].dropna().unique().tolist()
    matched_funds = [f for f in user_funds if f in holdings["fund_name"].values]
    unmatched     = [f for f in user_funds if f not in matched_funds]

    if unmatched:
        st.info(f"⚠️  Not found in our database (excluded): {', '.join(unmatched)}")
    if not matched_funds:
        st.error("None of your funds matched our database. Please check fund names match those on ETMoney.")
        return

    # ── Invested amount weighting ─────────────────────────────────────────────
    has_amounts  = "invested_amount" in portfolio_df.columns
    amount_map   = {}
    if has_amounts:
        for _, row in portfolio_df.iterrows():
            fund = row.get(fund_col)
            amt  = pd.to_numeric(row.get("invested_amount", None), errors="coerce")
            if fund in matched_funds and pd.notna(amt) and amt > 0:
                amount_map[fund] = float(amt)
    if not amount_map:
        amount_map = {f: 1.0 for f in matched_funds}
    total_invested = sum(amount_map.values())
    weight_map     = {f: amount_map.get(f, 0) / total_invested for f in matched_funds}

    sel_h      = holdings[holdings["fund_name"].isin(matched_funds)].copy()
    sel_sim    = similarity[similarity["fund_a"].isin(matched_funds) & similarity["fund_b"].isin(matched_funds)]
    sel_master = master[master["fund_name"].isin(matched_funds)].copy()
    if not sel_master.empty:
        sel_master["_order"] = sel_master["fund_name"].apply(lambda f: matched_funds.index(f) if f in matched_funds else 99)
        sel_master = sel_master.sort_values("_order").drop(columns=["_order"])
        sel_master["short_name"] = sel_master["fund_name"].apply(display_name)

    # ── Key portfolio metrics ─────────────────────────────────────────────────
    n_unique = sel_h["stock_name"].nunique()
    avg_sim  = sel_sim["normalized_score"].mean() if not sel_sim.empty else 0
    n_secs   = sel_h["sector"].nunique()

    if avg_sim >= 60:
        redun_label, redun_color = "High Redundancy",    "#DC2626"
    elif avg_sim >= 35:
        redun_label, redun_color = "Moderate Overlap",   "#D97706"
    else:
        redun_label, redun_color = "Well Diversified",   "#059669"

    wtd_er = None
    if not sel_master.empty and "expense_ratio" in sel_master.columns:
        er_df = sel_master.dropna(subset=["expense_ratio"]).copy()
        er_df["expense_ratio"] = pd.to_numeric(er_df["expense_ratio"], errors="coerce")
        er_df = er_df.dropna(subset=["expense_ratio"])
        if not er_df.empty:
            wts   = [weight_map.get(f, 0) for f in er_df["fund_name"]]
            wt_sum = sum(wts)
            wtd_er = sum(er * wt for er, wt in zip(er_df["expense_ratio"], wts)) / wt_sum if wt_sum else None

    # ── Summary header ────────────────────────────────────────────────────────
    st.markdown(
        f"<div style='font-size:1.55rem;font-weight:800;color:{_hd};letter-spacing:-0.02em;margin-bottom:0.15rem;'>"
        f"Analyse Your Portfolio</div>"
        f"<p style='color:{_bd};margin-top:0;margin-bottom:1.5rem;font-size:0.88rem;'>"
        f"{len(matched_funds)} funds analysed · {n_unique} unique stocks · {n_secs} sectors</p>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    inv_val  = f"₹{total_invested/100000:.1f}L" if has_amounts and total_invested > 0 else "—"
    er_val   = f"{wtd_er:.2f}%" if wtd_er else "—"
    for col, val, label, sub in [
        (c1, str(len(matched_funds)),     "Funds",              "in your portfolio"),
        (c2, str(n_unique),               "Unique Stocks",      "across all funds"),
        (c3, f"{avg_sim:.0f}%",           "Avg Overlap",        f'<span style="color:{redun_color};font-weight:700;">{redun_label}</span>'),
        (c4, inv_val,                     "Total Invested",     "from your upload" if has_amounts else "upload amounts for this"),
        (c5, er_val,                      "Wtd. Expense Ratio", "annual fee drag"),
    ]:
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{val}</div>
                <div class="metric-label">{label}</div>
                <div class="metric-sub">{sub}</div>
            </div>""", unsafe_allow_html=True)

    if has_amounts and total_invested > 0 and wtd_er:
        fee_drag = total_invested * wtd_er / 100
        st.caption(f"💸 At {wtd_er:.2f}% weighted expense ratio, you're paying approx **₹{fee_drag:,.0f}/year** in fund management fees.")

    # ── Return hint: shown after coming back from "Compare in detail" ────────
    if st.session_state.pop("_pf_xray_return_hint", False):
        st.markdown(
            f'<div style="background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.35);'
            f'border-radius:10px;padding:0.7rem 1rem;margin-bottom:0.75rem;display:flex;'
            f'align-items:center;gap:0.6rem;">'
            f'<span style="font-size:1.1rem;">🔗</span>'
            f'<span style="font-size:0.85rem;color:{_hd};">Comparison complete — click the '
            f'<strong>Fund Overlap</strong> tab to continue your analysis. '
            f'Your selections and filters are preserved.</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    def _norm_sector_label_sc(s) -> str:
        t = str(s).strip() if pd.notna(s) else ""
        if not t or t.lower() in ("nan", "none"):
            return "Other"
        return t.title()

    sel_sector = sector_df[sector_df["fund_name"].isin(matched_funds)].copy()
    sel_sector["sector"] = sel_sector["sector"].map(_norm_sector_label_sc)

    tab_ov, tab_ol, tab_exp, tab_perf, tab_sec, tab_ins = st.tabs([
        "📊 Overview",
        "🔗 Fund Overlap",
        "🔍 What You Actually Own",
        "📉 Fund Performance",
        "🏗️ Sector & Cap Size",
        "💡 Insights",
    ])

    # ── Tab 0: Overview ───────────────────────────────────────────────────────
    with tab_ov:
        FUND_COLORS = ["#6C3CE1", "#F97316", "#0891B2", "#16A34A", "#E11D48"]

        score_lk  = {}
        common_lk = {}
        for _, row in sel_sim.iterrows():
            for key in [(row["fund_a"], row["fund_b"]), (row["fund_b"], row["fund_a"])]:
                score_lk[key]  = row["normalized_score"]
                common_lk[key] = int(row["common_stocks"])

        cat_lk  = dict(zip(master["fund_name"], master["category"])) if not master.empty else {}
        cats    = [cat_lk.get(f, "") for f in matched_funds]
        n_sel   = len(matched_funds)

        def _xr_mx_name(name):
            n = short_name(name)
            return (n[:16] + "…") if len(n) > 16 else n

        m_names = [_xr_mx_name(f) for f in matched_funds]

        # ── Shared heatmap helpers (used by both compact & full-screen views) ──
        # Continuous green gradient — darker green = more overlap (matches screenshot)
        # Light themes: pale mint → forest green
        # Dark theme  : near-black → bright emerald (avoids "dark on dark" problem)
        _HM_GREEN = {
            "warm_light":   [[0,"#F0FFF4"],[0.25,"#BBF7D0"],[0.55,"#22C55E"],[0.80,"#15803D"],[1,"#14532D"]],
            "dark_premium": [[0,"#0D1F16"],[0.25,"#14532D"],[0.55,"#16A34A"],[0.80,"#22C55E"],[1,"#4ADE80"]],
            "ocean_blue":   [[0,"#F0FFF4"],[0.25,"#BBF7D0"],[0.55,"#22C55E"],[0.80,"#15803D"],[1,"#14532D"]],
            "forest_green": [[0,"#F0FFF4"],[0.25,"#BBF7D0"],[0.55,"#22C55E"],[0.80,"#15803D"],[1,"#14532D"]],
            "soft_rose":    [[0,"#F0FFF4"],[0.25,"#BBF7D0"],[0.55,"#22C55E"],[0.80,"#15803D"],[1,"#14532D"]],
        }
        _hm_colorscale = _HM_GREEN.get(t_name, _HM_GREEN["warm_light"])
        # Text colour that contrasts on the gradient (dark for light themes, light for dark)
        _hm_txt_color = "#064E3B" if not _is_dark else "#ECFDF5"

        def _hm_lbl(sc):
            if sc >= 60: return "Very High"
            if sc >= 45: return "High"
            if sc >= 30: return "Moderate"
            if sc >= 15: return "Good"
            return "Excellent"

        # Pre-build heatmap data so both compact & expanded views share it
        _hm_z, _hm_hover, _hm_annot_c, _hm_annot_f = [], [], [], []
        if n_sel > 5:
            for _fa in matched_funds:
                _rz, _rh, _rc, _rf = [], [], [], []
                for _fb in matched_funds:
                    if _fa == _fb:
                        _rz.append(None); _rh.append(""); _rc.append(""); _rf.append("")
                    else:
                        _sc = score_lk.get((_fa, _fb), 0)
                        _co = common_lk.get((_fa, _fb), 0)
                        _lb = _hm_lbl(_sc)
                        _rz.append(_sc)
                        _rh.append(f"<b>{_sc:.0f}%</b> overlap · {_co} shared stocks<br>{_lb}")
                        _rc.append(f"{_sc:.0f}%")
                        _rf.append(f"{_sc:.0f}%<br>{_lb}")
                _hm_z.append(_rz); _hm_hover.append(_rh)
                _hm_annot_c.append(_rc); _hm_annot_f.append(_rf)

        col_matrix, col_top = st.columns([3, 2], gap="large")

        with col_matrix:
            if n_sel <= 5:
                # ── HTML matrix (compact, colour-coded) ──────────────────────
                display_mode = st.radio(
                    "Show numbers as:",
                    ["% overlap", "plain words", "both"],
                    index=2, horizontal=True, key="xray_ov_display",
                )
                cell_h = 86 if n_sel <= 3 else 74 if n_sel == 4 else 64
                pct_fs = 20 if n_sel <= 3 else 17 if n_sel == 4 else 14
                hdr_fs = 11 if n_sel <= 3 else 10
                lbl_fs = 9  if n_sel <= 3 else 8
                pad    = 3  if n_sel <= 3 else 2

                def _xr_cell_cfg(score, common):
                    if common == 0 and score == 0:
                        return {"bg": _bdr, "txt": _sb, "label": "No data",
                                "bdg_bg": _bdr, "bdg_txt": _sb}
                    if score >= 60:
                        if _is_dark:
                            return {"bg": "rgba(239,68,68,0.30)", "txt": "#FCA5A5",
                                    "label": "Very High",
                                    "bdg_bg": "rgba(239,68,68,0.20)", "bdg_txt": "#FCA5A5"}
                        return {"bg": "#FEE2E2", "txt": "#991B1B",
                                "label": "Very High",
                                "bdg_bg": "#FECACA", "bdg_txt": "#991B1B"}
                    if score >= 45:
                        if _is_dark:
                            return {"bg": "rgba(245,158,11,0.30)", "txt": "#FDE68A",
                                    "label": "High",
                                    "bdg_bg": "rgba(245,158,11,0.20)", "bdg_txt": "#FDE68A"}
                        return {"bg": "#FEF9C3", "txt": "#854D0E",
                                "label": "High",
                                "bdg_bg": "#FDE68A", "bdg_txt": "#854D0E"}
                    if score >= 30:
                        return {"bg": _al, "txt": _a,
                                "label": "Moderate",
                                "bdg_bg": _al, "bdg_txt": _a}
                    if score >= 15:
                        if _is_dark:
                            return {"bg": "rgba(16,185,129,0.25)", "txt": "#6EE7B7",
                                    "label": "Good",
                                    "bdg_bg": "rgba(16,185,129,0.20)", "bdg_txt": "#6EE7B7"}
                        return {"bg": "#D1FAE5", "txt": "#065F46",
                                "label": "Good",
                                "bdg_bg": "#A7F3D0", "bdg_txt": "#065F46"}
                    if _is_dark:
                        return {"bg": "rgba(16,185,129,0.15)", "txt": "#34D399",
                                "label": "Excellent",
                                "bdg_bg": "rgba(16,185,129,0.10)", "bdg_txt": "#34D399"}
                    return {"bg": "#ECFDF5", "txt": "#064E3B",
                            "label": "Excellent",
                            "bdg_bg": "#D1FAE5", "bdg_txt": "#064E3B"}

                hdr = '<td style="width:18%;"></td>'
                for mn, cat in zip(m_names, cats):
                    hdr += (
                        f'<td style="text-align:center;padding:0 2px {pad*3}px;vertical-align:bottom;">'
                        f'<div style="font-weight:700;font-size:{hdr_fs}px;color:{_hd};'
                        f'line-height:1.3;word-break:break-word;">{mn}</div>'
                        f'<div style="font-size:{lbl_fs}px;color:{_sb};">{cat}</div></td>'
                    )
                tbl_rows = ""
                for fa, mn, fa_cat in zip(matched_funds, m_names, cats):
                    cells = ""
                    for fb in matched_funds:
                        if fa == fb:
                            cells += (
                                f'<td style="padding:{pad}px;"><div style="background:{_al};'
                                f'border-radius:8px;width:100%;height:{cell_h}px;display:flex;'
                                f'align-items:center;justify-content:center;">'
                                f'<span style="font-size:{lbl_fs}px;color:{_sb};font-style:italic;">—</span>'
                                f'</div></td>'
                            )
                        else:
                            sc  = score_lk.get((fa, fb), 0)
                            co  = common_lk.get((fa, fb), 0)
                            cfg = _xr_cell_cfg(sc, co)
                            pct = (
                                f'<div style="font-size:{pct_fs}px;font-weight:800;'
                                f'color:{cfg["txt"]};line-height:1;">{sc:.0f}%</div>'
                                if display_mode in ("% overlap", "both") else ""
                            )
                            lbl_badge = (
                                f'<div style="background:{cfg["bdg_bg"]};color:{cfg["bdg_txt"]};'
                                f'font-size:{lbl_fs}px;font-weight:700;border-radius:9999px;'
                                f'padding:2px 5px;margin-top:4px;white-space:nowrap;text-align:center;">'
                                f'{cfg["label"]}</div>'
                                if display_mode in ("plain words", "both") else ""
                            )
                            cells += (
                                f'<td style="padding:{pad}px;"><div style="background:{cfg["bg"]};'
                                f'border-radius:8px;width:100%;height:{cell_h}px;display:flex;'
                                f'flex-direction:column;align-items:center;justify-content:center;'
                                f'padding:0 4px;">{pct}{lbl_badge}</div></td>'
                            )
                    tbl_rows += (
                        f'<tr><td style="padding:{pad}px 8px {pad}px 0;text-align:right;vertical-align:middle;">'
                        f'<div style="font-weight:700;font-size:{hdr_fs}px;color:{_hd};'
                        f'word-break:break-word;line-height:1.3;">{mn}</div>'
                        f'<div style="font-size:{lbl_fs}px;color:{_sb};">{fa_cat}</div>'
                        f'</td>{cells}</tr>'
                    )
                st.markdown(
                    f'<table style="border-collapse:separate;border-spacing:0;width:100%;table-layout:fixed;">'
                    f'<thead><tr>{hdr}</tr></thead><tbody>{tbl_rows}</tbody></table>',
                    unsafe_allow_html=True,
                )
                _lgd_s = "#F0FFF4" if not _is_dark else "#0D1F16"
                _lgd_e = "#14532D" if not _is_dark else "#4ADE80"
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;margin-top:14px;'
                    f'font-size:11px;color:{_sb};flex-wrap:wrap;">'
                    f'<span>Less overlap</span>'
                    f'<div style="width:120px;height:10px;border-radius:3px;'
                    f'background:linear-gradient(to right,{_lgd_s},{_lgd_e});'
                    f'border:1px solid {_bdr};"></div>'
                    f'<span>More overlap &nbsp;·&nbsp; Higher = more redundant = less diversification</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            else:
                # ── Compact Plotly heatmap (>5 funds) ────────────────────────
                import plotly.graph_objects as go_mod
                cell_sz = max(55, min(90, 560 // n_sel))
                txt_sz  = max(10, 16 - n_sel)
                fig_hm = go_mod.Figure(go_mod.Heatmap(
                    z=_hm_z,
                    x=m_names, y=m_names,
                    text=_hm_annot_c,
                    hovertext=_hm_hover,
                    hovertemplate="%{hovertext}<extra></extra>",
                    texttemplate="%{text}",
                    textfont=dict(size=txt_sz, color=_hm_txt_color,
                                  family="Inter, sans-serif"),
                    colorscale=_hm_colorscale,
                    zmin=0, zmax=100,
                    showscale=True,
                    colorbar=dict(
                        title=dict(text="Overlap %", font=dict(color=_sb, size=11)),
                        thickness=12, len=0.9,
                        tickvals=[0, 25, 50, 75, 100],
                        ticktext=["0%", "25%", "50%", "75%", "100%"],
                        tickfont=dict(color=_sb, size=9),
                    ),
                    xgap=4, ygap=4,
                ))
                fig_hm.update_layout(**_dark_layout(
                    height=max(420, cell_sz * n_sel + 90),
                    font=_cf,
                    margin=dict(l=10, r=90, t=50, b=10),
                    xaxis=dict(side="top", tickangle=-30,
                               tickfont=dict(size=max(10, 13 - n_sel), color=_hd), title=""),
                    yaxis=dict(autorange="reversed",
                               tickfont=dict(size=max(10, 13 - n_sel), color=_hd), title=""),
                ))
                st.plotly_chart(
                    fig_hm, use_container_width=True,
                    config={"displayModeBar": "hover", "displaylogo": False,
                            "modeBarButtonsToRemove": ["pan2d", "select2d", "lasso2d",
                                                       "resetScale2d", "zoomIn2d", "zoomOut2d"]},
                )
                st.markdown(
                    f'<div style="font-size:0.7rem;color:{_sb};margin-top:4px;">'
                    f'Darker green = more overlap &nbsp;·&nbsp; hover any cell for details'
                    f' &nbsp;·&nbsp; <span style="color:{_a};">⛶ Expand for full-screen view below ↓</span></div>',
                    unsafe_allow_html=True,
                )

        with col_top:
            st.markdown('<div class="section-title">Top Common Holdings</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="section-sub">Stocks held across the most funds in your portfolio, ranked by avg allocation</div>',
                unsafe_allow_html=True,
            )

            top_com = (
                sel_h.groupby("stock_name")
                .agg(
                    funds_holding=("fund_name",          "nunique"),
                    avg_alloc    =("allocation_percent",  "mean"),
                    sector       =("sector",              "first"),
                )
                .reset_index()
                .sort_values(["funds_holding", "avg_alloc"], ascending=[False, False])
                .head(12)
            )
            top_com["stock_name"] = top_com["stock_name"].str.strip()
            top_com["avg_alloc"]  = top_com["avg_alloc"].round(2)

            stock_to_funds_xr = (
                sel_h.groupby("stock_name")["fund_name"]
                .apply(set)
                .to_dict()
            )

            max_alloc_top  = float(top_com["avg_alloc"].max()) if not top_com.empty else 1.0
            # Cap dots at 5 funds; for larger portfolios show count badge instead
            DOT_FUNDS      = matched_funds[:5]
            extra_funds    = n_sel - len(DOT_FUNDS)

            def _xr_ch_row(stock, alloc, sector_val):
                bar_w    = min(100.0, alloc / max_alloc_top * 100) if max_alloc_top else 0
                sec_str  = str(sector_val).strip() if pd.notna(sector_val) and str(sector_val).strip() not in ("", "nan") else ""
                sec_tag  = (
                    f'<span style="font-size:0.58rem;background:{_al};color:{_sb};'
                    f'border-radius:4px;padding:1px 5px;margin-left:4px;">'
                    + sec_str.title() + '</span>'
                ) if sec_str else ""
                holding_funds = stock_to_funds_xr.get(stock, set())
                dots = ""
                for idx, fund_name in enumerate(DOT_FUNDS):
                    bg = FUND_COLORS[idx] if fund_name in holding_funds else _bdr
                    dots += (
                        '<span style="display:inline-block;width:9px;height:9px;'
                        'border-radius:50%;background:' + bg + ';margin-right:2px;"></span>'
                    )
                # For extra funds, show how many of them also hold this stock
                if extra_funds > 0:
                    extra_holding = sum(
                        1 for f in matched_funds[5:] if f in holding_funds
                    )
                    if extra_holding > 0:
                        dots += (
                            f'<span style="font-size:0.6rem;color:{_sb};margin-left:1px;">'
                            f'+{extra_holding}</span>'
                        )
                return (
                    f'<div style="display:flex;align-items:center;padding:8px 0;'
                    f'border-bottom:1px solid {_bdr};gap:10px;">'
                    f'<div style="flex:1;min-width:0;">'
                    f'<div style="font-size:0.78rem;font-weight:700;color:{_hd};'
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                    + stock + sec_tag +
                    f'</div>'
                    f'<div style="background:{_al};border-radius:3px;height:5px;'
                    f'margin-top:5px;overflow:hidden;">'
                    f'<div style="background:{_a};width:{bar_w:.1f}%;'
                    f'height:100%;border-radius:3px;"></div>'
                    f'</div></div>'
                    f'<div style="flex-shrink:0;">' + dots + f'</div>'
                    f'<div style="font-size:0.78rem;font-weight:800;color:{_a};'
                    f'width:38px;text-align:right;flex-shrink:0;">'
                    + f"{alloc:.1f}%" +
                    f'</div></div>'
                )

            rows_html = "".join(
                _xr_ch_row(r["stock_name"], r["avg_alloc"], r["sector"])
                for _, r in top_com.iterrows()
            )

            # Legend: first 5 funds + "+N more" if needed
            legend_parts = []
            for i, fund_name in enumerate(DOT_FUNDS):
                dot_color = FUND_COLORS[i]
                legend_parts.append(
                    f'<div style="display:flex;align-items:center;gap:4px;margin-right:10px;">'
                    f'<div style="width:9px;height:9px;border-radius:50%;background:{dot_color};"></div>'
                    f'<span style="font-size:0.65rem;color:{_sb};">' + display_name(fund_name) + f'</span>'
                    f'</div>'
                )
            if extra_funds > 0:
                legend_parts.append(
                    f'<div style="font-size:0.65rem;color:{_sb};margin-right:10px;">'
                    f'+{extra_funds} more fund{"s" if extra_funds > 1 else ""}</div>'
                )

            st.markdown(
                f'<div style="background:{_cd};border:1px solid {_bdr};border-radius:12px;padding:0.75rem 1rem;">'
                f'<div style="display:flex;flex-wrap:wrap;gap:2px;margin-bottom:8px;'
                f'padding-bottom:8px;border-bottom:1px solid {_bdr};">'
                + "".join(legend_parts) +
                f'</div>'
                + rows_html +
                f'<div style="font-size:0.62rem;color:{_sb};margin-top:8px;text-align:right;">'
                f'Filled dots = fund holds stock &nbsp;·&nbsp; bar = avg allocation weight'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        # ── Full-screen heatmap expander (only when n_sel > 5) ───────────────
        if n_sel > 5:
            with st.expander("⛶  Expand heatmap — full view with labels", expanded=False):
                import plotly.graph_objects as _go_fs
                _fn_full   = [short_name(f) for f in matched_funds]
                _csz_full  = max(75, min(130, 900 // n_sel))
                _tsz_full  = max(11, 18 - n_sel)
                fig_fs = _go_fs.Figure(_go_fs.Heatmap(
                    z=_hm_z,
                    x=_fn_full, y=_fn_full,
                    text=_hm_annot_f,
                    hovertext=_hm_hover,
                    hovertemplate="%{hovertext}<extra></extra>",
                    texttemplate="%{text}",
                    textfont=dict(size=_tsz_full, color=_hm_txt_color,
                                  family="Inter, sans-serif"),
                    colorscale=_hm_colorscale,
                    zmin=0, zmax=100,
                    showscale=True,
                    colorbar=dict(
                        title=dict(text="Overlap %", font=dict(color=_sb, size=13)),
                        thickness=18, len=0.9,
                        tickvals=[0, 25, 50, 75, 100],
                        ticktext=["0%", "25%", "50%", "75%", "100%"],
                        tickfont=dict(color=_sb, size=11),
                    ),
                    xgap=5, ygap=5,
                ))
                _h_fs = max(680, _csz_full * n_sel + 140)
                fig_fs.update_layout(**_dark_layout(
                    height=_h_fs,
                    font=_cf,
                    margin=dict(l=20, r=160, t=70, b=20),
                    xaxis=dict(side="top", tickangle=-35,
                               tickfont=dict(size=13, color=_hd, family="Inter, sans-serif"),
                               title=""),
                    yaxis=dict(autorange="reversed",
                               tickfont=dict(size=13, color=_hd, family="Inter, sans-serif"),
                               title=""),
                ))
                st.plotly_chart(
                    fig_fs, use_container_width=True,
                    config={"displayModeBar": True, "displaylogo": False,
                            "modeBarButtonsToRemove": ["pan2d", "select2d", "lasso2d", "resetScale2d"]},
                )
                _grad_start = "#F0FFF4" if not _is_dark else "#0D1F16"
                _grad_end   = "#14532D" if not _is_dark else "#4ADE80"
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:10px;font-size:11px;color:{_sb};margin-top:6px;">'
                    f'<span>Less overlap</span>'
                    f'<div style="width:180px;height:12px;border-radius:4px;'
                    f'background:linear-gradient(to right,{_grad_start},{_grad_end});'
                    f'border:1px solid {_bdr};"></div>'
                    f'<span>More overlap</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ── Portfolio Insights expander ───────────────────────────────────────
        with st.expander("💡  Portfolio Insights & Recommendations", expanded=False):
            _pi_rows = []

            # ── Insight 1: Highest-overlap pair ──────────────────────────────
            if not sel_sim.empty:
                _worst = sel_sim.loc[sel_sim["normalized_score"].idxmax()]
                _ws    = _worst["normalized_score"]
                _wa    = display_name(_worst["fund_a"])
                _wb    = display_name(_worst["fund_b"])
                _wc    = int(_worst["common_stocks"])
                if _ws >= 60:
                    _pi_rows.append(("🔴", "alert",
                        f"<strong>{_wa}</strong> and <strong>{_wb}</strong> overlap by "
                        f"<strong>{_ws:.0f}%</strong> ({_wc} shared stocks) — this is Very High. "
                        f"You are effectively paying two fund managers for nearly the same portfolio. "
                        f"Consider replacing one with a fund from a different category (e.g. Mid Cap or Flexi Cap)."))
                elif _ws >= 45:
                    _pi_rows.append(("🟡", "warning",
                        f"<strong>{_wa}</strong> and <strong>{_wb}</strong> have the highest overlap "
                        f"in your portfolio at <strong>{_ws:.0f}%</strong> ({_wc} shared stocks). "
                        f"This is High. Both funds are making similar bets — check if one can be swapped "
                        f"for better diversification."))
                elif _ws >= 30:
                    _pi_rows.append(("🔵", "info",
                        f"Your most overlapping pair is <strong>{_wa}</strong> and <strong>{_wb}</strong> "
                        f"at <strong>{_ws:.0f}%</strong> ({_wc} shared stocks) — Moderate. "
                        f"Worth keeping an eye on, but not urgent."))
                else:
                    _pi_rows.append(("🟢", "success",
                        f"No pair has high overlap — your highest is <strong>{_wa}</strong> vs "
                        f"<strong>{_wb}</strong> at only <strong>{_ws:.0f}%</strong>. "
                        f"Your funds are well separated."))

            # ── Insight 2: Portfolio average overlap assessment ───────────────
            if avg_sim >= 45:
                _pi_rows.append(("🔴", "alert",
                    f"Your average portfolio overlap is <strong>{avg_sim:.0f}%</strong> — High. "
                    f"Most of your funds are buying the same stocks. Your effective diversification "
                    f"is much lower than the number of funds suggests. "
                    f"<strong>Action:</strong> Review your fund mix — aim for an average below 30%."))
            elif avg_sim >= 30:
                _pi_rows.append(("🟡", "warning",
                    f"Average portfolio overlap is <strong>{avg_sim:.0f}%</strong> — Moderate. "
                    f"There is noticeable duplication across your funds. "
                    f"<strong>Action:</strong> Identify the pair with highest overlap and consider "
                    f"whether both are needed."))
            else:
                _pi_rows.append(("🟢", "success",
                    f"Average portfolio overlap is <strong>{avg_sim:.0f}%</strong> — healthy. "
                    f"Your funds are investing in largely different companies. "
                    f"You are getting good diversification benefit from holding multiple funds."))

            # ── Insight 3: Fund contributing most unique stocks ───────────────
            _fund_unique: dict[str, int] = {}
            for _fn in matched_funds:
                _fn_stocks  = set(sel_h[sel_h["fund_name"] == _fn]["stock_name"].str.strip())
                _others_stk = set(sel_h[sel_h["fund_name"] != _fn]["stock_name"].str.strip())
                _fund_unique[_fn] = len(_fn_stocks - _others_stk)
            if _fund_unique:
                _best_fn  = max(_fund_unique, key=lambda f: _fund_unique[f])
                _worst_fn = min(_fund_unique, key=lambda f: _fund_unique[f])
                _best_u   = _fund_unique[_best_fn]
                _worst_u  = _fund_unique[_worst_fn]
                _pi_rows.append(("🔬", "info",
                    f"<strong>{display_name(_best_fn)}</strong> contributes the most unique stocks "
                    f"(<strong>{_best_u}</strong> stocks held by no other fund in your portfolio) — "
                    f"it is your strongest diversifier. "
                    + (
                        f"<strong>{display_name(_worst_fn)}</strong> adds only "
                        f"<strong>{_worst_u}</strong> exclusive stock{'s' if _worst_u != 1 else ''} — "
                        f"it overlaps heavily with your other funds and may be redundant."
                        if _worst_u <= 5 and _worst_fn != _best_fn else
                        f"All your funds contribute meaningfully unique stocks."
                    )))

            # ── Insight 4: High-overlap pairs count ───────────────────────────
            _n_very_high = int((sel_sim["normalized_score"] >= 60).sum()) if not sel_sim.empty else 0
            _n_high      = int(((sel_sim["normalized_score"] >= 45) & (sel_sim["normalized_score"] < 60)).sum()) if not sel_sim.empty else 0
            if _n_very_high > 0:
                _pi_rows.append(("⚠️", "alert",
                    f"<strong>{_n_very_high} fund pair{'s' if _n_very_high > 1 else ''}</strong> "
                    f"{'have' if _n_very_high > 1 else 'has'} Very High overlap (≥60%). "
                    f"These pairs are nearly redundant. "
                    f"<strong>Next step:</strong> Go to the Fund Overlap tab, select these funds, "
                    f"and use 'Compare in detail' to see exactly which stocks are duplicated."))
            elif _n_high > 0:
                _pi_rows.append(("🟡", "warning",
                    f"<strong>{_n_high} fund pair{'s' if _n_high > 1 else ''}</strong> "
                    f"{'have' if _n_high > 1 else 'has'} High overlap (45–59%). "
                    f"<strong>Next step:</strong> Use the Fund Overlap tab to compare these pairs "
                    f"and decide if both are needed."))

            # ── Render insight cards ──────────────────────────────────────────
            _pi_type_css = {
                "alert":   (f"rgba(239,68,68,{'0.15' if _is_dark else '0.08'})",
                            f"rgba(239,68,68,{'0.40' if _is_dark else '0.25'})", _col_red),
                "warning": (f"rgba(245,158,11,{'0.15' if _is_dark else '0.08'})",
                            f"rgba(245,158,11,{'0.40' if _is_dark else '0.25'})", _col_amber),
                "info":    (_al, _a50, _a),
                "success": (f"rgba(16,185,129,{'0.15' if _is_dark else '0.08'})",
                            f"rgba(16,185,129,{'0.40' if _is_dark else '0.25'})", "#059669"),
            }
            for _pi_icon, _pi_type, _pi_text in _pi_rows:
                _pi_bg, _pi_bdr, _pi_col = _pi_type_css.get(_pi_type, (_al, _bdr, _a))
                st.markdown(
                    f'<div style="background:{_pi_bg};border-left:3px solid {_pi_bdr};'
                    f'border-radius:0 10px 10px 0;padding:0.75rem 1rem;margin-bottom:0.6rem;'
                    f'display:flex;gap:0.65rem;align-items:flex-start;">'
                    f'<span style="font-size:1.1rem;flex-shrink:0;margin-top:1px;">{_pi_icon}</span>'
                    f'<span style="font-size:0.82rem;color:{_bd};line-height:1.6;">{_pi_text}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            st.caption("💡 Insights are generated from your portfolio data. Not investment advice.")

    # ── Tab 1: What You Actually Own ────────────────────────────────────────────────
    with tab_exp:
        st.markdown('<div class="section-title">What You Actually Own</div>', unsafe_allow_html=True)

        with st.expander("ℹ️  Eff. Exp % vs Avg Alloc % — what's the difference?", expanded=False):
            _wyo_has_amt = has_amounts and total_invested > 0
            _wyo_eff_note = (
                "Uses the <strong>amount you invested</strong> in each fund — "
                "funds where you put more money count more."
                if _wyo_has_amt
                else
                "Upload <strong>invested amounts</strong> on the portfolio page to enable this. "
                "Until then, the chart uses Avg Alloc % only."
            )
            st.markdown(
                f'<div style="font-size:0.82rem;color:{_bd};line-height:1.65;">'
                f'<p style="margin:0 0 0.75rem;">'
                f'This tab lists <strong>every stock</strong> in your portfolio. '
                f'Two columns answer different questions:</p>'
                f'<div style="display:grid;gap:10px;margin-bottom:0.85rem;">'
                f'<div style="background:{_al};border:1px solid {_bdr};border-radius:10px;padding:0.75rem 1rem;">'
                f'<div style="font-size:0.8rem;font-weight:700;color:{_a};margin-bottom:4px;">'
                f'Eff. Exp % (Effective exposure)</div>'
                f'<div style="font-size:0.78rem;color:{_bd};">'
                f'<strong>“Out of every ₹100 in my portfolio, how much is in this stock?”</strong><br>'
                f'For each fund: <em>(stock weight in fund) × (your share of money in that fund)</em>, '
                f'then add up.<br>{_wyo_eff_note}</div></div>'
                f'<div style="background:{_al};border:1px solid {_bdr};border-radius:10px;padding:0.75rem 1rem;">'
                f'<div style="font-size:0.8rem;font-weight:700;color:{_hd};margin-bottom:4px;">'
                f'Avg Alloc % (Average allocation)</div>'
                f'<div style="font-size:0.78rem;color:{_bd};">'
                f'<strong>“On average, how much does each fund put in this stock?”</strong><br>'
                f'Simple average across funds that hold it — '
                f'<em>every fund counts equally</em>, not weighted by your investment.<br>'
                f'Example: 6%, 8%, and 11% in three funds → Avg Alloc ≈ 8.3%.</div></div>'
                f'</div>'
                f'<p style="margin:0 0 0.5rem;font-size:0.78rem;color:{_sb};">'
                f'<strong>When they are close</strong> (e.g. Eff. Exp 8.66% vs Avg Alloc 8.34%) '
                f'your money is spread evenly across funds, or those funds hold similar weights.</p>'
                f'<p style="margin:0;font-size:0.78rem;color:{_sb};">'
                f'<strong>Overview → Top Common Holdings</strong> uses the same '
                f'<strong>Avg Alloc %</strong> for its bar, but shows only the top 12 stocks '
                f'ranked by <em>how many funds</em> hold them (overlap), not by exposure.</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Weighted effective exposure per stock
        sel_h_wt = sel_h.copy()
        sel_h_wt["weight"] = sel_h_wt["fund_name"].map(weight_map).fillna(0)
        sel_h_wt["eff_alloc"] = sel_h_wt["allocation_percent"] * sel_h_wt["weight"]

        exp = (
            sel_h_wt.groupby("stock_name")
            .agg(
                funds_holding =("fund_name",        "nunique"),
                eff_alloc     =("eff_alloc",         "sum"),
                avg_alloc     =("allocation_percent", "mean"),
                sector        =("sector",             "first"),
            )
            .reset_index()
            .sort_values("eff_alloc", ascending=False)
        )
        exp["stock_name"] = exp["stock_name"].str.strip()

        if has_amounts and total_invested > 0:
            x_col, x_label = "eff_alloc", "Effective Exposure %"
            _rank_by = "effective exposure"
        else:
            x_col, x_label = "avg_alloc", "Avg Allocation %"
            _rank_by = "average allocation"

        _n_stocks = len(exp)
        _top_n = min(15, _n_stocks)
        if _n_stocks > _top_n:
            st.markdown(
                '<div class="section-title" style="font-size:0.95rem;margin-top:0.25rem;">'
                f'Top {_top_n} holdings (chart)</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="section-sub">Largest positions by {_rank_by} — '
                f'chart shows {_top_n} of {_n_stocks} stocks</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="section-title" style="font-size:0.95rem;margin-top:0.25rem;">'
                'Holdings overview (chart)</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="section-sub">All {_n_stocks} stocks in your portfolio, ranked by {_rank_by}</div>',
                unsafe_allow_html=True,
            )

        n_bars = _top_n
        _chart_df = exp.sort_values("eff_alloc", ascending=False).head(_top_n).copy()
        _chart_y_order = _chart_df["stock_name"].tolist()
        fig_e = px.bar(
            _chart_df, x=x_col, y="stock_name", orientation="h",
            color="sector",
            text=x_col,
            labels={x_col: x_label, "stock_name": ""},
            height=max(380, n_bars * 34 + 140),
            category_orders={"stock_name": _chart_y_order},
        )
        fig_e.update_layout(
            **_dark_layout(
                margin=dict(l=10, r=72, t=15, b=120),
                font=_cf,
                yaxis=dict(
                    autorange="reversed",
                    tickfont=_ct,
                    showgrid=False,
                    categoryorder="array",
                    categoryarray=_chart_y_order,
                ),
                xaxis=_dark_xaxis(showgrid=True, gridcolor=_cg, title=x_label,
                                  title_font=dict(color=_sb, size=11)),
                legend=dict(
                    orientation="h", yanchor="top", y=-0.20,
                    xanchor="left", x=0, title=None, font=dict(size=11, color=_sb),
                ),
            )
        )
        fig_e.update_traces(
            texttemplate="%{text:.1f}%",
            textposition="outside",
            textfont=dict(size=11, color=_hd, family="Inter, sans-serif"),
            marker_line_width=0,
            cliponaxis=False,
        )
        st.plotly_chart(fig_e, use_container_width=True, config={"displayModeBar": False})

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            '<div class="section-title" style="font-size:0.95rem;">'
            'Sector exposure (effective)</div>',
            unsafe_allow_html=True,
        )
        def _norm_sector_label(s) -> str:
            t = str(s).strip() if pd.notna(s) else ""
            if not t or t.lower() in ("nan", "none"):
                return "Other"
            return t.title()

        _sec_exp = (
            exp.assign(sector=exp["sector"].map(_norm_sector_label))
            .groupby("sector", as_index=False)
            .agg(eff_alloc=("eff_alloc", "sum"), n_stocks=("stock_name", "count"))
            .sort_values("eff_alloc", ascending=False)
        )
        _sec_total = float(_sec_exp["eff_alloc"].sum()) if not _sec_exp.empty else 0.0
        st.markdown(
            f'<div class="section-sub">Effective exposure by sector (Eff. Exp %) — '
            f'sectors total {_sec_total:.1f}% of portfolio</div>',
            unsafe_allow_html=True,
        )

        _sec_top_n = 8
        _sec_top = _sec_exp.head(_sec_top_n).copy()
        _sec_rest = _sec_exp.iloc[_sec_top_n:]
        _sec_pie = _sec_top.copy()
        if not _sec_rest.empty:
            _other_eff = float(_sec_rest["eff_alloc"].sum())
            _other_n = int(_sec_rest["n_stocks"].sum())
            _other_mask = _sec_pie["sector"].str.lower().eq("other")
            if _other_mask.any():
                _oi = _sec_pie.index[_other_mask][0]
                _sec_pie.loc[_oi, "eff_alloc"] += _other_eff
                _sec_pie.loc[_oi, "n_stocks"] += _other_n
            else:
                _sec_pie = pd.concat([_sec_pie, pd.DataFrame([{
                    "sector": "Other",
                    "eff_alloc": _other_eff,
                    "n_stocks": _other_n,
                }])], ignore_index=True)

        _sec_scale_max = float(_sec_exp["eff_alloc"].max()) if not _sec_exp.empty else 1.0

        _c_sec_pie, _c_sec_tbl = st.columns([2, 3])
        with _c_sec_pie:
            fig_sec = px.pie(
                _sec_pie, names="sector", values="eff_alloc", hole=0.52, height=360,
            )
            fig_sec.update_layout(
                **_dark_layout(
                    margin=dict(l=10, r=10, t=10, b=10),
                    font=_cf,
                    legend=dict(
                        orientation="h", yanchor="top", y=-0.08,
                        xanchor="center", x=0.5, font=dict(size=10, color=_sb),
                    ),
                )
            )
            _pie_text = _sec_pie["eff_alloc"].map(lambda v: f"{v:.1f}%")
            fig_sec.update_traces(
                textposition="inside",
                textinfo="text",
                text=_pie_text,
                customdata=_sec_pie["eff_alloc"],
                hovertemplate="%{label}<br>%{customdata:.2f}% Eff. Exp<extra></extra>",
                insidetextfont=dict(size=11, color=_hd),
            )
            st.plotly_chart(fig_sec, use_container_width=True, config={"displayModeBar": False})
        with _c_sec_tbl:
            _sec_table_html = _sector_exposure_table_html(
                _sec_top,
                hd=_hd, sb=_sb, bd=_bd, a=_a, cd=_cd, bdr=_bdr,
                col_amber=_col_amber, is_dark=_is_dark,
                weight_hdr="Eff. Exp",
                high_thresh=25.0,
                scale_max=_sec_scale_max,
            )
            st.markdown(_sec_table_html, unsafe_allow_html=True)
            if not _sec_rest.empty:
                _n_sec_rest = len(_sec_rest)
                _rest_eff = float(_sec_rest["eff_alloc"].sum())
                with st.expander(
                    f"Show {_n_sec_rest} more sector{'s' if _n_sec_rest != 1 else ''} "
                    f"({_rest_eff:.1f}% combined Eff. Exp)",
                    expanded=False,
                ):
                    _sec_rest_html = _sector_exposure_table_html(
                        _sec_rest,
                        hd=_hd, sb=_sb, bd=_bd, a=_a, cd=_cd, bdr=_bdr,
                        col_amber=_col_amber, is_dark=_is_dark,
                        weight_hdr="Eff. Exp",
                        high_thresh=25.0,
                        scale_max=_sec_scale_max,
                        show_header=False,
                    )
                    st.markdown(_sec_rest_html, unsafe_allow_html=True)
            st.markdown(
                f'<div style="font-size:0.62rem;color:{_sb};margin-top:6px;text-align:right;">'
                f'▲ HIGH = sector ≥25% of effective portfolio</div>',
                unsafe_allow_html=True,
            )

        _wyo_wt_col = x_col
        _wyo_wt_hdr = "Eff. Exp" if _wyo_wt_col == "eff_alloc" else "Avg Alloc"
        with st.expander(
            f"📋 Complete holdings (table) — all {_n_stocks} stocks",
            expanded=False,
        ):
            st.markdown(
                f'<div class="section-sub" style="margin-top:0;">All {_n_stocks} stocks — '
                f'coverage bars, mini exposure bars, and ▲ HIGH flags for positions ≥8%</div>',
                unsafe_allow_html=True,
            )
            _exp_tbl = exp.sort_values(_wyo_wt_col, ascending=False).copy()
            _exp_tbl["_sector_clean"] = (
                _exp_tbl["sector"].fillna("Other").astype(str).str.strip()
            )
            _exp_tbl.loc[_exp_tbl["_sector_clean"].eq(""), "_sector_clean"] = "Other"
            _wyo_sectors = sorted(_exp_tbl["_sector_clean"].unique().tolist())
            _wyo_stocks = sorted(_exp_tbl["stock_name"].tolist())
            _wyo_eff_max = (
                min(100.0, max(0.5, float(np.ceil(_exp_tbl["eff_alloc"].max() * 10) / 10)))
                if not _exp_tbl.empty else 10.0
            )

            _wyo_fc_sec, _wyo_fc_stk, _wyo_fc_eff = st.columns(
                [1.1, 1.4, 1.5], gap="small", vertical_alignment="top",
            )
            with _wyo_fc_sec:
                st.markdown('<div class="ov-filter-lbl">Sector</div>', unsafe_allow_html=True)
                _wyo_sel_sectors = st.multiselect(
                    "Sector",
                    _wyo_sectors,
                    placeholder="All sectors",
                    key="wyo_hold_sector",
                    label_visibility="collapsed",
                )
            with _wyo_fc_stk:
                st.markdown('<div class="ov-filter-lbl">Stock</div>', unsafe_allow_html=True)
                _wyo_sel_stocks = st.multiselect(
                    "Stock",
                    _wyo_stocks,
                    placeholder="All stocks",
                    key="wyo_hold_stock",
                    label_visibility="collapsed",
                )
            with _wyo_fc_eff:
                st.markdown('<div class="ov-filter-lbl">Eff. Exp %</div>', unsafe_allow_html=True)
                _wyo_eff_sl, _wyo_eff_val = st.columns([4, 1], vertical_alignment="center")
                with _wyo_eff_sl:
                    _wyo_eff_range = st.slider(
                        "Eff. Exp range",
                        min_value=0.0,
                        max_value=_wyo_eff_max,
                        value=(0.0, _wyo_eff_max),
                        step=0.1,
                        key="wyo_hold_eff_range",
                        format="%.1f%%",
                        label_visibility="collapsed",
                    )
                with _wyo_eff_val:
                    _eff_lo, _eff_hi = _wyo_eff_range
                    _eff_lbl = (
                        "Any"
                        if _eff_lo <= 0 and _eff_hi >= _wyo_eff_max
                        else f"{_eff_lo:.1f}–{_eff_hi:.1f}%"
                    )
                    st.markdown(
                        f'<div class="ov-min-val">{_eff_lbl}</div>',
                        unsafe_allow_html=True,
                    )

            _exp_filtered = _exp_tbl
            if _wyo_sel_sectors:
                _exp_filtered = _exp_filtered[
                    _exp_filtered["_sector_clean"].isin(_wyo_sel_sectors)
                ]
            if _wyo_sel_stocks:
                _exp_filtered = _exp_filtered[
                    _exp_filtered["stock_name"].isin(_wyo_sel_stocks)
                ]
            _eff_lo, _eff_hi = _wyo_eff_range
            _exp_filtered = _exp_filtered[
                (_exp_filtered["eff_alloc"] >= _eff_lo)
                & (_exp_filtered["eff_alloc"] <= _eff_hi)
            ]
            _n_filtered = len(_exp_filtered)

            st.markdown(
                f'<div style="font-size:0.72rem;color:{_sb};margin:0.35rem 0 0.75rem;">'
                f'Showing <strong style="color:{_hd};">{_n_filtered}</strong> of '
                f'<strong style="color:{_hd};">{_n_stocks}</strong> stocks</div>',
                unsafe_allow_html=True,
            )

            if _exp_filtered.empty:
                st.info("No holdings match the current filters. Widen Eff. Exp % or clear sector/stock selections.")
            else:
                _wyo_table_html = _blended_exposure_table_html(
                    _exp_filtered.drop(columns=["_sector_clean"]),
                    len(matched_funds),
                    hd=_hd, sb=_sb, bd=_bd, a=_a, cd=_cd, bdr=_bdr,
                    col_amber=_col_amber, col_green=_col_green, is_dark=_is_dark,
                    weight_col=_wyo_wt_col,
                    weight_hdr=_wyo_wt_hdr,
                    high_thresh=8.0,
                )
                _conc = _exp_filtered[_exp_filtered[_wyo_wt_col] >= 8.0]
                if not _conc.empty:
                    _cn = ", ".join(
                        f"<strong>{s}</strong>"
                        for s in _conc["stock_name"].head(5).tolist()
                    )
                    st.markdown(
                        f'<div style="background:{"rgba(245,158,11,0.15)" if _is_dark else "#FEF3C7"};'
                        f'border:1px solid {"rgba(245,158,11,0.35)" if _is_dark else "#FCD34D"};'
                        f'border-left:3px solid {_col_amber};border-radius:10px;'
                        f'padding:0.75rem 1rem;margin-bottom:1rem;font-size:0.82rem;color:{_hd};line-height:1.55;">'
                        f'⚠️ <strong style="color:{_col_amber};">Concentration alert:</strong> '
                        f'{_cn} each make up ≥8% of your effective portfolio.</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(_wyo_table_html, unsafe_allow_html=True)
                st.markdown(
                    f'<div style="font-size:0.62rem;color:{_sb};margin-top:6px;text-align:right;">'
                    f'▲ HIGH = position ≥8% of portfolio · '
                    f'{_n_filtered} row{"s" if _n_filtered != 1 else ""} shown</div>',
                    unsafe_allow_html=True,
                )


    # ── Tab 2: Fund Performance ───────────────────────────────────────────────
    with tab_perf:
        from analytics.overlap_filters import MIN_RETURN_SLIDER_MAX, fund_return_pct, sort_funds_by_return

        st.markdown('<div class="section-title">Fund Performance Comparison</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-sub">Returns, risk, and efficiency metrics for funds in your portfolio</div>',
            unsafe_allow_html=True,
        )

        _pf_perf_cat_map: dict[str, str] = {}
        for _f in matched_funds:
            _row = master[master["fund_name"] == _f]
            if not _row.empty:
                _cv = _row.iloc[0].get("category", "Other")
                _pf_perf_cat_map[_f] = str(_cv) if pd.notna(_cv) else "Other"
            else:
                _pf_perf_cat_map[_f] = "Other"
        _pf_perf_cats = sorted(set(_pf_perf_cat_map.values()))
        _PF_PERF_ALL = "All"

        st.markdown('<div class="ov-tb-sentinel"></div>', unsafe_allow_html=True)
        _ppc_cat, _ppc_ret, _ppc_min = st.columns(
            [1.2, 0.8, 1.8], gap="small", vertical_alignment="top",
        )
        with _ppc_cat:
            st.markdown('<div class="ov-filter-lbl">Category</div>', unsafe_allow_html=True)
            _ppc_sel_cats = st.multiselect(
                "Category",
                _pf_perf_cats,
                placeholder="All categories",
                key="portfolio_perf_cats",
                label_visibility="collapsed",
            )
            if not _ppc_sel_cats:
                _ppc_sel_cats = [_PF_PERF_ALL]
        with _ppc_ret:
            st.markdown('<div class="ov-filter-lbl">Return yrs</div>', unsafe_allow_html=True)
            _ppc_period = st.selectbox(
                "Return period",
                ("1Y", "3Y", "5Y"),
                key="portfolio_perf_period",
                label_visibility="collapsed",
            )
        with _ppc_min:
            st.markdown('<div class="ov-filter-lbl">Min. past return</div>', unsafe_allow_html=True)
            _ppc_sl, _ppc_val = st.columns([4, 1], vertical_alignment="center")
            with _ppc_sl:
                _ppc_min_ret = st.slider(
                    "Min return",
                    min_value=0, max_value=MIN_RETURN_SLIDER_MAX, step=1,
                    key="portfolio_perf_min_return",
                    format="%d%%",
                    label_visibility="collapsed",
                    help="0 = Any (no minimum return filter).",
                )
            with _ppc_val:
                st.markdown(
                    f'<div class="ov-min-val">{"Any" if _ppc_min_ret == 0 else f"≥{_ppc_min_ret}%"}</div>',
                    unsafe_allow_html=True,
                )

        if not _ppc_sel_cats or _PF_PERF_ALL in _ppc_sel_cats:
            _ppc_funds = list(matched_funds)
        else:
            _ppc_funds = [f for f in matched_funds if _pf_perf_cat_map.get(f) in _ppc_sel_cats]

        if _ppc_min_ret > 0:
            _ppc_funds = [
                f for f in _ppc_funds
                if (fund_return_pct(master, f, _ppc_period) or -999) >= _ppc_min_ret
            ]

        _ppc_funds = sort_funds_by_return(_ppc_funds, master, _ppc_period)

        if not _ppc_funds:
            st.warning("No portfolio funds match the current filters. Widen category or lower the return threshold.")
        else:
            _ppc_master = sel_master[sel_master["fund_name"].isin(_ppc_funds)].copy()
            if _ppc_master.empty:
                st.info("Performance data not available for the matching funds.")
            else:
                st.markdown(
                f'<div style="font-size:0.72rem;color:{_sb};margin:0.25rem 0 0.75rem;">'
                f'Comparing <strong style="color:{_hd};">{len(_ppc_funds)}</strong> fund'
                f'{"s" if len(_ppc_funds) != 1 else ""} from your portfolio</div>',
                unsafe_allow_html=True,
                )
                _render_fund_performance_tab(
                    _ppc_master,
                    _ppc_funds,
                    hd=_hd, sb=_sb, bd=_bd, a=_a, cd=_cd, bdr=_bdr, al=_al,
                    col_amber=_col_amber, col_green=_col_green, col_red=_col_red,
                    cf=_cf, cg=_cg, ct=_ct, is_dark=_is_dark,
                    explainer_key="xray",
                    max_display=8,
                    amount_map=amount_map,
                    matched_funds=matched_funds,
                    has_amounts=has_amounts,
                )

    # ── Tab 3: Fund Overlap ───────────────────────────────────────────────────
    with tab_ol:
        from analytics.overlap_journey_viz import (
            BUCKET_LABEL_TO_RANGE,
            DEFAULT_BUCKET_LABEL,
            JOURNEY_MIN_EDGE,
            OVERLAP_BUCKETS,
            JourneyVizParams,
            fig_overlap_journey,
            journey_legend_html,
        )
        from analytics.overlap_filters import RETURN_PERIODS, sort_funds_by_return as _pf_sort_by_ret

        # Overlap page CSS (graph/sidebar/pills styling)
        _overlap_inject_page_css(t, t_name)
        _pf_ov_theme = _overlap_theme_dict(t, t_name)

        st.markdown('<div class="section-title">Overlap Between Your Funds</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-sub">Visualise how your portfolio funds overlap. '
            'Click a bubble or use the dropdown to select two funds and compare them in detail.</div>',
            unsafe_allow_html=True,
        )

        if len(matched_funds) < 2:
            st.info("Need at least 2 matched funds to compute overlap.")
        else:
            # ── Init portfolio overlap session state ──────────────────────────
            if "portfolio_overlap_selected_funds" not in st.session_state:
                st.session_state.portfolio_overlap_selected_funds = []
            if "portfolio_overlap_period" not in st.session_state:
                st.session_state.portfolio_overlap_period = "5Y"
            if "portfolio_overlap_min_return" not in st.session_state:
                st.session_state.portfolio_overlap_min_return = 8
            if "portfolio_overlap_conn_bucket" not in st.session_state:
                st.session_state.portfolio_overlap_conn_bucket = "✅ All connections"

            # ── Derive fund categories from master ────────────────────────────
            _pf_cat_map: dict[str, str] = {}
            for _f in matched_funds:
                _row = master[master["fund_name"] == _f]
                if not _row.empty:
                    _cv = _row.iloc[0].get("category", "Other")
                    _pf_cat_map[_f] = str(_cv) if pd.notna(_cv) else "Other"
                else:
                    _pf_cat_map[_f] = "Other"
            _pf_avail_cats = sorted(set(_pf_cat_map.values()))
            _PF_ALL = "All"

            # ── Filter toolbar — 4 dropdowns, same layout as Overlap Matrix ────
            from analytics.overlap_filters import MIN_RETURN_SLIDER_MAX, fund_return_pct
            st.markdown('<div class="ov-tb-sentinel"></div>', unsafe_allow_html=True)
            _pf_c_cat, _pf_c_ret, _pf_c_min, _pf_c_conn = st.columns(
                [1.0, 0.8, 1.8, 1.0], gap="small", vertical_alignment="top"
            )

            with _pf_c_cat:
                st.markdown('<div class="ov-filter-lbl">Category</div>', unsafe_allow_html=True)
                _pf_sel_cats = st.multiselect(
                    "Category",
                    _pf_avail_cats,
                    placeholder="All funds in portfolio",
                    key="portfolio_overlap_cats_dd",
                    label_visibility="collapsed",
                )
                # Empty selection = show all
                if not _pf_sel_cats:
                    _pf_sel_cats = [_PF_ALL]

            with _pf_c_ret:
                st.markdown('<div class="ov-filter-lbl">Return yrs</div>', unsafe_allow_html=True)
                _pf_period = st.selectbox(
                    "Return period",
                    RETURN_PERIODS,
                    key="portfolio_overlap_period",
                    label_visibility="collapsed",
                )
                if not _pf_period:
                    _pf_period = "1Y"

            with _pf_c_min:
                st.markdown('<div class="ov-filter-lbl">Min. past return</div>', unsafe_allow_html=True)
                _pf_sl_col, _pf_val_col = st.columns([4, 1], vertical_alignment="center")
                with _pf_sl_col:
                    _pf_min_ret = st.slider(
                        "Min return",
                        min_value=0, max_value=MIN_RETURN_SLIDER_MAX, step=1,
                        key="portfolio_overlap_min_return",
                        format="%d%%",
                        label_visibility="collapsed",
                        help="0 = Any (no minimum return filter).",
                    )
                with _pf_val_col:
                    st.markdown(
                        f'<div class="ov-min-val">{"Any" if _pf_min_ret == 0 else f"≥{_pf_min_ret}%"}</div>',
                        unsafe_allow_html=True,
                    )

            with _pf_c_conn:
                st.markdown('<div class="ov-filter-lbl">Show lines ≥</div>', unsafe_allow_html=True)
                _pf_conn_bucket = st.selectbox(
                    "Show lines ≥",
                    [b[0] for b in OVERLAP_BUCKETS],
                    key="portfolio_overlap_conn_bucket",
                    label_visibility="collapsed",
                    help="Draw connection lines only when overlap reaches this level.",
                )

            _pf_min_edge, _pf_max_edge = BUCKET_LABEL_TO_RANGE.get(_pf_conn_bucket, (JOURNEY_MIN_EDGE, 100.0))

            # ── Apply category filter ─────────────────────────────────────────
            if not _pf_sel_cats or _PF_ALL in _pf_sel_cats:
                _pf_funds = matched_funds
            else:
                _pf_funds = [f for f in matched_funds if _pf_cat_map.get(f) in _pf_sel_cats]

            # ── Apply min-return filter ───────────────────────────────────────
            if _pf_min_ret > 0:
                _pf_funds = [
                    f for f in _pf_funds
                    if (fund_return_pct(master, f, _pf_period) or 0) >= _pf_min_ret
                ]

            st.markdown("<br>", unsafe_allow_html=True)


            if len(_pf_funds) < 2:
                _pf_filter_note = (
                    "Only 1 fund in your portfolio matches the selected filters — need at least 2 to build the overlap graph. "
                    "Try selecting a broader category or lowering the Min. Past Return filter."
                )
                st.info(_pf_filter_note)
            else:
                # ── Build (or retrieve cached) overlap graph ──────────────────
                _pf_funds_key = tuple(sorted(_pf_funds))
                _pf_graph = _portfolio_overlap_graph(_pf_funds_key)

                if _pf_graph is None:
                    st.info("Could not build overlap graph for the selected funds.")
                else:
                    _pf_fund_a, _pf_fund_b = _overlap_get_ab(_pf_funds, ns="portfolio_overlap")

                    # ── View mode toggle ──────────────────────────────────────
                    _pf_view_col, _ = st.columns([3, 5])
                    with _pf_view_col:
                        _pf_view = st.segmented_control(
                            "View",
                            ["🔗 Overlap Graph", "📊 Bubble Chart"],
                            default=st.session_state.get("pf_overlap_view_mode", "🔗 Overlap Graph"),
                            key="pf_overlap_view_mode",
                            label_visibility="collapsed",
                        )
                    _pf_show_bubble = (_pf_view == "📊 Bubble Chart")

                    # ── Graph  +  Sidebar ─────────────────────────────────────
                    _pf_gcol, _pf_scol = st.columns([15, 7])

                    with _pf_gcol:
                        if _pf_show_bubble:
                            if not _pf_fund_a:
                                st.markdown(
                                    _overlap_bubble_guide_html(
                                        _pf_ov_theme, has_base=False, return_period=_pf_period,
                                    ),
                                    unsafe_allow_html=True,
                                )
                            else:
                                with st.expander("📖 How to read this chart", expanded=False):
                                    st.markdown(
                                        _overlap_bubble_guide_html(
                                            _pf_ov_theme, has_base=True, return_period=_pf_period,
                                        ),
                                        unsafe_allow_html=True,
                                    )
                                _pf_bubble_result = _overlap_bubble_chart_fig(
                                    _pf_graph, _pf_ov_theme, master,
                                    _pf_fund_a, _pf_fund_b, _pf_period,
                                    ns="portfolio_overlap",
                                )
                                if _pf_bubble_result is None:
                                    st.info("Not enough return data to build the bubble chart.")
                                else:
                                    _pf_bfig, _pf_bfunds, _pf_best_lbl, _pf_best_ov, _pf_best_ret = _pf_bubble_result
                                    _pf_bubble_ev = st.plotly_chart(
                                        _pf_bfig, use_container_width=True, on_select="rerun",
                                        key=f"pf_bubble_{_pf_period}_{_pf_fund_a}_{len(_pf_funds)}",
                                        config={"displayModeBar": False},
                                    )
                                    if _pf_bubble_ev and getattr(_pf_bubble_ev, "selection", None):
                                        _pf_bpts = _pf_bubble_ev.selection.get("points", [])
                                        if _pf_bpts:
                                            _pf_bidx = _pf_bpts[0].get("point_index", _pf_bpts[0].get("pointNumber"))
                                            if _pf_bidx is not None and 0 <= _pf_bidx < len(_pf_bfunds):
                                                _overlap_pick_fund(_pf_bfunds[_pf_bidx], _pf_funds, ns="portfolio_overlap")
                                                st.session_state.pop("portfolio_overlap_dropdown_last", None)
                                                st.rerun()
                                    from analytics.overlap_graph import fund_label as _pf_fl2
                                    _pf_base_lbl2 = _pf_fl2(_pf_fund_a, max_len=24)
                                    st.markdown(
                                        f'<div style="background:rgba(16,185,129,0.10);border:1px solid rgba(16,185,129,0.3);'
                                        f'border-radius:10px;padding:0.6rem 1rem;margin-top:6px;font-size:0.82rem;color:{_pf_ov_theme["body"]};">'
                                        f'<strong style="color:#10B981;">★ Best pair for {_pf_base_lbl2}:</strong> '
                                        f'<strong>{_pf_best_lbl}</strong> — lowest overlap '
                                        f'(<strong>{_pf_best_ov:.0f}%</strong>) with decent returns '
                                        f'(<strong>{_pf_best_ret:+.1f}%</strong>)'
                                        f'</div>',
                                        unsafe_allow_html=True,
                                    )
                                    st.markdown(
                                        f'<div style="font-size:0.72rem;color:{_pf_ov_theme["sub"]};margin-top:6px;">'
                                        f'← lower overlap = better pair &nbsp;·&nbsp; '
                                        f'↑ higher return = better performer &nbsp;·&nbsp; '
                                        f'Click a bubble to select it as Fund B</div>',
                                        unsafe_allow_html=True,
                                    )
                        else:
                            st.markdown(journey_legend_html(_pf_ov_theme), unsafe_allow_html=True)
                            _pf_fig = fig_overlap_journey(
                                _pf_graph, _pf_ov_theme, master,
                                JourneyVizParams(
                                    fund_a=_pf_fund_a, fund_b=_pf_fund_b,
                                    return_period=_pf_period,
                                    min_edge_pct=_pf_min_edge,
                                    max_edge_pct=_pf_max_edge,
                                ),
                            )
                            _pf_chart = st.plotly_chart(
                                _pf_fig,
                                use_container_width=True,
                                on_select="rerun",
                                key=f"pf_ov_j_{_pf_conn_bucket}_{_pf_period}_{len(_pf_funds)}",
                            )
                            _pf_click_idx = _overlap_pick_fund_index(
                                _pf_chart.selection if _pf_chart else None,
                                _pf_graph,
                            )
                            if _pf_click_idx is not None:
                                _overlap_pick_fund(_pf_graph.funds[_pf_click_idx], _pf_funds, ns="portfolio_overlap")
                                st.session_state.pop("portfolio_overlap_dropdown_last", None)
                                st.rerun()

                            _pf_insight = _overlap_graph_insight(
                                _pf_graph, _pf_min_edge, _pf_max_edge, _pf_conn_bucket, _pf_ov_theme,
                            )
                            if _pf_insight:
                                st.markdown(_pf_insight, unsafe_allow_html=True)

                            _pf_hint = _overlap_graph_hint(_pf_fund_a, _pf_fund_b)
                            st.markdown(f'<div class="ov-hint">{_pf_hint}</div>', unsafe_allow_html=True)

                    with _pf_scol:
                        st.markdown('<div class="ov-side-sentinel"></div>', unsafe_allow_html=True)
                        _overlap_render_fund_sidebar(
                            _pf_graph, _pf_funds, master, _pf_period,
                            _pf_ov_theme, similarity, holdings,
                            ns="portfolio_overlap",
                            return_source="portfolio_xray",
                            bubble_mode=_pf_show_bubble,
                        )

                    # ── Full-width holdings expander (when 2 funds selected) ──
                    if _pf_fund_a and _pf_fund_b:
                        from analytics.overlap_quick_compare import (
                            exclusive_holdings_table,
                            holdings_union_table,
                            top_common_holdings_table as _pf_top_common,
                        )
                        from analytics.overlap_graph import fund_label as _pf_fl

                        _fa_lbl   = _pf_fl(_pf_fund_a, max_len=28)
                        _fb_lbl   = _pf_fl(_pf_fund_b, max_len=28)
                        _fa_short = _pf_fl(_pf_fund_a, max_len=14)
                        _fb_short = _pf_fl(_pf_fund_b, max_len=14)
                        _pf_common_df = _pf_top_common(holdings, _pf_fund_a, _pf_fund_b, top_n=200)
                        _pf_n_shared  = len(_pf_common_df)

                        with st.expander(
                            f"📋  Holdings breakdown  ·  {_pf_n_shared} stocks in common  ·  {_fa_lbl} vs {_fb_lbl}",
                            expanded=False,
                        ):
                            _COLOR_A = "#534AB7"
                            _COLOR_B = "#0F6E56"
                            _ov_bdr = _bdr; _ov_hd = _hd; _ov_sb = _sb; _ov_al = _al; _ov_cd = _cd

                            _PF_VIEW_COMMON = f"Common ({_pf_n_shared})"
                            _PF_VIEW_ALL    = "All stocks"
                            _PF_VIEW_EX_A   = f"Only in {_fa_short}"
                            _PF_VIEW_EX_B   = f"Only in {_fb_short}"
                            _pf_view_opts   = [_PF_VIEW_COMMON, _PF_VIEW_ALL, _PF_VIEW_EX_A, _PF_VIEW_EX_B]

                            _pf_view = st.segmented_control(
                                "Stock view",
                                _pf_view_opts,
                                default=_PF_VIEW_COMMON,
                                key="portfolio_overlap_holdings_view",
                                label_visibility="collapsed",
                            )
                            if not _pf_view:
                                _pf_view = _PF_VIEW_COMMON

                            if _pf_view == _PF_VIEW_COMMON:
                                _pf_df_v   = _pf_common_df
                                _pf_bcols  = list(_pf_df_v.columns)[1:3] if len(_pf_df_v.columns) > 2 else []
                                _pf_bclrs  = [_COLOR_A, _COLOR_B]
                            elif _pf_view == _PF_VIEW_ALL:
                                _pf_df_v   = holdings_union_table(holdings, _pf_fund_a, _pf_fund_b)
                                _pf_bcols  = list(_pf_df_v.columns)[1:3] if not _pf_df_v.empty and len(_pf_df_v.columns) > 2 else []
                                _pf_bclrs  = [_COLOR_A, _COLOR_B]
                            elif _pf_view == _PF_VIEW_EX_A:
                                _pf_df_v   = exclusive_holdings_table(holdings, _pf_fund_a, _pf_fund_b)
                                _pf_bcols  = [list(_pf_df_v.columns)[1]] if not _pf_df_v.empty and len(_pf_df_v.columns) > 1 else []
                                _pf_bclrs  = [_COLOR_A]
                            else:
                                _pf_df_v   = exclusive_holdings_table(holdings, _pf_fund_b, _pf_fund_a)
                                _pf_bcols  = [list(_pf_df_v.columns)[1]] if not _pf_df_v.empty and len(_pf_df_v.columns) > 1 else []
                                _pf_bclrs  = [_COLOR_B]

                            if _pf_df_v.empty:
                                st.caption("No holdings data available for this selection.")
                            else:
                                _pf_all_cols  = list(_pf_df_v.columns)
                                _pf_data_cols = _pf_all_cols[1:]
                                _pf_maxv      = {c: float(_pf_df_v[c].max()) or 1.0 for c in _pf_data_cols if c in _pf_df_v.columns}
                                _pf_col_clr   = {c: _pf_bclrs[i] if i < len(_pf_bclrs) else _a for i, c in enumerate(_pf_data_cols)}

                                def _pf_th(lbl):
                                    return (
                                        f'<th style="padding:10px 14px;text-align:left;font-size:0.7rem;'
                                        f'font-weight:700;color:{_ov_sb};text-transform:uppercase;letter-spacing:0.5px;">{lbl}</th>'
                                    )

                                def _pf_bar(val, mx, color):
                                    try:
                                        v = float(val)
                                    except (TypeError, ValueError):
                                        return f'<span style="color:{_ov_sb};font-size:0.78rem;">—</span>'
                                    w = int(v / mx * 100) if mx > 0 else 0
                                    return (
                                        f'<div style="display:flex;align-items:center;gap:8px;">'
                                        f'<div style="flex:1;height:6px;border-radius:3px;background:{_ov_bdr};">'
                                        f'<div style="width:{w}%;height:100%;border-radius:3px;background:{color};"></div>'
                                        f'</div>'
                                        f'<span style="font-size:0.82rem;font-weight:700;color:{color};white-space:nowrap;">'
                                        f'{v:.2f}%</span></div>'
                                    )

                                _pf_hdr_html  = _pf_th("Stock") + "".join(_pf_th(c) for c in _pf_data_cols)
                                _pf_rows_html = ""
                                for _ri, _rrow in _pf_df_v.reset_index(drop=True).iterrows():
                                    _rbg   = _ov_al if _ri % 2 == 0 else _ov_cd
                                    _rstk  = str(_rrow[_pf_all_cols[0]])
                                    _rcells = "".join(
                                        f'<td style="padding:10px 14px;min-width:200px;">'
                                        f'{_pf_bar(_rrow[c], _pf_maxv.get(c, 1), _pf_col_clr[c])}</td>'
                                        for c in _pf_data_cols
                                    )
                                    _pf_rows_html += (
                                        f'<tr style="background:{_rbg};border-bottom:1px solid {_ov_bdr};">'
                                        f'<td style="padding:10px 14px;min-width:220px;font-size:0.82rem;'
                                        f'font-weight:600;color:{_ov_hd};line-height:1.3;">{_rstk}</td>'
                                        f'{_rcells}</tr>'
                                    )

                                st.caption(f"{len(_pf_df_v)} stock{'s' if len(_pf_df_v) != 1 else ''}")
                                st.markdown(
                                    f'<div style="border-radius:12px;border:1px solid {_ov_bdr};overflow:hidden;">'
                                    f'<table style="width:100%;border-collapse:collapse;">'
                                    f'<thead><tr style="background:{_ov_al};border-bottom:2px solid {_ov_bdr};">'
                                    f'{_pf_hdr_html}'
                                    f'</tr></thead><tbody>{_pf_rows_html}</tbody></table></div>',
                                    unsafe_allow_html=True,
                                )

        # ── What-If: fund selector + single card ─────────────────────────────
        if len(_pf_funds) >= 2:
            st.markdown("<br>", unsafe_allow_html=True)
            # Avg overlap of the currently filtered funds (matches graph)
            _pf_avg_sim = (
                similarity[similarity["fund_a"].isin(_pf_funds) & similarity["fund_b"].isin(_pf_funds)]
                ["normalized_score"].mean()
                if not similarity[similarity["fund_a"].isin(_pf_funds) & similarity["fund_b"].isin(_pf_funds)].empty
                else 0.0
            )
            with st.expander("🔍  What happens if you remove a fund?", expanded=False):
                st.markdown(
                    f'<div class="section-sub" style="margin-top:0.25rem;margin-bottom:0.9rem;">'
                    f'Pick a fund below to see what your portfolio looks like without it. '
                    f'Showing funds matching your current filters.</div>',
                    unsafe_allow_html=True,
                )

                # Fund selector — uses filtered fund list
                _wi_labels  = [display_name(f) for f in _pf_funds]
                _wi_sel_lbl = st.segmented_control(
                    "Select fund", _wi_labels, default=_wi_labels[0],
                    key="wi_fund_sel", label_visibility="collapsed",
                )
                _wi_fund = _pf_funds[_wi_labels.index(_wi_sel_lbl)] if _wi_sel_lbl else _pf_funds[0]

                # ── Compute impact for selected fund ──────────────────────────
                _wi_others      = [f for f in _pf_funds if f != _wi_fund]
                _wi_others_stk  = set(holdings[holdings["fund_name"].isin(_wi_others)]["stock_name"].str.strip())
                _wi_fund_stk    = set(sel_h[sel_h["fund_name"] == _wi_fund]["stock_name"].str.strip())
                _wi_unique_lost = len(_wi_fund_stk - _wi_others_stk)
                _wi_top_unique  = sorted(_wi_fund_stk - _wi_others_stk)[:4]
                _wi_ov_without  = (
                    similarity[similarity["fund_a"].isin(_wi_others) & similarity["fund_b"].isin(_wi_others)]
                    ["normalized_score"].mean()
                    if len(_wi_others) >= 2 else 0.0
                )
                _wi_ov_change   = _wi_ov_without - _pf_avg_sim
                _wifn           = display_name(_wi_fund)

                # ── Plain-English verdict lines ───────────────────────────────
                if _wi_unique_lost == 0:
                    _wi_line1 = (
                        f"Every stock held by <strong>{_wifn}</strong> is already covered by at least "
                        f"one of your other funds. You would not lose any unique exposure."
                    )
                elif _wi_unique_lost <= 3:
                    _wi_line1 = (
                        f"<strong>{_wifn}</strong> is the only fund in your portfolio that holds "
                        f"<strong>{_wi_unique_lost} stock{'s' if _wi_unique_lost > 1 else ''}</strong>"
                        + (f" ({', '.join(_wi_top_unique[:3])})." if _wi_top_unique else ".")
                        + " That is a very small number, so you would not lose much unique exposure."
                    )
                elif _wi_unique_lost <= 15:
                    _wi_line1 = (
                        f"<strong>{_wifn}</strong> is the only fund that invests in "
                        f"<strong>{_wi_unique_lost} stocks</strong> across your entire portfolio"
                        + (f" — such as {', '.join(_wi_top_unique[:3])}." if _wi_top_unique else ".")
                        + " If you remove it, you lose exposure to all of these companies."
                    )
                else:
                    _wi_line1 = (
                        f"<strong>{_wifn}</strong> brings <strong>{_wi_unique_lost} companies</strong> "
                        f"to your portfolio that none of your other funds invest in"
                        + (f" — including {', '.join(_wi_top_unique[:3])}." if _wi_top_unique else ".")
                        + " Removing it would noticeably narrow the variety of companies you own."
                    )

                if len(_wi_others) < 2:
                    _wi_line2 = ""
                elif abs(_wi_ov_change) < 1:
                    _wi_line2 = (
                        f"Your remaining funds already overlap with each other at around "
                        f"<strong>{_wi_ov_without:.0f}%</strong>. Removing <strong>{_wifn}</strong> "
                        f"would not change how similar those funds are to one another."
                    )
                elif _wi_ov_change > 0:
                    _wi_line2 = (
                        f"There is one thing to keep in mind: <strong>{_wifn}</strong>'s holdings "
                        f"are quite different from your other funds, which means it has been "
                        f"<em>lowering</em> your average overlap. If you remove it, the remaining "
                        f"funds would become more similar to each other — overlap would rise from "
                        f"{_pf_avg_sim:.0f}% to <strong>{_wi_ov_without:.0f}%</strong>."
                    )
                else:
                    _wi_line2 = (
                        f"After removing this fund, your remaining funds would actually be "
                        f"<strong>more distinct</strong> from each other — average overlap would "
                        f"drop from {_pf_avg_sim:.0f}% to <strong>{_wi_ov_without:.0f}%</strong>."
                    )

                # Card colour + verdict badge
                if _wi_unique_lost == 0 and abs(_wi_ov_change) < 1:
                    _wi_bg, _wi_bdr_c = "rgba(16,185,129,0.08)", "rgba(16,185,129,0.35)"
                    _wi_badge, _wi_badge_bg, _wi_badge_txt = "Safe to remove", "rgba(16,185,129,0.2)", "#059669"
                    _wi_icon = "✂️"
                elif _wi_unique_lost <= 3 and _wi_ov_change > 1:
                    _wi_bg, _wi_bdr_c = "rgba(245,158,11,0.08)", "rgba(245,158,11,0.35)"
                    _wi_badge, _wi_badge_bg, _wi_badge_txt = "Think twice", "rgba(245,158,11,0.2)", "#D97706"
                    _wi_icon = "🔄"
                elif _wi_unique_lost <= 5 and abs(_wi_ov_change) < 1:
                    _wi_bg, _wi_bdr_c = "rgba(16,185,129,0.08)", "rgba(16,185,129,0.35)"
                    _wi_badge, _wi_badge_bg, _wi_badge_txt = "Low impact", "rgba(16,185,129,0.2)", "#059669"
                    _wi_icon = "✂️"
                elif _wi_unique_lost > 15:
                    _wi_bg, _wi_bdr_c = "rgba(239,68,68,0.08)", "rgba(239,68,68,0.35)"
                    _wi_badge, _wi_badge_bg, _wi_badge_txt = "Keep this fund", "rgba(239,68,68,0.2)", "#DC2626"
                    _wi_icon = "⚠️"
                else:
                    _wi_bg, _wi_bdr_c = "rgba(245,158,11,0.08)", "rgba(245,158,11,0.35)"
                    _wi_badge, _wi_badge_bg, _wi_badge_txt = "Some impact", "rgba(245,158,11,0.2)", "#D97706"
                    _wi_icon = "🔄"

                st.markdown(
                    f'<div style="background:{_wi_bg};border:1px solid {_wi_bdr_c};'
                    f'border-radius:14px;padding:1.1rem 1.25rem;margin-top:0.6rem;">'
                    f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:0.85rem;">'
                    f'<span style="font-size:1.3rem;">{_wi_icon}</span>'
                    f'<span style="font-size:0.95rem;font-weight:700;color:{_hd};">If you remove '
                    f'<span style="color:{_a};">{_wifn}</span> …</span>'
                    f'<span style="margin-left:auto;background:{_wi_badge_bg};color:{_wi_badge_txt};'
                    f'font-size:0.72rem;font-weight:700;border-radius:9999px;padding:3px 10px;">'
                    f'{_wi_badge}</span></div>'
                    f'<div style="display:flex;gap:2.5rem;flex-wrap:wrap;margin-bottom:0.85rem;'
                    f'padding-bottom:0.85rem;border-bottom:1px solid {_wi_bdr_c};">'
                    f'<div style="text-align:center;">'
                    f'<div style="font-size:1.6rem;font-weight:800;color:{_hd};">{_wi_unique_lost}</div>'
                    f'<div style="font-size:0.7rem;color:{_sb};margin-top:2px;line-height:1.4;">'
                    f'companies only this<br>fund invests in</div></div>'
                    f'<div style="text-align:center;">'
                    f'<div style="font-size:1.6rem;font-weight:800;color:{_hd};">{_wi_ov_without:.0f}%</div>'
                    f'<div style="font-size:0.7rem;color:{_sb};margin-top:2px;line-height:1.4;">'
                    f'avg overlap of<br>remaining funds</div></div></div>'
                    f'<div style="font-size:0.83rem;color:{_bd};line-height:1.65;">{_wi_line1}</div>'
                    + (f'<div style="font-size:0.83rem;color:{_bd};line-height:1.65;margin-top:0.55rem;">'
                       f'{_wi_line2}</div>' if _wi_line2 else "")
                    + f'</div>',
                    unsafe_allow_html=True,
                )
                st.caption("Analysis only — not investment advice.")


    # ── Tab 4: Sector & Cap Size ──────────────────────────────────────────────
    with tab_sec:
        st.markdown('<div class="section-title">Sector Concentration</div>', unsafe_allow_html=True)

        _sec_stocks = (
            sel_h.assign(sector=sel_h["sector"].map(_norm_sector_label_sc))
            .groupby("sector")["stock_name"]
            .nunique()
            .reset_index(name="n_stocks")
        )
        avg_sec = (
            sel_sector.groupby("sector", as_index=False)
            .agg(avg_alloc=("allocation_percent", "mean"))
            .sort_values("avg_alloc", ascending=False)
        )
        avg_sec = avg_sec.merge(_sec_stocks, on="sector", how="left")
        avg_sec["n_stocks"] = avg_sec["n_stocks"].fillna(0).astype(int)
        _sec_conc = avg_sec.rename(columns={"avg_alloc": "eff_alloc"})

        _sec_total = float(_sec_conc["eff_alloc"].sum()) if not _sec_conc.empty else 0.0
        st.markdown(
            f'<div class="section-sub">Average sector allocation across your funds (Avg Alloc %) — '
            f'sectors total {_sec_total:.1f}%</div>',
            unsafe_allow_html=True,
        )

        _sec_top_n = 8
        _sec_top = _sec_conc.head(_sec_top_n).copy()
        _sec_rest = _sec_conc.iloc[_sec_top_n:]
        _sec_pie = _sec_top.copy()
        if not _sec_rest.empty:
            _other_avg = float(_sec_rest["eff_alloc"].sum())
            _other_n = int(_sec_rest["n_stocks"].sum())
            _other_mask = _sec_pie["sector"].str.lower().eq("other")
            if _other_mask.any():
                _oi = _sec_pie.index[_other_mask][0]
                _sec_pie.loc[_oi, "eff_alloc"] += _other_avg
                _sec_pie.loc[_oi, "n_stocks"] += _other_n
            else:
                _sec_pie = pd.concat([_sec_pie, pd.DataFrame([{
                    "sector": "Other",
                    "eff_alloc": _other_avg,
                    "n_stocks": _other_n,
                }])], ignore_index=True)

        _sec_scale_max = float(_sec_conc["eff_alloc"].max()) if not _sec_conc.empty else 1.0

        c_donut, c_table = st.columns([2, 3])
        with c_donut:
            fig_d = px.pie(
                _sec_pie, names="sector", values="eff_alloc", hole=0.52, height=360,
            )
            fig_d.update_layout(
                **_dark_layout(
                    margin=dict(l=10, r=10, t=10, b=10),
                    font=_cf,
                    legend=dict(
                        orientation="h", yanchor="top", y=-0.08,
                        xanchor="center", x=0.5, font=dict(size=10, color=_sb),
                    ),
                )
            )
            _pie_text_sc = _sec_pie["eff_alloc"].map(lambda v: f"{v:.1f}%")
            fig_d.update_traces(
                textposition="inside",
                textinfo="text",
                text=_pie_text_sc,
                customdata=_sec_pie["eff_alloc"],
                hovertemplate="%{label}<br>%{customdata:.2f}% Avg Alloc<extra></extra>",
                insidetextfont=dict(size=11, color=_hd),
            )
            st.plotly_chart(fig_d, use_container_width=True, config={"displayModeBar": False})
        with c_table:
            _sec_table_html = _sector_exposure_table_html(
                _sec_top,
                hd=_hd, sb=_sb, bd=_bd, a=_a, cd=_cd, bdr=_bdr,
                col_amber=_col_amber, is_dark=_is_dark,
                weight_hdr="Avg Alloc",
                high_thresh=25.0,
                scale_max=_sec_scale_max,
            )
            st.markdown(_sec_table_html, unsafe_allow_html=True)
            if not _sec_rest.empty:
                _n_sec_rest = len(_sec_rest)
                _rest_avg = float(_sec_rest["eff_alloc"].sum())
                with st.expander(
                    f"Show {_n_sec_rest} more sector{'s' if _n_sec_rest != 1 else ''} "
                    f"({_rest_avg:.1f}% combined Avg Alloc)",
                    expanded=False,
                ):
                    _sec_rest_html = _sector_exposure_table_html(
                        _sec_rest,
                        hd=_hd, sb=_sb, bd=_bd, a=_a, cd=_cd, bdr=_bdr,
                        col_amber=_col_amber, is_dark=_is_dark,
                        weight_hdr="Avg Alloc",
                        high_thresh=25.0,
                        scale_max=_sec_scale_max,
                        show_header=False,
                    )
                    st.markdown(_sec_rest_html, unsafe_allow_html=True)
            st.markdown(
                f'<div style="font-size:0.62rem;color:{_sb};margin-top:6px;text-align:right;">'
                f'▲ HIGH = sector ≥25% average allocation across funds</div>',
                unsafe_allow_html=True,
            )

        # Cap-size breakdown
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-title">Cap Size Distribution</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">How your investment is spread across market cap categories</div>', unsafe_allow_html=True)

        if not master.empty and "category" in master.columns:
            cat_map = dict(zip(master["fund_name"], master["category"]))
            cap_rows = []
            for fund in matched_funds:
                cat = cat_map.get(fund, "Other")
                cap_rows.append({"category": cat, "weight": weight_map.get(fund, 0), "fund": display_name(fund)})
            cap_df = pd.DataFrame(cap_rows)
            cap_agg = cap_df.groupby("category")["weight"].sum().reset_index()
            cap_agg["pct"] = (cap_agg["weight"] / cap_agg["weight"].sum() * 100).round(1)
            cap_agg = cap_agg.sort_values("pct", ascending=False)

            CAP_COLORS = {
                "Large Cap": "#6C3CE1", "Mid Cap": "#F97316", "Small Cap": "#0891B2",
                "Large & Mid Cap": "#16A34A", "Multi Cap": "#E11D48",
                "Flexi Cap": "#8B5CF6", "ELSS": "#F59E0B", "Other": "#9CA3AF",
            }
            fig_cap = px.bar(
                cap_agg, x="pct", y="category", orientation="h",
                color="category", color_discrete_map=CAP_COLORS,
                labels={"pct": "Portfolio Weight %", "category": ""},
                text="pct", height=max(200, 50 * len(cap_agg)),
            )
            fig_cap.update_traces(texttemplate="%{text:.1f}%", textposition="outside",
                                   textfont=dict(color=_bd, size=11),
                                   marker_line_width=0, showlegend=False)
            fig_cap.update_layout(
                **_dark_layout(
                    margin=dict(l=0, r=70, t=10, b=10),
                    font=_cf,
                    xaxis=_dark_xaxis(showgrid=False),
                    yaxis=_dark_yaxis(showgrid=False, gridcolor=_cg, zerolinecolor=_cg),
                )
            )
            st.plotly_chart(fig_cap, use_container_width=True, config={"displayModeBar": False})

            # Fund-level cap table
            fund_cap_tbl = cap_df[["fund", "category"]].copy()
            fund_cap_tbl.columns = ["Fund", "Category"]
            if has_amounts and total_invested > 0:
                fund_cap_tbl["Invested ₹"] = fund_cap_tbl["Fund"].apply(
                    lambda fn: amount_map.get(next((f for f in matched_funds if display_name(f) == fn), ""), 0)
                )
            st.dataframe(fund_cap_tbl, use_container_width=True, hide_index=True,
                         height=36 * len(fund_cap_tbl) + 38)

    # ── Tab 5: Insights (priority flags + detailed notes) ─────────────────────
    with tab_ins:
        st.markdown('<div class="section-title">Portfolio Insights</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-sub">Priority warnings first, then deeper notes by topic — '
            'for learning only, not advice</div>',
            unsafe_allow_html=True,
        )

        _render_concentration_flags(
            matched_funds=matched_funds,
            sel_sim=sel_sim,
            sel_h=sel_h,
            sel_sector=sel_sector,
            sel_master=sel_master,
            master=master,
            weight_map=weight_map,
            hd=_hd, bd=_bd, al=_al, bdr=_bdr,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div style="margin:0 0 0.5rem;">'
            f'<div style="font-size:0.95rem;font-weight:700;color:{_hd};">'
            f'📚 More detail by topic</div>'
            f'<div style="font-size:0.72rem;color:{_bd};margin-top:2px;">'
            f'Broader observations — including positive notes. Expand each section.</div></div>',
            unsafe_allow_html=True,
        )

        insights = generate_insights(matched_funds, similarity, holdings, sector_df, master)
        _render_categorized_insights(
            insights,
            hd=_hd, sb=_sb, bd=_bd, al=_al, bdr=_bdr,
            page_key="xray",
            empty_msg="No clear patterns stood out for your portfolio. Check the other X-Ray tabs for details.",
        )

        st.markdown(
            '<div class="disclaimer">These notes help you understand how your funds are built. '
            "They are not buy, sell, or hold advice.</div>",
            unsafe_allow_html=True,
        )


# ── ROUTER ────────────────────────────────────────────────────────────────────

# ── PAGE: STOCK EXPLORER ─────────────────────────────────────────────────────

def page_stock_explorer():
    t_name, t = _fl_get_theme()
    _fl_inject_css(t, t_name)
    _fl_render_navbar(t, t_name, "analyse_funds")
    _fl_render_breadcrumb([("Home", "home"), ("Analyse Funds", "analyse_funds"), ("Inspect a Stock", None)])

    holdings = load_holdings()
    if holdings.empty:
        st.warning("Holdings data not available.")
        return

    st.markdown("## Stock Explorer")
    st.markdown(
        f"<p style='color:{t['body']};margin-top:-0.5rem;margin-bottom:1.5rem;'>"
        "Select any stock to see which funds hold it, how much they allocate, and whether managers "
        "are buying more or trimming. For informational purposes only — not investment advice.</p>",
        unsafe_allow_html=True,
    )

    _a   = t["a"];   _al  = t["al"];  _bg  = t["bg"]
    _bdr = t["bdr"]; _bd  = t["body"]; _hd = t["head"]
    _cd  = t["card"]; _sb = t["sub"]

    all_stocks  = sorted(holdings["stock_name"].unique().tolist())
    preselected = st.session_state.pop("preselected_stock", "")
    default_idx = all_stocks.index(preselected) if preselected in all_stocks else 0

    selected_stock = st.selectbox("Search for a stock", all_stocks, index=default_idx)
    if not selected_stock:
        return

    stock_df = holdings[holdings["stock_name"] == selected_stock].sort_values(
        "allocation_percent", ascending=False
    ).reset_index(drop=True)

    n_holding   = len(stock_df)
    avg_alloc   = stock_df["allocation_percent"].mean()
    max_alloc   = stock_df["allocation_percent"].max()
    max_fund    = stock_df.loc[stock_df["allocation_percent"].idxmax(), "fund_name"]
    sector      = stock_df["sector"].mode().iloc[0] if not stock_df.empty else "—"
    total_funds = holdings["fund_name"].nunique()
    avg_3m      = stock_df["change_3m_percent"].mean()

    # ── 4 metric cards ──────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    for col, val, label, sub in [
        (c1, str(n_holding),        "Funds Holding",      f"Out of {total_funds} funds"),
        (c2, f"{avg_alloc:.2f}%",   "Avg Allocation",     "Across holding funds"),
        (c3, f"{max_alloc:.2f}%",   "Highest Conviction", display_name(max_fund, 24)),
        (c4, sector.title(),        "Sector",             "Primary classification"),
    ]:
        with col:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-value" style="font-size:1.65rem;">{val}</div>'
                f'<div class="metric-label">{label}</div>'
                f'<div class="metric-sub">{sub}</div>'
                f'</div>', unsafe_allow_html=True)

    # ── Pre-compute all data ─────────────────────────────────────────────────────
    master_tmp = load_master()
    cat_map_se = master_tmp.set_index("fund_name")["category"].to_dict() if not master_tmp.empty else {}
    stock_df["category"] = stock_df["fund_name"].map(cat_map_se).fillna("Other")

    _CAT_COLORS_SE = {
        "Large Cap": "#6366F1", "Mid Cap": "#F59E0B", "Small Cap": "#10B981",
        "Large & Mid Cap": "#06B6D4", "Multi Cap": "#8B5CF6",
        "Flexi Cap": "#F472B6", "ELSS": "#34D399", "Other": "#94A3B8",
    }
    cat_df_se = (
        stock_df.groupby("category")
        .agg(avg_alloc=("allocation_percent", "mean"), fund_count=("fund_name", "count"))
        .reset_index().sort_values("avg_alloc", ascending=False)
    )
    top_cat_row  = cat_df_se.iloc[0] if not cat_df_se.empty else None
    cat_df_chart = cat_df_se.sort_values("avg_alloc", ascending=True)

    _time_labels = ["1Y ago", "6M ago", "3M ago", "Now"]
    _period_map  = {"1Y ago": "1 year", "6M ago": "6 months", "3M ago": "3 months"}
    trend_rows   = []
    for _, _tr in stock_df.iterrows():
        _tc = str(_tr.get("category", "Other")).replace("nan", "Other")
        _cu = _tr["allocation_percent"]
        try:    _d3  = _cu - float(_tr["change_3m_percent"])
        except: _d3  = None
        try:    _d6  = _cu - float(_tr["change_6m_percent"])
        except: _d6  = None
        try:    _d1y = _cu - float(_tr["change_1y_percent"])
        except: _d1y = None
        trend_rows.append({"category": _tc, "1Y ago": _d1y, "6M ago": _d6, "3M ago": _d3, "Now": _cu})
    _trend_df  = pd.DataFrame(trend_rows)
    _cat_trend = _trend_df.groupby("category")[_time_labels].mean().reset_index()
    _cat_trend = _cat_trend.dropna(subset=["1Y ago", "6M ago", "3M ago"], how="all")
    _cats_list = _cat_trend.to_dict("records")

    _top_fn      = display_name(stock_df.iloc[0]["fund_name"], 28)
    _top_alloc   = stock_df.iloc[0]["allocation_percent"]
    _top_cat_lbl = (f"Highest: {top_cat_row['category']} at {top_cat_row['avg_alloc']:.2f}%"
                    if top_cat_row is not None else "")

    def _trend_chip_se(row):
        try:
            v3 = float(row["change_3m_percent"])
            return ("↑ Buying", "#059669") if v3 > 0.3 else \
                   ("↓ Trimming", "#DC2626") if v3 < -0.3 else ("→ Holding", "#6366F1")
        except Exception:
            return ("—", "#94A3B8")

    def _hex_rgba(hex_col, alpha):
        h = hex_col.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    def _delta_cell(val):
        try:
            v = float(val)
            if v > 0:   return f'<span style="color:#059669;font-weight:600;">+{v:.2f}%</span>'
            elif v < 0: return f'<span style="color:#DC2626;font-weight:600;">{v:.2f}%</span>'
            else:       return f'<span style="color:#94A3B8;">0.00%</span>'
        except Exception:
            return f'<span style="color:#94A3B8;">—</span>'

    def _trend_badge_tbl(row):
        try:
            v3 = float(row["change_3m_percent"])
            if v3 > 0.3:    return '<span style="color:#059669;font-size:0.7rem;font-weight:700;">↑ Buying</span>'
            elif v3 < -0.3: return '<span style="color:#DC2626;font-size:0.7rem;font-weight:700;">↓ Trimming</span>'
            else:            return '<span style="color:#6366F1;font-size:0.7rem;font-weight:700;">→ Holding</span>'
        except Exception:
            return '<span style="color:#94A3B8;font-size:0.7rem;">—</span>'

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Expander 1: Who holds it ──────────────────────────────────────────────────
    with st.expander(
        f"🏦  Who holds it & how much?   ·   {n_holding} funds   ·   Top: {_top_alloc:.2f}% — {_top_fn}",
        expanded=False,
    ):
        _max_bar   = stock_df["allocation_percent"].max()
        _cards_html = ""
        for i, row in stock_df.iterrows():
            fn        = display_name(row["fund_name"], 36)
            alloc     = row["allocation_percent"]
            bar_w     = int(alloc / _max_bar * 100) if _max_bar > 0 else 0
            chip_txt, chip_col = _trend_chip_se(row)
            cat       = str(row.get("category", "")).replace("nan", "")
            rank_col  = _a if i == 0 else (_sb if i >= 5 else _hd)
            _cards_html += (
                f'<div style="display:flex;align-items:center;gap:12px;padding:10px 0;'
                f'border-bottom:1px solid {_bdr};">'
                f'<span style="font-size:0.7rem;font-weight:700;color:{rank_col};min-width:24px;'
                f'text-align:right;">#{i+1}</span>'
                f'<div style="flex:1;min-width:0;">'
                f'<div style="font-size:0.8rem;font-weight:600;color:{_hd};line-height:1.3;">{fn}</div>'
                f'<div style="font-size:0.62rem;color:{_sb};margin-bottom:4px;">{cat}</div>'
                f'<div style="display:flex;align-items:center;gap:8px;">'
                f'<div style="flex:1;height:4px;border-radius:2px;background:{_bdr};">'
                f'<div style="width:{bar_w}%;height:100%;border-radius:2px;background:{_a};"></div>'
                f'</div>'
                f'<span style="font-size:0.75rem;font-weight:700;color:{_a};min-width:40px;'
                f'text-align:right;">{alloc:.2f}%</span>'
                f'</div></div>'
                f'<span style="font-size:0.62rem;font-weight:600;color:{chip_col};'
                f'background:{chip_col}18;border-radius:20px;padding:3px 9px;'
                f'white-space:nowrap;flex-shrink:0;">{chip_txt}</span>'
                f'</div>'
            )
        st.markdown(
            f'<div style="max-height:480px;overflow-y:auto;">{_cards_html}</div>',
            unsafe_allow_html=True,
        )

    # ── Expander 2: Category breakdown ───────────────────────────────────────────
    with st.expander(f"📊  Which categories hold it most?   ·   {_top_cat_lbl}", expanded=False):
        st.markdown(
            f'<div class="section-sub">Avg % of a fund\'s portfolio in this stock — grouped by category</div>',
            unsafe_allow_html=True,
        )
        _bar_colors = [_CAT_COLORS_SE.get(c, "#94A3B8") for c in cat_df_chart["category"]]
        fig_cat = go.Figure(go.Bar(
            x=cat_df_chart["avg_alloc"], y=cat_df_chart["category"], orientation="h",
            marker_color=_bar_colors, marker_line_width=0,
            text=[f'avg {v:.2f}%  ·  {int(n)} fund{"s" if n > 1 else ""}' for v, n in
                  zip(cat_df_chart["avg_alloc"], cat_df_chart["fund_count"])],
            textposition="outside", textfont=dict(size=11, color=_bd), cliponaxis=False,
        ))
        fig_cat.update_layout(**_dark_layout(
            height=max(200, len(cat_df_chart) * 44 + 40),
            margin=dict(l=10, r=170, t=10, b=10),
            xaxis=_dark_xaxis(showgrid=True, gridcolor=_CHART_GRID,
                              title="Avg % of fund portfolio",
                              title_font=dict(size=10, color=_sb)),
            yaxis=dict(tickfont=dict(size=11, color=_bd), showgrid=False),
        ))
        st.plotly_chart(fig_cat, use_container_width=True, config={"displayModeBar": False})

    # ── Expander 3: Category sparklines ──────────────────────────────────────────
    with st.expander("📈  How has each category's holding changed?", expanded=False):
        st.markdown(
            f'<div class="section-sub">Average allocation per category — 1Y ago → 6M ago → 3M ago → Now</div>',
            unsafe_allow_html=True,
        )
        if not _cats_list:
            st.info("Not enough historical data to show trends for this stock.")
        else:
            for _rs in range(0, len(_cats_list), 3):
                _row_cats = _cats_list[_rs: _rs + 3]
                _scols    = st.columns(3)
                for _ci, _crow in enumerate(_row_cats):
                    with _scols[_ci]:
                        _cat   = _crow["category"]
                        _col_c = _CAT_COLORS_SE.get(_cat, "#94A3B8")
                        _xpts  = [t for t in _time_labels if pd.notna(_crow.get(t))]
                        _ypts  = [_crow[t] for t in _time_labels if pd.notna(_crow.get(t))]
                        if len(_xpts) < 2:
                            continue
                        _change     = _ypts[-1] - _ypts[0]
                        _ch_col     = "#059669" if _change >= 0 else "#DC2626"
                        _period_lbl = _period_map.get(_xpts[0], "the period")
                        _change_str = f"{'+' if _change >= 0 else ''}{_change:.2f}% over {_period_lbl}"
                        _fig_m = go.Figure()
                        _fig_m.add_trace(go.Scatter(
                            x=_xpts, y=_ypts, mode="lines+markers",
                            line=dict(color=_col_c, width=2.5),
                            marker=dict(size=7, color=_col_c, line=dict(width=1.5, color="#ffffff")),
                            fill="tozeroy", fillcolor=_hex_rgba(_col_c, 0.15),
                            hovertemplate="%{x}: <b>%{y:.2f}%</b><extra></extra>",
                        ))
                        _fig_m.update_layout(
                            paper_bgcolor=_cd, plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(family="Inter, sans-serif"),
                            height=160, margin=dict(l=10, r=10, t=56, b=10),
                            showlegend=False,
                            xaxis=dict(showticklabels=False, showgrid=False,
                                       showline=False, zeroline=False, fixedrange=True),
                            yaxis=dict(showticklabels=False, showgrid=False,
                                       showline=False, zeroline=False, fixedrange=True),
                            annotations=[
                                dict(text=f"<b>{_cat}</b>", x=0.04, y=1,
                                     xref="paper", yref="paper", xanchor="left",
                                     yanchor="bottom", showarrow=False, yshift=30,
                                     font=dict(size=12, color=_hd, family="Inter, sans-serif")),
                                dict(text=_change_str, x=0.04, y=1,
                                     xref="paper", yref="paper", xanchor="left",
                                     yanchor="bottom", showarrow=False, yshift=10,
                                     font=dict(size=10, color=_ch_col, family="Inter, sans-serif")),
                            ],
                            shapes=[dict(type="rect", xref="paper", yref="paper",
                                         x0=0, y0=0, x1=1, y1=1,
                                         line=dict(color=_bdr, width=1), layer="below")],
                        )
                        st.plotly_chart(_fig_m, use_container_width=True,
                                        config={"displayModeBar": False, "staticPlot": True})

    # ── Expander 4: Full breakdown table ─────────────────────────────────────────
    with st.expander(f"📋  Full breakdown  ·  all {n_holding} funds", expanded=False):
        _max_alloc = stock_df["allocation_percent"].max()
        _rows_html = ""
        for i, row in stock_df.iterrows():
            fn      = display_name(row["fund_name"], 36)
            alloc   = row["allocation_percent"]
            bar_w   = int(alloc / _max_alloc * 100) if _max_alloc > 0 else 0
            cat     = str(row.get("category", "Other")).replace("nan", "Other")
            cat_col = _CAT_COLORS_SE.get(cat, "#94A3B8")
            row_bg  = _al if i % 2 == 0 else _cd
            _rows_html += (
                f'<tr style="background:{row_bg};border-bottom:1px solid {_bdr};">'
                f'<td style="padding:10px 14px;min-width:200px;">'
                f'<div style="font-size:0.78rem;font-weight:600;color:{_hd};line-height:1.3;">{fn}</div>'
                f'<span style="font-size:0.6rem;font-weight:600;color:{cat_col};background:{cat_col}20;'
                f'border-radius:20px;padding:2px 7px;display:inline-block;margin-top:3px;">{cat}</span>'
                f'</td>'
                f'<td style="padding:10px 14px;min-width:140px;">'
                f'<div style="display:flex;align-items:center;gap:8px;">'
                f'<div style="flex:1;height:6px;border-radius:3px;background:{_bdr};">'
                f'<div style="width:{bar_w}%;height:100%;border-radius:3px;background:{_a};"></div>'
                f'</div>'
                f'<span style="font-size:0.78rem;font-weight:700;color:{_a};white-space:nowrap;">'
                f'{alloc:.2f}%</span></div></td>'
                f'<td style="padding:10px 14px;white-space:nowrap;">{_trend_badge_tbl(row)}</td>'
                f'<td style="padding:10px 14px;text-align:right;">{_delta_cell(row.get("change_3m_percent"))}</td>'
                f'<td style="padding:10px 14px;text-align:right;">{_delta_cell(row.get("change_6m_percent"))}</td>'
                f'<td style="padding:10px 14px;text-align:right;">{_delta_cell(row.get("change_1y_percent"))}</td>'
                f'</tr>'
            )
        _th = lambda lbl, align="left": (
            f'<th style="padding:10px 14px;text-align:{align};font-size:0.7rem;font-weight:700;'
            f'color:{_sb};text-transform:uppercase;letter-spacing:0.5px;">{lbl}</th>'
        )
        st.markdown(
            f'<div style="overflow-x:auto;border-radius:12px;border:1px solid {_bdr};">'
            f'<table style="width:100%;border-collapse:collapse;">'
            f'<thead><tr style="background:{_al};border-bottom:2px solid {_bdr};">'
            f'{_th("Fund")}{_th("Allocation")}{_th("3M Trend")}'
            f'{_th("3M Δ","right")}{_th("6M Δ","right")}{_th("1Y Δ","right")}'
            f'</tr></thead><tbody>{_rows_html}</tbody></table></div>',
            unsafe_allow_html=True,
        )

    # ── Insights ─────────────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">Insights</div>', unsafe_allow_html=True)

    coverage = n_holding / total_funds * 100

    # 1. Coverage / market consensus
    if coverage >= 80:
        st.markdown(
            f'<div class="insight-card insight-alert"><div class="insight-icon">⚠️</div>'
            f'<div class="insight-text"><strong>Near-universal holding — {n_holding}/{total_funds} funds ({coverage:.0f}%)</strong> — '
            f'{selected_stock} is owned by almost every fund in this dataset. If you hold multiple funds, '
            f'your actual combined exposure to this stock is likely much larger than any single fund\'s number shows. '
            f'Open <strong>Who holds it</strong> above to see each fund\'s position size.</div></div>',
            unsafe_allow_html=True)
    elif coverage >= 50:
        st.markdown(
            f'<div class="insight-card insight-warning"><div class="insight-icon">📊</div>'
            f'<div class="insight-text"><strong>Held by most funds — {n_holding}/{total_funds} ({coverage:.0f}%)</strong> — '
            f'{selected_stock} is a popular pick in this segment. Investors holding 2+ funds very likely '
            f'own it through multiple routes, amplifying their real exposure. '
            f'Check <strong>Who holds it</strong> above to assess combined weight.</div></div>',
            unsafe_allow_html=True)
    elif coverage >= 25:
        st.markdown(
            f'<div class="insight-card insight-info"><div class="insight-icon">🔍</div>'
            f'<div class="insight-text"><strong>Selectively held — {n_holding}/{total_funds} funds ({coverage:.0f}%)</strong> — '
            f'{selected_stock} is not a broad-market consensus pick. The funds that own it are making '
            f'a more deliberate, focused bet. See <strong>Which categories hold it</strong> to identify '
            f'which fund types favour this name.</div></div>',
            unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="insight-card insight-info"><div class="insight-icon">🔍</div>'
            f'<div class="insight-text"><strong>High-conviction minority pick — {n_holding}/{total_funds} funds ({coverage:.0f}%)</strong> — '
            f'Very few funds hold {selected_stock}. Those that do are making a strong, deliberate bet '
            f'that most others skip. See <strong>Which categories hold it</strong> to identify which '
            f'fund types favour this name.</div></div>',
            unsafe_allow_html=True)

    # 2. Top holder standout
    if n_holding > 1 and _top_alloc > avg_alloc * 1.8:
        st.markdown(
            f'<div class="insight-card insight-info"><div class="insight-icon">🎯</div>'
            f'<div class="insight-text"><strong>{_top_fn} has an outsized position</strong> — at '
            f'<strong>{_top_alloc:.2f}%</strong>, it holds nearly double the average of '
            f'<strong>{avg_alloc:.2f}%</strong> across all funds holding this stock. '
            f'This fund has significantly higher conviction in {selected_stock} than its peers.</div></div>',
            unsafe_allow_html=True)

    # 3. Allocation spread (conviction disagreement)
    alloc_spread = stock_df["allocation_percent"].max() - stock_df["allocation_percent"].min()
    if alloc_spread > 3 and n_holding > 1:
        _bot_row   = stock_df.iloc[-1]
        _bot_fn    = display_name(_bot_row["fund_name"], 28)
        _bot_alloc = _bot_row["allocation_percent"]
        st.markdown(
            f'<div class="insight-card insight-info"><div class="insight-icon">📐</div>'
            f'<div class="insight-text"><strong>Fund managers disagree sharply on how much to hold</strong> — '
            f'<strong>{_top_fn}</strong> allocates <strong>{_top_alloc:.2f}%</strong> while '
            f'<strong>{_bot_fn}</strong> holds just <strong>{_bot_alloc:.2f}%</strong> '
            f'({alloc_spread:.2f}% spread). Some see {selected_stock} as a core holding; '
            f'others treat it as a small, token position.</div></div>',
            unsafe_allow_html=True)

    # 4. Category concentration
    if top_cat_row is not None and not cat_df_se.empty and n_holding > 2:
        _top_cat_name  = top_cat_row["category"]
        _top_cat_count = int(top_cat_row["fund_count"])
        _top_cat_pct   = _top_cat_count / n_holding * 100
        n_cats = len(cat_df_se)
        if _top_cat_pct >= 60:
            st.markdown(
                f'<div class="insight-card insight-info"><div class="insight-icon">🏷️</div>'
                f'<div class="insight-text"><strong>Dominant in {_top_cat_name} funds</strong> — '
                f'{_top_cat_count} of {n_holding} funds holding {selected_stock} are {_top_cat_name} funds '
                f'({_top_cat_pct:.0f}%). It\'s a particularly strong pick within this category. '
                f'See <strong>Which categories</strong> above for the full breakdown.</div></div>',
                unsafe_allow_html=True)
        elif n_cats >= 4:
            _first_cat = cat_df_se["category"].iloc[0]
            _last_cat  = cat_df_se["category"].iloc[-1]
            st.markdown(
                f'<div class="insight-card insight-success"><div class="insight-icon">🌐</div>'
                f'<div class="insight-text"><strong>Broad consensus across {n_cats} fund categories</strong> — '
                f'{selected_stock} is held across fund types from {_first_cat} to {_last_cat}. '
                f'Agreement across different fund styles is a stronger signal than concentration in one category alone.</div></div>',
                unsafe_allow_html=True)

    # 5. Momentum with 6M context
    avg_6m = stock_df["change_6m_percent"].mean() if "change_6m_percent" in stock_df.columns else float("nan")
    if not pd.isna(avg_3m):
        if avg_3m > 0.1:
            if not pd.isna(avg_6m) and avg_6m > 0.1:
                _trend_txt = (
                    f'<strong>Sustained buying — managers have increased their stake for at least 6 months</strong> '
                    f'(6M avg: <strong>{avg_6m:+.2f}%</strong>, 3M avg: <strong>{avg_3m:+.2f}%</strong>). '
                    f'A consistent directional move across independent fund managers.'
                )
            else:
                _trend_txt = (
                    f'<strong>Recent accumulation in {selected_stock}</strong> — funds added an average '
                    f'<strong>{avg_3m:+.2f}%</strong> over 3 months. '
                    f'Short-term buying signal without a confirmed 6-month pattern yet.'
                )
            st.markdown(
                f'<div class="insight-card insight-success"><div class="insight-icon">📈</div>'
                f'<div class="insight-text">{_trend_txt}</div></div>',
                unsafe_allow_html=True)
        elif avg_3m < -0.1:
            if not pd.isna(avg_6m) and avg_6m < -0.1:
                _trend_txt = (
                    f'<strong>Sustained trimming — managers have been cutting their stake for at least 6 months</strong> '
                    f'(6M avg: <strong>{avg_6m:+.2f}%</strong>, 3M avg: <strong>{avg_3m:+.2f}%</strong>). '
                    f'A consistent signal of reduced conviction across independent fund managers.'
                )
            else:
                _trend_txt = (
                    f'<strong>Recent trimming in {selected_stock}</strong> — funds cut their stake by an average '
                    f'<strong>{avg_3m:+.2f}%</strong> over 3 months. '
                    f'Worth monitoring whether this extends into a longer 6-month pattern.'
                )
            st.markdown(
                f'<div class="insight-card insight-warning"><div class="insight-icon">📉</div>'
                f'<div class="insight-text">{_trend_txt}</div></div>',
                unsafe_allow_html=True)

    st.markdown(
        '<div class="disclaimer">Stock exposure data is for informational and analytical purposes '
        'only — not investment advice.</div>',
        unsafe_allow_html=True)


# ── PAGE: OVERLAP MATRIX ────────────────────────────────────────────────────────


def _overlap_bubble_chart_fig(
    graph,
    theme: dict,
    master,
    fund_a: str | None,
    fund_b: str | None,
    return_period: str,
    *,
    ns: str = "overlap_matrix",
):
    """Plotly scatter: X = overlap% with fund_a, Y = trailing return, ideal = top-left."""
    import plotly.graph_objects as go
    from analytics.overlap_filters import fund_return_pct
    from analytics.overlap_graph import fund_label, pair_score

    _hd   = theme["head"];  _sb = theme["sub"];  _bd = theme["body"]
    _a    = theme["a"];     _al = theme["al"];   _bdr = theme["bdr"]
    _cd   = theme["card"];  _is_dark = theme.get("is_dark", False)

    # Overlap bucket colours (consistent with rest of app)
    def _bucket_color(pct: float):
        if pct >= 60: return "#EF4444"   # Very High — red
        if pct >= 45: return "#F59E0B"   # High — amber
        if pct >= 30: return "#6C3CE1"   # Moderate — purple (accent)
        if pct >= 15: return "#10B981"   # Good — green
        return "#34D399"                  # Excellent — light green

    def _bucket_label(pct: float):
        if pct >= 60: return "Very High"
        if pct >= 45: return "High"
        if pct >= 30: return "Moderate"
        if pct >= 15: return "Good"
        return "Excellent"

    funds  = graph.funds
    labels = [fund_label(f, max_len=22) for f in funds]

    if not fund_a or fund_a not in funds:
        return None  # caller shows "select a base fund" prompt

    # Build per-fund data (excluding fund_a — added separately as base marker)
    xs, ys, colors, texts, hovers, sizes = [], [], [], [], [], []

    valid_funds, valid_labels = [], []
    for f, lbl in zip(funds, labels):
        if f == fund_a:
            continue
        ov  = pair_score(graph.lookup, fund_a, f)
        ret = fund_return_pct(master, f, return_period)
        if ret is None:
            continue
        col = _bucket_color(ov)
        xs.append(float(ov))
        ys.append(float(ret))
        colors.append(col)
        sizes.append(22)
        texts.append(lbl)
        hovers.append(
            f"<b>{lbl}</b><br>"
            f"Overlap with base fund: <b>{ov:.0f}%</b> ({_bucket_label(ov)})<br>"
            f"{return_period} return: <b>{ret:+.1f}%</b>"
        )
        valid_funds.append(f)
        valid_labels.append(lbl)

    if not xs:
        return None

    # Base fund return (for its Y position)
    _base_ret = fund_return_pct(master, fund_a, return_period)
    _base_lbl = fund_label(fund_a, max_len=22)

    # Find best pair: score = low overlap + high return → minimise overlap - return
    scores   = [ov - ret for ov, ret in zip(xs, ys)]
    best_idx = int(min(range(len(scores)), key=lambda i: scores[i]))

    # Highlight selected fund_b with thicker border
    marker_colors, marker_lines, marker_lw = [], [], []
    for i, f in enumerate(valid_funds):
        if f == fund_b:
            marker_colors.append(colors[i])
            marker_lines.append(_hd)
            marker_lw.append(3)
        else:
            marker_colors.append(colors[i])
            marker_lines.append(_bdr)
            marker_lw.append(1)

    fig = go.Figure()

    # ── Main scatter (all funds except base) ─────────────────────────────────
    fig.add_trace(go.Scatter(
        x=xs, y=ys,
        mode="markers+text",
        marker=dict(
            size=sizes,
            color=marker_colors,
            line=dict(color=marker_lines, width=marker_lw),
            opacity=0.85,
        ),
        text=texts,
        textposition="top center",
        textfont=dict(size=10, color=_bd, family="Inter, sans-serif"),
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hovers,
        name="",
    ))

    # ── Base fund marker (pinned at X=0, its own return on Y) ────────────────
    if _base_ret is not None:
        fig.add_trace(go.Scatter(
            x=[0], y=[float(_base_ret)],
            mode="markers+text",
            marker=dict(
                symbol="diamond",
                size=18,
                color=_a,
                line=dict(color=_hd, width=2),
                opacity=1.0,
            ),
            text=[f"📍 {_base_lbl}"],
            textposition="top center",
            textfont=dict(size=10, color=_a, family="Inter, sans-serif"),
            hovertemplate=(
                f"<b>📍 Base fund: {_base_lbl}</b><br>"
                f"This is your selected base fund (X = 0%)<br>"
                f"{return_period} return: <b>{_base_ret:+.1f}%</b>"
                f"<extra></extra>"
            ),
            name="Base fund",
            showlegend=False,
        ))

    # ── Star on best pair ─────────────────────────────────────────────────────
    if best_idx is not None:
        fig.add_trace(go.Scatter(
            x=[xs[best_idx]], y=[ys[best_idx]],
            mode="markers",
            marker=dict(
                symbol="star",
                size=18,
                color=colors[best_idx],
                line=dict(color=_hd, width=1.5),
            ),
            hovertemplate=f"<b>★ Best pair</b><br>{hovers[best_idx]}<extra></extra>",
            name="Best pair",
            showlegend=False,
        ))

    # "Ideal zone" annotation (top-left) — always starts from X=0 (base fund)
    all_x   = xs + [0]  # include base fund x
    all_y   = ys + ([float(_base_ret)] if _base_ret is not None else [])
    x_mid   = (min(all_x) + max(all_x)) / 2
    y_mid   = (min(all_y) + max(all_y)) / 2
    x_range = max(all_x) - min(all_x) or 1
    y_range = max(all_y) - min(all_y) or 1
    fig.add_shape(type="rect",
        x0=-x_range * 0.04, x1=x_mid, y0=y_mid, y1=max(all_y) + y_range * 0.08,
        fillcolor="rgba(16,185,129,0.06)" if not _is_dark else "rgba(52,211,153,0.06)",
        line=dict(width=0),
        layer="below",
    )
    fig.add_annotation(
        x=min(all_x), y=max(all_y),
        text="⭐ Ideal zone<br>Low overlap + High return",
        showarrow=False,
        font=dict(size=9, color="#10B981", family="Inter, sans-serif"),
        xanchor="left", yanchor="top",
        bgcolor="rgba(16,185,129,0.10)",
        bordercolor="rgba(16,185,129,0.3)",
        borderwidth=1, borderpad=4,
    )

    # Axis labels
    base_lbl = fund_label(fund_a, max_len=24)
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=_bd, size=11),
        height=440,
        margin=dict(l=10, r=20, t=30, b=60),
        xaxis=dict(
            title=dict(text=f"Overlap % with {base_lbl} →", font=dict(size=11, color=_sb)),
            ticksuffix="%", gridcolor=_bdr, zerolinecolor=_bdr,
            tickfont=dict(color=_sb, size=10),
            range=[-5, max(xs + [0]) + 8] if xs else [-5, 105],
        ),
        yaxis=dict(
            title=dict(text=f"↑ {return_period} return", font=dict(size=11, color=_sb)),
            ticksuffix="%", gridcolor=_bdr, zerolinecolor=_bdr,
            tickfont=dict(color=_sb, size=10),
        ),
        showlegend=False,
        hoverlabel=dict(
            bgcolor=_cd, bordercolor=_bdr,
            font=dict(color=_hd, size=12, family="Inter, sans-serif"),
        ),
    )

    # Best pair callout text
    best_fund_lbl = valid_labels[best_idx] if best_idx is not None else "—"
    best_ov       = xs[best_idx] if best_idx is not None else 0
    best_ret      = ys[best_idx] if best_idx is not None else 0

    return fig, valid_funds, best_fund_lbl, best_ov, best_ret


def _overlap_bubble_guide_html(theme: dict, *, has_base: bool, return_period: str = "5Y") -> str:
    """User-facing guide for the overlap bubble chart (pick base fund or read the chart)."""
    _hd = theme["head"]
    _bd = theme["body"]
    _sb = theme["sub"]
    _a = theme["a"]
    _al = theme["al"]
    _bdr = theme["bdr"]

    def _step(n: int, title: str, body: str) -> str:
        return (
            f'<div style="display:flex;gap:10px;margin-bottom:10px;align-items:flex-start;">'
            f'<div style="flex-shrink:0;width:22px;height:22px;border-radius:50%;background:{_a};'
            f'color:#fff;font-size:0.72rem;font-weight:700;display:flex;align-items:center;'
            f'justify-content:center;">{n}</div>'
            f'<div>'
            f'<div style="font-size:0.82rem;font-weight:700;color:{_hd};margin-bottom:2px;">{title}</div>'
            f'<div style="font-size:0.78rem;color:{_bd};line-height:1.55;">{body}</div>'
            f'</div></div>'
        )

    if not has_base:
        steps = (
            _step(
                1,
                "Open the panel on the right",
                'Look for <strong>Pick a base fund</strong> on the right side of this page.',
            )
            + _step(
                2,
                "Pick your base fund",
                'Use the <strong>dropdown list</strong> under those slots and choose the fund you already hold '
                'or want to compare against — e.g. "I have ICICI Large Cap; which fund should I add?". '
                'Your first selection fills the highlighted <strong>Base fund</strong> pill on the right.',
            )
            + _step(
                3,
                "Chart appears here",
                'Once your base fund is set, this chart loads automatically. Every bubble shows how another fund '
                'overlaps with your base fund and how it has performed.',
            )
        )
        tip = (
            f'<div style="font-size:0.75rem;color:{_sb};margin-top:4px;padding-top:8px;'
            f'border-top:1px solid {_bdr};">'
            f'<strong>Tip:</strong> You can also pick your base fund on the <strong>Overlap Graph</strong> view '
            f'(click any node), then switch back to <strong>Bubble Chart</strong>.'
            f'</div>'
        )
        title = "How to get started"
        intro = (
            'The bubble chart answers: <em>"Which fund pairs best with the one I already have?"</em> '
            'You need to choose a <strong>base fund</strong> first.'
        )
    else:
        steps = (
            _step(
                1,
                "Read the axes",
                f'<strong>Horizontal:</strong> Overlap % with your base fund. '
                f'<strong>Further left = less overlap = better diversification.</strong><br>'
                f'<strong>Vertical:</strong> {return_period} past return. Higher = stronger recent performance.',
            )
            + _step(
                2,
                "Find the diamond",
                'Your <strong>base fund (Fund A)</strong> is the purple diamond at <strong>0% overlap</strong> '
                'on the left — every other fund is measured against it.',
            )
            + _step(
                3,
                "Hunt for the green zone (top-left)",
                'The shaded <strong>Ideal zone</strong> marks funds with <strong>low overlap</strong> and '
                '<strong>high return</strong> — the best candidates to add alongside your base fund.',
            )
            + _step(
                4,
                "Use bubble colours and the star",
                'Green bubbles = healthy diversification; red = very high overlap (similar portfolio). '
                'The <strong>star marker</strong> highlights our suggested best pair for your base fund.',
            )
            + _step(
                5,
                "Click a bubble to compare",
                'Click any bubble to set it as <strong>Fund B</strong>. The right panel then shows overlap %, '
                'shared stocks, and a <strong>Compare in detail</strong> button.',
            )
        )
        tip = ""
        title = "How to read this chart"
        intro = (
            'Each bubble is a fund (except your base fund). '
            '<strong>Best additions sit in the top-left</strong> — low overlap with your base fund, solid returns.'
        )

    return (
        f'<div class="ov-bubble-guide" style="background:{_al};border:1px solid {_bdr};'
        f'border-radius:12px;padding:1rem 1.15rem;margin:0.5rem 0 0.75rem;">'
        f'<div style="font-size:0.95rem;font-weight:700;color:{_hd};margin-bottom:4px;">📖 {title}</div>'
        f'<div style="font-size:0.78rem;color:{_sb};line-height:1.5;margin-bottom:10px;">{intro}</div>'
        f'{steps}{tip}'
        f'</div>'
    )



def _overlap_theme_dict(t, t_name):
    return {**t, "is_dark": t_name == "dark_premium"}


def _overlap_init_session():
    if "overlap_matrix_selected_funds" not in st.session_state:
        legacy = st.session_state.pop("overlap_matrix_selected_fund", "")
        st.session_state.overlap_matrix_selected_funds = [legacy] if legacy else []
    if "overlap_matrix_return_period" not in st.session_state:
        st.session_state.overlap_matrix_return_period = "1Y"
    if "overlap_matrix_min_return" not in st.session_state:
        st.session_state.overlap_matrix_min_return = 0


def _overlap_pick_fund_index(selection, graph):
    if not selection or not getattr(selection, "points", None):
        return None
    pt = selection.points[0]
    idx = pt.get("point_index", pt.get("pointNumber"))
    if idx is None or idx < 0 or idx >= len(graph.funds):
        return None
    return int(idx)


def _overlap_get_ab(allowed: list[str], ns: str = "overlap_matrix") -> tuple[str | None, str | None]:
    sel = [f for f in st.session_state.get(f"{ns}_selected_funds", []) if f in allowed]
    fund_a = sel[0] if len(sel) > 0 else None
    fund_b = sel[1] if len(sel) > 1 else None
    return fund_a, fund_b


def _overlap_pick_fund(fund: str, allowed: list[str], ns: str = "overlap_matrix"):
    """Fund A first, Fund B second; toggle A/B on re-click; new fund replaces B when both set."""
    if fund not in allowed:
        return
    fund_a, fund_b = _overlap_get_ab(allowed, ns)
    key = f"{ns}_selected_funds"
    if fund == fund_a:
        st.session_state[key] = []
    elif fund == fund_b:
        st.session_state[key] = [fund_a] if fund_a else []
    elif not fund_a:
        st.session_state[key] = [fund]
    elif not fund_b:
        st.session_state[key] = [fund_a, fund]
    else:
        st.session_state[key] = [fund_a, fund]


def _overlap_go_compare(fund_a: str, fund_b: str, return_source: str = "overlap_drilldown"):
    st.session_state.selected_funds = [fund_a, fund_b]
    st.session_state.overlap_matrix_return = True
    st.session_state.overlap_return_source = return_source
    st.session_state.page = "compare"
    st.rerun()


@st.cache_resource(ttl=3600)
def _overlap_filtered_graph(category: str, funds_key: tuple[str, ...]):
    from analytics.overlap_graph import build_category_graph, filter_pairs

    if len(funds_key) < 2:
        return None
    similarity = load_similarity()
    funds = list(funds_key)
    return build_category_graph(category, funds, filter_pairs(similarity, funds))


@st.cache_resource(ttl=3600)
def _portfolio_overlap_graph(funds_key: tuple[str, ...]):
    """Build an overlap graph keyed on an explicit list of portfolio funds."""
    from analytics.overlap_graph import build_category_graph, filter_pairs

    if len(funds_key) < 2:
        return None
    sim   = load_similarity()
    funds = list(funds_key)
    return build_category_graph("Portfolio", funds, filter_pairs(sim, funds))


def _overlap_hex_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return f"rgba(37,99,235,{alpha})"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _overlap_inject_page_css(t: dict, t_name: str):
    a = t["a"]
    al = t["al"]
    bdr = t["bdr"]
    cd = t["card"]
    bd = t["body"]
    hd = t["head"]
    sb = t["sub"]
    checked_fg = "#FFFFFF"

    st.markdown(
        f"""<style>
/* ── All selectboxes on this page ─────────────────────────────────── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stSelectbox"] [data-baseweb="select"] {{
  background:{cd} !important; border:1.5px solid {bdr} !important;
  color:{hd} !important; min-height:2rem !important;
}}
[data-testid="stSelectbox"] [data-baseweb="select"] span,
[data-testid="stSelectbox"] [data-baseweb="select"] [data-testid="stText"] {{
  color:{hd} !important; font-size:0.85rem !important; font-weight:500 !important;
  opacity:1 !important;
}}
[data-testid="stSelectbox"] svg {{ fill:{hd} !important; opacity:0.7 !important; }}
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] [data-testid="stSelectbox"] > div > div {{
  min-height:2rem !important; padding-top:0 !important; padding-bottom:0 !important;
}}

/* ── Toolbar card: grid layout, label-above-control ─────────────────── */
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] {{
  --primary-color: {a};
  background:{cd} !important; border:1px solid {bdr} !important;
  border-radius:12px !important; padding:0 !important;
  margin-bottom:0.85rem !important; align-items:stretch !important;
  flex-wrap:nowrap !important; gap:0 !important;
}}
/* Each column cell: flex-column, label above control, right divider */
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
  display:flex !important; flex-direction:column !important;
  align-items:stretch !important; justify-content:flex-start !important;
  padding:0.7rem 1rem 0.65rem !important;
  border-right:1px solid {bdr} !important;
}}
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {{
  border-right:none !important;
}}
/* Inner vertical block: column direction, tight gap */
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] [data-testid="stVerticalBlock"] {{
  flex-direction:column !important; gap:0 !important;
  padding:0 !important;
}}
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] [data-testid="stSlider"] {{
  margin:0 !important; padding:0 !important;
}}
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] [data-testid="stSelectbox"] {{
  margin:0 !important;
}}
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] [data-testid="stSegmentedControl"] {{
  margin:0 !important; padding:0 !important;
}}

/* Hide the period-wrap sentinel div inside the toolbar so it adds no visual space */
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] [data-testid="stMarkdownContainer"]:has(.ov-period-wrap) {{
  display:none !important;
}}

/* Return period segmented control (toolbar) */
[data-testid="stColumn"]:has(.ov-period-wrap) [data-testid="stSegmentedControl"] {{
  background:{cd} !important; border:1px solid {bdr} !important;
  border-radius:999px !important; padding:2px !important;
  min-height:2rem !important; margin-top:0 !important;
}}
/* Make the segmented control wrapper sit flush — no extra top gap */
[data-testid="stColumn"]:has(.ov-period-wrap)
  [data-testid="stVerticalBlock"] > [data-testid="stSegmentedControl"] {{
  margin-top:0 !important; padding-top:0 !important;
}}
[data-testid="stColumn"]:has(.ov-period-wrap) [data-testid="stSegmentedControl"] button {{
  font-size:0.8rem !important; font-weight:500 !important; color:{hd} !important;
  background:transparent !important; border:none !important;
  border-radius:999px !important; padding:4px 14px !important; min-height:1.65rem !important;
}}
[data-testid="stColumn"]:has(.ov-period-wrap) [data-testid="stSegmentedControl"] button[aria-checked="true"],
[data-testid="stColumn"]:has(.ov-period-wrap) [data-testid="stSegmentedControl"] button[aria-pressed="true"] {{
  background:{a} !important; color:{checked_fg} !important; font-weight:600 !important;
}}

/* ── Min return slider (toolbar only) ───────────────────────────────── */
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] [data-testid="stSlider"] [data-baseweb="slider"] {{
  background:transparent !important;
}}
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] [data-testid="stSlider"] [data-baseweb="slider"] > div {{
  background:{bdr} !important;
}}
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] [data-testid="stSlider"] [data-baseweb="slider"] > div > div {{
  background:{a} !important;
}}
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] [data-testid="stSlider"] [role="slider"] {{
  background:{a} !important; border-color:{a} !important;
  box-shadow:none !important;
}}
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] [data-testid="stSlider"] [data-testid="stThumbValue"] {{
  background:{a} !important; color:{checked_fg} !important;
  border-color:{a} !important; font-size:0.75rem !important;
}}
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] [data-testid="stSlider"] [data-testid="stTickBarMin"],
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] [data-testid="stSlider"] [data-testid="stTickBarMax"] {{
  color:{bd} !important;
}}

/* Filter label above each control */
.ov-filter-lbl {{
  font-size:0.65rem; font-weight:700; text-transform:uppercase;
  letter-spacing:0.55px; color:{sb}; margin-bottom:0.35rem;
  white-space:normal; line-height:1.3; word-break:break-word;
}}
/* Keep legacy alias so old references don't break */
.ov-flbl {{ font-size:0.65rem; font-weight:700; text-transform:uppercase;
  letter-spacing:0.55px; color:{sb}; margin-bottom:0.35rem;
  white-space:normal; line-height:1.3; }}
.ov-min-val {{
  font-size:0.8rem; font-weight:700; color:{a};
  white-space:nowrap; margin-top:2px;
}}
/* Connection selectbox: hide native Streamlit label (we use .ov-filter-lbl) */
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] [data-testid="stSelectbox"] label {{
  display:none !important;
}}
/* Unified control typography in toolbar */
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] [data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stMarkdownContainer"]:has(.ov-tb-sentinel)
  + [data-testid="stHorizontalBlock"] [data-testid="stSelectbox"] [data-baseweb="select"] span {{
  font-size:0.8rem !important;
}}

/* ── Side panel — style the column container via sentinel ─────────── */
[data-testid="stMarkdownContainer"]:has(.ov-side-sentinel)
  ~ [data-testid="stVerticalBlock"],
[data-testid="stMarkdownContainer"]:has(.ov-side-sentinel)
  + * {{
  /* no-op: actual styling applied to the column via the rule below */
}}
/* Target the stColumn that holds the sentinel + sidebar content */
[data-testid="stColumn"]:has(.ov-side-sentinel) > [data-testid="stVerticalBlock"] {{
  background:{cd}; border:1px solid {bdr};
  border-radius:12px; padding:0.9rem 1rem !important;
}}
/* Hide the sentinel element itself (zero height, no padding) */
[data-testid="stMarkdownContainer"]:has(.ov-side-sentinel) {{
  display:none !important;
}}
.ov-side-hdr {{
  font-size:0.85rem; font-weight:700; color:{hd};
  padding-bottom:0.45rem; border-bottom:1px solid {bdr}; margin-bottom:0.7rem;
}}

/* ── Selection pills ─────────────────────────────────────────────── */
.ov-pills-row {{
  display:flex; align-items:stretch; gap:0.45rem; margin-bottom:0.55rem;
}}
.ov-pill {{
  flex:1; border-radius:8px; padding:0.42rem 0.75rem;
  font-size:0.8rem; font-weight:600; color:{hd};
  border:1.5px solid transparent; line-height:1.4;
  min-height:2.2rem; display:flex; align-items:center;
}}
.ov-pill-a {{ background:#EEEDFE; border-color:#AFA9EC; color:#3730A3; }}
.ov-pill-b {{ background:#E1F5EE; border-color:#9FE1CB; color:#065F46; }}
.ov-empty-slot {{
  flex:1; border:1.5px dashed {bdr}; border-radius:8px;
  padding:0.42rem 0.75rem; font-size:0.78rem; color:{sb};
  min-height:2.2rem; display:flex; align-items:center;
}}
.ov-pill-x button {{
  padding:0 !important; width:24px !important; height:24px !important;
  min-width:24px !important; border-radius:50% !important;
  font-size:0.85rem !important; font-weight:700 !important;
  background:transparent !important; color:{bd} !important;
  border:1px solid {bdr} !important; line-height:1 !important;
  flex-shrink:0;
}}
.ov-pill-x button:hover {{
  background:{al} !important; color:{a} !important; border-color:{a} !important;
}}

/* ── Overlap card ─────────────────────────────────────────────────── */
.ov-overlap-card {{
  background:{al}; border:1px solid {bdr}; border-radius:10px;
  padding:0.8rem 1rem; margin:0.5rem 0 0.7rem;
}}
.ov-overlap-score {{
  font-size:1.5rem; font-weight:800; color:{hd}; line-height:1.15; margin-bottom:0.12rem;
}}
.ov-overlap-common {{
  font-size:0.78rem; color:{bd}; margin-bottom:0.5rem;
}}
.ov-verdict-badge {{
  display:inline-block; font-size:0.72rem; font-weight:700;
  padding:0.2rem 0.6rem; border-radius:6px; margin-bottom:0.4rem;
}}
.ov-verdict-desc {{
  font-size:0.76rem; color:{bd}; line-height:1.5; margin:0 0 0.5rem;
}}

/* ── Fund list dropdown ──────────────────────────────────────────── */
.ov-list-sub {{
  font-size:0.68rem; font-weight:700; color:{bd};
  text-transform:uppercase; letter-spacing:0.5px; margin:0.7rem 0 0.3rem;
}}
[data-testid="stColumn"]:has(.ov-side-sentinel) [data-testid="stSelectbox"] {{
  margin-bottom:0.3rem;
}}
/* Ensure dropdown text is fully readable */
[data-testid="stColumn"]:has(.ov-side-sentinel) [data-testid="stSelectbox"] [data-baseweb="select"] span {{
  color:{hd} !important; font-size:0.85rem !important; font-weight:500 !important;
}}

/* ── Hint bar ────────────────────────────────────────────────────── */
.ov-hint {{
  text-align:center; font-size:0.76rem; color:{sb};
  margin:0.3rem 0 0.6rem; font-style:italic; line-height:1.4;
}}
</style>""",
        unsafe_allow_html=True,
    )



def _overlap_graph_insight(graph, min_edge_pct: float, max_edge_pct: float, conn_bucket: str, theme: dict) -> str:
    """Generate a plain-English insight card based on current graph state."""
    from analytics.overlap_graph import fund_label, get_edges
    from analytics.overlap_journey_viz import _edge_style

    n = len(graph.funds)
    if n < 2:
        return ""

    # Build adjacency using only the edges that will actually be drawn
    all_edges = get_edges(graph.matrix, min_edge_pct, top_k_per_fund=None)
    edges = [(i, j, s) for i, j, s in all_edges
             if _edge_style(s, min_edge_pct, max_edge_pct) is not None]
    adj: dict[int, set[int]] = {i: set() for i in range(n)}
    for i, j, _ in edges:
        adj[i].add(j)
        adj[j].add(i)

    # BFS connected components
    visited: set[int] = set()
    components: list[list[int]] = []
    for start in range(n):
        if start in visited:
            continue
        comp: list[int] = []
        queue = [start]
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            comp.append(node)
            queue.extend(adj[node] - visited)
        components.append(comp)

    clusters     = [c for c in components if len(c) > 1]
    isolated     = [c[0] for c in components if len(c) == 1]
    n_connected  = n - len(isolated)
    n_isolated   = len(isolated)
    n_clusters   = len(clusters)
    bucket_label = conn_bucket.split("(")[0].strip()  # e.g. "🔴 Very High"

    _a   = theme["a"]
    _al  = theme["al"]
    _bdr = theme["bdr"]
    _hd  = theme["head"]
    _bd  = theme["body"]
    _sb  = theme["sub"]

    def _rgba(hex_c: str, alpha: float) -> str:
        h = hex_c.lstrip("#")
        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        return f"rgba({r},{g},{b},{alpha})"

    # ── Build sentences ──────────────────────────────────────────────────────
    if not edges:
        verdict_icon  = "✅"
        verdict_color = "#34D399"
        verdict_bg    = _rgba("#059669", 0.12)
        headline = f"No lines drawn — no two funds exceed {min_edge_pct:.0f}% overlap"
        body = (
            f"The <strong>Draw lines</strong> filter is set to <strong>{bucket_label}</strong>, "
            f"so lines only appear between funds with that level of overlap. "
            f"None of the {n} funds cross that threshold with any other fund — "
            f"which means this set is well-diversified at this level. "
            f"<strong>You can still compare any two funds</strong> — click a bubble or pick from the list on the right."
        )
        tip = "Lower the 'Draw lines' filter (e.g. to Moderate or Good) to see which funds have milder overlaps."
    elif n_clusters == 1 and n_connected == n:
        # All funds connected into one big cluster
        verdict_icon  = "⚠️"
        verdict_color = "#F87171"
        verdict_bg    = _rgba("#DC2626", 0.12)
        headline = f"Most funds in this category overlap significantly"
        body = (
            f"All {n} funds are connected at the <strong>{bucket_label}</strong> level — "
            f"meaning every fund shares a large chunk of its portfolio with at least one other. "
            f"Owning multiple funds from this group may give you less diversification than you expect."
        )
        tip = "Pick funds from opposite ends of the graph to maximise diversification."
    else:
        # Mixed — some clusters, some isolated
        cluster_names: list[str] = []
        for comp in sorted(clusters, key=len, reverse=True)[:2]:
            names = " · ".join(fund_label(graph.funds[i], max_len=14) for i in comp)
            cluster_names.append(f"<strong>{names}</strong>")

        if n_isolated == 0:
            verdict_icon  = "🟡"
            verdict_color = "#FCD34D"
            verdict_bg    = _rgba("#D97706", 0.12)
        else:
            verdict_icon  = "ℹ️"
            verdict_color = _a
            verdict_bg    = _rgba(_a, 0.08)

        headline = (
            f"{n_connected} of {n} funds have {bucket_label.lower()} overlap with at least one other"
        )

        cluster_desc = " and ".join(cluster_names)
        body_parts = [
            f"{cluster_desc} "
            + (f"hold very similar portfolios" if "Very High" in conn_bucket else "overlap significantly")
            + f" — owning two or more from {'these groups' if n_clusters > 1 else 'this group'} adds little diversification."
        ]
        if n_isolated > 0:
            isolated_names = ", ".join(
                f"<strong>{fund_label(graph.funds[i], max_len=14)}</strong>"
                for i in isolated[:3]
            )
            more = f" and {n_isolated - 3} others" if n_isolated > 3 else ""
            body_parts.append(
                f"{isolated_names}{more} {'are' if n_isolated > 1 else 'is'} free-standing "
                f"— {'they' if n_isolated > 1 else 'it'} can be paired with any other fund without significant duplication."
            )
        body = " ".join(body_parts)
        tip = "Click any bubble to see its specific overlaps with every other fund."

    return (
        f'<div style="background:{verdict_bg};border:1px solid {verdict_color}40;border-radius:10px;'
        f'padding:0.75rem 1rem;margin:0.5rem 0 0.4rem;">'
        f'<div style="font-size:0.88rem;font-weight:700;color:{verdict_color};margin-bottom:0.3rem;">'
        f'{verdict_icon}&nbsp; {headline}</div>'
        f'<div style="font-size:0.78rem;color:{_hd};line-height:1.6;">{body}</div>'
        f'<div style="font-size:0.72rem;color:{_sb};margin-top:0.4rem;">💡 {tip}</div>'
        f'</div>'
    )


def _overlap_graph_hint(fund_a: str | None, fund_b: str | None) -> str:
    from analytics.overlap_graph import fund_label

    if fund_a and fund_b:
        return (
            f"Comparing {fund_label(fund_a)} and {fund_label(fund_b)} "
            f"— see overlap details in the panel →"
        )
    if fund_a:
        return (
            f"Showing {fund_label(fund_a)}'s overlap — click another fund "
            f"or pick from the list to compare"
        )
    return "Click a fund on the graph or choose from the list · select two to compare"


def _overlap_render_fund_sidebar(
    graph,
    funds: list[str],
    master,
    period: str,
    theme: dict,
    similarity,
    holdings,
    ns: str = "overlap_matrix",
    return_source: str = "overlap_drilldown",
    *,
    bubble_mode: bool = False,
):
    from analytics.overlap_filters import fund_return_pct, sort_funds_by_return
    from analytics.overlap_graph import fund_label, pair_score
    from analytics.overlap_quick_compare import (
        overlap_pair_summary,
        pair_common_count,
        top_common_holdings_table,
    )

    t = theme
    fund_a, fund_b = _overlap_get_ab(funds, ns)
    sel_key = f"{ns}_selected_funds"
    pick_key = f"{ns}_fund_pick_label"
    prev_pick_key = f"{ns}_fund_pick_prev"

    _accent = t["a"]
    _pill_a_style = (
        f"background:{_overlap_hex_rgba(_accent, 0.18)};"
        f"border-color:{_overlap_hex_rgba(_accent, 0.55)};"
        f"color:{_accent};"
    )
    _pill_b_style = (
        "background:rgba(16,185,129,0.15);border-color:rgba(16,185,129,0.45);color:#059669;"
    )

    if bubble_mode:
        hdr = (
            f"Base fund — {fund_label(fund_a, max_len=20)}"
            if fund_a
            else f"Pick a base fund ({len(funds)} shown)"
        )
    else:
        hdr = (
            f"Funds — vs {fund_label(fund_a, max_len=20)}"
            if fund_a
            else f"Funds ({len(funds)} matching)"
        )
    st.markdown(f'<div class="ov-side-hdr">{hdr}</div>', unsafe_allow_html=True)

    if bubble_mode and not fund_a:
        st.markdown(
            '<div class="ov-pills-row">'
            '<div class="ov-empty-slot">Base fund — choose from list below</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    elif bubble_mode:
        pill_a_html = (
            f'<div class="ov-pill ov-pill-a" style="{_pill_a_style}">'
            f'<span style="font-size:0.62rem;opacity:0.85;margin-right:5px;">BASE</span>'
            f'{fund_label(fund_a, max_len=20)}</div>'
        )
        if fund_b:
            pill_b_html = (
                f'<div class="ov-pill ov-pill-b" style="{_pill_b_style}">'
                f'<span style="font-size:0.62rem;opacity:0.85;margin-right:5px;">VS</span>'
                f'{fund_label(fund_b, max_len=20)}</div>'
            )
            st.markdown(
                f'<div class="ov-pills-row">{pill_a_html}{pill_b_html}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="ov-pills-row">{pill_a_html}'
                f'<div class="ov-empty-slot" style="flex:1;">Click a bubble to compare</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        pill_a_html = (
            f'<div class="ov-pill ov-pill-a" style="{_pill_a_style}">'
            f'{fund_label(fund_a, max_len=22)}</div>'
            if fund_a else
            '<div class="ov-empty-slot">Fund A</div>'
        )
        pill_b_html = (
            f'<div class="ov-pill ov-pill-b" style="{_pill_b_style}">'
            f'{fund_label(fund_b, max_len=22)}</div>'
            if fund_b else
            '<div class="ov-empty-slot">Fund B</div>'
        )
        st.markdown(
            f'<div class="ov-pills-row">{pill_a_html}{pill_b_html}</div>',
            unsafe_allow_html=True,
        )

    # Clear buttons below pills
    if fund_a or fund_b:
        bc1, bc2 = st.columns(2)
        with bc1:
            if fund_a:
                st.markdown('<div class="ov-pill-x">', unsafe_allow_html=True)
                _clear_a_lbl = "✕ Clear base" if bubble_mode else "✕ Clear A"
                if st.button(_clear_a_lbl, key=f"{ns}_clear_a", use_container_width=True):
                    st.session_state[sel_key] = []
                    for _k in (pick_key, prev_pick_key, f"{ns}_dropdown_last"):
                        st.session_state.pop(_k, None)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
        with bc2:
            if fund_b:
                st.markdown('<div class="ov-pill-x">', unsafe_allow_html=True)
                if st.button(f"✕ Clear B", key=f"{ns}_clear_b", use_container_width=True):
                    st.session_state[sel_key] = [fund_a]
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    if fund_a and fund_b:
        score = pair_score(graph.lookup, fund_a, fund_b)
        common_n = pair_common_count(similarity, fund_a, fund_b)
        summary = overlap_pair_summary(score, common_n)
        st.markdown(
            f'<div class="ov-overlap-card">'
            f'<div class="ov-overlap-score">{score:.0f}% overlap</div>'
            f'<div class="ov-overlap-common">{summary["common_text"]}</div>'
            f'<div class="ov-verdict-badge" style="background:{summary["badge_bg"]};'
            f'color:{summary["badge_color"]};">{summary["label"]}</div>'
            f'<div class="ov-verdict-desc">{summary["description"]}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
        if st.button(
            "Compare in detail →",
            type="primary",
            use_container_width=True,
            key=f"{ns}_compare_detail",
        ):
            _overlap_go_compare(fund_a, fund_b, return_source)

    if bubble_mode and not fund_a:
        sub_label = "Step 1 — select your base fund"
    elif bubble_mode and fund_a and not fund_b:
        sub_label = f"Other funds vs {fund_label(fund_a, max_len=16)} — or click a bubble"
    else:
        sub_label = (
            f"By overlap with {fund_label(fund_a, max_len=16)}" if fund_a else "By return"
        )
    st.markdown(f'<div class="ov-list-sub">{sub_label}</div>', unsafe_allow_html=True)

    def _return_str(fund: str) -> str:
        ret = fund_return_pct(master, fund, period)
        return f"{ret:+.1f}%" if ret is not None else "—"

    def _option_label(fund: str, ov: float | None) -> str:
        name = fund_label(fund, max_len=26)
        ret = _return_str(fund)
        if ov is not None:
            return f"{name}  ·  {ret}  ·  {ov:.0f}% ov."
        return f"{name}  ·  {ret}"

    if fund_a:
        ordered = sorted(
            funds,
            key=lambda f: pair_score(graph.lookup, fund_a, f),
            reverse=True,
        )
        labels = [
            _option_label(
                f,
                None if f == fund_a else pair_score(graph.lookup, fund_a, f),
            )
            for f in ordered
        ]
    else:
        ordered = sort_funds_by_return(funds, master, period)
        labels = [_option_label(f, None) for f in ordered]

    label_to_fund = dict(zip(labels, ordered))

    if fund_a:
        if pick_key not in st.session_state or st.session_state[pick_key] not in labels:
            highlight = fund_b or fund_a
            default_idx = ordered.index(highlight) if highlight in ordered else 0
            st.session_state[pick_key] = labels[default_idx]
        pick_label = st.selectbox(
            "Choose fund",
            labels,
            key=pick_key,
            label_visibility="collapsed",
        )
    else:
        pick_label = st.selectbox(
            "Choose fund",
            labels,
            index=None,
            placeholder="Select base fund…" if bubble_mode else "Choose a fund…",
            key=pick_key,
            label_visibility="collapsed",
        )

    if not pick_label:
        return

    picked_fund = label_to_fund[pick_label]

    if not fund_a:
        if picked_fund not in (st.session_state.get(sel_key) or []):
            _overlap_pick_fund(picked_fund, funds, ns)
            st.session_state[prev_pick_key] = pick_label
            st.rerun()
    else:
        prev_label = st.session_state.get(prev_pick_key)
        if prev_label is None:
            st.session_state[prev_pick_key] = pick_label
        elif pick_label != prev_label:
            st.session_state[prev_pick_key] = pick_label
            _overlap_pick_fund(picked_fund, funds, ns)
            st.rerun()

    # ── Quick Facts comparison (only when both selected) ───────────────
    if fund_a and fund_b:
        _overlap_render_quick_facts(fund_a, fund_b, master, holdings, period, theme)


def _overlap_render_quick_facts(fund_a, fund_b, master, holdings, period, theme):
    from analytics.overlap_filters import fund_return_pct
    from analytics.overlap_graph import fund_label

    COLOR_A = "#534AB7"
    COLOR_B = "#0F6E56"
    _bdr = theme["bdr"]
    _hd  = theme["head"]
    _sb  = theme["sub"]
    _bd  = theme["body"]
    _al  = theme["al"]
    _cd  = theme["card"]

    def _mval(col, fund):
        row = master.loc[master["fund_name"] == fund, col]
        return float(row.iloc[0]) if not row.empty and row.iloc[0] == row.iloc[0] else None

    # ── Gather metrics ──────────────────────────────────────────────────
    ret_a  = fund_return_pct(master, fund_a, period)
    ret_b  = fund_return_pct(master, fund_b, period)
    aum_a  = _mval("aum_cr",       fund_a)
    aum_b  = _mval("aum_cr",       fund_b)
    er_a   = _mval("expense_ratio", fund_a)
    er_b   = _mval("expense_ratio", fund_b)

    # Top shared sector (highest combined % in both funds)
    top_sector = top_sector_a = top_sector_b = None
    if not holdings.empty and "sector" in holdings.columns:
        ha = holdings.loc[holdings["fund_name"] == fund_a, ["sector", "allocation_percent"]]
        hb = holdings.loc[holdings["fund_name"] == fund_b, ["sector", "allocation_percent"]]
        if not ha.empty and not hb.empty:
            sa = ha.groupby("sector")["allocation_percent"].sum()
            sb = hb.groupby("sector")["allocation_percent"].sum()
            combined = (sa.add(sb, fill_value=0)).sort_values(ascending=False)
            if not combined.empty:
                top_sector   = combined.index[0]
                top_sector_a = float(sa.get(top_sector, 0))
                top_sector_b = float(sb.get(top_sector, 0))

    fa_s = fund_label(fund_a, max_len=13)
    fb_s = fund_label(fund_b, max_len=13)

    def _fmt_ret(v):
        if v is None: return "—", False
        return f"{v:+.1f}%", v >= 0

    def _fmt_aum(v):
        if v is None: return "—"
        if v >= 10000: return f"₹{v/1000:.0f}K cr"
        if v >= 1000:  return f"₹{v/1000:.1f}K cr"
        return f"₹{v:.0f} cr"

    def _fmt_er(v):
        return f"{v:.2f}%" if v is not None else "—"

    WIN_BG = "rgba(16,185,129,0.13)"  # semi-transparent green — works on light and dark themes
    TICK_COLOR = "#34D399"

    def _cell(val_str, is_winner, color):
        bg = f"background:{WIN_BG};" if is_winner else ""
        tick = f' <span style="color:{TICK_COLOR};font-size:0.7rem;">✓</span>' if is_winner else ""
        return (
            f'<td style="padding:9px 10px;text-align:right;border-radius:6px;{bg}">'
            f'<span style="font-size:0.85rem;font-weight:700;color:{color};">{val_str}</span>'
            f'{tick}</td>'
        )

    def _winner(va, vb, *, higher_is_better=True):
        """Returns (a_wins, b_wins) booleans."""
        if va is None or vb is None: return False, False
        if abs(vb - va) < 0.01: return False, False
        b_wins = (vb > va) if higher_is_better else (vb < va)
        return not b_wins, b_wins

    ret_a_str, _ = _fmt_ret(ret_a)
    ret_b_str, _ = _fmt_ret(ret_b)
    ret_a_wins, ret_b_wins = _winner(ret_a, ret_b, higher_is_better=True)
    er_a_wins,  er_b_wins  = _winner(er_a,  er_b,  higher_is_better=False)

    RET_POS = "#34D399"   # green that reads on both light and dark backgrounds
    RET_NEG = "#F87171"   # red that reads on both light and dark backgrounds
    ret_color_a = RET_POS if (ret_a is not None and ret_a >= 0) else RET_NEG
    ret_color_b = RET_POS if (ret_b is not None and ret_b >= 0) else RET_NEG

    def _lbl(text):
        return (
            f'<td style="padding:9px 10px;font-size:0.75rem;font-weight:600;'
            f'color:{_sb};white-space:nowrap;width:38%;">{text}</td>'
        )

    def _divider():
        return f'<tr><td colspan="3" style="padding:0;border-bottom:1px solid {_bdr};"></td></tr>'

    rows = (
        f'<tr>'
        + _lbl(f"{period} Return")
        + _cell(ret_a_str, ret_a_wins, ret_color_a)
        + _cell(ret_b_str, ret_b_wins, ret_color_b)
        + f'</tr>'
        + _divider()
        + f'<tr>'
        + _lbl("Fund size (AUM)")
        + f'<td style="padding:9px 10px;text-align:right;font-size:0.82rem;font-weight:600;color:{_hd};">{_fmt_aum(aum_a)}</td>'
        + f'<td style="padding:9px 10px;text-align:right;font-size:0.82rem;font-weight:600;color:{_hd};">{_fmt_aum(aum_b)}</td>'
        + f'</tr>'
        + _divider()
        + f'<tr>'
        + _lbl("Expense ratio")
        + _cell(_fmt_er(er_a), er_a_wins, _hd)
        + _cell(_fmt_er(er_b), er_b_wins, _hd)
        + f'</tr>'
    )

    # Column headers with coloured dot + name
    def _col_hdr(name, color):
        return (
            f'<th style="padding:7px 10px;text-align:right;font-size:0.75rem;'
            f'font-weight:700;color:{color};white-space:nowrap;">'
            f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
            f'background:{color};margin-right:4px;vertical-align:middle;"></span>'
            f'{name}</th>'
        )

    sector_html = ""
    if top_sector:
        sa_str = f"{top_sector_a:.1f}%" if top_sector_a else "—"
        sb_str = f"{top_sector_b:.1f}%" if top_sector_b else "—"
        sector_html = (
            f'<div style="margin-top:0.6rem;padding-top:0.55rem;border-top:1px solid {_bdr};">'
            f'<div style="font-size:0.68rem;font-weight:700;color:{_sb};'
            f'text-transform:uppercase;letter-spacing:0.4px;margin-bottom:5px;">'
            f'Biggest shared sector</div>'
            f'<div style="font-size:0.85rem;font-weight:700;color:{_hd};margin-bottom:4px;">{top_sector}</div>'
            f'<div style="display:flex;gap:16px;">'
            f'<span style="font-size:0.78rem;color:{COLOR_A};font-weight:600;">'
            f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;'
            f'background:{COLOR_A};margin-right:3px;vertical-align:middle;"></span>'
            f'{fa_s}: {sa_str}</span>'
            f'<span style="font-size:0.78rem;color:{COLOR_B};font-weight:600;">'
            f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;'
            f'background:{COLOR_B};margin-right:3px;vertical-align:middle;"></span>'
            f'{fb_s}: {sb_str}</span>'
            f'</div></div>'
        )

    st.markdown(
        f'<div style="margin-top:0.7rem;padding:0.7rem 0.8rem;background:{_al};'
        f'border:1px solid {_bdr};border-radius:10px;">'
        f'<div style="font-size:0.68rem;font-weight:700;color:{_sb};'
        f'text-transform:uppercase;letter-spacing:0.4px;margin-bottom:0.4rem;">Quick facts</div>'
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr>'
        f'<th style="width:38%;"></th>'
        + _col_hdr(fa_s, COLOR_A)
        + _col_hdr(fb_s, COLOR_B)
        + f'</tr></thead>'
        f'<tbody>{rows}</tbody></table>'
        + sector_html
        + f'</div>',
        unsafe_allow_html=True,
    )


def page_overlap_drilldown():
    from analytics.overlap_filters import (
        CATEGORY_ORDER,
        MIN_RETURN_SLIDER_MAX,
        RETURN_PERIODS,
        filter_funds,
        sort_funds_by_return,
    )
    from analytics.overlap_journey_viz import (
        BUCKET_LABEL_TO_MIN,
        BUCKET_LABEL_TO_RANGE,
        DEFAULT_BUCKET_LABEL,
        JOURNEY_MIN_EDGE,
        OVERLAP_BUCKETS,
        JourneyVizParams,
        fig_overlap_journey,
        journey_legend_html,
    )
    from analytics.overlap_quick_compare import (
        display_table,
        overlap_pair_summary,
        pair_common_count,
        top_common_holdings_table,
    )

    t_name, t = _fl_get_theme()
    _fl_inject_css(t, t_name)
    _fl_render_navbar(t, t_name, "overlap_drilldown")
    theme = _overlap_theme_dict(t, t_name)
    _overlap_inject_page_css(t, t_name)
    _fl_render_breadcrumb([("Home", "home"), ("Analyse Funds", "analyse_funds"), ("Overlap matrix", None)])
    similarity = load_similarity()
    master = load_master()
    if similarity.empty:
        st.warning("Similarity data not available.")
        return

    _overlap_init_session()

    # ── Filter toolbar — 4 labelled grid cells ───────────────────────────────
    st.markdown('<div class="ov-tb-sentinel"></div>', unsafe_allow_html=True)
    c_cat, c_ret, c_min, c_conn = st.columns([1.0, 0.8, 1.8, 1.0], gap="small", vertical_alignment="top")

    with c_cat:
        st.markdown('<div class="ov-filter-lbl">Category</div>', unsafe_allow_html=True)
        prev_cat = st.session_state.get("overlap_matrix_category", "Large Cap")
        category = st.selectbox(
            "Category",
            CATEGORY_ORDER,
            key="overlap_matrix_category",
            label_visibility="collapsed",
        )
        if category != prev_cat:
            st.session_state.overlap_matrix_selected_funds = []
            st.session_state.pop("overlap_dropdown_last", None)

    with c_ret:
        st.markdown('<div class="ov-filter-lbl">Return yrs</div>', unsafe_allow_html=True)
        period = st.selectbox(
            "Return period",
            RETURN_PERIODS,
            key="overlap_matrix_return_period",
            label_visibility="collapsed",
        )

    with c_min:
        st.markdown('<div class="ov-filter-lbl">Min. past return</div>', unsafe_allow_html=True)
        sl_col, val_col = st.columns([4, 1], vertical_alignment="center")
        with sl_col:
            min_ret = st.slider(
                "Min return",
                min_value=0,
                max_value=MIN_RETURN_SLIDER_MAX,
                step=1,
                key="overlap_matrix_min_return",
                format="%d%%",
                label_visibility="collapsed",
                help="0 = Any (no minimum).",
            )
        with val_col:
            st.markdown(
                f'<div class="ov-min-val">{"Any" if min_ret == 0 else f"≥{min_ret}%"}</div>',
                unsafe_allow_html=True,
            )

    with c_conn:
        st.markdown('<div class="ov-filter-lbl">Show lines ≥</div>', unsafe_allow_html=True)
        conn_bucket = st.selectbox(
            "Show lines ≥",
            [b[0] for b in OVERLAP_BUCKETS],
            index=next(
                i for i, b in enumerate(OVERLAP_BUCKETS)
                if b[0] == DEFAULT_BUCKET_LABEL
            ),
            key="overlap_matrix_conn_bucket",
            label_visibility="collapsed",
            help="Draw connection lines only when overlap reaches this level.",
        )
    _bucket_range = BUCKET_LABEL_TO_RANGE.get(conn_bucket, (JOURNEY_MIN_EDGE, 100.0))
    min_edge_pct, max_edge_pct = _bucket_range
    min_return_floor = None if min_ret == 0 else float(min_ret)

    filtered = filter_funds(master, category, period, min_return_floor)
    filtered = sort_funds_by_return(filtered, master, period)

    if len(filtered) < 2:
        st.info(
            f"Need at least 2 funds in {category} matching your filters. "
            f"Try lowering the minimum return or choosing another category."
        )
        return

    graph = _overlap_filtered_graph(category, tuple(filtered))
    if graph is None:
        st.info("Could not build overlap graph for the selected funds.")
        return

    funds = graph.funds
    fund_a, fund_b = _overlap_get_ab(funds)
    holdings = load_holdings()

    # ── View mode toggle ─────────────────────────────────────────────────────
    _ov_view_col, _ = st.columns([3, 5])
    with _ov_view_col:
        _ov_view = st.segmented_control(
            "View",
            ["🔗 Overlap Graph", "📊 Bubble Chart"],
            default=st.session_state.get("overlap_matrix_view_mode", "🔗 Overlap Graph"),
            key="overlap_matrix_view_mode",
            label_visibility="collapsed",
        )
    _show_bubble = (_ov_view == "📊 Bubble Chart")

    col_graph, col_side = st.columns([15, 7])

    with col_graph:
        if _show_bubble:
            if not fund_a:
                st.markdown(
                    _overlap_bubble_guide_html(theme, has_base=False, return_period=period),
                    unsafe_allow_html=True,
                )
            else:
                with st.expander("📖 How to read this chart", expanded=False):
                    st.markdown(
                        _overlap_bubble_guide_html(theme, has_base=True, return_period=period),
                        unsafe_allow_html=True,
                    )
                _bubble_result = _overlap_bubble_chart_fig(
                    graph, theme, master, fund_a, fund_b, period,
                )
                if _bubble_result is None:
                    st.info("Not enough return data to build the bubble chart for this selection.")
                else:
                    _bfig, _bfunds, _best_lbl, _best_ov, _best_ret = _bubble_result
                    _bubble_event = st.plotly_chart(
                        _bfig, use_container_width=True, on_select="rerun",
                        key=f"overlap_bubble_{category}_{period}_{fund_a}_{len(funds)}",
                        config={"displayModeBar": False},
                    )
                    # Bubble click → select fund_b
                    if _bubble_event and getattr(_bubble_event, "selection", None):
                        _bpts = _bubble_event.selection.get("points", [])
                        if _bpts:
                            _bidx = _bpts[0].get("point_index", _bpts[0].get("pointNumber"))
                            if _bidx is not None and 0 <= _bidx < len(_bfunds):
                                _overlap_pick_fund(_bfunds[_bidx], funds)
                                st.session_state.pop("overlap_dropdown_last", None)
                                st.rerun()
                    # Best pair callout
                    _base_lbl = __import__("analytics.overlap_graph", fromlist=["fund_label"]).fund_label(fund_a, max_len=24)
                    st.markdown(
                        f'<div style="background:rgba(16,185,129,0.10);border:1px solid rgba(16,185,129,0.3);'
                        f'border-radius:10px;padding:0.6rem 1rem;margin-top:6px;font-size:0.82rem;color:{theme["body"]};">'
                        f'<strong style="color:#10B981;">★ Best pair for {_base_lbl}:</strong> '
                        f'<strong>{_best_lbl}</strong> — lowest overlap '
                        f'(<strong>{_best_ov:.0f}%</strong>) with decent returns '
                        f'(<strong>{_best_ret:+.1f}%</strong>)'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<div style="font-size:0.72rem;color:{theme["sub"]};margin-top:6px;">'
                        f'← lower overlap = better pair &nbsp;·&nbsp; '
                        f'↑ higher return = better performer &nbsp;·&nbsp; '
                        f'Click a bubble to select it as Fund B</div>',
                        unsafe_allow_html=True,
                    )
        else:
            st.markdown(journey_legend_html(theme), unsafe_allow_html=True)
            fig = fig_overlap_journey(
                graph, theme, master,
                JourneyVizParams(fund_a=fund_a, fund_b=fund_b, return_period=period,
                                 min_edge_pct=min_edge_pct, max_edge_pct=max_edge_pct),
            )
            chart_event = st.plotly_chart(
                fig, use_container_width=True, on_select="rerun",
                key=f"overlap_journey_{category}_{period}_{min_ret}_{len(funds)}",
            )
            idx = _overlap_pick_fund_index(
                chart_event.selection if chart_event else None, graph,
            )
            if idx is not None:
                _overlap_pick_fund(graph.funds[idx], funds)
                st.session_state.pop("overlap_dropdown_last", None)
                st.rerun()

            insight_html = _overlap_graph_insight(graph, min_edge_pct, max_edge_pct, conn_bucket, theme)
            if insight_html:
                st.markdown(insight_html, unsafe_allow_html=True)

            hint = _overlap_graph_hint(fund_a, fund_b)
            st.markdown(f'<div class="ov-hint">{hint}</div>', unsafe_allow_html=True)

    with col_side:
        st.markdown('<div class="ov-side-sentinel"></div>', unsafe_allow_html=True)
        _overlap_render_fund_sidebar(
            graph, funds, master, period, theme, similarity, holdings,
            bubble_mode=_show_bubble,
        )

    # ── Full-width shared holdings expander (only when both funds selected) ──
    if fund_a and fund_b:
        from analytics.overlap_quick_compare import (
            exclusive_holdings_table,
            holdings_union_table,
            top_common_holdings_table,
        )
        from analytics.overlap_graph import fund_label as _fl

        fa_lbl  = _fl(fund_a, max_len=28)
        fb_lbl  = _fl(fund_b, max_len=28)
        fa_short = _fl(fund_a, max_len=14)
        fb_short = _fl(fund_b, max_len=14)

        # Pre-compute counts for the expander title
        common_df = top_common_holdings_table(holdings, fund_a, fund_b, top_n=200)
        n_shared  = len(common_df)

        with st.expander(
            f"📋  Holdings breakdown  ·  {n_shared} stocks in common  ·  {fa_lbl} vs {fb_lbl}",
            expanded=False,
        ):
            COLOR_A = "#534AB7"
            COLOR_B = "#0F6E56"
            _a   = theme["a"]
            _al  = theme["al"]
            _cd  = theme["card"]
            _bdr = theme["bdr"]
            _hd  = theme["head"]
            _sb  = theme["sub"]

            VIEW_COMMON  = f"Common ({n_shared})"
            VIEW_ALL     = "All stocks"
            VIEW_EXCL_A  = f"Only in {fa_short}"
            VIEW_EXCL_B  = f"Only in {fb_short}"
            view_options = [VIEW_COMMON, VIEW_ALL, VIEW_EXCL_A, VIEW_EXCL_B]

            view = st.segmented_control(
                "Stock view",
                view_options,
                default=VIEW_COMMON,
                key="overlap_holdings_view",
                label_visibility="collapsed",
            )
            if not view:
                view = VIEW_COMMON

            # Build the appropriate dataframe
            if view == VIEW_COMMON:
                df_view = common_df
                bar_cols   = [(cols := list(df_view.columns))[1], cols[2]] if len(df_view.columns) > 2 else []
                bar_colors = [COLOR_A, COLOR_B]
            elif view == VIEW_ALL:
                df_view = holdings_union_table(holdings, fund_a, fund_b)
                bar_cols   = [(cols := list(df_view.columns))[1], cols[2]] if not df_view.empty and len(df_view.columns) > 2 else []
                bar_colors = [COLOR_A, COLOR_B]
            elif view == VIEW_EXCL_A:
                df_view    = exclusive_holdings_table(holdings, fund_a, fund_b)
                bar_cols   = [(cols := list(df_view.columns))[1]] if not df_view.empty and len(df_view.columns) > 1 else []
                bar_colors = [COLOR_A]
            else:  # Exclusive B
                df_view    = exclusive_holdings_table(holdings, fund_b, fund_a)
                bar_cols   = [(cols := list(df_view.columns))[1]] if not df_view.empty and len(df_view.columns) > 1 else []
                bar_colors = [COLOR_B]

            if df_view.empty:
                st.caption("No holdings data available for this selection.")
            else:
                all_cols   = list(df_view.columns)
                data_cols  = all_cols[1:]
                max_vals   = {c: float(df_view[c].max()) or 1.0 for c in data_cols if c in df_view.columns}
                col_colors = {c: bar_colors[i] if i < len(bar_colors) else _a for i, c in enumerate(data_cols)}

                def _th_fw(lbl, align="left"):
                    return (
                        f'<th style="padding:10px 14px;text-align:{align};font-size:0.7rem;'
                        f'font-weight:700;color:{_sb};text-transform:uppercase;letter-spacing:0.5px;">{lbl}</th>'
                    )

                def _bar_fw(val, max_val, color):
                    if val is None or (hasattr(val, '__class__') and val != val):  # NaN check
                        return f'<span style="color:{_sb};font-size:0.78rem;">—</span>'
                    try:
                        v = float(val)
                    except (TypeError, ValueError):
                        return f'<span style="color:{_sb};font-size:0.78rem;">—</span>'
                    w = int(v / max_val * 100) if max_val > 0 else 0
                    return (
                        f'<div style="display:flex;align-items:center;gap:8px;">'
                        f'<div style="flex:1;height:6px;border-radius:3px;background:{_bdr};">'
                        f'<div style="width:{w}%;height:100%;border-radius:3px;background:{color};"></div>'
                        f'</div>'
                        f'<span style="font-size:0.82rem;font-weight:700;color:{color};white-space:nowrap;">'
                        f'{v:.2f}%</span></div>'
                    )

                header_html = _th_fw("Stock") + "".join(_th_fw(c) for c in data_cols)
                rows_html   = ""
                for i, row in df_view.reset_index(drop=True).iterrows():
                    row_bg = _al if i % 2 == 0 else _cd
                    stock  = str(row[all_cols[0]])
                    cells  = "".join(
                        f'<td style="padding:10px 14px;min-width:200px;">'
                        f'{_bar_fw(row[c], max_vals.get(c, 1), col_colors[c])}</td>'
                        for c in data_cols
                    )
                    rows_html += (
                        f'<tr style="background:{row_bg};border-bottom:1px solid {_bdr};">'
                        f'<td style="padding:10px 14px;min-width:220px;font-size:0.82rem;'
                        f'font-weight:600;color:{_hd};line-height:1.3;">{stock}</td>'
                        f'{cells}</tr>'
                    )

                n_rows = len(df_view)
                st.caption(f"{n_rows} stock{'s' if n_rows != 1 else ''}")
                st.markdown(
                    f'<div style="border-radius:12px;border:1px solid {_bdr};overflow:hidden;">'
                    f'<table style="width:100%;border-collapse:collapse;">'
                    f'<thead><tr style="background:{_al};border-bottom:2px solid {_bdr};">'
                    f'{header_html}'
                    f'</tr></thead><tbody>{rows_html}</tbody></table></div>',
                    unsafe_allow_html=True,
                )

    st.markdown(
        '<div class="fl-disc">Overlap analysis is for informational purposes only — not investment advice.</div>',
        unsafe_allow_html=True,
    )



def main():
    # Handle ?nav= query params from sidebar links and internal navigation
    nav_target = st.query_params.get("nav", "")
    if nav_target:
        # Persist theme across page navigations
        theme_param = st.query_params.get("theme", "")
        if theme_param and theme_param in _FL_THEMES:
            st.session_state.fl_theme = theme_param
        if "stock" in st.query_params:
            st.session_state.preselected_stock = st.query_params.get("stock", "")
        # Restore selected_categories when navigating back to explorer from compare
        cats_param = st.query_params.get("cats", "")
        if cats_param:
            st.session_state.selected_categories = [
                urllib.parse.unquote_plus(c) for c in cats_param.split("|") if c
            ]
        st.session_state.page = nav_target
        st.query_params.clear()
        st.rerun()

    if "cache_cleared" not in st.session_state:
        st.cache_data.clear()
        st.session_state["cache_cleared"] = True

    for key, default in [
        ("page",                "home"),
        ("selected_funds",      []),
        ("selected_categories", []),
        ("preselected_stock",   ""),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    if "explorer_layout" not in st.session_state:
        st.session_state.explorer_layout = "D"

    # All FL pages use the top navbar — skip the sidebar everywhere
    _fl_pages = {
        "home", "analyse_funds", "category", "explorer", "compare",
        "stock_explorer", "overlap_drilldown", "portfolio_upload", "portfolio_xray",
    }
    if st.session_state.get("page", "home") not in _fl_pages:
        render_sidebar()

    routes = {
        "home":               page_home,
        "analyse_funds":      page_analyse_funds,
        "category":           page_category_select,
        "explorer":           page_fund_explorer,
        "compare":            page_compare,
        "portfolio_upload":   page_portfolio_upload,
        "portfolio_xray":     page_portfolio_xray,
        "stock_explorer":     page_stock_explorer,
        "overlap_drilldown":  page_overlap_drilldown,
    }
    routes.get(st.session_state.page, page_home)()


main()
