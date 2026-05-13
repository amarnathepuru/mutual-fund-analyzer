import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import urllib.parse

st.set_page_config(
    page_title="FundInsight — Investment Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── GLOBAL CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #F8F9FA; }
[data-testid="stHeader"] { display: none; }
footer { display: none; }
.block-container { padding: 2rem 2.5rem !important; max-width: 1100px !important; margin: 0 auto; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: #fff !important;
    border-right: 1px solid #E5E7EB !important;
    min-width: 220px !important;
    max-width: 240px !important;
    overflow: visible !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 1.5rem 0.75rem 1rem; overflow: visible !important; }
[data-testid="stSidebarCollapseButton"] { display: none; }

/* Typography */
h1, h2, h3 { color: #1A1A2E; }

/* App bar */
.app-bar {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 2rem; padding-bottom: 1rem;
    border-bottom: 1px solid #E5E7EB;
}
.app-logo { font-size: 20px; font-weight: 800; color: #6C3CE1; }

/* Cards */
.card {
    background: #fff; border: 1px solid #E5E7EB; border-radius: 12px;
    padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

/* Metric cards */
.metric-card {
    background: #fff; border: 1px solid #E5E7EB; border-radius: 12px;
    padding: 1.25rem 1.5rem; text-align: center;
    transition: border-color 0.18s ease, background 0.18s ease,
                box-shadow 0.18s ease, transform 0.18s ease;
}
a.metric-card-link { all: unset; display: block; cursor: pointer; }
a.metric-card-link:hover .metric-card,
.metric-card:hover {
    border-color: #6C3CE1;
    background: #F5F3FF;
    box-shadow: 0 4px 20px rgba(108,60,225,0.12);
    transform: translateY(-2px);
}
.metric-value { font-size: 2.25rem; font-weight: 800; color: #6C3CE1 !important; line-height: 1; }
.metric-label { font-size: 0.75rem; color: #6B7280 !important; font-weight: 600;
                text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }
.metric-sub { font-size: 0.7rem; color: #9CA3AF !important; margin-top: 4px; }

/* Journey cards */
.journey-card {
    background: #fff; border: 1.5px solid #E5E7EB; border-radius: 16px;
    padding: 2rem; height: 100%; transition: all 0.2s;
}

/* Stats banner */
.stats-banner {
    background: linear-gradient(135deg, #6C3CE1 0%, #4F46E5 100%);
    border-radius: 16px; padding: 1.5rem 2rem; color: white;
    display: flex; gap: 0; align-items: center; margin-bottom: 2rem;
    flex-wrap: wrap;
}
.stat-item { text-align: center; flex: 1; min-width: 100px; }
.stat-value { font-size: 1.75rem; font-weight: 800; }
.stat-label { font-size: 0.7rem; opacity: 0.8; margin-top: 2px; }
.stat-divider { width: 1px; background: rgba(255,255,255,0.2); height: 40px; flex-shrink: 0; }

/* Category cards */
.cat-card {
    background: #fff; border: 1.5px solid #E5E7EB; border-radius: 12px;
    padding: 1.25rem; cursor: pointer; height: 100%;
}
.cat-name { font-size: 0.9rem; font-weight: 700; color: #1A1A2E; margin-bottom: 4px; margin-top: 8px; }
.cat-desc { font-size: 0.75rem; color: #6B7280; line-height: 1.5; }

/* Primary Streamlit button — override red to purple */
.stButton > button[kind="primaryFormSubmit"],
.stButton > button[kind="primary"],
button[data-testid="baseButton-primary"] {
    background: #6C3CE1 !important;
    border-color: #6C3CE1 !important;
    color: #fff !important;
}

/* Category cards */
.cat-card-inner {
    background: #fff; border: 1.5px solid #E5E7EB; border-radius: 12px;
    padding: .9rem .9rem .85rem; min-height: 120px; position: relative;
    transition: border-color .15s, box-shadow .15s;
}
.cat-card-inner.selected {
    background: #F5F3FF; border: 2px solid #6C3CE1;
    box-shadow: 0 0 0 3px rgba(108,60,225,.10);
}
/* Style the checkbox in each cat-card column */
.cat-card-col [data-testid="stCheckbox"] {
    margin-top: .3rem;
}
.cat-card-col [data-testid="stCheckbox"] label {
    font-size: .78rem !important; color: #6B7280 !important; font-weight: 500;
}
.cat-card-col [data-testid="stCheckbox"] label span { color: #6B7280 !important; }

/* ── Nav header pill buttons ─────────────────────────────────────────────── */
a.nav-pill {
    display: inline-flex; align-items: center; gap: .3rem;
    padding: .3rem .9rem; border-radius: 9999px;
    border: 1.5px solid #E5E7EB; background: #fff;
    color: #6B7280; font-size: .78rem; font-weight: 600;
    text-decoration: none; cursor: pointer;
    transition: border-color .15s, color .15s, background .15s;
    white-space: nowrap;
}
a.nav-pill:hover {
    border-color: #6C3CE1; color: #6C3CE1; background: #F5F3FF;
}
.nav-pill-row {
    display: flex; gap: .5rem; align-items: center;
    margin-bottom: .85rem;
}

/* ── Sidebar nav card tooltip ────────────────────────────────────────────── */
.nav-tooltip-wrap { position: relative; display: block; }
.nav-tooltip {
    visibility: hidden;
    opacity: 0;
    position: absolute;
    left: calc(100% + 12px);
    top: 50%;
    transform: translateY(-50%) translateX(-4px);
    transition: opacity .18s ease, transform .18s ease, visibility .18s;
    background: #1A1A2E;
    color: #fff;
    border-radius: 10px;
    padding: .7rem .95rem;
    font-size: .75rem;
    line-height: 1.55;
    width: 210px;
    box-shadow: 0 8px 24px rgba(0,0,0,.22);
    z-index: 9999;
    pointer-events: none;
    white-space: normal;
}
.nav-tooltip-wrap:hover .nav-tooltip {
    visibility: visible;
    opacity: 1;
    transform: translateY(-50%) translateX(0);
}
.nav-tooltip-title { font-weight: 700; margin-bottom: .4rem; color: #C4B5FD; font-size: .78rem; }
.nav-tooltip-item { display: flex; gap: .35rem; margin-bottom: .22rem; opacity: .88; align-items: flex-start; }

/* Badges */
.badge {
    display: inline-block; padding: 2px 8px; border-radius: 9999px;
    font-size: 0.65rem; font-weight: 700;
}
.badge-live   { background: #D1FAE5; color: #059669; }
.badge-soon   { background: #F3F4F6; color: #9CA3AF; }
.badge-high   { background: #FEE2E2; color: #DC2626; }
.badge-medium { background: #FEF3C7; color: #D97706; }
.badge-low    { background: #D1FAE5; color: #059669; }

/* Insight cards */
.insight-card {
    border-radius: 10px; padding: 0.875rem 1rem;
    margin-bottom: 0.75rem; display: flex; align-items: flex-start; gap: 0.75rem;
}
.insight-alert   { background: #FEF2F2; border-left: 3px solid #EF4444; }
.insight-warning { background: #FFFBEB; border-left: 3px solid #F59E0B; }
.insight-info    { background: #EEF2FF; border-left: 3px solid #6C3CE1; }
.insight-success { background: #F0FDF4; border-left: 3px solid #10B981; }
.insight-icon { font-size: 1.1rem; flex-shrink: 0; }
.insight-text { font-size: 0.8rem; color: #374151; line-height: 1.6; }

/* Section headers */
.section-title { font-size: 1.05rem; font-weight: 700; color: #1A1A2E; margin-bottom: 2px; }
.section-sub   { font-size: 0.78rem; color: #6B7280; margin-bottom: 1rem; }

/* Disclaimer */
.disclaimer {
    background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px;
    padding: 0.75rem 1rem; font-size: 0.7rem; color: #9CA3AF;
    margin-top: 1.5rem; text-align: center; line-height: 1.6;
}

/* Overlap bar */
.overlap-row {
    background: #fff; border: 1px solid #E5E7EB; border-radius: 10px;
    padding: 1rem 1.25rem; margin-bottom: 0.75rem;
}
.overlap-bar-bg { background: #F3F4F6; border-radius: 4px; height: 8px; overflow: hidden; margin-top: 8px; }
.overlap-bar-fill { background: #6C3CE1; height: 100%; border-radius: 4px; }

/* ── Responsive ─────────────────────────────────────────────────────────────── */

/* Tablet (≤1024px) — tighten padding */
@media (max-width: 1024px) {
    .block-container { padding: 1.5rem 1.25rem !important; }
}

/* Mobile (≤768px) */
@media (max-width: 768px) {
    /* Layout */
    .block-container { padding: 0.75rem !important; max-width: 100% !important; }

    /* Show sidebar hamburger that we hid globally */
    [data-testid="stSidebarCollapseButton"] { display: flex !important; }

    /* Stack ALL st.columns() vertically */
    [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: 0.5rem !important; }
    [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        width: 100% !important;
        flex: 0 0 100% !important;
        min-width: 100% !important;
    }

    /* Typography scale-down */
    h1 { font-size: 1.5rem !important; }
    h2 { font-size: 1.25rem !important; }
    h3 { font-size: 1.1rem !important; }

    /* Cards — reduce padding */
    .feat-card  { padding: 1rem !important; }
    .card       { padding: 1rem !important; }
    .metric-card { padding: 1rem !important; }
    .journey-card { padding: 1.25rem !important; }

    /* Fund explorer cards — single column */
    .action-card { margin-bottom: 0.5rem !important; }

    /* Disclaimer */
    .disclaimer { font-size: 0.65rem !important; padding: 0.5rem 0.75rem !important; }

    /* Insight cards */
    .insight-card { padding: 0.65rem 0.75rem !important; }

    /* Overlap rows */
    .overlap-row { padding: 0.75rem !important; }

    /* Hide decorative elements on very small screens */
    .hide-mobile { display: none !important; }
}

/* Extra small (≤480px) — further scale */
@media (max-width: 480px) {
    .block-container { padding: 0.5rem !important; }
    .feat-card  { padding: 0.75rem !important; }
    .card       { padding: 0.75rem !important; }
}
</style>
""", unsafe_allow_html=True)


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
    if score >= 65:
        return "High", "badge-high"
    if score >= 45:
        return "Medium", "badge-medium"
    return "Low", "badge-low"


def short_name(name):
    return (
        name.replace("Aditya Birla Sun Life ", "ABSL ")
            .replace(" Large Cap Fund", "")
            .replace(" Largecap Fund", "")
            .replace(" Fund", "")
    )


def format_aum(val):
    try:
        v = float(val)
        return f"₹{v/1000:.1f}K Cr" if v >= 10000 else f"₹{v:,.0f} Cr"
    except Exception:
        return "—"


def generate_insights(fund_list, similarity_df, holdings_df, sector_df):
    insights = []
    sel_sim = similarity_df[
        similarity_df["fund_a"].isin(fund_list) & similarity_df["fund_b"].isin(fund_list)
    ]
    sel_h = holdings_df[holdings_df["fund_name"].isin(fund_list)]

    # 1. Highest-overlap pair — name the actual shared stocks
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
        tail     = ("Holding both adds minimal diversification benefit."
                    if wscore >= 60 else
                    "Moderate overlap — monitor combined concentration in shared positions.")
        insights.append({
            "type": stype, "icon": icon,
            "text": (
                f"<strong>{short_name(fa)}</strong> and <strong>{short_name(fb)}</strong> share "
                f"<strong>{wscore:.0f}% portfolio similarity</strong> ({wcommon} stocks in common). "
                f"Their largest shared positions are: {top3_txt}. {tail}"
            ),
        })

    # 2. Best diversification pair
    if not sel_sim.empty and len(sel_sim) > 1:
        best   = sel_sim.loc[sel_sim["normalized_score"].idxmin()]
        bscore = best["normalized_score"]
        if bscore < 50:
            insights.append({
                "type": "success", "icon": "✅",
                "text": (
                    f"<strong>{short_name(best['fund_a'])}</strong> and "
                    f"<strong>{short_name(best['fund_b'])}</strong> are the most complementary pair "
                    f"with only <strong>{bscore:.0f}% overlap</strong> — they bring the most distinct "
                    "exposure when held together."
                ),
            })

    # 3. Stocks held by ALL funds — name the top ones
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
                "type": "info", "icon": "📌",
                "text": (
                    f"<strong>{len(unani_stocks)} stock{'s' if len(unani_stocks) > 1 else ''}</strong> "
                    f"appear in all {len(fund_list)} selected funds — your indirect exposure to these "
                    f"is multiplied across every fund you hold: {top5_txt}."
                ),
            })

    # 4. Sector dominance — which fund is most/least exposed and by how much
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
            hi_fund  = short_name(by_fund.iloc[0]["fund_name"])
            hi_pct   = by_fund.iloc[0]["allocation_percent"]
            lo_txt   = ""
            if len(by_fund) > 1:
                lo_fund = short_name(by_fund.iloc[-1]["fund_name"])
                lo_pct  = by_fund.iloc[-1]["allocation_percent"]
                lo_txt  = (f" <strong>{lo_fund}</strong> has the lowest at "
                           f"<strong>{lo_pct:.1f}%</strong> — the widest spread in this selection.")
            insights.append({
                "type": "warning", "icon": "🏦",
                "text": (
                    f"<strong>{top_s.title()}</strong> dominates all selected funds (avg "
                    f"<strong>{top_pct:.1f}%</strong>). <strong>{hi_fund}</strong> carries the highest "
                    f"concentration at <strong>{hi_pct:.1f}%</strong>.{lo_txt}"
                ),
            })

    # 5. Per-fund unique holdings — what each fund contributes exclusively
    if not sel_h.empty and len(fund_list) >= 2:
        for fund in fund_list:
            fund_stocks   = set(sel_h[sel_h["fund_name"] == fund]["stock_name"])
            others_stocks = set(sel_h[sel_h["fund_name"] != fund]["stock_name"])
            unique        = fund_stocks - others_stocks
            if len(unique) >= 3:
                top_unique = (
                    sel_h[(sel_h["fund_name"] == fund) & (sel_h["stock_name"].isin(unique))]
                    .nlargest(3, "allocation_percent")["stock_name"].tolist()
                )
                u_txt = ", ".join(f"<strong>{s}</strong>" for s in top_unique)
                insights.append({
                    "type": "info", "icon": "🔬",
                    "text": (
                        f"<strong>{short_name(fund)}</strong> holds <strong>{len(unique)} exclusive "
                        f"positions</strong> not found in any other selected fund, including: {u_txt}. "
                        "These represent the unique exposure this fund adds to the mix."
                    ),
                })

    # 6. Allocation momentum — stocks with consistent buying/selling across funds
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
                f"<strong>{r['stock_name']}</strong> (+{r['avg_3m']:.1f}%)"
                for _, r in growing.iterrows()
            )
            insights.append({
                "type": "success", "icon": "📈",
                "text": (
                    f"Fund managers across the selection have been consistently "
                    f"<strong>increasing allocation</strong> to: {g_txt} over the last 3 months."
                ),
            })
        if not declining.empty:
            d_txt = ", ".join(
                f"<strong>{r['stock_name']}</strong> ({r['avg_3m']:.1f}%)"
                for _, r in declining.iterrows()
            )
            insights.append({
                "type": "warning", "icon": "📉",
                "text": (
                    f"Fund managers across the selection have been consistently "
                    f"<strong>reducing allocation</strong> to: {d_txt} over the last 3 months."
                ),
            })

    return insights


# ── NAV HEADER ────────────────────────────────────────────────────────────────

def nav_header(back_page=None, back_label="Back"):
    back_pill = ""
    if back_page and back_page != "home":
        href = f"?nav={back_page}"
        # Preserve selected_categories in URL so the explorer isn't empty after a reload
        if back_page == "explorer":
            cats = st.session_state.get("selected_categories", [])
            if cats:
                cats_enc = "|".join(urllib.parse.quote_plus(c) for c in cats)
                href = f"?nav={back_page}&cats={cats_enc}"
        back_pill = f'<a href="{href}" target="_self" class="nav-pill">← {back_label}</a>'

    st.markdown(
        f'<div class="nav-pill-row">'
        f'<a href="?nav=home" target="_self" class="nav-pill">🏠 Home</a>'
        f'{back_pill}'
        f'</div>'
        f'<div style="height:1px;background:#E5E7EB;margin:0 0 1.25rem;"></div>',
        unsafe_allow_html=True,
    )


# ── SIDEBAR ───────────────────────────────────────────────────────────────────

def render_sidebar():
    page = st.session_state.get("page", "home")

    with st.sidebar:
        st.markdown(
            '<div style="font-size:1.1rem;font-weight:800;color:#6C3CE1;'
            'display:flex;align-items:center;gap:.4rem;padding:.25rem 0 1.5rem;">'
            '<span style="font-size:1.25rem;">📊</span> FundInsight</div>',
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
             "📋", "Portfolio X-Ray", "Upload your holdings",         "#FEF3C7", "#D97706",
             "X-Ray your portfolio",
             ["CSV / XLSX upload or manual entry", "Hidden stock & sector exposure", "Detect duplicate fund holdings"]),
        ]

        for target, active_pages, icon, title, sub, ic_bg, ic_color, tip_title, tip_bullets in nav_items:
            is_active   = page in active_pages
            card_bg     = "#F5F3FF"      if is_active else "#FAFAFA"
            card_border = "#6C3CE1"      if is_active else "#E5E7EB"
            title_color = "#6C3CE1"      if is_active else "#1A1A2E"
            arrow_color = "#6C3CE1"      if is_active else "#D1D5DB"
            shadow      = "0 2px 8px rgba(108,60,225,.10)" if is_active else "none"
            bullets_html = "".join(
                f'<div class="nav-tooltip-item"><span>▸</span>{b}</div>' for b in tip_bullets
            )
            st.markdown(
                f'<div class="nav-tooltip-wrap">'
                f'<a href="?nav={target}" target="_self" style="all:unset;display:block;cursor:pointer;">'
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
        '<div style="font-size:2rem;font-weight:900;color:#1A1A2E;line-height:1.2;margin-bottom:.75rem;">'
        'Invest with <span style="color:#6C3CE1;">clarity.</span><br>'
        'Backed by <span style="color:#6C3CE1;">data.</span></div>'
        '<p style="font-size:.95rem;color:#6B7280;line-height:1.75;max-width:560px;margin:0 0 1.5rem;">'
        'Most mutual fund apps show NAV charts and SIP calculators. '
        'FundInsight goes deeper — it reveals what\'s actually <em>inside</em> your funds.'
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
        ("📋", "Portfolio X-Ray",
         "Upload your existing holdings (CSV/XLSX) and get a full breakdown of true diversification, hidden concentration and duplicate funds."),
        ("📈", "Stock-level intelligence",
         "Pick any stock and see every fund that holds it, with allocation % and 3-month change — useful for tracking institutional conviction."),
    ]

    for icon, title, desc in features:
        st.markdown(
            f'<div style="display:flex;gap:1rem;align-items:flex-start;padding:1rem 1.25rem;'
            f'background:#fff;border:1px solid #E5E7EB;border-radius:12px;margin-bottom:.65rem;">'
            f'<div style="width:2.25rem;height:2.25rem;border-radius:9px;background:#EDE9FE;'
            f'display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0;">{icon}</div>'
            f'<div><div style="font-size:.9rem;font-weight:700;color:#1A1A2E;margin-bottom:.25rem;">{title}</div>'
            f'<div style="font-size:.82rem;color:#6B7280;line-height:1.6;">{desc}</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<p style="font-size:.78rem;color:#9CA3AF;margin-top:1.5rem;text-align:center;">'
        'Select a feature from the sidebar to get started.</p>',
        unsafe_allow_html=True,
    )


# ── PAGE: HOME ────────────────────────────────────────────────────────────────

def page_home():
    nav_target = st.query_params.get("nav", "")
    if nav_target:
        if "stock" in st.query_params:
            st.session_state.preselected_stock = st.query_params.get("stock", "")
        st.session_state.page = nav_target
        st.query_params.clear()
        st.rerun()

    holdings   = load_holdings()
    similarity = load_similarity()
    master     = load_master()

    n_funds  = master["fund_name"].nunique()    if not master.empty   else 0
    n_cats   = master["category"].nunique()     if not master.empty   else 0
    n_unique = holdings["stock_name"].nunique() if not holdings.empty else 0
    max_sim  = similarity["normalized_score"].max() if not similarity.empty else 0

    top_stocks = (
        holdings.groupby("stock_name").agg(
            funds=("fund_name", "nunique"),
            avg_alloc=("allocation_percent", "mean"),
        ).nlargest(6, "funds").reset_index()
        if not holdings.empty else pd.DataFrame()
    )

    # ── Page-level CSS ────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    .feat-card {
        background:#fff; border:1.5px solid #E5E7EB; border-radius:16px;
        padding:1.5rem; height:100%;
        transition:border-color .2s, box-shadow .2s, transform .2s;
    }
    a:hover .feat-card {
        border-color:#6C3CE1; box-shadow:0 4px 20px rgba(108,60,225,.12);
        transform:translateY(-2px);
    }
    .feat-icon  { font-size:1.75rem; margin-bottom:.75rem; }
    .feat-title { font-size:1rem; font-weight:700; color:#1A1A2E; margin-bottom:.4rem; }
    .feat-desc  { font-size:.82rem; color:#6B7280; line-height:1.65; margin-bottom:1rem; }
    .feat-foot  { font-size:.78rem; color:#6C3CE1; font-weight:600; }
    .stock-row  { padding:.7rem 0; border-bottom:1px solid #F3F4F6; }
    .stock-row:last-child { border-bottom:none; }
    </style>
    """, unsafe_allow_html=True)

    # ── Top nav bar ───────────────────────────────────────────────────────────
    st.markdown(
        '<div style="display:flex;align-items:center;justify-content:space-between;'
        'padding-bottom:1.25rem;border-bottom:1px solid #E5E7EB;margin-bottom:2.5rem;">'
        '<div class="app-logo">📊 FundInsight</div>'
        '<div style="display:flex;gap:1.5rem;align-items:center;">'
        '<a href="?nav=home" target="_self" style="font-size:.85rem;font-weight:600;color:#6C3CE1;text-decoration:none;">Home</a>'
        '<a href="?nav=category" target="_self" style="font-size:.85rem;font-weight:500;color:#6B7280;text-decoration:none;">Compare</a>'
        '<a href="?nav=portfolio_upload" target="_self" style="font-size:.85rem;font-weight:500;color:#6B7280;text-decoration:none;">X-Ray</a>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Hero ──────────────────────────────────────────────────────────────────
    hero_col, deco_col = st.columns([3, 2], gap="large")
    with deco_col:
        st.markdown(
            '<div class="hide-mobile" style="display:flex;align-items:center;justify-content:center;height:100%;padding:1rem 0;">'
            '<div style="background:linear-gradient(135deg,#F5F3FF 0%,#EDE9FE 100%);'
            'border:1.5px solid #DDD6FE;border-radius:20px;padding:2rem 2.5rem;text-align:center;">'
            '<div style="font-size:3.5rem;margin-bottom:.5rem;">📊</div>'
            '<div style="font-size:.8rem;color:#6C3CE1;font-weight:700;letter-spacing:.5px;">'
            'ANALYZE · COMPARE · DECIDE</div>'
            '</div></div>',
            unsafe_allow_html=True,
        )
    with hero_col:
        st.markdown(
            '<div style="padding:1rem 0 2rem;">'
            '<div style="font-size:2.75rem;font-weight:900;color:#1A1A2E;'
            'line-height:1.15;letter-spacing:-0.5px;margin-bottom:.85rem;">'
            'Invest with <span style="color:#6C3CE1;">clarity.</span><br>'
            'Backed by <span style="color:#6C3CE1;">data.</span>'
            '</div>'
            '<p style="font-size:1rem;color:#6B7280;line-height:1.75;margin:0;">'
            'Compare funds, analyze portfolios and make informed investment decisions.'
            '</p>'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── Feature cards ─────────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns(3, gap="medium")
    for col, href, icon, title, desc, foot in [
        (fc1, "?nav=category",
         "🔍", "Compare Funds",
         "Pick up to 5 funds and instantly see portfolio overlap, sector exposure, common holdings and hidden redundancy.",
         f"{n_funds} funds · {n_cats} categories →"),
        (fc2, "?nav=portfolio_upload",
         "📋", "Portfolio X-Ray",
         "Upload your existing mutual fund portfolio and uncover hidden stock exposure, duplicate funds and sector concentration.",
         "CSV / XLSX upload →"),
        (fc3, "?nav=category",
         "📂", "Explore Categories",
         f"Browse {n_funds} funds across {n_cats} categories with live star ratings, returns and risk metrics side by side.",
         f"{n_cats} categories →"),
    ]:
        with col:
            st.markdown(
                f'<a href="{href}" target="_self" style="all:unset;display:block;cursor:pointer;">'
                f'<div class="feat-card">'
                f'<div class="feat-icon">{icon}</div>'
                f'<div class="feat-title">{title}</div>'
                f'<div class="feat-desc">{desc}</div>'
                f'<div class="feat-foot">{foot}</div>'
                f'</div></a>',
                unsafe_allow_html=True,
            )

    st.markdown('<div style="height:2rem;"></div>', unsafe_allow_html=True)

    # ── Stats strip ───────────────────────────────────────────────────────────
    s1, s2, s3, s4 = st.columns(4, gap="medium")
    for col, val, label in [
        (s1, str(n_funds),       "Funds Tracked"),
        (s2, str(n_unique),      "Unique Stocks"),
        (s3, f"{max_sim:.0f}%",  "Max Fund Overlap"),
        (s4, str(n_cats),        "Fund Categories"),
    ]:
        with col:
            st.markdown(
                f'<div style="background:#fff;border:1px solid #E5E7EB;border-radius:12px;'
                f'padding:1rem 1.25rem;text-align:center;">'
                f'<div style="font-size:1.6rem;font-weight:800;color:#6C3CE1;">{val}</div>'
                f'<div style="font-size:.7rem;color:#6B7280;font-weight:600;text-transform:uppercase;'
                f'letter-spacing:.4px;margin-top:4px;">{label}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div style="height:2rem;"></div>', unsafe_allow_html=True)

    # ── Most Widely Held Stocks ───────────────────────────────────────────────
    if not top_stocks.empty:
        max_alloc = top_stocks["avg_alloc"].max()

        def stock_rows_html(subset):
            html = ""
            for _, row in subset.iterrows():
                bar_pct = int(row["avg_alloc"] / max_alloc * 100)
                slug = str(row["stock_name"]).replace(" ", "+")
                html += (
                    f'<a href="?nav=stock_explorer&stock={slug}" target="_self"'
                    f' style="all:unset;cursor:pointer;display:block;">'
                    f'<div class="stock-row">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;">'
                    f'<span style="font-size:.85rem;font-weight:700;color:#1A1A2E;">{row["stock_name"]}</span>'
                    f'<span style="font-size:.78rem;font-weight:600;color:#6C3CE1;">{row["avg_alloc"]:.1f}%'
                    f'<span style="color:#9CA3AF;font-weight:400;margin-left:5px;">{int(row["funds"])} funds</span></span>'
                    f'</div>'
                    f'<div style="background:#F3F4F6;border-radius:4px;height:5px;overflow:hidden;">'
                    f'<div style="background:#6C3CE1;width:{bar_pct}%;height:100%;border-radius:4px;"></div>'
                    f'</div></div></a>'
                )
            return html

        st.markdown(
            '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.75rem;">'
            '<div>'
            '<div style="font-size:1rem;font-weight:700;color:#1A1A2E;">Most Widely Held Stocks</div>'
            '<div style="font-size:.75rem;color:#9CA3AF;margin-top:2px;">Stocks held across the most funds in the registry</div>'
            '</div>'
            '<a href="?nav=stock_explorer" target="_self"'
            ' style="font-size:.78rem;color:#6C3CE1;font-weight:600;text-decoration:none;">View all →</a>'
            '</div>',
            unsafe_allow_html=True,
        )

        left_col, right_col = st.columns(2, gap="large")
        with left_col:
            st.markdown(
                '<div style="background:#fff;border:1px solid #E5E7EB;border-radius:14px;padding:1rem 1.25rem;">'
                + stock_rows_html(top_stocks.iloc[:3]) + '</div>',
                unsafe_allow_html=True,
            )
        with right_col:
            st.markdown(
                '<div style="background:#fff;border:1px solid #E5E7EB;border-radius:14px;padding:1rem 1.25rem;">'
                + stock_rows_html(top_stocks.iloc[3:]) + '</div>',
                unsafe_allow_html=True,
            )

    # ── Disclaimer ────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="disclaimer">
        Investments in mutual funds are subject to market risks. This platform provides portfolio
        analytics and transparency insights only — it does not constitute investment advice or
        recommendations. Past performance is not indicative of future returns. Data sourced from ETMoney.
    </div>
    """, unsafe_allow_html=True)


# ── PAGE: CATEGORY SELECT ─────────────────────────────────────────────────────

def page_category_select():
    nav_header(back_page="home", back_label="Home")
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
            '<div style="font-size:1.3rem;font-weight:800;color:#1A1A2E;margin-bottom:.2rem;">'
            'Choose Fund Category</div>'
            '<div style="font-size:.8rem;color:#9CA3AF;">'
            'Tap a category to select · mix multiple for cross-category comparison</div>',
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
                '<div style="text-align:right;font-size:.8rem;color:#D1D5DB;padding-top:.6rem;">'
                'Select a category to continue →</div>',
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
        tc      = "#6C3CE1" if is_sel else "#1A1A2E"

        st.markdown(
            f'<div class="cat-card-inner{sel_cls}">'
            f'<div style="font-size:1.5rem;margin-bottom:.35rem;">{icon}</div>'
            f'<div style="font-size:.88rem;font-weight:700;color:{tc};margin-bottom:.2rem;">{name}</div>'
            f'<div style="font-size:.7rem;color:#9CA3AF;margin-bottom:.5rem;line-height:1.4;">{desc}</div>'
            f'<span style="background:#D1FAE5;color:#059669;border-radius:9999px;'
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
    nav_header(back_page="category", back_label="Categories")

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
            "<p style='color:#6B7280;margin-top:-0.5rem;margin-bottom:0.5rem;'>"
            "Browse funds and add up to 5 to compare portfolios side by side.</p>",
            unsafe_allow_html=True,
        )
    with hs:
        st.markdown(
            '<div style="text-align:right;font-size:0.72rem;color:#9CA3AF;'
            'font-weight:600;margin-bottom:4px;">Choose layout</div>',
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
            f'<span style="background:#FEF3C7;color:#92400E;border-radius:9999px;'
            f'padding:3px 10px;font-size:0.72rem;font-weight:600;">'
            f'⚠ {short_name(r["fund_a"])} ↔ {short_name(r["fund_b"])}: '
            f'{r["normalized_score"]:.0f}% overlap</span>'
            for _, r in sim[sim["normalized_score"] >= 60]
                          .sort_values("normalized_score", ascending=False).head(2).iterrows()
        ]
        return ('<div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;">'
                + " ".join(parts) + "</div>") if parts else ""

    def stars_html(rating):
        if rating is None or (isinstance(rating, float) and np.isnan(rating)):
            return '<span style="color:#D1D5DB;font-size:0.75rem;">Not rated</span>'
        r = int(rating)
        filled = "★" * r
        empty  = "☆" * (5 - r)
        colour = {5:"#F59E0B", 4:"#F59E0B", 3:"#6B7280", 2:"#EF4444", 1:"#EF4444"}.get(r, "#6B7280")
        return (f'<span style="color:{colour};font-size:0.95rem;letter-spacing:1px;">{filled}</span>'
                f'<span style="color:#D1D5DB;font-size:0.95rem;letter-spacing:1px;">{empty}</span>')

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
            f'<span style="background:#EDE9FE;color:#6C3CE1;border-radius:9999px;'
            f'padding:4px 12px;font-size:0.78rem;font-weight:600;white-space:nowrap;">'
            f'{short_name(fn)}</span>'
            for fn in sel
        )

    def selection_tray(sel, n, cmp_key, clr_key):
        if n == 0:
            st.markdown(
                '<div style="background:#F9FAFB;border:1.5px dashed #D1D5DB;border-radius:10px;'
                'padding:0.75rem 1rem;font-size:0.82rem;color:#9CA3AF;text-align:center;">'
                'Add 2–5 funds below to compare.</div>',
                unsafe_allow_html=True,
            )
        else:
            tc, cc = st.columns([5, 1])
            with tc:
                st.markdown(
                    f'<div style="background:#F5F3FF;border:1.5px solid #DDD6FE;'
                    f'border-radius:10px;padding:0.75rem 1rem;">'
                    f'<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">'
                    f'<span style="font-size:0.72rem;color:#7C3AED;font-weight:700;'
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
                border = "2px solid #6C3CE1"               if is_sel else "1.5px solid #E5E7EB"
                bg     = "#F5F3FF"                         if is_sel else "#FFFFFF"
                shadow = "0 0 0 3px rgba(108,60,225,0.10)" if is_sel else "0 1px 3px rgba(0,0,0,0.06)"
                name_c = "#6C3CE1"                         if is_sel else "#1A1A2E"
                badge  = (
                    '<div style="margin-top:8px;"><span style="background:#EDE9FE;color:#6C3CE1;'
                    'border-radius:9999px;padding:2px 8px;font-size:0.65rem;font-weight:700;">'
                    '✓ In comparison</span></div>'
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
                        <div style="font-size:0.72rem;color:#6B7280;margin-bottom:10px;">
                            {amc_str}{(' &nbsp;·&nbsp; '+cat_str) if show_cat_filter else ''}
                        </div>
                        <div style="display:flex;gap:10px;margin-bottom:8px;flex-wrap:wrap;">
                            <div>
                                <div style="font-size:0.6rem;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.4px;">1Y Ret</div>
                                <div style="font-size:0.8rem;font-weight:600;color:#1A1A2E;">{r1y_str}</div>
                            </div>
                            <div>
                                <div style="font-size:0.6rem;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.4px;">3Y Ret</div>
                                <div style="font-size:0.8rem;font-weight:600;color:#1A1A2E;">{r3y_str}</div>
                            </div>
                            <div>
                                <div style="font-size:0.6rem;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.4px;">5Y Ret</div>
                                <div style="font-size:0.8rem;font-weight:600;color:#1A1A2E;">{r5y_str}</div>
                            </div>
                            <div>
                                <div style="font-size:0.6rem;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.4px;">Since Inc.</div>
                                <div style="font-size:0.8rem;font-weight:600;color:#1A1A2E;">{rsi_str}</div>
                            </div>
                            <div>
                                <div style="font-size:0.6rem;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.4px;">Exp.</div>
                                <div style="font-size:0.8rem;font-weight:600;color:#1A1A2E;">{er_str}</div>
                            </div>
                            <div>
                                <div style="font-size:0.6rem;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.4px;">AUM</div>
                                <div style="font-size:0.8rem;font-weight:600;color:#1A1A2E;">{aum_str}</div>
                            </div>
                        </div>
                        <div style="font-size:0.7rem;color:#6B7280;">
                            Top sector: <strong style="color:#374151;">{top_sec}</strong>
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
                row_bg  = "#F5F3FF"             if is_b else "#FFFFFF"
                row_bdr = "1.5px solid #6C3CE1" if is_b else "1px solid #E5E7EB"
                r1, r2  = st.columns([4, 1])
                with r1:
                    st.markdown(f"""
                    <div style="background:{row_bg};border:{row_bdr};border-radius:10px;
                                padding:0.75rem 1rem;">
                        <div style="font-size:0.85rem;font-weight:700;color:#1A1A2E;
                                    margin-bottom:2px;">{fn}</div>
                        <div style="margin-bottom:2px;">{stars_html(star)}</div>
                        <div style="font-size:0.72rem;color:#6B7280;">
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
            tray_bg  = "#F5F3FF" if n_sel > 0 else "#F9FAFB"
            tray_bdr = "#DDD6FE" if n_sel > 0 else "#E5E7EB"
            st.markdown(f"""
            <div style="background:{tray_bg};border:1.5px solid {tray_bdr};
                        border-radius:12px;padding:1.25rem;">
                <div style="font-size:0.85rem;font-weight:700;color:#1A1A2E;margin-bottom:0.75rem;">
                    Your Comparison &nbsp;
                    <span style="font-size:0.72rem;color:#6C3CE1;font-weight:600;">{n_sel} / 5</span>
                </div>""", unsafe_allow_html=True)
            if n_sel == 0:
                st.markdown(
                    '<div style="font-size:0.8rem;color:#9CA3AF;text-align:center;padding:1rem 0;">'
                    'Add funds from the left to build your comparison</div>',
                    unsafe_allow_html=True,
                )
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                for idx, fn in enumerate(selected):
                    rc1, rc2 = st.columns([4, 1])
                    with rc1:
                        st.markdown(
                            f'<div style="font-size:0.82rem;font-weight:600;color:#1A1A2E;'
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
                    f'<span style="font-size:0.75rem;color:#6B7280;font-weight:600;">{n_c} selected:</span>'
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
                '<span style="background:#EDE9FE;color:#6C3CE1;border-radius:9999px;'
                'padding:5px 14px;font-size:0.82rem;font-weight:600;white-space:nowrap;">'
                f'{short_name(fn)}</span> '
                for fn in selected
            )
            dc, db = st.columns([5, 1])
            with dc:
                st.markdown(
                    f'<div style="background:#F5F3FF;border:1.5px solid #DDD6FE;'
                    f'border-radius:10px;padding:0.75rem 1rem;">'
                    f'<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">'
                    f'<span style="font-size:0.72rem;color:#7C3AED;font-weight:700;'
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
            row_bg  = "#F5F3FF"             if is_d else "#FFFFFF"
            row_bdr = "1.5px solid #6C3CE1" if is_d else "1px solid #E5E7EB"
            dot_c   = "#6C3CE1"             if is_d else "#D1D5DB"
            dr1, dr2 = st.columns([5, 1])
            with dr1:
                st.markdown(f"""
                <div style="background:{row_bg};border:{row_bdr};border-radius:8px;
                            padding:0.6rem 1rem;display:flex;align-items:center;gap:10px;">
                    <div style="width:8px;height:8px;border-radius:50%;background:{dot_c};
                                flex-shrink:0;margin-top:2px;"></div>
                    <div style="flex:1;">
                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:1px;">
                            <span style="font-size:0.85rem;font-weight:700;color:#1A1A2E;">{fn}</span>
                            <span>{stars_html(star)}</span>
                        </div>
                        <div style="font-size:0.7rem;color:#6B7280;">
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
    nav_header(back_page="explorer", back_label="Fund Explorer")

    selected = st.session_state.get("selected_funds", [])
    if len(selected) < 2:
        st.warning("Please select at least 2 funds to compare.")
        return

    holdings   = load_holdings()
    similarity = load_similarity()
    sector_df  = get_sector_breakdown(holdings)

    sel_h   = holdings[holdings["fund_name"].isin(selected)].copy()
    sel_sim = similarity[
        similarity["fund_a"].isin(selected) & similarity["fund_b"].isin(selected)
    ]

    st.markdown("## Fund Comparison")
    fund_labels = ", ".join(short_name(f) for f in selected)
    st.markdown(
        f"<p style='color:#6B7280;margin-top:-0.5rem;margin-bottom:1.5rem;'>"
        f"{len(selected)} funds selected — {fund_labels}</p>",
        unsafe_allow_html=True,
    )

    # ── Top metrics ──
    avg_sim  = sel_sim["normalized_score"].mean()  if not sel_sim.empty else 0
    max_sim  = sel_sim["normalized_score"].max()   if not sel_sim.empty else 0
    n_unique = sel_h["stock_name"].nunique()

    stock_counts = sel_h.groupby("stock_name")["fund_name"].nunique()
    n_common_all = int((stock_counts == len(selected)).sum())

    slabel, scls = sim_badge(avg_sim)
    c1, c2, c3, c4 = st.columns(4)
    for col, val, label, sub in [
        (c1, f"{avg_sim:.0f}%",   "Avg Portfolio Similarity", f'<span class="badge {scls}">{slabel}</span>'),
        (c2, str(n_common_all),    f"Stocks in All {len(selected)} Funds", "Held by every selected fund"),
        (c3, f"{max_sim:.0f}%",   "Highest Pair Similarity",  "Most overlapping pair"),
        (c4, str(n_unique),        "Total Unique Stocks",       "Across all selected funds"),
    ]:
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{val}</div>
                <div class="metric-label">{label}</div>
                <div class="metric-sub">{sub}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    tab_ov, tab_ol, tab_sec, tab_hold, tab_ins = st.tabs([
        "📊 Overview",
        "🔗 Holdings Overlap",
        "🏗️ Sector Analysis",
        "📋 Common Holdings",
        "💡 Key Insights",
    ])

    # ── Tab 1: Overview ──────────────────────────────────────────────────────
    with tab_ov:
        display_mode = st.radio(
            "Show numbers as:",
            ["% overlap", "plain words", "both"],
            index=2,
            horizontal=True,
        )

        col_matrix, col_top = st.columns([3, 2], gap="large")

        with col_matrix:
            # Build score / common-stock lookups from pairwise similarity data
            score_lk  = {}
            common_lk = {}
            for _, row in sel_sim.iterrows():
                for key in [(row["fund_a"], row["fund_b"]), (row["fund_b"], row["fund_a"])]:
                    score_lk[key]  = row["normalized_score"]
                    common_lk[key] = int(row["common_stocks"])

            master  = load_master()
            cat_lk  = dict(zip(master["fund_name"], master["category"])) if not master.empty else {}
            s_names = [short_name(f) for f in selected]
            cats    = [cat_lk.get(f, "Large Cap") for f in selected]

            def _cell_cfg(score, common):
                if common == 0 and score == 0:
                    return {"bg": "#F9FAFB", "txt": "#9CA3AF",
                            "label": "No data",
                            "bdg_bg": "#F3F4F6", "bdg_txt": "#9CA3AF"}
                if score >= 65:
                    return {"bg": "#1B4332", "txt": "#FFFFFF",
                            "label": "Avoid pairing",
                            "bdg_bg": "#FCA5A5", "bdg_txt": "#7F1D1D"}
                if score >= 50:
                    return {"bg": "#2D6A4F", "txt": "#FFFFFF",
                            "label": "Mostly redundant",
                            "bdg_bg": "#FDE68A", "bdg_txt": "#78350F"}
                if score >= 35:
                    return {"bg": "#52B788", "txt": "#FFFFFF",
                            "label": "Some overlap",
                            "bdg_bg": "#A7F3D0", "bdg_txt": "#064E3B"}
                if score >= 20:
                    return {"bg": "#B7E4C7", "txt": "#1B4332",
                            "label": "Good pairing",
                            "bdg_bg": "#D1FAE5", "bdg_txt": "#065F46"}
                return {"bg": "#D8F3DC", "txt": "#1B4332",
                        "label": "Best pairing",
                        "bdg_bg": "#ECFDF5", "bdg_txt": "#065F46"}

            # Column headers
            hdr = '<td style="min-width:90px;"></td>'
            for sn, cat in zip(s_names, cats):
                hdr += (
                    f'<td style="text-align:center;padding:0 4px 10px;min-width:110px;vertical-align:bottom;">'
                    f'<div style="font-weight:700;font-size:12px;color:#1A1A2E;line-height:1.4;">{sn}</div>'
                    f'<div style="font-size:10px;color:#6B7280;">{cat}</div>'
                    f'</td>'
                )

            # Matrix rows
            rows = ""
            for fa, fa_sn, fa_cat in zip(selected, s_names, cats):
                cells = ""
                for fb in selected:
                    if fa == fb:
                        cells += (
                            '<td style="padding:3px;">'
                            '<div style="background:#F3F4F6;border-radius:10px;'
                            'width:104px;height:80px;display:flex;align-items:center;justify-content:center;">'
                            '<span style="font-size:11px;color:#9CA3AF;font-style:italic;">same fund</span>'
                            '</div></td>'
                        )
                    else:
                        sc  = score_lk.get((fa, fb), 0)
                        co  = common_lk.get((fa, fb), 0)
                        cfg = _cell_cfg(sc, co)
                        pct = (
                            f'<div style="font-size:22px;font-weight:800;color:{cfg["txt"]};line-height:1;">'
                            f'{sc:.0f}%</div>'
                            if display_mode in ("% overlap", "both") else ""
                        )
                        lbl = (
                            f'<div style="background:{cfg["bdg_bg"]};color:{cfg["bdg_txt"]};'
                            f'font-size:9px;font-weight:700;border-radius:9999px;'
                            f'padding:2px 7px;margin-top:5px;white-space:nowrap;">'
                            f'{cfg["label"]}</div>'
                            if display_mode in ("plain words", "both") else ""
                        )
                        cells += (
                            f'<td style="padding:3px;">'
                            f'<div style="background:{cfg["bg"]};border-radius:10px;'
                            f'width:104px;height:80px;display:flex;flex-direction:column;'
                            f'align-items:center;justify-content:center;">'
                            f'{pct}{lbl}</div></td>'
                        )

                rows += (
                    f'<tr>'
                    f'<td style="padding:3px 12px 3px 0;text-align:right;vertical-align:middle;white-space:nowrap;">'
                    f'<div style="font-weight:700;font-size:12px;color:#1A1A2E;">{fa_sn}</div>'
                    f'<div style="font-size:10px;color:#6B7280;">{fa_cat}</div>'
                    f'</td>{cells}</tr>'
                )

            st.markdown(
                f'<div style="overflow-x:auto;padding-bottom:4px;">'
                f'<table style="border-collapse:separate;border-spacing:0;">'
                f'<thead><tr>{hdr}</tr></thead>'
                f'<tbody>{rows}</tbody>'
                f'</table></div>',
                unsafe_allow_html=True,
            )

            # Colour legend
            st.markdown("""
            <div style="display:flex;align-items:center;gap:8px;margin-top:14px;
                        font-size:11px;color:#6B7280;flex-wrap:wrap;">
                <span>Low overlap</span>
                <div style="display:flex;gap:3px;align-items:center;">
                    <div style="width:14px;height:14px;background:#D8F3DC;border-radius:3px;"></div>
                    <div style="width:14px;height:14px;background:#B7E4C7;border-radius:3px;"></div>
                    <div style="width:14px;height:14px;background:#52B788;border-radius:3px;"></div>
                    <div style="width:14px;height:14px;background:#2D6A4F;border-radius:3px;"></div>
                    <div style="width:14px;height:14px;background:#1B4332;border-radius:3px;"></div>
                </div>
                <span>High overlap &nbsp;·&nbsp;
                    Higher = more redundant = less diversification</span>
            </div>
            """, unsafe_allow_html=True)

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

            max_alloc_top = float(top_com["avg_alloc"].max()) if not top_com.empty else 1.0
            n_sel         = len(selected)

            def _ch_row(stock, n_funds, alloc, sector_val):
                bar_w = min(100.0, alloc / max_alloc_top * 100) if max_alloc_top else 0
                sec_str = str(sector_val).strip() if pd.notna(sector_val) and str(sector_val).strip() not in ("", "nan") else ""
                sec_tag = (
                    '<span style="font-size:0.58rem;background:#F3F4F6;color:#6B7280;'
                    'border-radius:4px;padding:1px 5px;margin-left:4px;">'
                    + sec_str.title() + '</span>'
                ) if sec_str else ""
                dots = ""
                for idx in range(n_sel):
                    bg = "#6C3CE1" if idx < n_funds else "#E5E7EB"
                    dots += (
                        '<span style="display:inline-block;width:9px;height:9px;'
                        'border-radius:50%;background:' + bg + ';margin-right:2px;"></span>'
                    )
                return (
                    '<div style="display:flex;align-items:center;padding:8px 0;'
                    'border-bottom:1px solid #F9FAFB;gap:10px;">'
                    '<div style="flex:1;min-width:0;">'
                    '<div style="font-size:0.78rem;font-weight:700;color:#1A1A2E;'
                    'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                    + stock + sec_tag +
                    '</div>'
                    '<div style="background:#EDE9FE;border-radius:3px;height:5px;'
                    'margin-top:5px;overflow:hidden;">'
                    '<div style="background:#6C3CE1;width:' + f"{bar_w:.1f}" + '%;'
                    'height:100%;border-radius:3px;"></div>'
                    '</div></div>'
                    '<div style="flex-shrink:0;">' + dots + '</div>'
                    '<div style="font-size:0.78rem;font-weight:800;color:#6C3CE1;'
                    'width:38px;text-align:right;flex-shrink:0;">'
                    + f"{alloc:.1f}%" +
                    '</div></div>'
                )

            rows_html = "".join(
                _ch_row(r["stock_name"], int(r["funds_holding"]), r["avg_alloc"], r["sector"])
                for _, r in top_com.iterrows()
            )

            legend_parts = []
            for fund_name in selected:
                legend_parts.append(
                    '<div style="display:flex;align-items:center;gap:4px;margin-right:10px;">'
                    '<div style="width:9px;height:9px;border-radius:50%;background:#6C3CE1;"></div>'
                    '<span style="font-size:0.65rem;color:#6B7280;">' + short_name(fund_name) + '</span>'
                    '</div>'
                )
            legend_html = "".join(legend_parts)

            st.markdown(
                '<div style="background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:0.75rem 1rem;">'
                '<div style="display:flex;flex-wrap:wrap;gap:2px;margin-bottom:8px;'
                'padding-bottom:8px;border-bottom:1px solid #F3F4F6;">'
                + legend_html +
                '</div>'
                + rows_html +
                '<div style="font-size:0.62rem;color:#9CA3AF;margin-top:8px;text-align:right;">'
                'Filled dots = fund holds stock &nbsp;·&nbsp; bar = avg allocation weight'
                '</div></div>',
                unsafe_allow_html=True,
            )

    # ── Tab 2: Holdings Overlap ──────────────────────────────────────────────
    with tab_ol:
        st.markdown('<div class="section-title">Fund-Pair Overlap</div>', unsafe_allow_html=True)
        if not sel_sim.empty:
            for _, row in sel_sim.sort_values("normalized_score", ascending=False).iterrows():
                fa, fb, score, common = (
                    row["fund_a"], row["fund_b"],
                    row["normalized_score"], int(row["common_stocks"]),
                )
                label, cls = sim_badge(score)
                st.markdown(f"""
                <div class="overlap-row">
                    <div style="display:flex;align-items:center;justify-content:space-between;">
                        <div style="font-size:0.9rem;font-weight:600;color:#1A1A2E;">
                            {short_name(fa)}
                            <span style="color:#9CA3AF;font-weight:400;margin:0 6px;">vs</span>
                            {short_name(fb)}
                        </div>
                        <div style="display:flex;align-items:center;gap:8px;">
                            <span style="font-size:1.4rem;font-weight:800;color:#6C3CE1;">{score:.0f}%</span>
                            <span class="badge {cls}">{label}</span>
                        </div>
                    </div>
                    <div class="overlap-bar-bg">
                        <div class="overlap-bar-fill" style="width:{score}%;"></div>
                    </div>
                    <div style="font-size:0.72rem;color:#9CA3AF;margin-top:5px;">{common} stocks in common</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown('<div class="section-title">Stock-Level Allocation Comparison</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Stocks held by 2+ funds — bar width shows allocation weight per fund</div>', unsafe_allow_html=True)

        pivot = (
            sel_h.pivot_table(index="stock_name", columns="fund_name", values="allocation_percent", aggfunc="sum")
            .fillna(0)
        )
        pivot.index = pivot.index.str.strip()
        pivot.columns = [short_name(c) for c in pivot.columns]
        pivot["_n"] = (pivot > 0).sum(axis=1)
        pivot = pivot[pivot["_n"] > 1].drop(columns=["_n"])

        if pivot.empty:
            st.info("No stocks are held by more than one selected fund.")
        else:
            fund_cols = pivot.columns.tolist()
            pivot = pivot.sort_values(fund_cols[0], ascending=False)

            # Enrich: add Sector and # Funds columns
            sector_map = (
                sel_h.assign(stock_name=sel_h["stock_name"].str.strip())
                .dropna(subset=["sector"])
                .groupby("stock_name")["sector"]
                .first()
                .to_dict()
            )
            pivot_tbl  = pivot.reset_index()
            pivot_tbl.rename(columns={"stock_name": "Stock"}, inplace=True)
            pivot_tbl.insert(1, "Sector",  pivot_tbl["Stock"].map(sector_map).fillna("—"))
            pivot_tbl.insert(2, "# Funds", (pivot_tbl[fund_cols] > 0).sum(axis=1))

            max_alloc_pv = float(pivot_tbl[fund_cols].values.max()) * 1.25 if pivot_tbl[fund_cols].values.max() > 0 else 1.0

            col_cfg = {
                "Stock":   st.column_config.TextColumn("Stock",   width="medium"),
                "Sector":  st.column_config.TextColumn("Sector",  width="small"),
                "# Funds": st.column_config.ProgressColumn(
                    "# Funds", format="%d",
                    min_value=0, max_value=len(selected), width="small",
                ),
            }
            for fc in fund_cols:
                col_cfg[fc] = st.column_config.ProgressColumn(
                    fc, format="%.2f%%",
                    min_value=0, max_value=max_alloc_pv,
                )

            st.dataframe(
                pivot_tbl,
                use_container_width=True,
                height=min(560, 36 * len(pivot_tbl) + 38),
                hide_index=True,
                column_config=col_cfg,
            )

    # ── Tab 3: Sector Analysis ───────────────────────────────────────────────
    with tab_sec:
        st.markdown('<div class="section-title">Sector Allocation by Fund</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Stacked breakdown — identify concentration per fund and across the group</div>', unsafe_allow_html=True)

        sel_sector = sector_df[sector_df["fund_name"].isin(selected)].copy()
        sel_sector["fund_short"] = sel_sector["fund_name"].apply(short_name)

        top_sectors = (
            sel_sector.groupby("sector")["allocation_percent"]
            .sum().nlargest(10).index.tolist()
        )
        plot_df = sel_sector[sel_sector["sector"].isin(top_sectors)]

        SECTOR_COLORS = {
            "FINANCIAL": "#3B82F6", "TECHNOLOGY": "#8B5CF6", "ENERGY": "#F97316",
            "HEALTHCARE": "#10B981", "CONSUMER DISCRETIONARY": "#F59E0B",
            "CONSUMER STAPLES": "#84CC16", "AUTOMOBILE": "#EC4899",
            "COMMUNICATION": "#06B6D4", "CAPITAL GOODS": "#6366F1",
            "MATERIALS": "#A78BFA", "SERVICES": "#F472B6",
        }

        fig_bar = px.bar(
            plot_df, x="fund_short", y="allocation_percent", color="sector",
            barmode="stack", color_discrete_map=SECTOR_COLORS,
            labels={"fund_short": "Fund", "allocation_percent": "Allocation %", "sector": "Sector"},
        )
        fig_bar.update_layout(
            height=420,
            legend=dict(orientation="h", yanchor="bottom", y=-0.45, xanchor="left", x=0),
            margin=dict(l=0, r=0, t=10, b=100),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif"),
            xaxis=dict(tickangle=-15),
        )
        fig_bar.update_traces(marker_line_width=0)
        st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown('<div class="section-title" style="margin-top:1rem;">Sector Concentration Table</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Each bar shows allocation % to that sector — compare widths across funds at a glance</div>', unsafe_allow_html=True)

        sec_pivot = (
            sel_sector.pivot_table(index="sector", columns="fund_short", values="allocation_percent", aggfunc="sum")
            .fillna(0)
        )
        sec_pivot["_avg"] = sec_pivot.mean(axis=1)
        sec_pivot = sec_pivot.sort_values("_avg", ascending=False).drop(columns=["_avg"])
        sec_tbl   = sec_pivot.reset_index()
        fund_cols = [c for c in sec_tbl.columns if c != "sector"]
        max_sec   = float(sec_pivot.values.max()) * 1.25

        col_cfg = {"sector": st.column_config.TextColumn("Sector", width="medium")}
        for fc in fund_cols:
            col_cfg[fc] = st.column_config.ProgressColumn(
                fc, format="%.1f%%", min_value=0, max_value=max_sec,
            )
        st.dataframe(
            sec_tbl,
            use_container_width=True,
            height=min(420, 36 * len(sec_tbl) + 38),
            hide_index=True,
            column_config=col_cfg,
        )

    # ── Tab 4: Common Holdings ───────────────────────────────────────────────
    with tab_hold:
        st.markdown('<div class="section-title">Common Holdings Intelligence</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Stocks held across multiple selected funds — with allocation trend data</div>', unsafe_allow_html=True)

        stock_detail = (
            sel_h.groupby("stock_name")
            .agg(
                funds_holding=("fund_name",        "nunique"),
                avg_alloc    =("allocation_percent","mean"),
                avg_3m       =("change_3m_percent", "mean"),
                avg_6m       =("change_6m_percent", "mean"),
                avg_1y       =("change_1y_percent", "mean"),
                sector       =("sector",            "first"),
            )
            .reset_index()
        )
        stock_detail["stock_name"] = stock_detail["stock_name"].str.strip()
        stock_detail = (
            stock_detail[stock_detail["funds_holding"] > 1]
            .sort_values(["funds_holding", "avg_alloc"], ascending=[False, False])
            .reset_index(drop=True)
        )

        def _t(v):
            try:
                return "↑" if float(v) > 0.3 else ("↓" if float(v) < -0.3 else "→")
            except Exception:
                return "→"

        stock_detail.insert(2, "Trend", stock_detail["avg_3m"].apply(_t))
        max_alloc_ch = float(stock_detail["avg_alloc"].max()) * 1.25

        st.dataframe(
            stock_detail,
            use_container_width=True,
            height=min(560, 36 * len(stock_detail) + 38),
            hide_index=True,
            column_config={
                "stock_name":    st.column_config.TextColumn("Stock",        width="medium"),
                "funds_holding": st.column_config.ProgressColumn(
                                     "Funds Holding", format="%d",
                                     min_value=0, max_value=len(selected),   width="small"),
                "Trend":         st.column_config.TextColumn("Trend",        width=60,
                                     help="3M direction: ↑ growing · ↓ declining · → stable"),
                "avg_alloc":     st.column_config.ProgressColumn(
                                     "Avg Alloc %", format="%.2f%%",
                                     min_value=0, max_value=max_alloc_ch,    width="medium"),
                "avg_3m":        st.column_config.NumberColumn("3M Δ%",      format="%+.2f%%", width="small"),
                "avg_6m":        st.column_config.NumberColumn("6M Δ%",      format="%+.2f%%", width="small"),
                "avg_1y":        st.column_config.NumberColumn("1Y Δ%",      format="%+.2f%%", width="small"),
                "sector":        st.column_config.TextColumn("Sector",       width="small"),
            },
        )

    # ── Tab 5: Insights ──────────────────────────────────────────────────────
    with tab_ins:
        st.markdown('<div class="section-title">Key Insights</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Data-driven observations — for analysis only, not investment advice</div>', unsafe_allow_html=True)

        insights = generate_insights(selected, similarity, holdings, sector_df)
        if not insights:
            st.info("No significant patterns detected for this fund combination.")
        for ins in insights:
            cls_map = {"alert": "insight-alert", "warning": "insight-warning",
                       "info": "insight-info", "success": "insight-success"}
            st.markdown(f"""
            <div class="insight-card {cls_map[ins['type']]}">
                <div class="insight-icon">{ins['icon']}</div>
                <div class="insight-text">{ins['text']}</div>
            </div>
            """, unsafe_allow_html=True)

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
            st.metric("Portfolio Overlap Score", f"{avg_s:.0f}%")

        st.markdown("""
        <div class="disclaimer">
            Insights are generated from portfolio data for informational purposes only.
            They do not constitute investment advice, buy/sell recommendations, or financial planning guidance.
        </div>
        """, unsafe_allow_html=True)


# ── PAGE: PORTFOLIO UPLOAD ────────────────────────────────────────────────────

def page_portfolio_upload():
    nav_header(back_page="home", back_label="Home")

    st.markdown("## Analyze Your MF Portfolio")
    st.markdown(
        "<p style='color:#6B7280;margin-top:-0.5rem;margin-bottom:1.5rem;'>"
        "Upload your portfolio to discover hidden exposure, overlap and concentration insights.</p>",
        unsafe_allow_html=True,
    )

    col_up, col_info = st.columns([3, 2], gap="large")

    with col_up:
        uploaded = st.file_uploader(
            "Drop your portfolio CSV or XLSX here",
            type=["csv", "xlsx"],
            help="Expected columns: fund_name, invested_amount (optional), units (optional)",
        )

        st.markdown("<div style='text-align:center;color:#9CA3AF;margin:0.5rem 0;font-size:0.85rem;'>— or enter manually —</div>", unsafe_allow_html=True)

        if st.toggle("Enter portfolio manually"):
            manual_df = pd.DataFrame({
                "fund_name":       ["HDFC Large Cap Fund", "ICICI Prudential Bluechip Fund"],
                "invested_amount": [50000,  30000],
                "units":           [100.50, 80.20],
            })
            edited = st.data_editor(manual_df, num_rows="dynamic", use_container_width=True, key="manual_edit")
            if st.button("Run X-Ray →", type="primary", use_container_width=True):
                st.session_state.portfolio_df = edited
                st.session_state.page = "portfolio_xray"
                st.rerun()

        # Template download
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

        if uploaded:
            try:
                portfolio_df = (
                    pd.read_csv(uploaded)
                    if uploaded.name.endswith(".csv")
                    else pd.read_excel(uploaded)
                )
                st.success(f"✓ {len(portfolio_df)} holdings loaded from **{uploaded.name}**")
                st.dataframe(portfolio_df.head(10), use_container_width=True)
                if st.button("Run Portfolio X-Ray →", type="primary", use_container_width=True):
                    st.session_state.portfolio_df = portfolio_df
                    st.session_state.page = "portfolio_xray"
                    st.rerun()
            except Exception as e:
                st.error(f"Could not read file: {e}")

        st.markdown(
            "<div style='text-align:center;font-size:0.72rem;color:#9CA3AF;margin-top:1rem;'>"
            "🔒 Your data stays in your browser session and is never stored or shared.</div>",
            unsafe_allow_html=True,
        )

    with col_info:
        st.markdown('<div class="section-title">What you\'ll discover</div>', unsafe_allow_html=True)
        for icon, title, desc in [
            ("🏦", "Hidden Stock Exposure",  "See exactly which stocks you indirectly own and in what proportions across all funds."),
            ("🔍", "Duplicate Fund Detection","Identify funds with near-identical portfolios that add no real diversification."),
            ("📊", "Sector Concentration",   "Find if you're over-exposed to a single sector like BFSI or IT across your portfolio."),
            ("🔗", "Portfolio Overlap Score", "A single score showing how truly diversified your combined fund portfolio is."),
            ("📈", "Allocation Trends",      "See how fund managers have been adjusting stock weights over 3M, 6M and 1Y periods."),
        ]:
            st.markdown(f"""
            <div style="display:flex;gap:0.75rem;margin-bottom:1rem;align-items:flex-start;">
                <div style="font-size:1.5rem;flex-shrink:0;">{icon}</div>
                <div>
                    <div style="font-weight:600;font-size:0.85rem;color:#1A1A2E;margin-bottom:2px;">{title}</div>
                    <div style="font-size:0.75rem;color:#6B7280;line-height:1.5;">{desc}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("""
        <div style="background:#EEF2FF;border-radius:10px;padding:1rem;margin-top:0.5rem;">
            <div style="font-size:0.8rem;font-weight:700;color:#6C3CE1;margin-bottom:0.5rem;">📌 Expected CSV Format</div>
            <div style="font-family:monospace;font-size:0.72rem;color:#374151;line-height:1.8;">
                fund_name, invested_amount, units<br>
                HDFC Large Cap Fund, 50000, 100.5<br>
                ICICI Prudential Bluechip Fund, 30000, 80.2
            </div>
        </div>
        """, unsafe_allow_html=True)


# ── PAGE: PORTFOLIO X-RAY ─────────────────────────────────────────────────────

def page_portfolio_xray():
    nav_header(back_page="portfolio_upload", back_label="Upload")

    portfolio_df = st.session_state.get("portfolio_df", pd.DataFrame())
    if portfolio_df.empty:
        st.warning("No portfolio data. Please upload your portfolio first.")
        return

    holdings   = load_holdings()
    similarity = load_similarity()
    sector_df  = get_sector_breakdown(holdings)

    fund_col = next((c for c in portfolio_df.columns if "fund" in c.lower()), None)
    if not fund_col:
        st.error("Could not find a 'fund_name' column in your file.")
        return

    user_funds    = portfolio_df[fund_col].dropna().unique().tolist()
    matched_funds = [f for f in user_funds if f in holdings["fund_name"].values]
    unmatched     = [f for f in user_funds if f not in matched_funds]

    st.markdown("## Portfolio X-Ray")
    st.markdown(
        f"<p style='color:#6B7280;margin-top:-0.5rem;margin-bottom:1.5rem;'>"
        f"Analysis of {len(user_funds)} fund(s) — {len(matched_funds)} matched in our database</p>",
        unsafe_allow_html=True,
    )

    if unmatched:
        st.info(f"⚠️  Funds not found in our database (will be excluded): {', '.join(unmatched)}")
    if not matched_funds:
        st.error("None of your funds matched our database. Please check fund names match those on ETMoney.")
        return

    sel_h   = holdings[holdings["fund_name"].isin(matched_funds)].copy()
    sel_sim = similarity[
        similarity["fund_a"].isin(matched_funds) & similarity["fund_b"].isin(matched_funds)
    ]

    # ── Summary metrics ──
    n_unique = sel_h["stock_name"].nunique()
    avg_sim  = sel_sim["normalized_score"].mean() if not sel_sim.empty else 0
    n_secs   = sel_h["sector"].nunique()
    c1, c2, c3, c4 = st.columns(4)
    for col, val, label in [
        (c1, str(len(matched_funds)), "Funds Analyzed"),
        (c2, str(n_unique),           "Unique Stocks You Own"),
        (c3, f"{avg_sim:.0f}%",       "Avg Fund Overlap"),
        (c4, str(n_secs),             "Sectors Covered"),
    ]:
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{val}</div>
                <div class="metric-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    tab_exp, tab_ol, tab_sec, tab_ins = st.tabs([
        "🏦 Hidden Exposure",
        "🔗 Fund Overlap",
        "🏗️ Sector Concentration",
        "💡 Insights",
    ])

    with tab_exp:
        st.markdown('<div class="section-title">Your Indirect Stock Exposure</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Stocks you own through your mutual funds (by average allocation across holdings)</div>', unsafe_allow_html=True)

        exp = (
            sel_h.groupby("stock_name")
            .agg(funds_holding=("fund_name", "nunique"), avg_alloc=("allocation_percent", "mean"), sector=("sector", "first"))
            .reset_index()
            .sort_values("avg_alloc", ascending=False)
        )
        exp["stock_name"] = exp["stock_name"].str.strip()

        fig_e = px.bar(
            exp.head(15), x="avg_alloc", y="stock_name", orientation="h",
            color="sector", labels={"avg_alloc": "Avg Allocation %", "stock_name": ""},
            height=420,
        )
        fig_e.update_layout(
            yaxis=dict(autorange="reversed"),
            margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="top", y=-0.15),
            font=dict(family="Inter, sans-serif"),
        )
        st.plotly_chart(fig_e, use_container_width=True)

        st.dataframe(
            exp.reset_index(drop=True),
            use_container_width=True, height=380,
            column_config={
                "stock_name":    st.column_config.TextColumn("Stock"),
                "funds_holding": st.column_config.NumberColumn("Funds Holding", format="%d"),
                "avg_alloc":     st.column_config.NumberColumn("Avg Alloc %",   format="%.2f%%"),
                "sector":        st.column_config.TextColumn("Sector"),
            },
            hide_index=True,
        )

    with tab_ol:
        st.markdown('<div class="section-title">Overlap Between Your Funds</div>', unsafe_allow_html=True)
        if sel_sim.empty:
            st.info("Need at least 2 matched funds to compute overlap.")
        else:
            for _, row in sel_sim.sort_values("normalized_score", ascending=False).iterrows():
                label, cls = sim_badge(row["normalized_score"])
                st.markdown(f"""
                <div class="overlap-row">
                    <div style="display:flex;align-items:center;justify-content:space-between;">
                        <div style="font-size:0.9rem;font-weight:600;color:#1A1A2E;">
                            {short_name(row['fund_a'])}
                            <span style="color:#9CA3AF;font-weight:400;margin:0 6px;">vs</span>
                            {short_name(row['fund_b'])}
                        </div>
                        <div style="display:flex;align-items:center;gap:8px;">
                            <span style="font-size:1.4rem;font-weight:800;color:#6C3CE1;">{row['normalized_score']:.0f}%</span>
                            <span class="badge {cls}">{label} Overlap</span>
                        </div>
                    </div>
                    <div class="overlap-bar-bg">
                        <div class="overlap-bar-fill" style="width:{row['normalized_score']}%;"></div>
                    </div>
                    <div style="font-size:0.72rem;color:#9CA3AF;margin-top:5px;">{int(row['common_stocks'])} common stocks</div>
                </div>
                """, unsafe_allow_html=True)

    with tab_sec:
        st.markdown('<div class="section-title">Sector Concentration in Your Portfolio</div>', unsafe_allow_html=True)

        sel_sector = sector_df[sector_df["fund_name"].isin(matched_funds)]
        avg_sec    = sel_sector.groupby("sector")["allocation_percent"].mean().reset_index()
        avg_sec    = avg_sec.sort_values("allocation_percent", ascending=False)

        c_donut, c_table = st.columns([2, 3])
        with c_donut:
            fig_d = px.pie(
                avg_sec.head(8), names="sector", values="allocation_percent",
                hole=0.52, height=340,
            )
            fig_d.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif"),
                legend=dict(orientation="v", yanchor="middle", y=0.5),
            )
            fig_d.update_traces(textposition="outside", textinfo="percent+label")
            st.plotly_chart(fig_d, use_container_width=True)

        with c_table:
            avg_sec["bar"] = avg_sec["allocation_percent"].round(1)
            st.dataframe(
                avg_sec.reset_index(drop=True),
                use_container_width=True, height=340,
                column_config={
                    "sector":             st.column_config.TextColumn("Sector"),
                    "allocation_percent": st.column_config.NumberColumn("Avg Allocation %", format="%.1f%%"),
                    "bar":                st.column_config.ProgressColumn("Weight", min_value=0, max_value=50),
                },
                hide_index=True,
            )

    with tab_ins:
        st.markdown('<div class="section-title">Portfolio X-Ray Insights</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Findings based on your uploaded portfolio — for analysis only</div>', unsafe_allow_html=True)

        insights = generate_insights(matched_funds, similarity, holdings, sector_df)
        for ins in insights:
            cls_map = {"alert": "insight-alert", "warning": "insight-warning",
                       "info": "insight-info", "success": "insight-success"}
            st.markdown(f"""
            <div class="insight-card {cls_map[ins['type']]}">
                <div class="insight-icon">{ins['icon']}</div>
                <div class="insight-text">{ins['text']}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("""
        <div class="disclaimer">
            Insights are generated from portfolio holdings data for informational and analytical purposes only.
            They do not constitute investment advice, buy/sell recommendations, or financial planning guidance.
        </div>
        """, unsafe_allow_html=True)


# ── ROUTER ────────────────────────────────────────────────────────────────────

# ── PAGE: STOCK EXPLORER ─────────────────────────────────────────────────────

def page_stock_explorer():
    nav_header(back_page="home", back_label="Home")

    holdings = load_holdings()
    if holdings.empty:
        st.warning("Holdings data not available.")
        return

    st.markdown("## Stock Explorer")
    st.markdown(
        "<p style='color:#6B7280;margin-top:-0.5rem;margin-bottom:1.5rem;'>"
        "Select any stock to see which funds hold it, their exposure levels, and historical allocation trends. "
        "For informational and analytical purposes only — not investment advice.</p>",
        unsafe_allow_html=True,
    )

    all_stocks = sorted(holdings["stock_name"].unique().tolist())
    preselected = st.session_state.pop("preselected_stock", "")
    default_idx = all_stocks.index(preselected) if preselected in all_stocks else 0

    selected_stock = st.selectbox("Search for a stock", all_stocks, index=default_idx)
    if not selected_stock:
        return

    stock_df = holdings[holdings["stock_name"] == selected_stock].sort_values(
        "allocation_percent", ascending=False
    )
    n_holding   = len(stock_df)
    avg_alloc   = stock_df["allocation_percent"].mean()
    max_alloc   = stock_df["allocation_percent"].max()
    max_fund    = stock_df.loc[stock_df["allocation_percent"].idxmax(), "fund_name"]
    sector      = stock_df["sector"].mode().iloc[0] if not stock_df.empty else "—"
    total_funds = holdings["fund_name"].nunique()

    # Metric row
    c1, c2, c3, c4 = st.columns(4)
    for col, val, label, sub in [
        (c1, str(n_holding),        "Funds Holding",      f"Out of {total_funds} funds"),
        (c2, f"{avg_alloc:.2f}%",   "Avg Allocation",     "Average across holding funds"),
        (c3, f"{max_alloc:.2f}%",   "Highest Allocation", max_fund[:28]),
        (c4, sector.title(),        "Sector",             "Primary classification"),
    ]:
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value" style="font-size:1.65rem;">{val}</div>
                <div class="metric-label">{label}</div>
                <div class="metric-sub">{sub}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Allocation bar chart
    fig = px.bar(
        stock_df,
        x="allocation_percent", y="fund_name", orientation="h",
        color="allocation_percent",
        color_continuous_scale=[[0, "#EDE9FE"], [1, "#6C3CE1"]],
        labels={"allocation_percent": "Allocation %", "fund_name": ""},
        title=f"{selected_stock} — Allocation Across Funds",
        text="allocation_percent",
    )
    fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    fig.update_layout(
        height=max(300, n_holding * 44),
        yaxis={"categoryorder": "total ascending"},
        showlegend=False, coloraxis_showscale=False,
        plot_bgcolor="#F8F9FA", paper_bgcolor="#F8F9FA",
        title_font_color="#1A1A2E",
        margin={"l": 10, "r": 60, "t": 45, "b": 20},
    )
    st.plotly_chart(fig, use_container_width=True)

    # Fund breakdown table
    st.markdown('<div class="section-title">Fund-level Breakdown</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">Allocation % and 3M / 6M / 1Y allocation changes per fund</div>',
        unsafe_allow_html=True,
    )

    display_df = stock_df[[
        "fund_name", "allocation_percent",
        "sector", "change_3m_percent", "change_6m_percent", "change_1y_percent",
    ]].copy()

    def _trend_arrow(v):
        try:
            return "↑" if float(v) > 0.3 else ("↓" if float(v) < -0.3 else "→")
        except Exception:
            return "→"

    display_df.insert(1, "Trend", display_df["change_3m_percent"].apply(_trend_arrow))
    display_df.columns = ["Fund", "Trend", "Alloc %", "Sector", "3M Δ%", "6M Δ%", "1Y Δ%"]

    max_alloc_val = float(display_df["Alloc %"].max()) * 1.25
    tbl_height    = min(580, 36 * len(display_df) + 38)

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=tbl_height,
        column_config={
            "Fund":   st.column_config.TextColumn("Fund", width="large"),
            "Trend":  st.column_config.TextColumn("Trend", width=60,
                          help="↑ allocation growing · ↓ declining · → stable (3M)"),
            "Alloc %": st.column_config.ProgressColumn(
                "Allocation %", format="%.2f%%",
                min_value=0, max_value=max_alloc_val, width="medium",
            ),
            "Sector": st.column_config.TextColumn("Sector", width="medium"),
            "3M Δ%":  st.column_config.NumberColumn("3M Δ%",  format="%+.2f%%", width="small"),
            "6M Δ%":  st.column_config.NumberColumn("6M Δ%",  format="%+.2f%%", width="small"),
            "1Y Δ%":  st.column_config.NumberColumn("1Y Δ%",  format="%+.2f%%", width="small"),
        },
    )

    # Insights
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">Insights</div>', unsafe_allow_html=True)

    coverage = n_holding / total_funds * 100
    if coverage >= 80:
        st.markdown(f"""<div class="insight-card insight-alert">
            <div class="insight-icon">⚠️</div>
            <div class="insight-text"><strong>High Concentration Risk</strong> — {selected_stock} appears in
            {n_holding}/{total_funds} funds ({coverage:.0f}% coverage). Investors holding multiple funds
            across categories likely have significant overlapping exposure to this stock.</div></div>""",
            unsafe_allow_html=True)
    elif coverage >= 50:
        st.markdown(f"""<div class="insight-card insight-warning">
            <div class="insight-icon">📊</div>
            <div class="insight-text"><strong>Moderate Coverage</strong> — {selected_stock} is held by
            {n_holding}/{total_funds} funds ({coverage:.0f}% coverage), a moderately common
            holding across the registry.</div></div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div class="insight-card insight-info">
            <div class="insight-icon">🔍</div>
            <div class="insight-text"><strong>Selective Holding</strong> — {selected_stock} appears in only
            {n_holding}/{total_funds} funds ({coverage:.0f}% coverage), indicating a selective conviction
            pick rather than a consensus position.</div></div>""", unsafe_allow_html=True)

    alloc_spread = stock_df["allocation_percent"].max() - stock_df["allocation_percent"].min()
    if alloc_spread > 3:
        st.markdown(f"""<div class="insight-card insight-info">
            <div class="insight-icon">📐</div>
            <div class="insight-text"><strong>Wide Allocation Spread</strong> — Allocation ranges from
            {stock_df["allocation_percent"].min():.2f}% to {stock_df["allocation_percent"].max():.2f}%
            (spread: {alloc_spread:.2f}%), reflecting significantly different conviction levels among
            fund managers.</div></div>""", unsafe_allow_html=True)

    avg_3m = stock_df["change_3m_percent"].mean()
    if not pd.isna(avg_3m):
        direction = "increasing" if avg_3m > 0.1 else "decreasing" if avg_3m < -0.1 else "stable"
        icon      = "📈" if avg_3m > 0.1 else "📉" if avg_3m < -0.1 else "➡️"
        ctype     = "insight-success" if avg_3m > 0.1 else "insight-warning" if avg_3m < -0.1 else "insight-info"
        st.markdown(f"""<div class="insight-card {ctype}">
            <div class="insight-icon">{icon}</div>
            <div class="insight-text"><strong>3-Month Trend</strong> — Average allocation to
            {selected_stock} has been {direction} over the last 3 months
            (avg change: {avg_3m:+.2f}%) across holding funds.</div></div>""",
            unsafe_allow_html=True)

    st.markdown("""<div class="disclaimer">
        Stock exposure data is for informational and analytical purposes only — not investment advice.
        Data sourced from ETMoney.</div>""", unsafe_allow_html=True)


# ── PAGE: OVERLAP DRILLDOWN ───────────────────────────────────────────────────

def page_overlap_drilldown():
    nav_header(back_page="home", back_label="Home")

    holdings   = load_holdings()
    similarity = load_similarity()

    if similarity.empty:
        st.warning("Similarity data not available.")
        return

    def _short(name):
        return name.replace(" Large Cap Fund", "").replace(" Large Cap", "").strip()

    st.markdown("## Fund Overlap Analysis")
    st.markdown(
        "<p style='color:#6B7280;margin-top:-0.5rem;margin-bottom:1.5rem;'>"
        "Explore which fund pairs share the most holdings — a key indicator of portfolio redundancy. "
        "For informational and analytical purposes only — not investment advice.</p>",
        unsafe_allow_html=True,
    )

    top_row    = similarity.nlargest(1, "normalized_score").iloc[0]
    max_pair_a = top_row["fund_a"]
    max_pair_b = top_row["fund_b"]
    max_score  = top_row["normalized_score"]
    max_common = int(top_row["common_stocks"])
    high_count = int((similarity["normalized_score"] >= 60).sum())

    # ── Summary metrics ──
    c1, c2, c3, c4 = st.columns(4)
    for col, val, label, sub in [
        (c1, f"{max_score:.0f}%",   "Highest Overlap",    "Max pairwise similarity score"),
        (c2, str(max_common),       "Common Stocks",      "In the top-overlap pair"),
        (c3, str(high_count),       "High-Overlap Pairs", "Pairs with ≥60% overlap"),
        (c4, str(len(similarity)),  "Pairs Analyzed",     "All fund-pair combinations"),
    ]:
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value" style="font-size:2rem;">{val}</div>
                <div class="metric-label">{label}</div>
                <div class="metric-sub">{sub}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Top 15 bar chart (full width) ──
    st.markdown('<div class="section-title">Top 15 Fund Pair Overlaps</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">Higher score = more shared holdings = higher redundancy risk</div>',
        unsafe_allow_html=True,
    )
    top15 = similarity.nlargest(15, "normalized_score").copy()
    top15["pair"] = top15.apply(
        lambda r: f"{_short(r['fund_a'])} ↔ {_short(r['fund_b'])}", axis=1
    )
    fig = px.bar(
        top15.iloc[::-1],
        x="normalized_score", y="pair", orientation="h",
        color="normalized_score",
        color_continuous_scale=[[0, "#EDE9FE"], [0.6, "#9B7FE8"], [1, "#6C3CE1"]],
        labels={"normalized_score": "Overlap %", "pair": ""},
        text="normalized_score",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        height=460, showlegend=False, coloraxis_showscale=False,
        plot_bgcolor="#F8F9FA", paper_bgcolor="#F8F9FA",
        margin={"l": 10, "r": 60, "t": 10, "b": 20},
        xaxis={"range": [0, max_score + 12]},
        yaxis={"tickfont": {"size": 11}},
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── All Pairs table (full width, selectable) ──
    st.markdown('<div class="section-title">All Fund Pairs</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">Select a row to update the Common Holdings section below</div>',
        unsafe_allow_html=True,
    )

    sorted_sim = similarity.sort_values("normalized_score", ascending=False).reset_index(drop=True)

    def _risk(score):
        if score >= 65: return "High"
        if score >= 45: return "Medium"
        return "Low"

    disp = pd.DataFrame({
        "Fund A":        sorted_sim["fund_a"].apply(_short),
        "Fund B":        sorted_sim["fund_b"].apply(_short),
        "Overlap %":     sorted_sim["normalized_score"],
        "Common Stocks": sorted_sim["common_stocks"],
        "Risk Level":    sorted_sim["normalized_score"].apply(_risk),
    })

    sel_result = st.dataframe(
        disp,
        use_container_width=True,
        hide_index=True,
        height=min(400, 36 * len(disp) + 38),
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Fund A":        st.column_config.TextColumn("Fund A",        width="large"),
            "Fund B":        st.column_config.TextColumn("Fund B",        width="large"),
            "Overlap %":     st.column_config.ProgressColumn(
                                 "Overlap %", format="%.1f%%",
                                 min_value=0, max_value=100, width="medium"),
            "Common Stocks": st.column_config.NumberColumn(
                                 "Common Stocks", format="%d stocks",    width="small"),
            "Risk Level":    st.column_config.TextColumn("Risk",          width="small"),
        },
    )

    # Resolve selected pair (default = top pair)
    sel_rows = sel_result.selection.rows
    if sel_rows:
        row       = sorted_sim.iloc[sel_rows[0]]
        sel_a     = row["fund_a"]
        sel_b     = row["fund_b"]
        sel_score = float(row["normalized_score"])
        sel_n     = int(row["common_stocks"])
    else:
        sel_a, sel_b, sel_score, sel_n = max_pair_a, max_pair_b, max_score, max_common

    short_a = _short(sel_a)
    short_b = _short(sel_b)

    # ── Common Holdings (dynamic) ──
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f'<div class="section-title">Common Holdings: {short_a} ↔ {short_b}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="section-sub">{sel_n} shared positions · {sel_score:.1f}% overlap score</div>',
        unsafe_allow_html=True,
    )

    if not holdings.empty:
        h_a = holdings[holdings["fund_name"] == sel_a][
            ["stock_name", "allocation_percent", "sector"]
        ].rename(columns={"allocation_percent": "alloc_a"})
        h_b = holdings[holdings["fund_name"] == sel_b][
            ["stock_name", "allocation_percent"]
        ].rename(columns={"allocation_percent": "alloc_b"})
        common_df = pd.merge(h_a, h_b, on="stock_name").sort_values("alloc_a", ascending=False)
        common_df.columns = ["Stock", f"{short_a} %", "Sector", f"{short_b} %"]
        max_alloc_scale = max(
            common_df[f"{short_a} %"].max(), common_df[f"{short_b} %"].max()
        ) * 1.25
        st.dataframe(
            common_df,
            use_container_width=True,
            hide_index=True,
            height=min(520, 36 * len(common_df) + 38),
            column_config={
                "Stock": st.column_config.TextColumn("Stock", width="medium"),
                f"{short_a} %": st.column_config.ProgressColumn(
                    short_a, format="%.2f%%",
                    min_value=0, max_value=max_alloc_scale, width="medium",
                ),
                "Sector": st.column_config.TextColumn("Sector", width="small"),
                f"{short_b} %": st.column_config.ProgressColumn(
                    short_b, format="%.2f%%",
                    min_value=0, max_value=max_alloc_scale, width="medium",
                ),
            },
        )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button(
        f"Open Full Comparison: {short_a} vs {short_b} →",
        type="primary", use_container_width=True,
    ):
        st.session_state.selected_funds = [sel_a, sel_b]
        st.session_state.page = "compare"
        st.rerun()

    # ── Insights ──
    st.markdown("<br>", unsafe_allow_html=True)
    if high_count > 0:
        st.markdown(f"""<div class="insight-card insight-warning">
            <div class="insight-icon">⚠️</div>
            <div class="insight-text"><strong>{high_count} High-Overlap Pair(s)</strong> —
            {high_count} fund combination(s) share ≥60% of their portfolios. Holding these funds
            together may provide less diversification than expected.</div></div>""",
            unsafe_allow_html=True)

    median_overlap = similarity["normalized_score"].median()
    st.markdown(f"""<div class="insight-card insight-info">
        <div class="insight-icon">📊</div>
        <div class="insight-text"><strong>Median Overlap: {median_overlap:.1f}%</strong> —
        The typical fund pair shares {median_overlap:.1f}% of their portfolio, reflecting
        the structural concentration of equity funds around a core set of index-dominant
        stocks.</div></div>""", unsafe_allow_html=True)

    st.markdown("""<div class="disclaimer">
        Overlap analysis is for informational and analytical purposes only — not investment advice.
        Data sourced from ETMoney.</div>""", unsafe_allow_html=True)


def main():
    # Handle ?nav= query params from sidebar links and internal navigation
    nav_target = st.query_params.get("nav", "")
    if nav_target:
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

    render_sidebar()

    routes = {
        "home":               render_welcome,
        "category":           page_category_select,
        "explorer":           page_fund_explorer,
        "compare":            page_compare,
        "portfolio_upload":   page_portfolio_upload,
        "portfolio_xray":     page_portfolio_xray,
        "stock_explorer":     page_stock_explorer,
        "overlap_drilldown":  page_overlap_drilldown,
    }
    routes.get(st.session_state.page, render_welcome)()


main()
