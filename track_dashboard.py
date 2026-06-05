"""FundLens Track portfolio dashboard v2 — screenshot-aligned layout."""
from __future__ import annotations

import html as _html
from datetime import date
from typing import Any, Callable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import portfolio_track as pt

_PRIMARY = "#2563EB"
_GREEN = "#16A34A"
_RED = "#DC2626"
_DONUT_COLORS = (
    "#2563EB", "#16A34A", "#F59E0B", "#8B5CF6", "#06B6D4",
    "#EC4899", "#64748B", "#84CC16", "#F97316",
)


def _track_palette(t: dict, t_name: str) -> dict[str, Any]:
    is_dark = t_name == "dark_premium"
    return {
        "t": t,
        "t_name": t_name,
        "is_dark": is_dark,
        "hd": t["head"],
        "bd": t["body"],
        "sb": t["sub"],
        "cd": t["card"],
        "bdr": t["bdr"],
        "a": t.get("a") or _PRIMARY,
        "al": t["al"],
        "green": "#34D399" if is_dark else _GREEN,
        "red": "#FCA5A5" if is_dark else _RED,
        "pill_g_bg": "rgba(16,185,129,0.15)" if is_dark else "#DCFCE7",
        "pill_g_fg": "#34D399" if is_dark else _GREEN,
        "pill_r_bg": "rgba(239,68,68,0.15)" if is_dark else "#FEE2E2",
        "pill_r_fg": "#FCA5A5" if is_dark else _RED,
        "pill_a_bg": "rgba(37,99,235,0.12)" if is_dark else "#DBEAFE",
        "pill_a_fg": "#60A5FA" if is_dark else _PRIMARY,
        "pill_o_bg": "rgba(245,158,11,0.15)" if is_dark else "#FEF3C7",
        "pill_o_fg": "#FBBF24" if is_dark else "#D97706",
    }


def inject_track_dashboard_css(p: dict) -> None:
    hd, sb, bd, bdr, cd, al, a = p["hd"], p["sb"], p["bd"], p["bdr"], p["cd"], p["al"], p["a"]
    shadow = "0 1px 3px rgba(15,23,42,0.06),0 4px 16px rgba(15,23,42,0.04)"
    if p["is_dark"]:
        shadow = "0 4px 20px rgba(0,0,0,0.25)"
    st.markdown(
        f"""<style>
.fl-track-dash {{ margin-top:0.5rem; }}
.fl-track-dash .metric-card,.fl-track-dash .metric-value,.fl-track-dash .metric-label {{
  all:unset;
}}
.fl-track-hero {{
  display:flex;justify-content:space-between;align-items:flex-start;gap:16px;
  margin:0 0 0.65rem;
}}
.fl-track-hero h2 {{
  font-size:1.75rem!important;font-weight:800!important;color:{hd}!important;
  margin:0 0 4px!important;line-height:1.2!important;
}}
.fl-track-hero p {{ color:{bd};font-size:0.88rem;margin:0;line-height:1.5; }}
.fl-track-hero-meta {{
  text-align:right;font-size:0.72rem;color:{sb};white-space:nowrap;padding-top:4px;
}}
.fl-track-hero-meta strong {{ display:block;color:{hd};font-size:0.82rem;margin-top:2px; }}
.fl-track-page-sentinel,.fl-track-v2-tabs,.fl-track-chart-sentinel,.fl-track-side-sentinel,
.fl-track-filter-sentinel,.fl-track-ov-sentinel,.fl-track-alloc-sentinel,
.fl-track-alloc-fill,.fl-track-side-compact,.fl-track-ov-r1,.fl-track-ov-r2,.fl-track-ov-r3,
.fl-track-ov-r2-box,.fl-track-ov-r3-box {{
  display:none!important;height:0!important;margin:0!important;padding:0!important;
}}
[data-testid="stTabPanel"]:has(.fl-track-ov-sentinel) [data-testid="stHorizontalBlock"] {{
  gap:0.4rem!important;align-items:stretch!important;margin-bottom:0.45rem!important;
}}
[data-testid="stTabPanel"]:has(.fl-track-ov-sentinel) [data-testid="stHorizontalBlock"] > [data-testid="column"] {{
  display:flex!important;flex-direction:column!important;
}}
[data-testid="stTabPanel"]:has(.fl-track-ov-sentinel) [data-testid="stHorizontalBlock"] > [data-testid="column"] > div {{
  flex:1 1 auto!important;display:flex!important;flex-direction:column!important;
}}
[data-testid="stTabPanel"]:has(.fl-track-ov-sentinel) [data-testid="stVerticalBlockBorderWrapper"] {{
  padding:10px 12px!important;margin-bottom:0!important;flex:1 1 auto!important;
  display:flex!important;flex-direction:column!important;box-sizing:border-box!important;
}}
[data-testid="stHorizontalBlock"]:has(.fl-track-ov-r1) [data-testid="stVerticalBlockBorderWrapper"] {{
  min-height:458px!important;
}}
[data-testid="stTabPanel"]:has(.fl-track-ov-sentinel) [data-testid="stMarkdownContainer"]:has(.fl-track-ov-r2-box) + div [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stTabPanel"]:has(.fl-track-ov-sentinel) [data-testid="stMarkdownContainer"]:has(.fl-track-ov-r2-box) + [data-testid="stVerticalBlockBorderWrapper"] {{
  height:390px!important;min-height:390px!important;max-height:390px!important;
  margin-bottom:0!important;overflow:visible!important;box-sizing:border-box!important;
}}
[data-testid="stTabPanel"]:has(.fl-track-ov-sentinel) [data-testid="stMarkdownContainer"]:has(.fl-track-ov-r3-box) + div [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stTabPanel"]:has(.fl-track-ov-sentinel) [data-testid="stMarkdownContainer"]:has(.fl-track-ov-r3-box) + [data-testid="stVerticalBlockBorderWrapper"] {{
  height:234px!important;min-height:234px!important;max-height:234px!important;
  margin-bottom:0!important;overflow:visible!important;box-sizing:border-box!important;
}}
.fl-track-insights-body,.fl-track-health-body,.fl-track-movers-body {{
  flex:1 1 auto;display:flex;flex-direction:column;
}}
.fl-track-insights-body {{
  justify-content:space-between;min-height:360px;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(.fl-track-alloc-fill) [data-testid="stHorizontalBlock"] {{
  flex:1 1 auto!important;align-items:stretch!important;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(.fl-track-alloc-fill) [data-testid="stPlotlyChart"] {{
  flex:1 1 auto!important;
}}
.fl-track-health-body {{
  justify-content:flex-start;min-height:0;gap:0;
}}
.fl-track-health-compact .fl-track-health-row {{
  padding:2px 0!important;line-height:1.25!important;
  align-items:flex-start!important;min-height:0!important;
}}
.fl-track-movers-body {{
  justify-content:flex-start;min-height:0;
}}
.fl-track-risk-body {{
  flex:1 1 auto;display:flex;flex-direction:column;justify-content:flex-start;
  min-height:0;
}}
.fl-track-risk-compact .fl-track-mini-grid {{
  margin-bottom:0;
}}
[data-testid="stMarkdownContainer"]:has(.fl-track-ov-r3-box) + div [data-testid="stVerticalBlockBorderWrapper"] .fl-track-mover,
[data-testid="stMarkdownContainer"]:has(.fl-track-ov-r3-box) + [data-testid="stVerticalBlockBorderWrapper"] .fl-track-mover {{
  padding:8px 11px!important;margin-bottom:5px!important;font-size:0.78rem!important;
}}
[data-testid="stMarkdownContainer"]:has(.fl-track-ov-r3-box) + div [data-testid="stVerticalBlockBorderWrapper"] .fl-track-movers-foot,
[data-testid="stMarkdownContainer"]:has(.fl-track-ov-r3-box) + [data-testid="stVerticalBlockBorderWrapper"] .fl-track-movers-foot {{
  margin-top:8px!important;
}}
.fl-track-ov-panel-hdr {{
  display:flex;justify-content:space-between;align-items:center;
  margin-bottom:6px;padding-bottom:0;border:none;min-height:22px;
}}
.fl-track-health-extra {{
  font-size:0.58rem;color:{sb};margin-top:2px;line-height:1.3;
}}
.fl-track-health-extra a {{
  color:{a};text-decoration:none;font-weight:600;
}}
div[data-testid="column"]:has(.fl-track-side-compact) [data-testid="stVerticalBlockBorderWrapper"] {{
  padding:8px 10px!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-panel-hdr {{
  margin-bottom:7px!important;padding-bottom:7px!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-panel-title {{
  font-size:0.82rem!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-ov-panel-hdr {{
  margin-bottom:8px!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-panel-link {{
  font-size:0.66rem!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-insight-row {{
  padding:5px 0!important;font-size:0.71rem!important;gap:7px!important;line-height:1.42!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-insight-ico {{
  width:22px!important;height:22px!important;font-size:0.68rem!important;border-radius:6px!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-health-row {{
  padding:2px 0!important;font-size:0.68rem!important;line-height:1.25!important;
  align-items:flex-start!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-health-row div span {{
  font-size:0.68rem!important;line-height:1.25!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-health-body {{
  justify-content:flex-start!important;min-height:0!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-badge {{
  font-size:0.56rem!important;padding:2px 7px!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-mini-grid {{
  gap:6px!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-mini {{
  padding:6px 7px!important;border-radius:8px!important;gap:5px!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-mini-val {{
  font-size:0.82rem!important;line-height:1.1!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-mini-lbl {{
  font-size:0.52rem!important;margin-top:1px!important;line-height:1.2!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-risk-body {{
  justify-content:flex-start!important;min-height:0!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-mini-ico {{
  font-size:0.85rem!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-section-kicker {{
  margin-bottom:6px!important;font-size:0.6rem!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-risk-foot {{
  font-size:0.56rem!important;margin-top:4px!important;line-height:1.35!important;
}}
div[data-testid="column"]:has(.fl-track-side-compact) .fl-track-health-extra {{
  font-size:0.54rem!important;margin-top:1px!important;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(.fl-track-alloc-sentinel) [data-testid="stHorizontalBlock"] {{
  gap:0.2rem!important;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(.fl-track-alloc-sentinel) [data-testid="column"] {{
  padding-left:2px!important;padding-right:2px!important;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(.fl-track-alloc-sentinel) [data-testid="stPlotlyChart"] {{
  margin-bottom:0!important;
}}
.fl-track-chart-hdr {{
  display:flex;justify-content:space-between;align-items:center;gap:10px;
  margin-bottom:6px;flex-wrap:wrap;
}}
.fl-track-filter-field-lbl {{
  font-size:0.62rem;font-weight:600;color:{sb};text-transform:uppercase;
  letter-spacing:0.05em;margin:0 0 3px;line-height:1.2;
}}
[data-testid="stMarkdownContainer"]:has(.fl-track-filter-sentinel) + div [data-testid="stVerticalBlockBorderWrapper"] {{
  padding:5px 10px 6px!important;margin-bottom:0.6rem!important;
}}
[data-testid="stMarkdownContainer"]:has(.fl-track-filter-sentinel) + div [data-testid="stVerticalBlockBorderWrapper"] > div {{
  gap:0.15rem!important;
}}
[data-testid="stMarkdownContainer"]:has(.fl-track-filter-sentinel) + div [data-testid="stVerticalBlockBorderWrapper"] [data-testid="column"] {{
  gap:0.1rem!important;
}}
[data-testid="stMarkdownContainer"]:has(.fl-track-filter-sentinel) + div [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMultiSelect"] {{
  margin-bottom:0!important;
}}
[data-testid="stMarkdownContainer"]:has(.fl-track-filter-sentinel) + div [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMultiSelect"] > div > div {{
  min-height:1.65rem!important;padding:0.08rem 0.32rem!important;
  font-size:0.72rem!important;border-radius:7px!important;
}}
[data-testid="stMarkdownContainer"]:has(.fl-track-filter-sentinel) + div [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMultiSelect"] [data-baseweb="tag"] {{
  font-size:0.66rem!important;height:1.2rem!important;margin:1px 2px 1px 0!important;
  border-radius:5px!important;
}}
[data-testid="stMarkdownContainer"]:has(.fl-track-filter-sentinel) + div [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMultiSelect"] span {{
  font-size:0.72rem!important;
}}
[data-testid="stMarkdownContainer"]:has(.fl-track-filter-sentinel) + div [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stDateInput"] {{
  margin-top:0!important;
}}
[data-testid="stMarkdownContainer"]:has(.fl-track-filter-sentinel) + div [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stDateInput"] > div {{
  min-height:1.65rem!important;
}}
[data-testid="stMarkdownContainer"]:has(.fl-track-filter-sentinel) + div [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stDateInput"] input {{
  font-size:0.72rem!important;min-height:1.65rem!important;padding:0.15rem 0.4rem!important;
  border-radius:7px!important;
}}
.fl-track-kpi-row {{
  display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:0 0 1rem;
  overflow:visible;
}}
.fl-track-kpi-card {{
  background:{cd};border:1px solid {bdr};border-radius:12px;padding:18px 20px;
  box-shadow:{shadow};min-height:112px;display:flex;flex-direction:column;justify-content:center;
  transition:box-shadow 0.15s ease,border-color 0.15s ease;overflow:visible;position:relative;
}}
.fl-track-kpi-card:hover {{ box-shadow:0 4px 20px rgba(37,99,235,0.08);border-color:{a}33; }}
.fl-track-kpi-lbl {{
  font-size:0.64rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:{sb};
  margin-bottom:8px;display:flex;align-items:center;gap:5px;
}}
.fl-track-tip-wrap {{
  position:relative;display:inline-flex;align-items:center;flex-shrink:0;
}}
.fl-track-tip-ico {{
  width:14px;height:14px;border-radius:50%;border:1px solid {bdr};
  font-size:0.58rem;font-weight:800;color:{sb};cursor:help;
  display:inline-flex;align-items:center;justify-content:center;line-height:1;
  background:{al};text-transform:none;letter-spacing:0;
}}
.fl-track-tip-pop {{
  display:none;position:absolute;bottom:calc(100% + 8px);left:50%;
  transform:translateX(-50%);width:min(248px,72vw);z-index:10050;
  background:{cd};border:1px solid {bdr};border-radius:10px;padding:0.65rem 0.75rem;
  font-size:0.7rem;font-weight:500;line-height:1.5;color:{bd};text-align:left;
  text-transform:none;letter-spacing:0;white-space:normal;
  box-shadow:0 10px 28px rgba(15,23,42,0.14);pointer-events:none;
}}
.fl-track-tip-pop::after {{
  content:"";position:absolute;top:100%;left:50%;transform:translateX(-50%);
  border:6px solid transparent;border-top-color:{cd};
}}
.fl-track-tip-wrap:hover .fl-track-tip-pop,
.fl-track-tip-wrap:focus-within .fl-track-tip-pop {{ display:block; }}
.fl-track-panel-title-row {{
  display:flex;align-items:center;gap:6px;
}}
.fl-track-kpi-val {{
  font-size:1.72rem;font-weight:800;line-height:1.1;font-feature-settings:"tnum";
  letter-spacing:-0.025em;
}}
.fl-track-kpi-sub {{ font-size:0.74rem;color:{sb};margin-top:8px;line-height:1.45; }}
.fl-track-kpi-sub .pos {{ color:{_GREEN};font-weight:700; }}
.fl-track-kpi-sub .neg {{ color:{_RED};font-weight:700; }}
.fl-track-perf-wrap {{
  background:{cd};border:1px solid {bdr};border-radius:12px;padding:16px 18px;
  margin-bottom:1.25rem;box-shadow:{shadow};overflow:visible;
}}
.fl-track-perf-title {{
  font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;
  color:{sb};margin-bottom:12px;display:flex;align-items:center;gap:6px;overflow:visible;
}}
.fl-track-perf-row {{ display:flex;flex-wrap:wrap;gap:8px; }}
.fl-track-perf-pill {{
  background:{cd};border:1px solid {bdr};border-radius:10px;padding:8px 16px;
  font-size:0.68rem;font-weight:600;color:{sb};min-width:72px;text-align:center;
  box-shadow:0 1px 2px rgba(15,23,42,0.04);
}}
.fl-track-perf-pill.pos {{ background:#F0FDF4;border-color:#BBF7D0; }}
.fl-track-perf-pill.neg {{ background:#FEF2F2;border-color:#FECACA; }}
.fl-track-perf-pill strong {{ display:block;font-size:0.88rem;margin-top:2px;font-weight:800; }}
.fl-track-hero + div [data-testid="stVerticalBlockBorderWrapper"],
.fl-track-page-sentinel ~ div [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stTabs"] [data-testid="stVerticalBlockBorderWrapper"] {{
  background:{cd}!important;border:1px solid {bdr}!important;border-radius:14px!important;
  box-shadow:{shadow}!important;padding:12px 16px!important;margin-bottom:14px!important;
}}
[data-testid="stTabs"] [data-testid="stPlotlyChart"] {{
  margin-bottom:-0.35rem!important;
}}
.fl-track-panel-hdr {{
  display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;
  padding-bottom:12px;border-bottom:1px solid {bdr};
}}
.fl-track-panel-title {{ font-size:0.95rem;font-weight:700;color:{hd}; }}
.fl-track-panel-link {{
  font-size:0.74rem;font-weight:600;color:{a};text-decoration:none;
}}
.fl-track-panel-link:hover {{ text-decoration:underline; }}
.fl-track-section-kicker {{
  font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;
  color:{a};margin:0 0 10px;
}}
.fl-track-side {{ position:sticky;top:68px; }}
.fl-track-health-score {{
  display:flex;align-items:center;gap:14px;margin-bottom:14px;padding-bottom:14px;
  border-bottom:1px solid {bdr};
}}
.fl-track-health-num {{
  font-size:2rem;font-weight:800;color:{a};line-height:1;font-feature-settings:"tnum";
}}
.fl-track-health-lbl {{ font-size:0.72rem;color:{sb};margin-top:2px; }}
.fl-track-insight-row {{
  display:flex;gap:12px;align-items:flex-start;padding:12px 0;
  border-bottom:1px solid {bdr};font-size:0.82rem;color:{bd};line-height:1.55;
}}
.fl-track-insight-row:last-child {{ border-bottom:none; }}
.fl-track-insight-ico {{
  flex-shrink:0;width:32px;height:32px;border-radius:10px;display:flex;
  align-items:center;justify-content:center;font-size:0.9rem;font-weight:700;
}}
.fl-track-health-row {{
  display:flex;justify-content:space-between;align-items:center;gap:10px;
  padding:10px 0;border-bottom:1px solid {bdr};font-size:0.82rem;color:{bd};
}}
.fl-track-health-row:last-child {{ border-bottom:none; }}
.fl-track-badge {{
  font-size:0.66rem;font-weight:700;padding:4px 11px;border-radius:9999px;white-space:nowrap;
}}
.fl-track-badge.g {{ background:{p["pill_g_bg"]};color:{p["pill_g_fg"]}; }}
.fl-track-badge.m {{ background:{p["pill_o_bg"]};color:{p["pill_o_fg"]}; }}
.fl-track-badge.p {{ background:{p["pill_r_bg"]};color:{p["pill_r_fg"]}; }}
.fl-track-mini-grid {{ display:grid;grid-template-columns:repeat(2,1fr);gap:10px; }}
.fl-track-mini {{
  background:{al};border:1px solid {bdr};border-radius:12px;padding:14px 12px;
  display:flex;gap:10px;align-items:flex-start;
}}
.fl-track-mini-ico {{ font-size:1.15rem;line-height:1;opacity:0.9;flex-shrink:0; }}
.fl-track-mini-val {{ font-size:1.15rem;font-weight:800;color:{hd};line-height:1.1; }}
.fl-track-mini-lbl {{
  font-size:0.62rem;color:{sb};margin-top:3px;text-transform:uppercase;letter-spacing:0.04em;
}}
.fl-track-mover {{
  display:flex;justify-content:space-between;gap:12px;padding:12px 14px;margin-bottom:8px;
  background:{al};border-radius:10px;border:1px solid {bdr};font-size:0.82rem;color:{bd};
}}
.fl-track-mover.win {{ border-left:3px solid {_GREEN}; }}
.fl-track-mover.loss {{ border-left:3px solid {_RED}; }}
.fl-track-mover-name {{ font-weight:600;color:{hd};overflow:hidden;text-overflow:ellipsis; }}
.fl-track-movers-foot {{
  margin-top:12px;font-size:0.76rem;font-weight:600;color:{a};text-align:center;
}}
.fl-track-hold-row {{
  display:grid;grid-template-columns:minmax(0,1fr) 80px 80px 72px 64px;gap:8px;
  padding:10px 12px;border-bottom:1px solid {bdr};align-items:center;
}}
.fl-track-hold-fn {{ font-size:0.8rem;font-weight:600;color:{hd}; }}
.fl-track-hold-fa {{ font-size:0.68rem;color:{sb}; }}
.fl-track-hold-num {{ text-align:right;font-size:0.8rem;font-variant-numeric:tabular-nums;color:{bd}; }}
div[data-testid="column"]:has(.fl-track-chart-sentinel) [data-testid="stRadio"] > div {{
  background:{al}!important;border:1px solid {bdr}!important;border-radius:10px!important;
  padding:4px!important;gap:4px!important;flex-wrap:nowrap!important;
}}
div[data-testid="column"]:has(.fl-track-chart-sentinel) [data-testid="stRadio"] label {{
  background:transparent!important;border:none!important;border-radius:7px!important;
  padding:0.3rem 0.7rem!important;font-size:0.72rem!important;font-weight:600!important;
  margin:0!important;min-width:unset!important;
}}
div[data-testid="column"]:has(.fl-track-chart-sentinel) [data-testid="stRadio"] label[data-checked="true"],
div[data-testid="column"]:has(.fl-track-chart-sentinel) [data-testid="stRadio"] label:has(input:checked) {{
  background:{a}!important;color:#fff!important;
}}
@media (max-width:1100px) {{
  .fl-track-kpi-row {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
  .fl-track-side {{ position:static; }}
}}
</style>""",
        unsafe_allow_html=True,
    )


def _inject_pill_tabs_css(p: dict, sentinel: str) -> None:
    shadow = "0 2px 8px rgba(0,0,0,0.22)" if p["is_dark"] else "0 2px 10px rgba(15,23,42,0.08)"
    a, sb, al, bdr, cd = p["a"], p["sb"], p["al"], p["bdr"], p["cd"]
    st.markdown(
        f"""<style>
[data-testid="stMarkdownContainer"]:has(.{sentinel}) + [data-testid="stTabs"] {{
  margin-top: 0 !important; margin-bottom: 0.75rem !important;
}}
[data-testid="stMarkdownContainer"]:has(.{sentinel}) + [data-testid="stTabs"] [data-baseweb="tab-list"] {{
  background: {al} !important; border: 1.5px solid {bdr} !important;
  border-radius: 12px !important; padding: 5px !important; gap: 6px !important;
  border-bottom: none !important; box-shadow: {shadow};
}}
[data-testid="stMarkdownContainer"]:has(.{sentinel}) + [data-testid="stTabs"] [data-baseweb="tab"] {{
  background: transparent !important; border: none !important; border-radius: 8px !important;
  color: {sb} !important; font-size: 0.84rem !important; font-weight: 600 !important;
  padding: 0.55rem 0.85rem !important; flex: 1 1 0 !important; justify-content: center !important;
}}
[data-testid="stMarkdownContainer"]:has(.{sentinel}) + [data-testid="stTabs"] [aria-selected="true"] {{
  background: {a} !important; color: #FFFFFF !important;
}}
[data-testid="stMarkdownContainer"]:has(.{sentinel}) + [data-testid="stTabs"] [data-baseweb="tab-panel"] {{
  padding-top: 0.5rem !important;
}}
</style>""",
        unsafe_allow_html=True,
    )


def _signed_inr(val: float, fmt_inr: Callable[[Any], str]) -> str:
    prefix = "+" if val >= 0 else "−"
    return f"{prefix}{fmt_inr(abs(val))}"


def _ret_color(val: float | None, p: dict) -> str:
    if val is None:
        return p["sb"]
    return p["green"] if val >= 0 else p["red"]


def _badge_html(level: str, p: dict) -> str:
    cls = {"Good": "g", "Medium": "m", "Poor": "p", "High": "p", "Low": "g"}.get(level, "m")
    return f'<span class="fl-track-badge {cls}">{_html.escape(str(level))}</span>'


def _track_tip_icon(text: str) -> str:
    return (
        f'<span class="fl-track-tip-wrap" tabindex="0" role="button" aria-label="More info">'
        f'<span class="fl-track-tip-ico">i</span>'
        f'<span class="fl-track-tip-pop">{_html.escape(text)}</span>'
        f"</span>"
    )


def _panel_title_html(title: str, *, tip: str = "") -> str:
    tip_html = _track_tip_icon(tip) if tip else ""
    return (
        f'<div class="fl-track-panel-title-row">'
        f'<span class="fl-track-panel-title">{_html.escape(title)}</span>{tip_html}</div>'
    )


def _kpi_card(
    label: str,
    value: str,
    p: dict,
    *,
    sub: str = "",
    value_color: str = "",
    tip: str = "",
) -> str:
    vcol = value_color or p["hd"]
    sub_html = f'<div class="fl-track-kpi-sub">{sub}</div>' if sub else ""
    tip_html = _track_tip_icon(tip) if tip else ""
    return (
        f'<div class="fl-track-kpi-card">'
        f'<div class="fl-track-kpi-lbl"><span>{_html.escape(label)}</span>{tip_html}</div>'
        f'<div class="fl-track-kpi-val" style="color:{vcol};">{_html.escape(value)}</div>'
        f"{sub_html}</div>"
    )


def render_snapshot_kpis(
    totals: dict,
    xirr_pct: float | None,
    portfolio_age_y: float,
    cagr_pct: float | None,
    health: dict[str, Any],
    p: dict,
    fmt_inr: Callable[[Any], str],
    *,
    perf: dict[str, float | None] | None = None,
) -> None:
    cur = fmt_inr(totals.get("current_value"))
    inv = fmt_inr(totals.get("invested"))
    gain = float(totals.get("gain") or 0)
    gain_s = _signed_inr(gain, fmt_inr)
    gain_col = p["green"] if gain >= 0 else p["red"]
    abs_ret = totals.get("return_pct")
    abs_s = f"{abs_ret:+.2f}%" if abs_ret is not None else "—"

    cur_f = float(totals.get("current_value") or 0)
    day_ret = (perf or {}).get("1D")
    cur_sub = ""
    if day_ret is not None:
        cls = "pos" if day_ret >= 0 else "neg"
        delta_inr = cur_f * float(day_ret) / 100.0 if cur_f else 0.0
        cur_sub = (
            f'vs yesterday <span class="{cls}">'
            f"{_html.escape(_signed_inr(delta_inr, fmt_inr))} ({day_ret:+.2f}%)</span>"
        )

    if portfolio_age_y < 1.0:
        ret_label = "Portfolio return"
        ret_val = abs_s
        ret_sub = "Absolute return · portfolio age &lt; 1 year"
        ret_col = _ret_color(abs_ret, p)
        ret_tip = pt.PORTFOLIO_RETURN_TOOLTIP
    else:
        ret_label = "XIRR (annualised)"
        ret_val = f"{xirr_pct:+.2f}%" if xirr_pct is not None else abs_s
        cagr_s = f"{cagr_pct:+.2f}%" if cagr_pct is not None else "—"
        ret_sub = f'CAGR <span class="pos">{_html.escape(cagr_s)}</span> · secondary metric'
        ret_col = _ret_color(xirr_pct or abs_ret, p)
        ret_tip = pt.XIRR_TOOLTIP

    score = int(health.get("score") or 0)
    status = str(health.get("status") or "—")
    status_cls = "g" if status == "Good" else "m" if status == "Medium" else "p"
    gain_cls = "pos" if gain >= 0 else "neg"

    health_sub = f'<span class="fl-track-badge {status_cls}">{_html.escape(status)}</span>'
    cards = (
        _kpi_card("Current value", cur, p, sub=cur_sub, value_color=p["a"])
        + _kpi_card("Total invested", inv, p, value_color=p["a"])
        + _kpi_card(
            "Gain / loss", gain_s, p,
            sub=f'<span class="{gain_cls}">{_html.escape(abs_s)}</span>',
            value_color=gain_col,
        )
        + _kpi_card(ret_label, ret_val, p, sub=ret_sub, value_color=ret_col, tip=ret_tip)
        + _kpi_card(
            "Portfolio health",
            f"{score} / 100",
            p,
            sub=health_sub,
            value_color=p["a"],
            tip=pt.HEALTH_SCORE_TOOLTIP,
        )
    )
    st.markdown(
        f'<div class="fl-track-dash"><div class="fl-track-kpi-row">{cards}</div></div>',
        unsafe_allow_html=True,
    )


def render_performance_pills(perf: dict[str, float | None], p: dict) -> None:
    order = ("1D", "1W", "1M", "3M", "6M", "1Y", "3Y CAGR")
    pills: list[str] = []
    for key in order:
        val = perf.get(key)
        if val is None:
            txt, col, pcls = "—", p["sb"], ""
        else:
            txt, col = f"{val:+.2f}%", _ret_color(val, p)
            pcls = "pos" if val >= 0 else "neg"
        pills.append(
            f'<div class="fl-track-perf-pill {pcls}">{key}'
            f'<strong style="color:{col};">{txt}</strong></div>'
        )
    st.markdown(
        f'<div class="fl-track-perf-wrap">'
        f'<div class="fl-track-perf-title">Performance snapshot {_track_tip_icon(pt.PERF_SNAPSHOT_TOOLTIP)}</div>'
        f'<div class="fl-track-perf-row">{"".join(pills)}</div></div>',
        unsafe_allow_html=True,
    )


def _plotly_dual_line(
    dual: pd.DataFrame,
    p: dict,
    *,
    height: int = 360,
    fmt_inr: Callable[[Any], str] | None = None,
) -> go.Figure:
    a, sb, bdr = p["a"], p["sb"], p["bdr"]
    df = dual.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")
    fig = go.Figure()
    cur_vals = df["current_value"] if "current_value" in df.columns else pd.Series(dtype=float)
    inv_vals = df["invested_value"] if "invested_value" in df.columns else pd.Series(dtype=float)

    if "invested_value" in df.columns and not inv_vals.empty:
        fig.add_trace(
            go.Scatter(
                x=df["date"], y=df["invested_value"], name="Invested value",
                mode="lines", line=dict(color="#94A3B8", width=1.8, dash="dot"),
                hovertemplate="%{x|%d %b %Y}<br>₹%{y:,.0f}<extra>Invested</extra>",
            )
        )
    if "current_value" in df.columns and not cur_vals.empty:
        fill_clr = "rgba(37,99,235,0.12)" if not p["is_dark"] else "rgba(37,99,235,0.2)"
        fig.add_trace(
            go.Scatter(
                x=df["date"], y=df["current_value"], name="Current value",
                mode="lines", line=dict(color=a, width=2.8),
                fill="tozeroy", fillcolor=fill_clr,
                hovertemplate="%{x|%d %b %Y}<br>₹%{y:,.0f}<extra>Current</extra>",
            )
        )

    annotations: list[dict] = []
    if not df.empty and fmt_inr:
        last = df.iloc[-1]
        if "current_value" in last and pd.notna(last["current_value"]):
            annotations.append(dict(
                x=last["date"], y=float(last["current_value"]),
                text=fmt_inr(last["current_value"]),
                showarrow=False, xanchor="left", xshift=8,
                font=dict(size=11, color=a, family="Inter, sans-serif"),
                bgcolor="rgba(255,255,255,0.85)" if not p["is_dark"] else p["cd"],
                bordercolor=bdr, borderwidth=1, borderpad=4,
            ))
        if "invested_value" in last and pd.notna(last["invested_value"]):
            annotations.append(dict(
                x=last["date"], y=float(last["invested_value"]),
                text=fmt_inr(last["invested_value"]),
                showarrow=False, xanchor="left", xshift=8, yshift=-18,
                font=dict(size=10, color=sb, family="Inter, sans-serif"),
            ))

    fig.update_layout(
        margin=dict(l=8, r=72, t=12, b=8),
        height=height,
        hoverlabel=dict(bgcolor=p["cd"], font_size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=p["bd"], size=11),
        legend=dict(orientation="h", yanchor="bottom", y=1.04, x=0, font=dict(size=10)),
        hovermode="x unified",
        annotations=annotations,
        xaxis=dict(showgrid=True, gridcolor=bdr, showline=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor=bdr, tickformat=",.0f", showline=False, zeroline=False),
    )
    return fig


def _short_amc_label(name: str) -> str:
    s = str(name or "—").strip()
    for suffix in (" Mutual Fund", " MF", " Asset Management Company", " AMC"):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    return s if len(s) <= 22 else s[:20] + "…"


def _rollup_donut_items(
    items: list[tuple[str, float]],
    *,
    max_slices: int = 6,
) -> list[tuple[str, float]]:
    clean = [(str(k), float(v or 0)) for k, v in items if float(v or 0) > 0]
    if len(clean) <= max_slices:
        return clean
    head = clean[: max_slices - 1]
    tail_sum = sum(v for _, v in clean[max_slices - 1 :])
    if tail_sum > 0:
        head.append(("Other", tail_sum))
    return head


def _donut_chart(
    items: list[tuple[str, float]],
    title: str,
    p: dict,
    *,
    center_label: str = "",
    height: int = 280,
    show_labels: bool = True,
    legend_below: bool = False,
    compact_legend: bool = False,
    label_fn: Callable[[str], str] | None = None,
    rollup: bool = False,
    grid_cell: bool = False,
) -> go.Figure:
    rows = _rollup_donut_items(items) if rollup else list(items[:8])
    labels = [(label_fn or (lambda x: x))(k) for k, _ in rows]
    values = [float(v or 0) for _, v in rows]
    if not values or sum(values) <= 0:
        fig = go.Figure()
        fig.add_annotation(text="No data", showarrow=False, font=dict(color=p["sb"], size=11))
        fig.update_layout(height=height, margin=dict(l=4, r=4, t=32, b=4))
        return fig
    n = len(labels)
    if grid_cell:
        compact_legend = True
        show_labels = False
        legend_below = False
    use_outside = show_labels and n <= 4 and not compact_legend
    colors = [_DONUT_COLORS[i % len(_DONUT_COLORS)] for i in range(n)]
    if grid_cell:
        pie_domain = dict(x=[0.0, 0.52], y=[0.02, 0.98])
        center_xy = (0.26, 0.5)
    elif legend_below:
        pie_domain = dict(x=[0.18, 0.82], y=[0.12, 0.92])
        center_xy = (0.5, 0.5)
    elif compact_legend:
        pie_domain = dict(x=[0.0, 0.44], y=[0.04, 0.96])
        center_xy = (0.22, 0.5)
    else:
        pie_domain = None
        center_xy = (0.5, 0.5)
    fig = go.Figure(
        go.Pie(
            labels=labels, values=values, hole=0.58,
            marker=dict(colors=colors, line=dict(color=p["cd"], width=2)),
            textinfo="percent" if use_outside else "none",
            textposition="outside" if use_outside else "inside",
            textfont=dict(size=10),
            domain=pie_domain,
            hovertemplate="%{label}<br>₹%{value:,.0f}<br>%{percent}<extra></extra>",
        )
    )
    center_ann: list[dict] = []
    if center_label:
        cx, cy = center_xy
        center_ann.append(dict(
            text=f"<b>{center_label}</b>",
            x=cx, y=cy, xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=9 if grid_cell else (10 if compact_legend else 11), color=p["sb"]),
        ))
    if legend_below:
        legend = dict(
            orientation="h", yanchor="top", y=-0.02, x=0.5, xanchor="center",
            font=dict(size=11), itemsizing="constant", traceorder="normal",
        )
        margin = dict(l=24, r=24, t=48, b=88)
    elif compact_legend:
        legend = dict(
            orientation="v", yanchor="middle", y=0.5,
            x=0.54 if grid_cell else 0.46,
            xanchor="left",
            font=dict(size=8 if grid_cell else 9),
        )
        margin = dict(l=0, r=0, t=32 if grid_cell else 36, b=0)
    else:
        legend = dict(font=dict(size=9), orientation="v", yanchor="middle", y=0.5, x=1.02)
        margin = dict(l=4, r=4, t=40, b=4)
    title_size = 11 if grid_cell else 12
    fig.update_layout(
        title=dict(text=title, font=dict(size=title_size, color=p["hd"], family="Inter, sans-serif")),
        height=height, margin=margin,
        showlegend=True, legend=legend,
        paper_bgcolor="rgba(0,0,0,0)",
        annotations=center_ann,
    )
    return fig


def _movers_section(
    best: list,
    worst: list,
    p: dict,
    fmt_inr: Callable[[Any], str],
    *,
    perf_href: str = "",
) -> str:
    def _row(f: dict, *, win: bool) -> str:
        gl = float(f.get("gl") or 0)
        ret = float(f.get("ret") or 0)
        if win:
            col = p["green"] if gl >= 0 else p["red"]
        else:
            col = p["red"] if ret < 0 else (p["sb"] if gl >= 0 else p["red"])
        cls = "win" if win else "loss"
        return (
            f'<div class="fl-track-mover {cls}">'
            f'<div class="fl-track-mover-name">{_html.escape(str(f.get("name") or ""))}</div>'
            f'<div style="text-align:right;white-space:nowrap;">'
            f'<div style="color:{col};font-weight:700;">{_html.escape(_signed_inr(gl, fmt_inr))}</div>'
            f'<div style="font-size:0.72rem;color:{col};">{ret:+.1f}%</div></div></div>'
        )

    left = "".join(_row(f, win=True) for f in best) or f'<div style="color:{p["sb"]};font-size:0.8rem;">—</div>'
    right = "".join(_row(f, win=False) for f in worst) or f'<div style="color:{p["sb"]};font-size:0.8rem;">—</div>'
    foot = ""
    if perf_href:
        foot = (
            f'<div class="fl-track-movers-foot">'
            f'<a href="{_html.escape(perf_href)}" target="_self" '
            f'style="color:{p["a"]};text-decoration:none;">View all funds performance →</a></div>'
        )
    grid = (
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;flex:1 1 auto;">'
        f'<div><div class="fl-track-section-kicker" style="color:{p["green"]};">▲ Best performers</div>{left}</div>'
        f'<div><div class="fl-track-section-kicker" style="color:{p["red"]};">▼ Biggest drags</div>{right}</div>'
        f"</div>"
    )
    return f'<div class="fl-track-movers-body">{grid}{foot}</div>'


def _insight_html(line: str) -> str:
    chunks = str(line).split("**")
    out: list[str] = []
    for i, chunk in enumerate(chunks):
        if i % 2 == 1:
            out.append(f"<strong>{_html.escape(chunk)}</strong>")
        else:
            out.append(_html.escape(chunk))
    return "".join(out)


def _insight_style(line: str, p: dict) -> tuple[str, str, str]:
    low = line.lower()
    if "xirr" in low or "return" in low or "improved" in low:
        return "↑", p["pill_g_bg"], p["pill_g_fg"]
    if "concentrated" in low or "fund house" in low or "% of value" in low:
        return "◆", p["pill_a_bg"], p["pill_a_fg"]
    if "drag" in low or "loss" in low or "loser" in low:
        return "↓", p["pill_r_bg"], p["pill_r_fg"]
    if "cap" in low or "category" in low or "contribute" in low:
        return "◎", "rgba(139,92,246,0.12)", "#7C3AED"
    if "international" in low or "exposure" in low:
        return "◉", p["pill_o_bg"], p["pill_o_fg"]
    if "gain" in low or "top 3" in low:
        return "✓", p["pill_a_bg"], p["pill_a_fg"]
    if "overlap" in low:
        return "⚠", p["pill_o_bg"], p["pill_o_fg"]
    return "•", p["al"], p["sb"]


def _insights_panel(insights: list[str], p: dict, *, fill: bool = False) -> str:
    if not insights:
        inner = f'<div class="fl-track-insight-row" style="color:{p["sb"]};">No insights yet.</div>'
    else:
        parts: list[str] = []
        for line in insights:
            sym, bg, fg = _insight_style(line, p)
            parts.append(
                f'<div class="fl-track-insight-row">'
                f'<div class="fl-track-insight-ico" style="background:{bg};color:{fg};">{sym}</div>'
                f'<div>{_insight_html(line)}</div></div>'
            )
        parts.append(
            f'<div class="fl-track-insight-row" style="border:none;font-size:0.7rem;color:{p["sb"]};">'
            f"Observations only — not financial advice.</div>"
        )
        inner = "".join(parts)
    cls = "fl-track-insights-body" + (" fl-track-insights-fill" if fill else "")
    return f'<div class="{cls}">{inner}</div>'


def _health_panel(
    health: dict,
    p: dict,
    *,
    analyse_href: str = "",
    show_score: bool = True,
    compact: bool = False,
    fill: bool = False,
) -> str:
    score = int(health.get("score") or 0)
    status = str(health.get("status") or "—")
    status_cls = "g" if status == "Good" else "m" if status == "Medium" else "p"
    header = ""
    if show_score:
        header = (
            f'<div class="fl-track-health-score">'
            f'<div><div class="fl-track-health-num">{score}</div>'
            f'<div class="fl-track-health-lbl">out of 100</div></div>'
            f'<span class="fl-track-badge {status_cls}">{_html.escape(status)}</span></div>'
        )
    dims = health.get("dimensions") or {}
    exp_info = health.get("expense_info") or {}
    exp_pct = exp_info.get("pct")
    try:
        exp_pct_f = float(exp_pct) if exp_pct is not None else None
    except (TypeError, ValueError):
        exp_pct_f = None
    labels = {
        "diversification": "Diversification",
        "concentration": "Concentration risk",
        "expense_ratio": (
            f"Expense ratio ({exp_pct_f:.2f}% wt avg)" if exp_pct_f is not None else "Expense ratio"
        ),
        "fund_overlap": "Fund overlap (category)",
        "liquidity": "Liquidity",
        "international": "International exposure",
    }
    rows: list[str] = []
    for k, lbl in labels.items():
        badge = _badge_html(str(dims.get(k, "Medium")), p)
        extra = ""
        if k == "fund_overlap" and analyse_href:
            if compact:
                extra = (
                    f'<div class="fl-track-health-extra">'
                    f'<a href="{_html.escape(analyse_href)}" target="_self">Analyse →</a></div>'
                )
            else:
                extra = (
                    f'<div style="font-size:0.66rem;color:{p["sb"]};margin-top:3px;">'
                    f'<a href="{_html.escape(analyse_href)}" target="_self" '
                    f'style="color:{p["a"]};text-decoration:none;font-weight:600;">'
                    f"Analyse my portfolio</a> for holding overlap.</div>"
                )
        rows.append(
            f'<div class="fl-track-health-row"><div><span>{_html.escape(lbl)}</span>{extra}</div>{badge}</div>'
        )
    body = header + "".join(rows)
    if fill or not show_score:
        cls = "fl-track-health-body" + (" fl-track-health-compact" if compact else "")
        return f'<div class="{cls}">{body}</div>'
    return body


def _risk_mini_cards(
    metrics: list, overlap: str, p: dict, *, analyse_href: str = "", compact: bool = False
) -> str:
    top3 = pt.concentration_pct(metrics, 3)
    top1 = pt.concentration_pct(metrics, 1)
    n = len(metrics)
    top1_name = ""
    if metrics:
        top_m = max(metrics, key=lambda m: float(m.get("current_value") or 0))
        top1_name = str(top_m.get("fund_name") or "")[:32]
    specs = (
        ("📊", "Top 3 funds", f"{top3:.0f}%", ""),
        ("🏦", "Top 1 fund", f"{top1:.0f}%", top1_name),
        ("🔗", "Portfolio overlap", str(overlap), "category estimate"),
        ("📋", "Number of funds", str(n), "active"),
    )
    html = []
    for ico, lbl, val, hint in specs:
        hint_html = (
            f'<div style="font-size:0.62rem;color:{p["sb"]};margin-top:3px;">'
            f"{_html.escape(hint)}</div>"
            if hint
            else ""
        )
        html.append(
            f'<div class="fl-track-mini"><span class="fl-track-mini-ico">{ico}</span><div>'
            f'<div class="fl-track-mini-val">{_html.escape(val)}</div>'
            f'<div class="fl-track-mini-lbl">{_html.escape(lbl)}</div>{hint_html}</div></div>'
        )
    foot = ""
    if analyse_href and not compact:
        foot = (
            f'<p style="font-size:0.72rem;color:{p["sb"]};margin:10px 0 0;">'
            f"Overlap is category-based here. "
            f'<a href="{_html.escape(analyse_href)}" target="_self" '
            f'style="color:{p["a"]};font-weight:600;text-decoration:none;">'
            f"Analyse my portfolio</a> for a deep overlap dive.</p>"
        )
    elif analyse_href and compact:
        foot = (
            f'<p class="fl-track-risk-foot" style="color:{p["sb"]};margin:4px 0 0;">'
            f'<a href="{_html.escape(analyse_href)}" target="_self" '
            f'style="color:{p["a"]};font-weight:600;text-decoration:none;font-size:0.56rem;">'
            f"Analyse overlap →</a></p>"
        )
    risk_cls = "fl-track-risk-body" + (" fl-track-risk-compact" if compact else "")
    return f'<div class="{risk_cls}"><div class="fl-track-mini-grid">{"".join(html)}</div>{foot}</div>'


def _holdings_rows_html(rows: list[dict], p: dict, fmt_inr: Callable[[Any], str]) -> str:
    out: list[str] = []
    for f in rows:
        gl = float(f.get("gl") or 0)
        gl_color = p["green"] if gl > 0 else p["red"] if gl < 0 else p["sb"]
        gl_txt = "—" if gl == 0 else _signed_inr(gl, fmt_inr)
        out.append(
            f'<div class="fl-track-hold-row">'
            f'<div><div class="fl-track-hold-fn">{_html.escape(f["name"])}</div>'
            f'<div class="fl-track-hold-fa">{_html.escape(f["acct"])}</div></div>'
            f'<div class="fl-track-hold-num">{_html.escape(fmt_inr(f["inv"]))}</div>'
            f'<div class="fl-track-hold-num">{_html.escape(fmt_inr(f["val"]))}</div>'
            f'<div class="fl-track-hold-num" style="color:{gl_color};font-weight:600;">{gl_txt}</div>'
            f'<div class="fl-track-hold-num">{float(f["ret"]):.1f}%</div></div>'
        )
    return "".join(out) if out else f'<div style="padding:12px;color:{p["sb"]};">No holdings</div>'


def _filter_dual_curve(dual: pd.DataFrame, period: str) -> pd.DataFrame:
    if dual is None or dual.empty or period == "All":
        return dual
    months = {"1M": 1, "3M": 3, "6M": 6, "1Y": 12, "3Y": 36}.get(period, 0)
    if not months:
        return dual
    out = dual.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    end = out["date"].max()
    if pd.isna(end):
        return out
    return out[out["date"] >= (end - pd.DateOffset(months=months))]


def render_tabbed_dashboard(
    metrics: list[dict[str, Any]],
    totals: dict,
    xirr_pct: float | None,
    curve: pd.DataFrame,
    t: dict,
    t_name: str,
    fmt_inr: Callable[[Any], str],
    *,
    holdings: pd.DataFrame | None = None,
    txns: pd.DataFrame | None = None,
    as_of_date: date | None = None,
    dual_curve: pd.DataFrame | None = None,
) -> None:
    p = _track_palette(t, t_name)

    as_of = as_of_date or date.today()
    fund_rows = pt.metrics_to_fund_rows(metrics)
    total_val = float(totals.get("current_value") or 0)
    best, worst = pt.top_movers(metrics, n=3)
    age_y = (
        pt.portfolio_age_years(holdings, txns, end=as_of)
        if holdings is not None and txns is not None
        else 0.0
    )
    cagr = (
        pt.portfolio_cagr(holdings, txns, as_of=as_of)
        if holdings is not None and txns is not None
        else None
    )
    perf = (
        pt.performance_snapshot(holdings, txns, curve, as_of=as_of)
        if holdings is not None and txns is not None
        else {}
    )
    overlap_lvl = pt.estimate_overlap_level(metrics)
    expense_info = pt.weighted_expense_ratio(metrics)
    health = pt.portfolio_health(metrics, overlap_label=overlap_lvl, expense_info=expense_info)
    insights = pt.generate_insights(metrics, totals, xirr_pct, perf, health)[:5]
    analyse_href = f"?nav=portfolio_xray&theme={t_name}"
    perf_tab_href = "#fl-track-perf-tab"

    render_snapshot_kpis(
        totals, xirr_pct, age_y, cagr, health, p, fmt_inr, perf=perf
    )
    render_performance_pills(perf, p)

    _inject_pill_tabs_css(p, "fl-track-v2-tabs")
    st.markdown('<div class="fl-track-v2-tabs" aria-hidden="true"></div>', unsafe_allow_html=True)
    tab_ov, tab_perf, tab_hold, tab_ins = st.tabs(
        ["📊  Overview", "📈  Performance", "📋  Holdings", "💡  Insights"]
    )

    with tab_ov:
        st.markdown('<div class="fl-track-ov-sentinel" aria-hidden="true"></div>', unsafe_allow_html=True)
        _ov_main, _ov_side = 2.8, 0.78

        _r1_main, _r1_side = st.columns([_ov_main, _ov_side], gap="small")
        with _r1_main:
            st.markdown('<div class="fl-track-ov-r1" aria-hidden="true"></div>', unsafe_allow_html=True)
            with st.container(border=True):
                _ch_title, _ch_period = st.columns([1, 1.35], gap="small")
                with _ch_title:
                    st.markdown(
                        '<div class="fl-track-panel-title" style="margin-top:4px;">'
                        "Portfolio value over time</div>",
                        unsafe_allow_html=True,
                    )
                with _ch_period:
                    st.markdown(
                        '<div class="fl-track-chart-sentinel" aria-hidden="true"></div>',
                        unsafe_allow_html=True,
                    )
                    chart_period = st.radio(
                        "Chart period",
                        ["1M", "3M", "6M", "1Y", "3Y", "All"],
                        horizontal=True,
                        key="fl_track_chart_period",
                        label_visibility="collapsed",
                    )
                dual = dual_curve if dual_curve is not None else pd.DataFrame()
                if not dual.empty:
                    dual_f = _filter_dual_curve(dual, chart_period)
                    st.plotly_chart(
                        _plotly_dual_line(dual_f, p, height=380, fmt_inr=fmt_inr),
                        use_container_width=True,
                        config={"displayModeBar": False},
                        key="fl_track_chart_ov_dual",
                    )
                else:
                    st.caption("Need more history to plot portfolio value.")
        with _r1_side:
            st.markdown(
                '<div class="fl-track-side-compact fl-track-ov-r1" aria-hidden="true"></div>',
                unsafe_allow_html=True,
            )
            with st.container(border=True):
                st.markdown(
                    f'<div class="fl-track-panel-hdr">'
                    f'<span class="fl-track-panel-title">Portfolio insights</span>'
                    f'<a class="fl-track-panel-link" href="#fl-track-insights-tab">View all</a></div>',
                    unsafe_allow_html=True,
                )
                st.markdown(_insights_panel(insights, p, fill=True), unsafe_allow_html=True)

        _r2_main, _r2_side = st.columns([_ov_main, _ov_side], gap="small")
        with _r2_main:
            st.markdown('<div class="fl-track-ov-r2-box" aria-hidden="true"></div>', unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown(
                    '<div class="fl-track-ov-panel-hdr">'
                    '<span class="fl-track-panel-title">Allocation overview</span></div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    '<div class="fl-track-alloc-sentinel fl-track-alloc-fill" aria-hidden="true"></div>',
                    unsafe_allow_html=True,
                )
                by_cat = pt.category_allocation(metrics)
                by_house = pt.allocation_breakdown(metrics, "fund_house")
                by_acct = pt.allocation_breakdown(metrics, "account_name")
                _tot_lbl = fmt_inr(total_val) if total_val > 0 else ""
                _donut_h = 300
                _donut_kw = dict(
                    center_label=_tot_lbl,
                    height=_donut_h,
                    grid_cell=True,
                    rollup=True,
                )
                d1, d2, d3 = st.columns(3, gap="small")
                with d1:
                    st.plotly_chart(
                        _donut_chart(by_cat, "By category", p, **_donut_kw),
                        use_container_width=True,
                        config={"displayModeBar": False},
                        key="fl_track_donut_category",
                    )
                with d2:
                    st.plotly_chart(
                        _donut_chart(
                            by_house,
                            "By fund house",
                            p,
                            label_fn=_short_amc_label,
                            **_donut_kw,
                        ),
                        use_container_width=True,
                        config={"displayModeBar": False},
                        key="fl_track_donut_fund_house",
                    )
                with d3:
                    st.plotly_chart(
                        _donut_chart(by_acct, "By account", p, **_donut_kw),
                        use_container_width=True,
                        config={"displayModeBar": False},
                        key="fl_track_donut_account",
                    )
        with _r2_side:
            st.markdown('<div class="fl-track-side-compact" aria-hidden="true"></div>', unsafe_allow_html=True)
            st.markdown('<div class="fl-track-ov-r2-box" aria-hidden="true"></div>', unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown(
                    f'<div class="fl-track-ov-panel-hdr">'
                    f'{_panel_title_html("Portfolio health", tip=pt.HEALTH_SCORE_TOOLTIP)}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    _health_panel(
                        health,
                        p,
                        analyse_href=analyse_href,
                        show_score=False,
                        compact=True,
                        fill=True,
                    ),
                    unsafe_allow_html=True,
                )

        _r3_main, _r3_side = st.columns([_ov_main, _ov_side], gap="small")
        with _r3_main:
            st.markdown('<div class="fl-track-ov-r3-box" aria-hidden="true"></div>', unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown(
                    '<div class="fl-track-ov-panel-hdr">'
                    '<span class="fl-track-panel-title">Top movers</span></div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    _movers_section(best, worst, p, fmt_inr, perf_href=perf_tab_href),
                    unsafe_allow_html=True,
                )
        with _r3_side:
            st.markdown('<div class="fl-track-side-compact" aria-hidden="true"></div>', unsafe_allow_html=True)
            st.markdown('<div class="fl-track-ov-r3-box" aria-hidden="true"></div>', unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown(
                    '<div class="fl-track-ov-panel-hdr">'
                    '<span class="fl-track-panel-title">Risk &amp; concentration</span></div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    _risk_mini_cards(
                        metrics, overlap_lvl, p, analyse_href=analyse_href, compact=True
                    ),
                    unsafe_allow_html=True,
                )

    with tab_perf:
        st.markdown('<div id="fl-track-perf-tab"></div>', unsafe_allow_html=True)
        with st.container(border=True):
            period = st.radio(
                "Period", ["3M", "6M", "1Y", "All"],
                horizontal=True, key="fl_track_perf_period", label_visibility="collapsed",
            )
            curve_p = pt.filter_curve_by_period(curve, period)
            if curve_p is not None and not curve_p.empty:
                st.plotly_chart(
                    _plotly_dual_line(
                        curve_p.rename(columns={"value": "current_value"}).assign(invested_value=0),
                        p, height=300,
                    ),
                    use_container_width=True,
                    config={"displayModeBar": False},
                    key="fl_track_chart_perf_curve",
                )
            else:
                st.caption("Need more history for this period.")
        with st.container(border=True):
            st.markdown('<div class="fl-track-section-kicker">Returns by fund</div>', unsafe_allow_html=True)
            sorted_rows = sorted(fund_rows, key=lambda x: float(x.get("ret") or 0), reverse=True)
            if sorted_rows:
                names = [r["name"] for r in sorted_rows]
                rets = [float(r.get("ret") or 0) for r in sorted_rows]
                colors = [p["green"] if r >= 0 else p["red"] for r in rets]
                fig_bar = go.Figure(go.Bar(y=names, x=rets, orientation="h", marker=dict(color=colors)))
                fig_bar.update_layout(
                    height=max(200, len(names) * 28),
                    margin=dict(l=8, r=8, t=8, b=8),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(size=11, color=p["bd"]), xaxis_title="%",
                )
                st.plotly_chart(
                    fig_bar,
                    use_container_width=True,
                    config={"displayModeBar": False},
                    key="fl_track_chart_perf_bar",
                )

    with tab_hold:
        with st.container(border=True):
            h_f1, h_f2 = st.columns([3, 1])
            with h_f1:
                q = st.text_input(
                    "Search", key="fl_track_holdings_search",
                    placeholder="Search funds…", label_visibility="collapsed",
                )
            with h_f2:
                sort_key = st.selectbox(
                    "Sort", ["val", "gl", "ret"],
                    format_func=lambda k: {"val": "Value", "gl": "P&L ₹", "ret": "Return %"}[k],
                    key="fl_track_holdings_sort", label_visibility="collapsed",
                )
            ql = (q or "").strip().lower()
            filtered = [
                f for f in fund_rows
                if not ql or ql in f["name"].lower() or ql in f["acct"].lower()
            ]
            if sort_key == "val":
                filtered.sort(key=lambda x: float(x.get("val") or 0), reverse=True)
            elif sort_key == "gl":
                filtered.sort(key=lambda x: float(x.get("gl") or 0), reverse=True)
            else:
                filtered.sort(key=lambda x: float(x.get("ret") or 0), reverse=True)
            st.markdown(
                f'<div class="fl-track-hold-row" style="font-size:0.68rem;font-weight:700;color:{p["sb"]};'
                f'text-transform:uppercase;">'
                f'<span>Fund</span><span style="text-align:right">Invested</span>'
                f'<span style="text-align:right">Value</span><span style="text-align:right">P&amp;L</span>'
                f'<span style="text-align:right">Ret%</span></div>',
                unsafe_allow_html=True,
            )
            st.markdown(_holdings_rows_html(filtered, p, fmt_inr), unsafe_allow_html=True)

    with tab_ins:
        st.markdown('<div id="fl-track-insights-tab"></div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(_insights_panel(insights, p), unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(
                _health_panel(health, p, analyse_href=analyse_href, show_score=False),
                unsafe_allow_html=True,
            )
