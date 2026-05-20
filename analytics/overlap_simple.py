"""Plain-language cluster UI for the overlap matrix."""

from __future__ import annotations

import streamlit as st

from analytics.overlap_graph import CategoryGraph
from analytics.overlap_viz import TIER_COLORS

_TIER_USER_COPY = {
    "very_similar": ("Very similar", "Pick just one fund from this group — they hold largely the same stocks."),
    "high": ("High overlap", "Noticeable duplication if you hold several from here."),
    "moderate": ("Moderate overlap", "Related funds, but not copies of each other."),
    "distinct": ("Most distinct", "Relatively different within this category."),
}


def render_cluster_cards(
    graph: CategoryGraph,
    *,
    selected_funds: list[str],
    on_toggle,
) -> None:
    st.info(
        "Funds are sorted into **similarity groups**. "
        "Same group = many shared stocks. Tap a fund to see overlap details below."
    )

    cols = st.columns(2)
    for gi, group in enumerate(graph.clusters):
        if not group.fund_indices:
            continue
        stroke, _ = TIER_COLORS.get(group.tier_key, TIER_COLORS["distinct"])
        title, desc = _TIER_USER_COPY.get(group.tier_key, _TIER_USER_COPY["distinct"])

        with cols[gi % 2]:
            with st.container(border=True):
                st.markdown(f"**Group {group.letter} — {title}**")
                st.caption(f"{desc} ({len(group.fund_indices)} funds)")
                chip_cols = st.columns(3)
                for ki, fi in enumerate(group.fund_indices):
                    fund = graph.funds[fi]
                    label = graph.labels[fi]
                    with chip_cols[ki % 3]:
                        if st.button(
                            label,
                            key=f"ov_chip_{graph.category}_{gi}_{fi}",
                            type="primary" if fund in selected_funds else "secondary",
                            use_container_width=True,
                        ):
                            on_toggle(fund)
