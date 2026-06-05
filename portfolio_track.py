"""
NAV-based portfolio tracking: holdings metrics, XIRR, combined value curve.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

import portfolio_data as pf


def _parse_date(val) -> date | None:
    if val is None or val == "":
        return None
    if isinstance(val, date):
        return val
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return None


def _scheme_code(row) -> int | None:
    code = row.get("mf_scheme_code")
    if pd.isna(code):
        return None
    try:
        return int(float(code))
    except (TypeError, ValueError):
        return None


_NAV_SERIES_CACHE: dict[tuple[int, str], pd.DataFrame] = {}


def _trackable_scheme_codes(holdings: pd.DataFrame) -> list[int]:
    codes: list[int] = []
    seen: set[int] = set()
    if holdings is None or holdings.empty:
        return codes
    for _, h in holdings.iterrows():
        if not h.get("can_track"):
            continue
        code = _scheme_code(h)
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def prefetch_nav_histories(
    holdings: pd.DataFrame, *, end_date: date | None = None
) -> dict[int, pd.DataFrame]:
    """Load each scheme's NAV series once (avoids repeated MFAPI/db lookups)."""
    end = end_date or date.today()
    end_key = end.isoformat()
    nav_by_code: dict[int, pd.DataFrame] = {}
    for code in _trackable_scheme_codes(holdings):
        cache_key = (code, end_key)
        cached = _NAV_SERIES_CACHE.get(cache_key)
        if cached is None:
            cached = pf.get_nav_history(code, end_date=end)
            _NAV_SERIES_CACHE[cache_key] = cached
        nav_by_code[code] = cached
    return nav_by_code


def _nav_from_series(series: pd.DataFrame | None, on_date: date) -> float | None:
    if series is None or series.empty:
        return None
    ts = pd.Timestamp(on_date)
    sub = series[series["nav_date"] <= ts]
    if sub.empty:
        return None
    try:
        return float(sub.iloc[-1]["nav"])
    except (TypeError, ValueError):
        return None


def _portfolio_month_ends(
    holdings: pd.DataFrame, txns: pd.DataFrame, end_date: date
) -> pd.DatetimeIndex:
    start: date | None = None
    for _, h in holdings.iterrows():
        if not h.get("can_track"):
            continue
        for td, _ in cashflows_for_holding(h, txns):
            start = td if start is None else min(start, td)
    if start is None:
        return pd.DatetimeIndex([])
    month_ends = pd.date_range(pd.Timestamp(start), pd.Timestamp(end_date), freq="ME")
    if month_ends.empty:
        return pd.DatetimeIndex([pd.Timestamp(end_date)])
    return month_ends


def _txns_for_lot(txns: pd.DataFrame, lot_group_id: str) -> pd.DataFrame:
    if txns is None or txns.empty or not lot_group_id:
        return pd.DataFrame()
    if "lot_group_id" not in txns.columns:
        return pd.DataFrame()
    return txns[txns["lot_group_id"].astype(str) == str(lot_group_id)].copy()


def units_on_date(holding: pd.Series, txns: pd.DataFrame, on_date: date) -> float:
    code = _scheme_code(holding)
    lot = str(holding.get("lot_group_id") or "").strip()
    txs = _txns_for_lot(txns, lot)
    if not txs.empty:
        total = 0.0
        for _, tr in txs.iterrows():
            td = _parse_date(tr.get("invested_date"))
            if not td or td > on_date:
                continue
            tu = float(tr.get("units") or 0)
            if tu > 0:
                total += tu
                continue
            amt = float(tr.get("invested_amount") or 0)
            nav = float(tr.get("nav") or 0)
            if nav <= 0 and code:
                nav = pf.get_nav_on_or_before(code, td) or 0.0
            if nav > 0 and amt > 0:
                total += amt / nav
        return total

    inv = _parse_date(holding.get("invested_date"))
    if not inv or inv > on_date:
        return 0.0
    units = float(holding.get("units") or 0)
    if units > 0:
        return units
    amt = float(holding.get("invested_amount") or 0)
    nav = float(holding.get("nav") or 0)
    if nav <= 0 and code and inv:
        nav = pf.get_nav_on_or_before(code, inv) or 0.0
    if nav > 0 and amt > 0:
        return amt / nav
    return 0.0


def invested_date_display(holding: pd.Series, txns: pd.DataFrame) -> str:
    lot = str(holding.get("lot_group_id") or "").strip()
    txs = _txns_for_lot(txns, lot)
    if not txs.empty:
        dates = [_parse_date(tr.get("invested_date")) for _, tr in txs.iterrows()]
        dates = [d for d in dates if d]
        if not dates:
            return "—"
        if len(dates) == 1 or min(dates) == max(dates):
            return min(dates).isoformat()
        return f"{min(dates).isoformat()} … {max(dates).isoformat()}"
    inv = _parse_date(holding.get("invested_date"))
    return inv.isoformat() if inv else "—"


def invested_amount_for_holding(holding: pd.Series, txns: pd.DataFrame) -> float:
    lot = str(holding.get("lot_group_id") or "").strip()
    txs = _txns_for_lot(txns, lot)
    if not txs.empty:
        return float(
            pd.to_numeric(txs.get("invested_amount"), errors="coerce").fillna(0).sum()
        )
    return float(holding.get("invested_amount") or 0)


def cashflows_for_holding(
    holding: pd.Series, txns: pd.DataFrame
) -> list[tuple[date, float]]:
    """Outflows only (negative amounts)."""
    lot = str(holding.get("lot_group_id") or "").strip()
    txs = _txns_for_lot(txns, lot)
    flows: list[tuple[date, float]] = []
    if not txs.empty:
        for _, tr in txs.iterrows():
            td = _parse_date(tr.get("invested_date"))
            amt = float(tr.get("invested_amount") or 0)
            if td and amt > 0:
                flows.append((td, -amt))
        return flows
    td = _parse_date(holding.get("invested_date"))
    amt = float(holding.get("invested_amount") or 0)
    if td and amt > 0:
        flows.append((td, -amt))
    return flows


def holding_metrics(
    holding: pd.Series,
    txns: pd.DataFrame,
    *,
    display_name_fn=None,
    as_of_date: date | None = None,
) -> dict[str, Any] | None:
    if not holding.get("can_track"):
        return None
    code = _scheme_code(holding)
    if not code:
        return None

    as_of = as_of_date or date.today()
    invested = invested_amount_for_holding(holding, txns)
    inv = _parse_date(holding.get("invested_date"))
    purchase_nav = float(holding.get("nav") or 0)
    if purchase_nav <= 0 and inv:
        purchase_nav = pf.get_nav_on_or_before(code, inv) or 0.0

    units = units_on_date(holding, txns, as_of)
    if units <= 0 and purchase_nav > 0 and invested > 0:
        units = invested / purchase_nav
    elif units > 0 and invested > 0 and purchase_nav <= 0:
        purchase_nav = invested / units

    latest_nav, latest_date = pf.get_nav_on_or_before_with_date(code, as_of)
    current_val = units * latest_nav if latest_nav and units > 0 else None
    ret_pct = None
    if purchase_nav > 0 and latest_nav:
        ret_pct = (latest_nav / purchase_nav - 1.0) * 100.0

    gain = None
    if current_val is not None:
        gain = current_val - invested

    fund = str(holding.get("display_fund_name") or holding.get("fund_name") or "")
    if display_name_fn:
        fund = display_name_fn(fund, 56)

    lbl = str(holding.get("investment_label") or "").strip()
    fund_house = str(holding.get("fund_house") or "").strip()
    et_fund_name = str(holding.get("et_fund_name") or "").strip()
    scheme_category = ""
    if code:
        resolved = pf.resolve_mf_scheme_code(mf_scheme_code=code)
        if resolved:
            if not fund_house:
                fund_house = str(resolved.get("fund_house") or "").strip()
            if not et_fund_name:
                et_fund_name = str(resolved.get("et_fund_name") or "").strip()
            scheme_category = str(resolved.get("scheme_category") or "").strip()
    return {
        "mf_scheme_code": code,
        "fund_name": fund,
        "fund_house": fund_house or "—",
        "et_fund_name": et_fund_name,
        "scheme_category": scheme_category or "Other",
        "account_name": str(holding.get("account_name") or ""),
        "investment_label": lbl or "—",
        "invested_date": invested_date_display(holding, txns),
        "plan_type": str(holding.get("plan_type") or "Direct"),
        "option_type": str(holding.get("option_type") or "Growth"),
        "invested": invested,
        "units": round(units, 4) if units else None,
        "purchase_nav": round(purchase_nav, 4) if purchase_nav else None,
        "latest_nav": round(latest_nav, 4) if latest_nav else None,
        "nav_as_of": latest_date or "",
        "current_value": round(current_val, 2) if current_val is not None else None,
        "gain": round(gain, 2) if gain is not None else None,
        "return_pct": round(ret_pct, 2) if ret_pct is not None else None,
        "has_txns": not _txns_for_lot(txns, str(holding.get("lot_group_id") or "")).empty,
    }


def build_holdings_metrics(
    holdings: pd.DataFrame,
    txns: pd.DataFrame,
    *,
    display_name_fn=None,
    as_of_date: date | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if holdings is None or holdings.empty:
        return rows
    for _, h in holdings.iterrows():
        m = holding_metrics(
            h, txns, display_name_fn=display_name_fn, as_of_date=as_of_date
        )
        if m:
            rows.append(m)
    return rows


def portfolio_totals(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    invested = sum(float(m["invested"] or 0) for m in metrics)
    current = sum(
        float(m["current_value"] or 0) for m in metrics if m.get("current_value") is not None
    )
    gain = current - invested if metrics else 0.0
    ret_pct = (gain / invested * 100.0) if invested > 0 else None
    latest_dates = [str(m.get("nav_as_of") or "") for m in metrics if m.get("nav_as_of")]
    nav_as_of = max(latest_dates) if latest_dates else ""
    return {
        "invested": invested,
        "current_value": current,
        "gain": gain,
        "return_pct": round(ret_pct, 2) if ret_pct is not None else None,
        "nav_as_of": nav_as_of,
        "n_holdings": len(metrics),
    }


def compute_xirr(cashflows: list[tuple[date, float]], guess: float = 0.1) -> float | None:
    """Annualized return (percent). Negative = invested, positive = terminal value."""
    if len(cashflows) < 2:
        return None
    if not any(a < 0 for _, a in cashflows) or not any(a > 0 for _, a in cashflows):
        return None
    d0 = min(d for d, _ in cashflows)

    def npv(rate: float) -> float:
        return sum(
            a / (1.0 + rate) ** ((d - d0).days / 365.25)
            for d, a in cashflows
        )

    rate = guess
    for _ in range(80):
        f0 = npv(rate)
        eps = 1e-6
        f1 = npv(rate + eps)
        deriv = (f1 - f0) / eps
        if abs(deriv) < 1e-12:
            break
        step = f0 / deriv
        rate -= step
        if abs(step) < 1e-9:
            break
        if rate <= -0.999:
            rate = -0.999
    try:
        if abs(npv(rate)) > 0.05:
            return None
        return rate * 100.0
    except (OverflowError, ZeroDivisionError):
        return None


def portfolio_xirr(
    holdings: pd.DataFrame,
    txns: pd.DataFrame,
    terminal_value: float,
    terminal_date: date | None = None,
) -> float | None:
    flows: list[tuple[date, float]] = []
    if holdings is None or holdings.empty:
        return None
    for _, h in holdings.iterrows():
        if not h.get("can_track"):
            continue
        flows.extend(cashflows_for_holding(h, txns))
    if not flows or terminal_value <= 0:
        return None
    td = terminal_date or date.today()
    flows.append((td, terminal_value))
    return compute_xirr(flows)


def portfolio_value_curve(
    holdings: pd.DataFrame,
    txns: pd.DataFrame,
    *,
    end_date: date | None = None,
    nav_by_code: dict[int, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Month-end combined portfolio value (trackable holdings only)."""
    if holdings is None or holdings.empty:
        return pd.DataFrame(columns=["date", "value"])

    end = end_date or date.today()
    month_ends = _portfolio_month_ends(holdings, txns, end)
    if month_ends.empty:
        return pd.DataFrame(columns=["date", "value"])

    if nav_by_code is None:
        nav_by_code = prefetch_nav_histories(holdings, end_date=end)

    values: list[float] = []
    dates_out: list[date] = []
    for ts in month_ends:
        d = ts.date()
        total = 0.0
        for _, h in holdings.iterrows():
            if not h.get("can_track"):
                continue
            code = _scheme_code(h)
            if not code:
                continue
            u = units_on_date(h, txns, d)
            if u <= 0:
                continue
            nav = _nav_from_series(nav_by_code.get(code), d)
            if nav:
                total += u * nav
        dates_out.append(d)
        values.append(total)

    return pd.DataFrame({"date": dates_out, "value": values})


def allocation_pie_data(
    metrics: list[dict[str, Any]], *, by: str = "invested"
) -> pd.DataFrame:
    key = "current_value" if by == "current" else "invested"
    rows = [
        {"fund_name": m["fund_name"], "amount": float(m.get(key) or 0)}
        for m in metrics
        if float(m.get(key) or 0) > 0
    ]
    return pd.DataFrame(rows)


def metrics_to_fund_rows(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize holding metrics for Track dashboard UI."""
    rows: list[dict[str, Any]] = []
    for m in metrics:
        inv = float(m.get("invested") or 0)
        val = float(m.get("current_value") or 0) if m.get("current_value") is not None else 0.0
        gl = float(m.get("gain") or 0) if m.get("gain") is not None else (val - inv)
        ret = float(m.get("return_pct") or 0) if m.get("return_pct") is not None else 0.0
        rows.append(
            {
                "name": str(m.get("fund_name") or ""),
                "acct": str(m.get("account_name") or ""),
                "label": str(m.get("investment_label") or "—"),
                "cat": str(m.get("plan_type") or "—"),
                "inv": inv,
                "val": val,
                "gl": gl,
                "ret": ret,
                "raw": m,
            }
        )
    return rows


def allocation_breakdown(
    metrics: list[dict[str, Any]], key: str
) -> list[tuple[str, float]]:
    totals: dict[str, float] = {}
    for m in metrics:
        k = str(m.get(key) or "—").strip() or "—"
        totals[k] = totals.get(k, 0.0) + float(m.get("current_value") or 0)
    return sorted(totals.items(), key=lambda x: -x[1])


def top_movers(
    metrics: list[dict[str, Any]], n: int = 3
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Best = highest return %; worst = lowest return % (no overlap with best)."""
    rows = metrics_to_fund_rows(metrics)
    if not rows:
        return [], []

    def _rank_key(r: dict[str, Any]) -> tuple[float, float]:
        return (float(r.get("ret") or 0), float(r.get("gl") or 0))

    def _fund_id(r: dict[str, Any]) -> tuple[str, str]:
        return (str(r.get("name") or ""), str(r.get("acct") or ""))

    ranked_desc = sorted(rows, key=_rank_key, reverse=True)
    ranked_asc = sorted(rows, key=_rank_key)

    if len(rows) == 1:
        return ranked_desc[:1], []

    best = ranked_desc[:n]
    best_ids = {_fund_id(r) for r in best}
    worst = [r for r in ranked_asc if _fund_id(r) not in best_ids][:n]

    if not worst:
        mid = max(1, len(ranked_desc) // 2)
        best = ranked_desc[:mid]
        best_ids = {_fund_id(r) for r in best}
        worst = [r for r in ranked_asc if _fund_id(r) not in best_ids][:n]

    return best[:n], worst[:n]


def filter_curve_by_period(curve: pd.DataFrame, period: str) -> pd.DataFrame:
    if curve is None or curve.empty:
        return pd.DataFrame(columns=["date", "value"])
    period = str(period or "All").strip()
    out = curve.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out = out.dropna(subset=["date", "value"]).sort_values("date")
    if out.empty:
        return out
    if period == "All":
        return out.reset_index(drop=True)
    months = {"1M": 1, "3M": 3, "6M": 6, "1Y": 12, "3Y": 36}.get(period, 0)
    if not months:
        return out.reset_index(drop=True)
    end = out["date"].max()
    if pd.isna(end):
        return out.reset_index(drop=True)
    start = pd.Timestamp(end) - pd.DateOffset(months=months)
    filtered = out[out["date"] >= start].copy()
    return filtered.reset_index(drop=True)


def portfolio_value_on_date(
    holdings: pd.DataFrame,
    txns: pd.DataFrame,
    on_date: date,
    *,
    nav_by_code: dict[int, pd.DataFrame] | None = None,
) -> float:
    if holdings is None or holdings.empty:
        return 0.0
    if nav_by_code is None:
        nav_by_code = prefetch_nav_histories(holdings, end_date=on_date)
    total = 0.0
    for _, h in holdings.iterrows():
        if not h.get("can_track"):
            continue
        code = _scheme_code(h)
        if not code:
            continue
        u = units_on_date(h, txns, on_date)
        if u <= 0:
            continue
        nav = _nav_from_series(nav_by_code.get(code), on_date)
        if nav:
            total += u * nav
    return total


def cumulative_invested_on_date(
    holdings: pd.DataFrame, txns: pd.DataFrame, on_date: date
) -> float:
    total = 0.0
    if holdings is None or holdings.empty:
        return total
    for _, h in holdings.iterrows():
        if not h.get("can_track"):
            continue
        for td, amt in cashflows_for_holding(h, txns):
            if td <= on_date and amt < 0:
                total += -amt
    return total


def portfolio_earliest_investment_date(
    holdings: pd.DataFrame, txns: pd.DataFrame
) -> date | None:
    start: date | None = None
    if holdings is None or holdings.empty:
        return None
    for _, h in holdings.iterrows():
        if not h.get("can_track"):
            continue
        for td, _ in cashflows_for_holding(h, txns):
            start = td if start is None else min(start, td)
    return start


def portfolio_age_years(holdings: pd.DataFrame, txns: pd.DataFrame, *, end: date | None = None) -> float:
    start = portfolio_earliest_investment_date(holdings, txns)
    if not start:
        return 0.0
    end_d = end or date.today()
    return max(0.0, (end_d - start).days / 365.25)


def portfolio_invested_curve(
    holdings: pd.DataFrame,
    txns: pd.DataFrame,
    *,
    end_date: date | None = None,
    value_curve: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if value_curve is None:
        value_curve = portfolio_value_curve(holdings, txns, end_date=end_date)
    if value_curve.empty:
        return pd.DataFrame(columns=["date", "invested_value"])
    rows: list[dict] = []
    for _, r in value_curve.iterrows():
        d = _parse_date(r["date"])
        if not d:
            continue
        rows.append({"date": d, "invested_value": cumulative_invested_on_date(holdings, txns, d)})
    return pd.DataFrame(rows)


def portfolio_dual_curves(
    holdings: pd.DataFrame,
    txns: pd.DataFrame,
    *,
    end_date: date | None = None,
    value_curve: pd.DataFrame | None = None,
    nav_by_code: dict[int, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    end = end_date or date.today()
    if nav_by_code is None:
        nav_by_code = prefetch_nav_histories(holdings, end_date=end)
    if value_curve is None:
        value_curve = portfolio_value_curve(
            holdings, txns, end_date=end, nav_by_code=nav_by_code
        )
    inv = portfolio_invested_curve(holdings, txns, end_date=end, value_curve=value_curve)
    if value_curve.empty:
        return pd.DataFrame(columns=["date", "current_value", "invested_value"])
    out = value_curve.rename(columns={"value": "current_value"})
    if not inv.empty:
        out = out.merge(inv, on="date", how="left")
    else:
        out["invested_value"] = 0.0
    out["invested_value"] = pd.to_numeric(out["invested_value"], errors="coerce").fillna(0)
    return out


def _simple_return_pct(current: float, prior: float) -> float | None:
    if prior <= 0:
        return None
    return (current / prior - 1.0) * 100.0


def _cagr_pct(begin: float, end: float, years: float) -> float | None:
    if begin <= 0 or end <= 0 or years <= 0:
        return None
    return ((end / begin) ** (1.0 / years) - 1.0) * 100.0


def performance_snapshot(
    holdings: pd.DataFrame,
    txns: pd.DataFrame,
    curve: pd.DataFrame,
    *,
    as_of: date | None = None,
    nav_by_code: dict[int, pd.DataFrame] | None = None,
) -> dict[str, float | None]:
    """1D–1Y simple returns; 3Y CAGR from month-end curve."""
    end = as_of or date.today()
    if nav_by_code is None:
        nav_by_code = prefetch_nav_histories(holdings, end_date=end)
    cur_val = portfolio_value_on_date(holdings, txns, end, nav_by_code=nav_by_code)
    out: dict[str, float | None] = {}

    for label, days in (("1D", 1), ("1W", 7)):
        prior_d = end - timedelta(days=days)
        prior_val = portfolio_value_on_date(
            holdings, txns, prior_d, nav_by_code=nav_by_code
        )
        out[label] = round(_simple_return_pct(cur_val, prior_val) or 0.0, 2) if prior_val > 0 else None

    if curve is not None and not curve.empty:
        cdf = curve.copy()
        cdf["date"] = pd.to_datetime(cdf["date"], errors="coerce")
        cdf["value"] = pd.to_numeric(cdf["value"], errors="coerce")
        cdf = cdf.dropna().sort_values("date")
        end_ts = pd.Timestamp(end)
        for label, months in (("1M", 1), ("3M", 3), ("6M", 6), ("1Y", 12)):
            start_ts = end_ts - pd.DateOffset(months=months)
            prior_rows = cdf[cdf["date"] <= start_ts]
            if prior_rows.empty:
                prior_rows = cdf.head(1)
            begin = float(prior_rows.iloc[-1]["value"])
            out[label] = round(_simple_return_pct(cur_val, begin) or 0.0, 2) if begin > 0 else None

        three_y_start = end_ts - pd.DateOffset(months=36)
        prior_3y = cdf[cdf["date"] <= three_y_start]
        if not prior_3y.empty:
            begin = float(prior_3y.iloc[-1]["value"])
            years = max(1.0, (end_ts - prior_3y.iloc[-1]["date"]).days / 365.25)
            cagr = _cagr_pct(begin, cur_val, years)
            out["3Y CAGR"] = round(cagr, 2) if cagr is not None else None
        else:
            out["3Y CAGR"] = None
    else:
        for label in ("1M", "3M", "6M", "1Y", "3Y CAGR"):
            out[label] = None
    return out


def portfolio_cagr(
    holdings: pd.DataFrame,
    txns: pd.DataFrame,
    *,
    as_of: date | None = None,
    nav_by_code: dict[int, pd.DataFrame] | None = None,
) -> float | None:
    end = as_of or date.today()
    start = portfolio_earliest_investment_date(holdings, txns)
    if not start or start >= end:
        return None
    if nav_by_code is None:
        nav_by_code = prefetch_nav_histories(holdings, end_date=end)
    begin = portfolio_value_on_date(holdings, txns, start, nav_by_code=nav_by_code)
    end_val = portfolio_value_on_date(holdings, txns, end, nav_by_code=nav_by_code)
    years = (end - start).days / 365.25
    return _cagr_pct(begin, end_val, years)


def _category_label(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return "Other"
    for token in (
        "Large Cap",
        "Mid Cap",
        "Small Cap",
        "Flexi Cap",
        "Multi Cap",
        "Hybrid",
        "International",
        "Debt",
        "Liquid",
        "ELSS",
    ):
        if token.lower() in s.lower():
            return token
    if "index" in s.lower():
        return "Index"
    return s.split(" - ")[0].split(":")[0][:28] or "Other"


def category_allocation(metrics: list[dict[str, Any]]) -> list[tuple[str, float]]:
    totals: dict[str, float] = {}
    for m in metrics:
        cat = _category_label(str(m.get("scheme_category") or ""))
        totals[cat] = totals.get(cat, 0.0) + float(m.get("current_value") or 0)
    return sorted(totals.items(), key=lambda x: -x[1])


def concentration_pct(metrics: list[dict[str, Any]], n: int = 1) -> float:
    vals = sorted(
        (float(m.get("current_value") or 0) for m in metrics),
        reverse=True,
    )
    total = sum(vals)
    if total <= 0:
        return 0.0
    return sum(vals[:n]) / total * 100.0


def _rating_from_pct(pct: float, *, good_max: float, med_max: float) -> str:
    if pct <= good_max:
        return "Good"
    if pct <= med_max:
        return "Medium"
    return "Poor"


def weighted_expense_ratio(
    metrics: list[dict[str, Any]],
    expense_map: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Value-weighted expense ratio for ET-mapped holdings (fund_master_auto)."""
    emap = expense_map if expense_map is not None else pf.et_expense_ratio_by_fund_name()
    weighted = 0.0
    mapped_val = 0.0
    n_mapped = 0
    for m in metrics:
        et = str(m.get("et_fund_name") or "").strip()
        val = float(m.get("current_value") or 0)
        if not et or val <= 0:
            continue
        er = emap.get(et)
        if er is None:
            continue
        weighted += float(er) * val
        mapped_val += val
        n_mapped += 1
    if mapped_val <= 0 or n_mapped == 0:
        return {
            "pct": None,
            "rating": "Medium",
            "detail": "No ET-mapped funds with expense data",
            "mapped_share_pct": 0.0,
        }
    pct = weighted / mapped_val
    total = sum(float(x.get("current_value") or 0) for x in metrics)
    share = mapped_val / total * 100.0 if total > 0 else 0.0
    rating = "Good" if pct <= 1.05 else "Medium" if pct <= 1.35 else "Poor"
    return {
        "pct": round(pct, 2),
        "rating": rating,
        "detail": f"{pct:.2f}% weighted avg (ET-mapped holdings)",
        "mapped_share_pct": round(share, 1),
    }


HEALTH_SCORE_TOOLTIP = (
    "Portfolio health score (0–100) combines: diversification (22%), "
    "concentration risk (22%), expense ratio (12%), fund overlap (18%), "
    "liquidity (10%), and international exposure (16%). "
    "75+ is Good, 55–74 is Medium, below 55 needs attention."
)

XIRR_TOOLTIP = (
    "Extended Internal Rate of Return — your annualised return after accounting for "
    "when you invested. Uses purchase dates from Manage (including split transactions "
    "if added). Shown when the portfolio is at least one year old."
)

PORTFOLIO_RETURN_TOOLTIP = (
    "Absolute return from total invested to current value, using purchase NAV vs "
    "latest NAV per holding. Switches to XIRR (annualised) once the portfolio is "
    "at least one year old."
)

PERF_SNAPSHOT_TOOLTIP = (
    "Portfolio-level returns for each period. 1D–1Y are simple returns from the "
    "value curve; 3Y CAGR is compound annual growth over three years."
)


def portfolio_health(
    metrics: list[dict[str, Any]],
    *,
    overlap_label: str = "Medium",
    expense_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    n = len(metrics)
    top1 = concentration_pct(metrics, 1)
    top3 = concentration_pct(metrics, 3)
    cats = category_allocation(metrics)
    intl_pct = sum(v for k, v in cats if "international" in k.lower())
    total = sum(float(m.get("current_value") or 0) for m in metrics)

    diversification = (
        "Good" if n >= 5 and top1 < 30 else "Medium" if n >= 3 and top1 < 45 else "Poor"
    )
    concentration = (
        "Good" if top3 < 55 else "Medium" if top3 < 75 else "Poor"
    )
    intl = (
        "Good" if total > 0 and intl_pct / total >= 0.08
        else "Medium" if total > 0 and intl_pct / total >= 0.03
        else "Poor"
    )
    _exp = expense_info or weighted_expense_ratio(metrics)
    expense = str(_exp.get("rating") or "Medium")
    liquidity = "Good"
    overlap = overlap_label

    dim_scores = {"Good": 100, "Medium": 62, "Poor": 28, "High": 28, "Low": 100}
    weights = {
        "diversification": 0.22,
        "concentration": 0.22,
        "expense": 0.12,
        "overlap": 0.18,
        "liquidity": 0.10,
        "international": 0.16,
    }
    dims = {
        "diversification": diversification,
        "concentration": concentration,
        "expense_ratio": expense,
        "fund_overlap": overlap,
        "liquidity": liquidity,
        "international": intl,
    }
    _dim_keys = {
        "diversification": "diversification",
        "concentration": "concentration",
        "expense": "expense_ratio",
        "overlap": "fund_overlap",
        "liquidity": "liquidity",
        "international": "international",
    }
    score = round(
        sum(
            dim_scores[dims[_dim_keys[k]]] * weights[k]
            for k in weights
        ),
    )
    status = "Good" if score >= 75 else "Medium" if score >= 55 else "Needs attention"
    return {
        "score": score,
        "status": status,
        "dimensions": dims,
        "expense_info": _exp,
        "score_tooltip": HEALTH_SCORE_TOOLTIP,
    }


def estimate_overlap_level(metrics: list[dict[str, Any]]) -> str:
    """Heuristic overlap from category concentration (full overlap matrix on Analyse)."""
    cats = [str(m.get("scheme_category") or "") for m in metrics]
    if len(metrics) < 2:
        return "Low"
    from collections import Counter

    top_cat = Counter(cats).most_common(1)
    if not top_cat:
        return "Medium"
    share = top_cat[0][1] / len(metrics)
    if share >= 0.6 and len(metrics) >= 4:
        return "High"
    if share >= 0.45:
        return "Medium"
    return "Low"


def generate_insights(
    metrics: list[dict[str, Any]],
    totals: dict[str, Any],
    xirr_pct: float | None,
    perf: dict[str, float | None],
    health: dict[str, Any],
) -> list[str]:
    insights: list[str] = []
    total = float(totals.get("current_value") or 0)
    if total <= 0 or not metrics:
        return ["Add trackable holdings to see portfolio insights."]

    by_house = allocation_breakdown(metrics, "fund_house")
    if by_house:
        top_h, top_v = by_house[0]
        pct = top_v / total * 100
        if pct >= 35:
            insights.append(
                f"Your portfolio is heavily concentrated in **{top_h}** ({pct:.0f}% of value)."
            )

    cats = category_allocation(metrics)
    if cats:
        top_c, top_cv = cats[0]
        cpct = top_cv / total * 100
        if cpct >= 50:
            insights.append(
                f"**{top_c}** funds contribute {cpct:.0f}% of your portfolio value."
            )

    intl = health.get("dimensions", {}).get("international")
    if intl == "Poor":
        insights.append("Your portfolio currently has **no meaningful international exposure**.")

    top3_gain = sorted(metrics, key=lambda m: float(m.get("gain") or 0), reverse=True)[:3]
    gain_sum = sum(float(m.get("gain") or 0) for m in metrics if float(m.get("gain") or 0) > 0)
    top3_gain_sum = sum(float(m.get("gain") or 0) for m in top3_gain if float(m.get("gain") or 0) > 0)
    if gain_sum > 0 and top3_gain_sum / gain_sum >= 0.7:
        insights.append(
            f"Top **3 funds** contributed **{top3_gain_sum / gain_sum * 100:.0f}%** of total gains."
        )

    if xirr_pct is not None and perf.get("3M") is not None:
        insights.append(
            f"Portfolio XIRR is **{xirr_pct:+.2f}%**. "
            f"3-month return is **{perf['3M']:+.2f}%**."
        )
    elif xirr_pct is not None:
        insights.append(f"Portfolio XIRR is **{xirr_pct:+.2f}%** (annualised).")

    overlap = health.get("dimensions", {}).get("fund_overlap", "Medium")
    if overlap == "High":
        insights.append(
            "Holdings show **high category overlap** — consider diversifying across styles."
        )

    return insights[:5]
