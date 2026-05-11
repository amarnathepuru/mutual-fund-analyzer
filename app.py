import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

st.set_page_config(
    page_title="FundInsight — Investment Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── GLOBAL CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #F8F9FA; }
[data-testid="stHeader"] { display: none; }
[data-testid="stSidebar"] { display: none; }
footer { display: none; }
.block-container { padding: 2rem 3rem !important; max-width: 1280px !important; margin: 0 auto; }

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
}
.metric-value { font-size: 2.25rem; font-weight: 800; color: #6C3CE1; line-height: 1; }
.metric-label { font-size: 0.75rem; color: #6B7280; font-weight: 600;
                text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }
.metric-sub { font-size: 0.7rem; color: #9CA3AF; margin-top: 4px; }

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
</style>
""", unsafe_allow_html=True)


# ── DATA LOADING ──────────────────────────────────────────────────────────────

@st.cache_data
def load_holdings():
    try:
        return pd.read_csv("data/processed/normalized_holdings.csv")
    except Exception:
        return pd.DataFrame()


@st.cache_data
def load_master():
    try:
        return pd.read_csv("data/fund_master.csv")
    except Exception:
        return pd.DataFrame()


@st.cache_data
def load_similarity():
    try:
        return pd.read_csv("data/processed/fund_similarity.csv")
    except Exception:
        return pd.DataFrame()


@st.cache_data
def load_common():
    try:
        return pd.read_csv("data/processed/common_holdings.csv")
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


def build_sim_matrix(similarity_df, fund_names):
    matrix = pd.DataFrame(100.0, index=fund_names, columns=fund_names)
    for _, row in similarity_df.iterrows():
        a, b, s = row["fund_a"], row["fund_b"], row["similarity_score"]
        if a in fund_names and b in fund_names:
            matrix.loc[a, b] = s
            matrix.loc[b, a] = s
    return matrix


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

    if not sel_sim.empty:
        worst = sel_sim.loc[sel_sim["similarity_score"].idxmax()]
        if worst["similarity_score"] >= 60:
            insights.append({
                "type": "alert", "icon": "⚠️",
                "text": (
                    f"<strong>{short_name(worst['fund_a'])}</strong> and "
                    f"<strong>{short_name(worst['fund_b'])}</strong> share "
                    f"<strong>{worst['similarity_score']:.0f}%</strong> portfolio similarity. "
                    "Holding both funds provides minimal additional diversification."
                ),
            })
        best = sel_sim.loc[sel_sim["similarity_score"].idxmin()]
        if best["similarity_score"] < 45:
            insights.append({
                "type": "success", "icon": "✅",
                "text": (
                    f"<strong>{short_name(best['fund_a'])}</strong> and "
                    f"<strong>{short_name(best['fund_b'])}</strong> have "
                    f"relatively low overlap ({best['similarity_score']:.0f}%), "
                    "offering meaningful diversification when combined."
                ),
            })

    sel_sector = sector_df[sector_df["fund_name"].isin(fund_list)]
    if not sel_sector.empty:
        avg_by_sector = sel_sector.groupby("sector")["allocation_percent"].mean()
        top_s = avg_by_sector.idxmax()
        top_pct = avg_by_sector.max()
        if top_pct > 28:
            insights.append({
                "type": "warning", "icon": "🏦",
                "text": (
                    f"All selected funds carry heavy <strong>{top_s}</strong> sector exposure "
                    f"(avg {top_pct:.1f}%). This creates correlated sector risk "
                    "even across multiple funds."
                ),
            })

    sel_h = holdings_df[holdings_df["fund_name"].isin(fund_list)]
    counts = sel_h.groupby("stock_name")["fund_name"].nunique()
    unanimous = (counts == len(fund_list)).sum()
    if unanimous > 0:
        insights.append({
            "type": "info", "icon": "📌",
            "text": (
                f"<strong>{unanimous} stock{'s' if unanimous > 1 else ''}</strong> "
                f"appear in all {len(fund_list)} selected funds. "
                "Your indirect exposure to these stocks is amplified across your entire portfolio."
            ),
        })

    return insights


# ── NAV HEADER ────────────────────────────────────────────────────────────────

def nav_header(back_page=None, back_label="Back"):
    c1, c2 = st.columns([1, 6])
    with c1:
        st.markdown('<div class="app-logo">📊 FundInsight</div>', unsafe_allow_html=True)
    if back_page:
        with c2:
            if st.button(f"← {back_label}", key="nav_back_btn"):
                st.session_state.page = back_page
                st.rerun()


# ── PAGE: HOME ────────────────────────────────────────────────────────────────

def page_home():
    holdings = load_holdings()
    similarity = load_similarity()
    common = load_common()

    st.markdown('<div class="app-logo" style="margin-bottom:2rem;">📊 FundInsight</div>', unsafe_allow_html=True)

    st.markdown("## Understand Your Investments Better")
    st.markdown(
        "<p style='color:#6B7280;font-size:1rem;margin-top:-0.5rem;margin-bottom:1.5rem;'>"
        "Analyze mutual fund overlap, exposure, diversification and portfolio concentration — all in one place."
        "</p>",
        unsafe_allow_html=True,
    )

    # Live stats banner
    n_funds   = holdings["fund_name"].nunique() if not holdings.empty else 0
    n_unique  = holdings["stock_name"].nunique() if not holdings.empty else 0
    n_rows    = len(holdings) if not holdings.empty else 0
    max_sim   = similarity["similarity_score"].max() if not similarity.empty else 0
    top_stock = common.iloc[0]["stock_name"].strip() if not common.empty else "—"

    st.markdown(f"""
    <div class="stats-banner">
        <div class="stat-item">
            <div class="stat-value">{n_funds}</div>
            <div class="stat-label">Funds Analyzed</div>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
            <div class="stat-value">{n_unique}</div>
            <div class="stat-label">Unique Stocks</div>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
            <div class="stat-value">{n_rows:,}</div>
            <div class="stat-label">Holdings Records</div>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
            <div class="stat-value">{max_sim:.0f}%</div>
            <div class="stat-label">Max Fund Overlap</div>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
            <div class="stat-value" style="font-size:1.1rem;">{top_stock}</div>
            <div class="stat-label">Most Widely Held Stock</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Choose your journey")
    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("""
        <div class="journey-card">
            <div style="font-size:2.5rem;margin-bottom:1rem;">🔍</div>
            <div style="font-size:1.1rem;font-weight:700;color:#1A1A2E;margin-bottom:0.5rem;">
                Explore Mutual Funds
            </div>
            <div style="font-size:0.85rem;color:#6B7280;line-height:1.7;margin-bottom:1.25rem;">
                Select a fund category, pick up to 5 funds, and get a deep-dive
                comparison — portfolio overlap, common holdings, sector concentration,
                and hidden redundancies.
            </div>
            <div style="font-size:0.75rem;color:#6C3CE1;font-weight:600;">
                Category → Select Funds → Compare →
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Explore Funds →", key="btn_explore", use_container_width=True, type="primary"):
            st.session_state.page = "category"
            st.rerun()

    with col2:
        st.markdown("""
        <div class="journey-card">
            <div style="font-size:2.5rem;margin-bottom:1rem;">📋</div>
            <div style="font-size:1.1rem;font-weight:700;color:#1A1A2E;margin-bottom:0.5rem;">
                Portfolio X-Ray
            </div>
            <div style="font-size:0.85rem;color:#6B7280;line-height:1.7;margin-bottom:1.25rem;">
                Upload your existing mutual fund portfolio and instantly discover
                hidden stock exposure, duplicate funds, sector concentration risks,
                and true diversification across your holdings.
            </div>
            <div style="font-size:0.75rem;color:#6C3CE1;font-weight:600;">
                Upload CSV → Instant X-Ray →
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("X-Ray My Portfolio →", key="btn_xray", use_container_width=True):
            st.session_state.page = "portfolio_upload"
            st.rerun()

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

    st.markdown("## Choose a Fund Category")
    st.markdown(
        "<p style='color:#6B7280;margin-top:-0.5rem;margin-bottom:1.5rem;'>Select a category to explore and compare funds</p>",
        unsafe_allow_html=True,
    )

    holdings = load_holdings()
    fund_counts = {}
    if not holdings.empty:
        fund_counts = holdings.groupby("category")["fund_name"].nunique().to_dict()

    categories = [
        ("Large Cap",        "🏛️", "Top 100 companies by market cap. Lower risk, stable long-term returns.", True),
        ("Mid Cap",          "📈", "Ranked 101–250. Higher growth potential with moderate risk.",            False),
        ("Small Cap",        "🚀", "Ranked 251+. High growth potential, higher volatility.",                 False),
        ("Flexi Cap",        "🔄", "Invests flexibly across large, mid and small caps.",                     False),
        ("ELSS (Tax Saver)", "💰", "Tax saving under Sec 80C with 3-year lock-in.",                         False),
        ("Index Funds",      "📊", "Passively track market indices with low cost.",                          False),
    ]

    cols = st.columns(3, gap="medium")
    for i, (name, icon, desc, live) in enumerate(categories):
        with cols[i % 3]:
            count = fund_counts.get(name, 0)
            badge = (
                f'<span class="badge badge-live">{count} funds • Live Data</span>'
                if live else
                '<span class="badge badge-soon">Coming Soon</span>'
            )
            st.markdown(f"""
            <div class="cat-card">
                <div style="font-size:2rem;">{icon}</div>
                <div class="cat-name">{name}</div>
                <div class="cat-desc">{desc}</div>
                <div style="margin-top:0.75rem;">{badge}</div>
            </div>
            """, unsafe_allow_html=True)

            if live:
                if st.button(f"Explore {name} →", key=f"cat_{name}", use_container_width=True, type="primary"):
                    st.session_state.selected_category = name
                    st.session_state.selected_funds = []
                    st.session_state.page = "explorer"
                    st.rerun()
            else:
                st.button("Coming Soon", key=f"cat_{name}", use_container_width=True, disabled=True)


# ── PAGE: FUND EXPLORER ───────────────────────────────────────────────────────

def page_fund_explorer():
    nav_header(back_page="category", back_label="Categories")

    category = st.session_state.get("selected_category", "Large Cap")
    holdings  = load_holdings()
    master    = load_master()
    similarity = load_similarity()
    enriched  = compute_fund_enriched(holdings, master)
    cat_funds = enriched[enriched["category"] == category].copy()

    if "selected_funds" not in st.session_state:
        st.session_state.selected_funds = []

    st.markdown(f"## {category} Funds")
    st.markdown(
        "<p style='color:#6B7280;margin-top:-0.5rem;margin-bottom:1.25rem;'>Select up to 5 funds to compare their portfolios</p>",
        unsafe_allow_html=True,
    )

    # ── Filters ──
    c_search, c_sort, c_amc = st.columns([3, 2, 2])
    with c_search:
        search = st.text_input("Search funds…", placeholder="Fund name or AMC", label_visibility="collapsed")
    with c_sort:
        sort_by = st.selectbox(
            "Sort", ["AUM (High→Low)", "AUM (Low→High)", "Expense Ratio (Low→High)", "Holdings Count"],
            label_visibility="collapsed",
        )
    with c_amc:
        amcs = ["All AMCs"] + sorted(cat_funds["fund_house"].dropna().unique().tolist())
        amc_filter = st.selectbox("AMC", amcs, label_visibility="collapsed")

    filtered = cat_funds.copy()
    if search:
        mask = (
            filtered["fund_name"].str.contains(search, case=False, na=False) |
            filtered["fund_house"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]
    if amc_filter != "All AMCs":
        filtered = filtered[filtered["fund_house"] == amc_filter]

    sort_map = {
        "AUM (High→Low)":              ("aum_cr",         False),
        "AUM (Low→High)":              ("aum_cr",         True),
        "Expense Ratio (Low→High)":    ("expense_ratio",  True),
        "Holdings Count":              ("holding_count",  False),
    }
    scol, sasc = sort_map[sort_by]
    if scol in filtered.columns:
        filtered = filtered.sort_values(scol, ascending=sasc, na_position="last")

    # ── Selection widget ──
    st.markdown("---")
    selected = st.multiselect(
        "**Select funds to compare** (choose 2–5):",
        options=filtered["fund_name"].tolist(),
        default=[f for f in st.session_state.selected_funds if f in filtered["fund_name"].tolist()],
        max_selections=5,
        placeholder="Choose funds…",
    )
    st.session_state.selected_funds = selected

    # ── Progress ──
    n_sel = len(selected)
    prog_text = f"{n_sel} / 5 selected"
    c_prog, c_cta = st.columns([4, 1])
    with c_prog:
        st.progress(n_sel / 5, text=prog_text)
    with c_cta:
        if st.button("Compare →", disabled=(n_sel < 2), type="primary", use_container_width=True):
            st.session_state.page = "compare"
            st.rerun()

    # ── Overlap warning for current selection ──
    if n_sel >= 2:
        sel_sim = similarity[
            similarity["fund_a"].isin(selected) & similarity["fund_b"].isin(selected)
        ]
        high_pairs = sel_sim[sel_sim["similarity_score"] >= 60].sort_values("similarity_score", ascending=False)
        if not high_pairs.empty:
            st.markdown("**⚠️ High-overlap pairs in your selection:**")
            for _, row in high_pairs.head(3).iterrows():
                label, cls = sim_badge(row["similarity_score"])
                st.markdown(f"""
                <div style="background:#FFFBEB;border:1px solid #FEF3C7;border-radius:8px;
                            padding:0.6rem 1rem;margin-bottom:6px;font-size:0.8rem;">
                    <span class="badge {cls}">{label} overlap</span>
                    &nbsp; <strong>{short_name(row['fund_a'])}</strong>
                    &nbsp;↔&nbsp; <strong>{short_name(row['fund_b'])}</strong>
                    &nbsp;—&nbsp; {row['similarity_score']:.0f}% similar,
                    {int(row['common_stocks'])} common stocks
                </div>
                """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Fund table ──
    st.markdown('<div class="section-title">All Funds in Category</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Full universe — use the selector above to add funds for comparison</div>', unsafe_allow_html=True)

    table_df = filtered[["fund_name", "fund_house", "aum_cr", "expense_ratio", "holding_count", "top_sector"]].copy()
    table_df = table_df.rename(columns={
        "fund_name":     "Fund",
        "fund_house":    "AMC",
        "aum_cr":        "AUM (₹ Cr)",
        "expense_ratio": "Exp Ratio %",
        "holding_count": "Holdings",
        "top_sector":    "Top Sector",
    })
    table_df["AUM (₹ Cr)"]    = pd.to_numeric(table_df["AUM (₹ Cr)"],    errors="coerce")
    table_df["Exp Ratio %"]   = pd.to_numeric(table_df["Exp Ratio %"],   errors="coerce")
    table_df["Holdings"]      = pd.to_numeric(table_df["Holdings"],      errors="coerce").astype("Int64")
    table_df["In Selection"]  = table_df["Fund"].isin(selected)

    st.dataframe(
        table_df.reset_index(drop=True),
        use_container_width=True,
        height=420,
        column_config={
            "Fund":         st.column_config.TextColumn("Fund Name", width="large"),
            "AMC":          st.column_config.TextColumn("AMC"),
            "AUM (₹ Cr)":  st.column_config.NumberColumn("AUM (₹ Cr)", format="₹%,.0f Cr"),
            "Exp Ratio %":  st.column_config.NumberColumn("Expense Ratio", format="%.2f%%"),
            "Holdings":     st.column_config.NumberColumn("Holdings", format="%d"),
            "Top Sector":   st.column_config.TextColumn("Top Sector"),
            "In Selection": st.column_config.CheckboxColumn("Selected?", disabled=True),
        },
        hide_index=True,
    )


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
    avg_sim  = sel_sim["similarity_score"].mean()  if not sel_sim.empty else 0
    max_sim  = sel_sim["similarity_score"].max()   if not sel_sim.empty else 0
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
        col_heat, col_top = st.columns([3, 2], gap="large")

        with col_heat:
            st.markdown('<div class="section-title">Pairwise Similarity Heatmap</div>', unsafe_allow_html=True)
            st.markdown('<div class="section-sub">Overlap score between every pair of selected funds</div>', unsafe_allow_html=True)

            mat = build_sim_matrix(similarity, selected)
            short_labels = [short_name(f) for f in mat.columns]

            # Mask diagonal for better visual (show as 100 but style differently)
            z_vals = mat.values.tolist()
            text_vals = [[f"{v:.0f}%" for v in row] for row in mat.values]

            fig_h = go.Figure(go.Heatmap(
                z=z_vals,
                x=short_labels,
                y=short_labels,
                colorscale=[[0, "#D1FAE5"], [0.45, "#FEF3C7"], [0.65, "#FEE2E2"], [1, "#DC2626"]],
                zmin=0, zmax=100,
                text=text_vals,
                texttemplate="%{text}",
                textfont={"size": 12, "color": "#1A1A2E"},
                showscale=True,
                colorbar=dict(title="Similarity %", ticksuffix="%", len=0.85),
            ))
            fig_h.update_layout(
                height=max(320, len(selected) * 68),
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif", size=11),
            )
            st.plotly_chart(fig_h, use_container_width=True)

        with col_top:
            st.markdown('<div class="section-title">Top Common Holdings</div>', unsafe_allow_html=True)
            st.markdown('<div class="section-sub">Stocks held by the most selected funds</div>', unsafe_allow_html=True)

            top_com = (
                sel_h.groupby("stock_name")
                .agg(funds_holding=("fund_name", "nunique"), avg_alloc=("allocation_percent", "mean"))
                .reset_index()
                .sort_values(["funds_holding", "avg_alloc"], ascending=[False, False])
                .head(12)
            )
            top_com["stock_name"] = top_com["stock_name"].str.strip()
            top_com["avg_alloc"]  = top_com["avg_alloc"].round(2)

            st.dataframe(
                top_com.reset_index(drop=True),
                use_container_width=True,
                height=380,
                column_config={
                    "stock_name":    st.column_config.TextColumn("Stock"),
                    "funds_holding": st.column_config.NumberColumn("Funds Holding", format="%d"),
                    "avg_alloc":     st.column_config.NumberColumn("Avg Alloc %",   format="%.2f%%"),
                },
                hide_index=True,
            )

    # ── Tab 2: Holdings Overlap ──────────────────────────────────────────────
    with tab_ol:
        st.markdown('<div class="section-title">Fund-Pair Overlap</div>', unsafe_allow_html=True)
        if not sel_sim.empty:
            for _, row in sel_sim.sort_values("similarity_score", ascending=False).iterrows():
                fa, fb, score, common = (
                    row["fund_a"], row["fund_b"],
                    row["similarity_score"], int(row["common_stocks"]),
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
        st.markdown('<div class="section-sub">Allocation % of each stock per fund — cells shaded by weight</div>', unsafe_allow_html=True)

        pivot = (
            sel_h.pivot_table(index="stock_name", columns="fund_name", values="allocation_percent", aggfunc="sum")
            .fillna(0)
        )
        pivot.index = pivot.index.str.strip()
        pivot.columns = [short_name(c) for c in pivot.columns]
        pivot["_funds_holding"] = (pivot > 0).sum(axis=1)
        pivot = pivot[pivot["_funds_holding"] > 1].drop(columns=["_funds_holding"])

        if pivot.empty:
            st.info("No stocks are held by more than one selected fund.")
        else:
            if pivot.columns.tolist():
                pivot = pivot.sort_values(pivot.columns.tolist()[0], ascending=False)
            st.dataframe(
                pivot.style.format("{:.2f}%"),
                use_container_width=True,
                height=520,
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
        sec_pivot = (
            sel_sector.pivot_table(index="sector", columns="fund_short", values="allocation_percent", aggfunc="sum")
            .fillna(0)
        )
        sec_pivot["Avg"] = sec_pivot.mean(axis=1)
        sec_pivot = sec_pivot.sort_values("Avg", ascending=False).drop(columns=["Avg"])

        st.dataframe(
            sec_pivot.style.format("{:.1f}%"),
            use_container_width=True,
            height=400,
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

        st.dataframe(
            stock_detail,
            use_container_width=True,
            height=520,
            column_config={
                "stock_name":    st.column_config.TextColumn("Stock"),
                "funds_holding": st.column_config.NumberColumn("Funds Holding", format="%d"),
                "avg_alloc":     st.column_config.NumberColumn("Avg Alloc %",   format="%.2f%%"),
                "avg_3m":        st.column_config.NumberColumn("3M Δ Alloc",    format="%.2f%%"),
                "avg_6m":        st.column_config.NumberColumn("6M Δ Alloc",    format="%.2f%%"),
                "avg_1y":        st.column_config.NumberColumn("1Y Δ Alloc",    format="%.2f%%"),
                "sector":        st.column_config.TextColumn("Sector"),
            },
            hide_index=True,
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
        avg_s   = sel_sim["similarity_score"].mean() if not sel_sim.empty else 0

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
    avg_sim  = sel_sim["similarity_score"].mean() if not sel_sim.empty else 0
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
            for _, row in sel_sim.sort_values("similarity_score", ascending=False).iterrows():
                label, cls = sim_badge(row["similarity_score"])
                st.markdown(f"""
                <div class="overlap-row">
                    <div style="display:flex;align-items:center;justify-content:space-between;">
                        <div style="font-size:0.9rem;font-weight:600;color:#1A1A2E;">
                            {short_name(row['fund_a'])}
                            <span style="color:#9CA3AF;font-weight:400;margin:0 6px;">vs</span>
                            {short_name(row['fund_b'])}
                        </div>
                        <div style="display:flex;align-items:center;gap:8px;">
                            <span style="font-size:1.4rem;font-weight:800;color:#6C3CE1;">{row['similarity_score']:.0f}%</span>
                            <span class="badge {cls}">{label} Overlap</span>
                        </div>
                    </div>
                    <div class="overlap-bar-bg">
                        <div class="overlap-bar-fill" style="width:{row['similarity_score']}%;"></div>
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

def main():
    for key, default in [
        ("page",           "home"),
        ("selected_funds", []),
        ("selected_category", "Large Cap"),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    routes = {
        "home":             page_home,
        "category":         page_category_select,
        "explorer":         page_fund_explorer,
        "compare":          page_compare,
        "portfolio_upload": page_portfolio_upload,
        "portfolio_xray":   page_portfolio_xray,
    }
    routes.get(st.session_state.page, page_home)()


main()
