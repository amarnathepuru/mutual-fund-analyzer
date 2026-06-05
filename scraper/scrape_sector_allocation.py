"""
Scrape sector allocation from ET Money portfolio pages when stock holdings table
is missing (sector-only / thematic / innovation cohort).

This scrapes the JS object `var getAssetAllocationData = {...}` and extracts:
  - mfLAHDTOList: list of {sId, astDt, astPer, ...}
  - mfSectorDTOMap: mapping of sId -> {sector: "...", ...}

We then pick the latest astDt (as-of date) and aggregate astPer by sId.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

import pandas as pd
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0",
}


def _extract_js_object(html: str, var_name: str) -> str:
    start = html.find(f"var {var_name} =")
    if start == -1:
        raise ValueError(f"JS var {var_name} not found")
    brace_start = html.find("{", start)
    if brace_start == -1:
        raise ValueError("Opening '{' not found")

    i = brace_start
    depth = 0
    in_str = False
    esc = False
    quote: str | None = None

    while i < len(html):
        ch = html[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif quote and ch == quote:
                in_str = False
                quote = None
        else:
            if ch in ('"', "'"):
                in_str = True
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return html[brace_start : i + 1]
        i += 1

    raise ValueError("JS object end not found")


def _norm_dt(x: Any) -> str:
    if isinstance(x, dict):
        return str(x.get("value") or x.get("date") or "")
    return str(x or "")


def scrape_sector_allocation_from_url(*, fund: dict) -> pd.DataFrame:
    """
    fund keys expected:
      - url
      - fund_name (ET fund name)
      - category (optional)
      - fund_house (optional)
      - scheme_id (ET scheme id)
    """

    url = str(fund["url"])
    html = requests.get(url, headers=HEADERS, timeout=45).text

    js_obj = _extract_js_object(html, "getAssetAllocationData")
    parsed = json.loads(js_obj)

    mf_sector_map: dict[str, dict] = parsed.get("mfSectorDTOMap") or {}
    lahs: list[dict] = parsed.get("mfLAHDTOList") or []

    if not mf_sector_map or not lahs:
        return pd.DataFrame()

    dts = [_norm_dt(rec.get("astDt")) for rec in lahs if _norm_dt(rec.get("astDt"))]
    if not dts:
        return pd.DataFrame()

    latest = max(dts)
    latest_rows = [rec for rec in lahs if _norm_dt(rec.get("astDt")) == latest]

    by_sid: dict[str, float] = {}
    for rec in latest_rows:
        sid = rec.get("sId")
        if sid is None:
            continue
        try:
            val = float(rec.get("astPer"))
        except Exception:
            continue
        sid_s = str(int(float(sid))) if isinstance(sid, (int, float, str)) else str(sid)
        by_sid[sid_s] = by_sid.get(sid_s, 0.0) + val

    scrape_date = datetime.now().strftime("%Y-%m-%d")
    rows: list[dict] = []
    for sid_s, pct in by_sid.items():
        sec = mf_sector_map.get(sid_s) or {}
        sector_lbl = sec.get("sector") or sec.get("displayName") or sec.get("name") or sid_s
        rows.append(
            {
                "scheme_id": int(fund["scheme_id"]),
                "fund_name": str(fund.get("fund_name") or "").strip(),
                "category": str(fund.get("category") or "Sectoral/Thematic"),
                "fund_house": str(fund.get("fund_house") or ""),
                "sector": str(sector_lbl).strip(),
                "allocation_percent": float(pct),
                "granularity": "sector",
                "source": "ETMoney",
                "scrape_date": scrape_date,
                "as_of_date": latest,
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    out["allocation_percent"] = pd.to_numeric(out["allocation_percent"], errors="coerce")
    out = out[out["allocation_percent"] > 0].copy()
    return out.sort_values(["allocation_percent"], ascending=False).reset_index(drop=True)

