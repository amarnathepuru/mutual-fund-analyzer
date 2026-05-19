"""Force-directed overlap graph for the overlap matrix journey."""

from __future__ import annotations

from dataclasses import dataclass, field

import plotly.graph_objects as go

from analytics.overlap_graph import CategoryGraph, get_edges
from analytics.overlap_filters import format_return_suffix, fund_return_pct
from analytics.overlap_quick_compare import COLOR_OV_HIGH, COLOR_OV_MID, overlap_list_color
from analytics.overlap_viz import _layout, _normalize_positions

JOURNEY_MIN_EDGE = 45.0   # default threshold (High+)
JOURNEY_EDGE_HIGH = 60.0  # Very High bucket boundary

WIDTH_EDGE_HIGH = 3.5
WIDTH_EDGE_MID  = 2.0
WIDTH_EDGE_LOW  = 1.2
FADED_EDGE_OPACITY  = 0.06
NODE_MIN_SIZE       = 26
UNSELECTED_NODE_OPACITY = 0.45

# Edge colours aligned with Fund Comparison page buckets
COLOR_EDGE_VERY_HIGH = "#DC2626"   # >60% Very High  — red
COLOR_EDGE_HIGH      = "#D97706"   # 45–60% High     — amber
COLOR_EDGE_MODERATE  = "#6366F1"   # 30–45% Moderate — indigo
# Keep backward-compat aliases
COLOR_EDGE_MID = COLOR_EDGE_HIGH

# Overlap buckets: (label, min_pct, max_pct, edge-colour, badge-bg, description)
# Each bucket shows ONLY connections whose overlap falls within [min_pct, max_pct).
# "All connections" uses max=100 to show everything with score-based colours.
OVERLAP_BUCKETS: list[tuple[str, float, float, str, str, str]] = [
    ("🔴 Very High (60%+)",   60.0, 100.0, COLOR_EDGE_VERY_HIGH, "#FEE2E2", "Nearly identical — consider replacing one fund."),
    ("🟡 High (45–59%)",      45.0,  60.0, COLOR_EDGE_HIGH,      "#FEF3C7", "Significant overlap — paying two managers for similar results."),
    ("🔵 Moderate (30–44%)",  30.0,  45.0, COLOR_EDGE_MODERATE,  "#EEF2FF", "Noticeable overlap — worth monitoring."),
    ("🟢 Good (15–29%)",      15.0,  30.0, "#059669",             "#ECFDF5", "Healthy diversification — generally fine."),
    ("🟢 Excellent (<15%)",    0.0,  15.0, "#34D399",             "#ECFDF5", "Very different portfolios — ideal combination."),
    ("✅ All connections",     0.0,  100.0, "#94A3B8",             "#F8FAFC", "Show every pair with any overlap."),
]

# Maps from display label → (min, max) thresholds
BUCKET_LABEL_TO_RANGE: dict[str, tuple[float, float]] = {b[0]: (b[1], b[2]) for b in OVERLAP_BUCKETS}
# Keep legacy min-only map for backward compat
BUCKET_LABEL_TO_MIN: dict[str, float] = {b[0]: b[1] for b in OVERLAP_BUCKETS}
# Default selection label
DEFAULT_BUCKET_LABEL = "🟡 High (45–59%)"

# Node fill palette – constant, readable on any background
NODE_FILL_DEFAULT  = "#6C63FF"   # soft indigo
NODE_FILL_SELECTED_A = "#534AB7" # deep purple (Fund A)
NODE_FILL_SELECTED_B = "#0F6E56" # teal-green  (Fund B)
NODE_FILL_FADED    = "#A0AEC0"   # muted grey for unselected

NODE_TEXT_DEFAULT  = "#FFFFFF"
NODE_TEXT_FADED    = "#718096"


@dataclass
class JourneyVizParams:
    fund_a: str | None = None
    fund_b: str | None = None
    return_period: str = "1Y"
    min_edge_pct: float = JOURNEY_MIN_EDGE
    max_edge_pct: float = 100.0          # upper bound — 100 means no upper limit
    selected_funds: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.selected_funds and not self.fund_a:
            sf = tuple(self.selected_funds)
            object.__setattr__(self, "fund_a", sf[0] if sf else None)
            object.__setattr__(self, "fund_b", sf[1] if len(sf) > 1 else None)


def journey_palette(theme: dict) -> dict:
    return {
        "select_a":   NODE_FILL_SELECTED_A,
        "select_b":   NODE_FILL_SELECTED_B,
        "pill_a_bg":  "#EEEDFE",
        "pill_a_bdr": "#AFA9EC",
        "pill_b_bg":  "#E1F5EE",
        "pill_b_bdr": "#9FE1CB",
        "ret_green":  "#34D399" if theme.get("is_dark") else "#059669",
        "ov_low":     theme.get("a", "#2563EB"),
        "card":       theme.get("card", "#FFFFFF"),
        "head":       theme.get("head", "#1A1A18"),
        "sub":        theme.get("sub", "#ABA9A3"),
        "bdr":        theme.get("bdr", "#E8E6DE"),
    }


def _hex_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _edge_style(
    score: float,
    min_edge: float = JOURNEY_MIN_EDGE,
    max_edge: float = 100.0,
) -> tuple[str, float] | None:
    """Return (colour, width) if score falls within [min_edge, max_edge), else None."""
    if score < min_edge or score >= max_edge:
        return None
    # Colour by actual overlap level regardless of which bucket filter is active
    if score >= 60.0:
        return COLOR_EDGE_VERY_HIGH, WIDTH_EDGE_HIGH
    if score >= 45.0:
        return COLOR_EDGE_HIGH, WIDTH_EDGE_MID
    if score >= 30.0:
        return COLOR_EDGE_MODERATE, WIDTH_EDGE_LOW
    return "#059669", WIDTH_EDGE_LOW  # Good (15–30%)


def _node_label(graph: CategoryGraph, idx: int, master, period: str) -> str:
    fund  = graph.funds[idx]
    short = graph.labels[idx]
    suffix = format_return_suffix(master, fund, period).strip()
    return f"{short}<br><span style='font-size:8px'>{suffix}</span>" if suffix else short


def _node_sizes(graph: CategoryGraph, master, period: str) -> list[int]:
    vals  = [fund_return_pct(master, f, period) for f in graph.funds]
    valid = [v for v in vals if v is not None]
    lo    = min(valid) if valid else 0.0
    hi    = max(valid) if valid else 1.0
    span  = hi - lo if hi > lo else 1.0
    sizes: list[int] = []
    for v in vals:
        if v is None:
            sizes.append(NODE_MIN_SIZE)
        else:
            norm = (v - lo) / span
            sizes.append(max(NODE_MIN_SIZE, int(NODE_MIN_SIZE + norm * 18)))
    return sizes


def _node_colors(
    graph: CategoryGraph,
    fund_a: str | None,
    fund_b: str | None,
    fund_a_idx: int | None,
) -> tuple[list[str], list[str]]:
    """Return (fill_colors, text_colors) per node."""
    fills  = []
    texts  = []
    for i, fund in enumerate(graph.funds):
        if fund == fund_a:
            fills.append(NODE_FILL_SELECTED_A)
            texts.append(NODE_TEXT_DEFAULT)
        elif fund == fund_b:
            fills.append(NODE_FILL_SELECTED_B)
            texts.append(NODE_TEXT_DEFAULT)
        elif fund_a_idx is not None:
            fills.append(NODE_FILL_FADED)
            texts.append(NODE_TEXT_FADED)
        else:
            fills.append(NODE_FILL_DEFAULT)
            texts.append(NODE_TEXT_DEFAULT)
    return fills, texts


def _node_opacities(
    graph: CategoryGraph,
    fund_a: str | None,
    fund_a_idx: int | None,
) -> list[float]:
    if fund_a_idx is None:
        return [1.0] * len(graph.funds)
    return [
        1.0 if i == fund_a_idx or graph.funds[i] == fund_a else UNSELECTED_NODE_OPACITY
        for i in range(len(graph.funds))
    ]


def _add_faded_edge_batch(fig, xs, ys, hovers, color, width):
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="lines",
        line=dict(color=_hex_rgba(color, FADED_EDGE_OPACITY), width=width * 0.7),
        hovertext=hovers, hoverinfo="text", showlegend=False,
    ))


def _add_edge_traces(
    fig: go.Figure,
    graph: CategoryGraph,
    pos,
    fund_a: str | None,
    min_edge_pct: float = JOURNEY_MIN_EDGE,
    max_edge_pct: float = 100.0,
) -> None:
    fund_a_idx = graph.funds.index(fund_a) if fund_a and fund_a in graph.funds else None
    batches: dict[tuple, tuple] = {}

    if fund_a_idx is not None:
        for i, j, score in get_edges(graph.matrix, min_edge_pct, top_k_per_fund=None):
            if i == fund_a_idx or j == fund_a_idx:
                continue
            style = _edge_style(score, min_edge_pct, max_edge_pct)
            if style is None:
                continue
            color, width = style
            k = (color, width, "faded")
            xs, ys, hovers = batches.setdefault(k, ([], [], []))
            xs.extend([pos[i, 0], pos[j, 0], None])
            ys.extend([pos[i, 1], pos[j, 1], None])
            hovers.extend([f"{graph.labels[i]} ↔ {graph.labels[j]}: {score:.0f}%"] * 2 + [""])

        for j in range(len(graph.funds)):
            if j == fund_a_idx:
                continue
            score = float(graph.matrix[fund_a_idx, j])
            style = _edge_style(score, min_edge_pct, max_edge_pct)
            if style is None:
                continue
            color, width = style
            k = (color, width, "active")
            xs, ys, hovers = batches.setdefault(k, ([], [], []))
            xs.extend([pos[fund_a_idx, 0], pos[j, 0], None])
            ys.extend([pos[fund_a_idx, 1], pos[j, 1], None])
            hovers.extend([f"{graph.labels[fund_a_idx]} ↔ {graph.labels[j]}: {score:.0f}%"] * 2 + [""])
    else:
        for i, j, score in get_edges(graph.matrix, min_edge_pct, top_k_per_fund=None):
            style = _edge_style(score, min_edge_pct, max_edge_pct)
            if style is None:
                continue
            color, width = style
            k = (color, width, "active")
            xs, ys, hovers = batches.setdefault(k, ([], [], []))
            xs.extend([pos[i, 0], pos[j, 0], None])
            ys.extend([pos[i, 1], pos[j, 1], None])
            hovers.extend([f"{graph.labels[i]} ↔ {graph.labels[j]}: {score:.0f}%"] * 2 + [""])

    for (color, width, kind), (xs, ys, hovers) in batches.items():
        if kind == "faded":
            _add_faded_edge_batch(fig, xs, ys, hovers, color, width)
        else:
            fig.add_trace(go.Scatter(
                x=xs, y=ys, mode="lines",
                line=dict(color=color, width=width),
                hovertext=hovers, hoverinfo="text", showlegend=False,
            ))


def _overlap_annotations(
    graph: CategoryGraph,
    pos,
    fund_a: str | None,
    palette: dict,
    min_edge_pct: float = JOURNEY_MIN_EDGE,
) -> list[dict]:
    if not fund_a or fund_a not in graph.funds:
        return []
    ai = graph.funds.index(fund_a)
    annotations = []
    for j in range(len(graph.funds)):
        if j == ai:
            continue
        score = float(graph.matrix[ai, j])
        if score < min_edge_pct:
            continue
        mx = (pos[ai, 0] + pos[j, 0]) / 2
        my = (pos[ai, 1] + pos[j, 1]) / 2
        color = overlap_list_color(score)
        annotations.append(dict(
            x=mx, y=my, text=f"<b>{score:.0f}%</b>",
            showarrow=False,
            font=dict(size=10, color="#FFFFFF", family="Inter, sans-serif"),
            bgcolor=color, bordercolor=color,
            borderwidth=1, borderpad=4,
        ))
    return annotations


def fig_overlap_journey(
    graph: CategoryGraph,
    theme: dict,
    master,
    params: JourneyVizParams,
) -> go.Figure:
    palette = journey_palette(theme)
    pos     = _normalize_positions(graph.positions_force)
    fund_a  = params.fund_a
    fund_b  = params.fund_b
    fund_a_idx = graph.funds.index(fund_a) if fund_a and fund_a in graph.funds else None

    min_edge = params.min_edge_pct
    max_edge = params.max_edge_pct
    fig = go.Figure()
    _add_edge_traces(fig, graph, pos, fund_a, min_edge, max_edge)

    sizes               = _node_sizes(graph, master, params.return_period)
    fills, text_colors  = _node_colors(graph, fund_a, fund_b, fund_a_idx)
    opacities           = _node_opacities(graph, fund_a, fund_a_idx)

    labels = [_node_label(graph, i, master, params.return_period) for i in range(len(graph.funds))]

    line_colors = []
    line_widths = []
    for i, fund in enumerate(graph.funds):
        if fund == fund_a:
            line_colors.append("#FFFFFF"); line_widths.append(3)
        elif fund == fund_b:
            line_colors.append("#FFFFFF"); line_widths.append(3)
        else:
            line_colors.append("rgba(0,0,0,0)"); line_widths.append(0)

    fig.add_trace(go.Scatter(
        x=pos[:, 0],
        y=pos[:, 1],
        mode="markers+text",
        text=labels,
        textposition="top center",
        textfont=dict(size=10, color=palette["head"], family="Inter, sans-serif"),
        marker=dict(
            size=sizes,
            color=fills,
            opacity=opacities,
            line=dict(color=line_colors, width=line_widths),
        ),
        customdata=list(range(len(graph.funds))),
        hovertemplate="<b>%{text}</b><extra></extra>",
        name="funds",
    ))

    layout = _layout(theme, height=640)
    layout["annotations"] = _overlap_annotations(graph, pos, fund_a, palette, min_edge)
    # Slightly warmer plot background
    bg = theme.get("bg", "#F5F4F0")
    layout["plot_bgcolor"]  = bg
    layout["paper_bgcolor"] = bg
    fig.update_layout(**layout)
    return fig


def journey_legend_html(theme: dict) -> str:
    sub  = theme.get("sub", "#64748B")
    head = theme.get("head", "#1E293B")
    bdr  = theme.get("bdr", "#E8E6DE")
    al   = theme.get("al",  "#F5F4F0")

    def _swatch(color: str, label: str) -> str:
        return (
            f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:14px;'
            f'margin-bottom:4px;">'
            f'<span style="display:inline-block;width:22px;height:4px;border-radius:2px;'
            f'background:{color};flex-shrink:0;"></span>'
            f'<span style="color:{head};font-size:0.75rem;">{label}</span>'
            f'</span>'
        )

    def _icon_item(icon: str, title: str, desc: str) -> str:
        return (
            f'<div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:6px;">'
            f'<span style="font-size:1rem;line-height:1.3;flex-shrink:0;">{icon}</span>'
            f'<span style="font-size:0.75rem;color:{sub};line-height:1.4;">'
            f'<strong style="color:{head};">{title}</strong> &mdash; {desc}'
            f'</span></div>'
        )

    no_line = (
        f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:14px;'
        f'margin-bottom:4px;">'
        f'<span style="display:inline-block;width:22px;height:0;border-top:2px dashed #94A3B8;'
        f'flex-shrink:0;"></span>'
        f'<span style="color:{sub};font-size:0.75rem;">No line = &lt;65% overlap — funds are sufficiently different</span>'
        f'</span>'
    )

    lines_section = (
        f'<div style="font-size:0.72rem;font-weight:700;color:{sub};text-transform:uppercase;'
        f'letter-spacing:0.4px;margin-bottom:0.4rem;">Line colours (overlap level)</div>'
        f'<div style="margin-bottom:0.5rem;display:flex;flex-wrap:wrap;align-items:center;">'
        + _swatch(COLOR_EDGE_VERY_HIGH, "🔴 Very High 60%+ &mdash; nearly identical")
        + _swatch(COLOR_EDGE_HIGH,      "🟡 High 45&ndash;59% &mdash; significant overlap")
        + _swatch(COLOR_EDGE_MODERATE,  "🔵 Moderate 30&ndash;44% &mdash; worth monitoring")
        + _swatch("#059669",            "🟢 Good 15&ndash;29% &mdash; healthy diversification")
        + _swatch("#34D399",            "🟢 Excellent &lt;15% &mdash; very different, ideal combination")
        + no_line
        + f'</div>'
        f'<div style="font-size:0.72rem;color:{sub};background:{bdr}20;border-radius:6px;'
        f'padding:6px 8px;margin-bottom:0.75rem;line-height:1.5;">'
        f'<strong style="color:{head};">Draw lines when overlap ≥</strong> filter sets the <em>minimum</em> threshold. '
        f'Selecting <strong>High &amp; above (≥45%)</strong> draws amber lines (High) <em>and</em> red lines (Very High). '
        f'Choose <strong>Very High only</strong> to see exclusively the &gt;60% connections.<br>'
        f'&nbsp;<br>This filter only affects the lines drawn — '
        f'<strong style="color:{head};">you can compare any two funds regardless</strong> by clicking a bubble or using the list.'
        f'</div>'
    )

    bubbles_section = (
        f'<div style="font-size:0.72rem;font-weight:700;color:{sub};text-transform:uppercase;'
        f'letter-spacing:0.4px;margin-bottom:0.4rem;">Bubbles</div>'
        + _icon_item("📍", "Position", "The closer two bubbles sit, the higher their portfolio overlap. Clusters of nearby bubbles are funds that largely hold the same stocks.")
        + _icon_item("⚪", "Size", "Larger bubble = higher past return for the selected period.")
        + _icon_item("🟣", "Colour", "Purple = Fund A selected &nbsp;&bull;&nbsp; Teal = Fund B selected &nbsp;&bull;&nbsp; Grey = others when a fund is active.")
        + _icon_item("🖱️", "Selecting", "Click any bubble, or use the dropdown on the right, to select Fund A and Fund B for comparison.")
    )

    return (
        f'<details style="background:{al};border:1px solid {bdr};border-radius:10px;'
        f'padding:0.55rem 0.85rem;margin-bottom:0.7rem;cursor:pointer;">'
        f'<summary style="font-size:0.78rem;font-weight:700;color:{head};'
        f'list-style:none;display:flex;align-items:center;gap:6px;">'
        f'&#8505;&#65039;&nbsp; How to read this graph'
        f'</summary>'
        f'<div style="margin-top:0.65rem;padding-top:0.55rem;border-top:1px solid {bdr};">'
        + lines_section
        + bubbles_section
        + f'</div></details>'
    )


def overlap_row_color(score: float, palette: dict | None = None) -> str:
    return overlap_list_color(score)
