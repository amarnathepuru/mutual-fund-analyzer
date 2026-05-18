"""Plotly figures for overlap matrix cluster views."""

from __future__ import annotations

from dataclasses import dataclass

import plotly.graph_objects as go

from analytics.overlap_graph import (
    STRONG_EDGE_PCT,
    CategoryGraph,
    ClusterGroup,
    fund_label,
    get_edges,
    neighbor_indices,
    selected_indices,
    top_overlaps,
)

TIER_COLORS = {
    "very_similar": ("#EF4444", "rgba(239,68,68,0.12)"),
    "high": ("#F59E0B", "rgba(245,158,11,0.12)"),
    "moderate": ("#8B5CF6", "rgba(139,92,246,0.12)"),
    "distinct": ("#10B981", "rgba(16,185,129,0.12)"),
}

EDGE_COLOR_STRONG = "#EF4444"
EDGE_COLOR_MID = "#F59E0B"
EDGE_COLOR_WEAK = "rgba(148,163,184,0.45)"


@dataclass(frozen=True)
class OverlapVizParams:
    min_pct: float = 30.0
    selected_funds: tuple[str, ...] = ()
    simplify_dense: bool = True
    top_k: int = 3


def _layout(theme: dict, *, height: int = 580) -> dict:
    return dict(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        xaxis=dict(
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            range=[-0.05, 1.05],
        ),
        yaxis=dict(
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            scaleanchor="x",
            scaleratio=1,
            range=[-0.05, 1.05],
        ),
        font=dict(family="Inter, sans-serif", color=theme.get("body", "#64748B")),
        hovermode="closest",
    )


def _normalize_positions(positions):
    import numpy as np

    if len(positions) == 0:
        return positions
    p = positions.copy()
    p -= p.min(axis=0)
    span = (p.max(axis=0) - p.min(axis=0)).max()
    if span <= 0:
        return np.full_like(p, 0.5)
    return p / span


def _edge_color(score: float) -> str:
    if score >= STRONG_EDGE_PCT:
        return EDGE_COLOR_STRONG
    if score >= 45.0:
        return EDGE_COLOR_MID
    return EDGE_COLOR_WEAK


def _edge_width(score: float, *, emphasis: bool = False) -> float:
    base = max(0.8, score / 40.0)
    return base * 1.6 if emphasis else base


def _resolve_edges(graph: CategoryGraph, params: OverlapVizParams) -> list[tuple[int, int, float]]:
    top_k = params.top_k if params.simplify_dense else None
    return get_edges(graph.matrix, params.min_pct, top_k_per_fund=top_k)


def _edge_trace_batched(
    graph: CategoryGraph,
    positions,
    edges: list[tuple[int, int, float]],
    *,
    selected_idx: set[int],
) -> list[go.Scatter]:
    if not edges:
        return []

    by_color: dict[str, tuple[list[float], list[float], list[str]]] = {}
    for i, j, score in edges:
        color = _edge_color(score)
        emphasis = selected_idx and i in selected_idx and j in selected_idx
        xs, ys, hovers = by_color.setdefault(color, ([], [], []))
        xs.extend([positions[i, 0], positions[j, 0], None])
        ys.extend([positions[i, 1], positions[j, 1], None])
        hovers.extend([
            f"{graph.labels[i]} ↔ {graph.labels[j]}: {score:.0f}%",
            f"{graph.labels[i]} ↔ {graph.labels[j]}: {score:.0f}%",
            "",
        ])

    traces = []
    for color, (xs, ys, hovers) in by_color.items():
        sample_score = 75.0 if color == EDGE_COLOR_STRONG else 50.0 if color == EDGE_COLOR_MID else 30.0
        traces.append(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line=dict(color=color, width=_edge_width(sample_score)),
                hovertext=hovers,
                hoverinfo="text",
                showlegend=False,
            )
        )
    return traces


def _colors_for_clusters(graph: CategoryGraph) -> list[str]:
    out = ["#94A3B8"] * len(graph.funds)
    for group in graph.clusters:
        stroke, _ = TIER_COLORS.get(group.tier_key, TIER_COLORS["distinct"])
        for fi in group.fund_indices:
            out[fi] = stroke
    return out


def _node_emphasis(
    graph: CategoryGraph,
    params: OverlapVizParams,
) -> tuple[set[int], set[int], list[float], list[int], list[str], str]:
    n = len(graph.funds)
    sel = selected_indices(graph, list(params.selected_funds))
    has_sel = bool(sel)
    neigh = neighbor_indices(graph, list(params.selected_funds), params.min_pct) if has_sel else set()

    opacities: list[float] = []
    sizes: list[int] = []
    texts: list[str] = []
    modes: list[str] = []

    for i in range(n):
        max_ov = float(graph.matrix[i, :].max()) if n > 1 else 0.0
        base_size = int(12 + min(max_ov, 80) / 6)

        if not has_sel:
            opacities.append(1.0)
            sizes.append(base_size)
            texts.append("")
            modes.append("markers")
        elif i in sel:
            opacities.append(1.0)
            sizes.append(base_size + 8)
            texts.append(graph.labels[i])
            modes.append("markers+text")
        elif i in neigh:
            opacities.append(0.88)
            sizes.append(base_size + 2)
            texts.append(graph.labels[i])
            modes.append("markers+text")
        else:
            opacities.append(0.22)
            sizes.append(max(10, base_size - 2))
            texts.append("")
            modes.append("markers")

    mode = "markers+text" if any(m == "markers+text" for m in modes) else "markers"
    return sel, neigh, opacities, sizes, texts, mode


def _node_trace(
    graph: CategoryGraph,
    positions,
    theme: dict,
    params: OverlapVizParams,
) -> go.Scatter:
    sel, neigh, opacities, sizes, texts, mode = _node_emphasis(graph, params)
    custom = []
    for i in range(len(graph.funds)):
        fund = graph.funds[i]
        top = top_overlaps(fund, graph.funds, graph.lookup, limit=1, min_pct=params.min_pct)
        top_line = f"<br>Top match: {fund_label(top[0][0])} ({top[0][1]:.0f}%)" if top else ""
        gi = graph.fund_cluster.get(i)
        cluster_line = ""
        if gi is not None and gi < len(graph.clusters):
            g = graph.clusters[gi]
            cluster_line = f"<br>Cluster {g.letter} — {g.title}"
        custom.append([graph.labels[i], float(graph.matrix[i, :].max()), cluster_line + top_line])

    scatter_kw: dict = dict(
        x=positions[:, 0],
        y=positions[:, 1],
        mode=mode,
        marker=dict(
            size=sizes,
            color=_colors_for_clusters(graph),
            line=dict(width=2 if sel else 1.5, color=theme.get("card", "#FFFFFF")),
            opacity=opacities,
        ),
    )
    if mode == "markers+text":
        scatter_kw["text"] = texts
        scatter_kw["textposition"] = "top center"
        scatter_kw["textfont"] = dict(size=10, color=theme.get("head", "#1E293B"))
    scatter_kw["customdata"] = custom
    scatter_kw["hovertemplate"] = (
        "<b>%{customdata[0]}</b><br>Max overlap: %{customdata[1]:.0f}%"
        "%{customdata[2]}<extra></extra>"
    )
    scatter_kw["name"] = "funds"
    return go.Scatter(**scatter_kw)


def _bubble_shapes(groups: list[ClusterGroup], *, fade_unselected: set[int] | None) -> list[dict]:
    centers = [(0.28, 0.72), (0.72, 0.72), (0.28, 0.28), (0.72, 0.28)]
    shapes = []
    for gi, group in enumerate(groups):
        if not group.fund_indices:
            continue
        cx, cy = centers[gi % len(centers)]
        m = len(group.fund_indices)
        radius = min(0.22, 0.12 + 0.008 * m)
        _, fill = TIER_COLORS.get(group.tier_key, TIER_COLORS["distinct"])
        stroke, _ = TIER_COLORS.get(group.tier_key, TIER_COLORS["distinct"])
        faded = fade_unselected is not None and not any(
            fi in fade_unselected for fi in group.fund_indices
        )
        shapes.append(
            dict(
                type="circle",
                xref="x",
                yref="y",
                x0=cx - radius,
                y0=cy - radius,
                x1=cx + radius,
                y1=cy + radius,
                fillcolor=fill if not faded else "rgba(148,163,184,0.06)",
                line=dict(color=stroke if not faded else "rgba(148,163,184,0.35)", width=2),
                layer="below",
            )
        )
    return shapes


def _bubble_annotations(groups: list[ClusterGroup]) -> list[dict]:
    centers = [(0.28, 0.72), (0.72, 0.72), (0.28, 0.28), (0.72, 0.28)]
    ann = []
    for gi, group in enumerate(groups):
        if not group.fund_indices:
            continue
        cx, cy = centers[gi % len(centers)]
        m = len(group.fund_indices)
        radius = min(0.22, 0.12 + 0.008 * m)
        stroke, _ = TIER_COLORS.get(group.tier_key, TIER_COLORS["distinct"])
        ann.append(
            dict(
                x=cx,
                y=cy + radius + 0.06,
                text=(
                    f"<b>Cluster {group.letter} — {group.title}</b><br>"
                    f"<span style='font-size:10px'>{group.subtitle}</span>"
                ),
                showarrow=False,
                font=dict(size=11, color=stroke),
                align="center",
            )
        )
    return ann


def fig_force_network(graph: CategoryGraph, theme: dict, params: OverlapVizParams) -> go.Figure:
    pos = _normalize_positions(graph.positions_force)
    edges = _resolve_edges(graph, params)
    sel = selected_indices(graph, list(params.selected_funds))
    fig = go.Figure()
    for tr in _edge_trace_batched(graph, pos, edges, selected_idx=sel):
        fig.add_trace(tr)
    fig.add_trace(_node_trace(graph, pos, theme, params))
    fig.update_layout(**_layout(theme))
    return fig


def fig_constellation(graph: CategoryGraph, theme: dict, params: OverlapVizParams) -> go.Figure:
    pos = _normalize_positions(graph.positions_constellation) * 0.85 + 0.075
    edges = _resolve_edges(graph, params)
    sel = selected_indices(graph, list(params.selected_funds))
    fig = go.Figure()
    for tr in _edge_trace_batched(graph, pos, edges, selected_idx=sel):
        fig.add_trace(tr)
    fig.add_trace(_node_trace(graph, pos, theme, params))
    fig.update_layout(**_layout(theme))
    return fig


def fig_bubble_clusters(graph: CategoryGraph, theme: dict, params: OverlapVizParams) -> go.Figure:
    pos = graph.positions_bubble
    neigh = neighbor_indices(graph, list(params.selected_funds), params.min_pct)
    fig = go.Figure()
    fig.add_trace(_node_trace(graph, pos, theme, params))
    layout = _layout(theme, height=600)
    layout["shapes"] = _bubble_shapes(
        graph.clusters,
        fade_unselected=neigh if params.selected_funds else None,
    )
    layout["annotations"] = _bubble_annotations(graph.clusters)
    fig.update_layout(**layout)
    return fig


def fig_top_overlaps_bar(
    fund: str,
    overlaps: list[tuple[str, float]],
    labels_map: dict[str, str],
    theme: dict,
) -> go.Figure:
    if not overlaps:
        return go.Figure()

    names = [labels_map.get(f, f) for f, _ in overlaps]
    scores = [s for _, s in overlaps]
    colors = [
        EDGE_COLOR_STRONG if s >= STRONG_EDGE_PCT else theme.get("a", "#7C3AED")
        for s in scores
    ]

    fig = go.Figure(
        go.Bar(
            y=names[::-1],
            x=scores[::-1],
            orientation="h",
            marker_color=colors[::-1],
            text=[f"{s:.0f}%" for s in scores[::-1]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Overlap: %{x:.0f}%<extra></extra>",
        )
    )
    is_dark = theme.get("is_dark", False)
    tick = "#94A3B8" if is_dark else "#64748B"
    fig.update_layout(
        height=max(180, 44 * len(names) + 40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=50, t=10, b=10),
        xaxis=dict(range=[0, min(100, max(scores) + 15)], tickfont=dict(color=tick), gridcolor=tick),
        yaxis=dict(tickfont=dict(color=theme.get("head", tick))),
        font=dict(family="Inter, sans-serif"),
        showlegend=False,
    )
    return fig
