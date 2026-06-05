"""
MFAPI portfolio universe + ET holdings bridge for Manage / Track / X-ray.

Single portfolio upload validated against MFAPI; holdings analyse uses ET names.
"""
from __future__ import annotations

import difflib
import json
import re
import sqlite3
import sys
import urllib.request
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import pandas as pd

_SCRIPTS = Path(__file__).resolve().parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from mfapi_scheme_name import (  # noqa: E402
    extract_fund_name_base,
    format_display_fund_name,
    parse_scheme_name,
)

ROOT = Path(__file__).resolve().parent
MF_UNIVERSE_RAW = ROOT / "data" / "raw" / "mfapi" / "nav_universe_schemes.csv"
MF_UNIVERSE_PROCESSED = ROOT / "data" / "processed" / "nav_universe_schemes.csv"
MF_UNIVERSE_PATHS = (MF_UNIVERSE_PROCESSED, MF_UNIVERSE_RAW)
MF_UNIVERSE = MF_UNIVERSE_PROCESSED
SCHEME_MAP = ROOT / "data" / "fund_scheme_map.csv"
ET_MASTER = ROOT / "data" / "fund_master_auto.csv"
NAV_DB = ROOT / "data" / "nav" / "nav.db"
NAV_LATEST_CSV = ROOT / "data" / "processed" / "nav_latest.csv"
HOLDINGS_NORM = ROOT / "data" / "processed" / "normalized_holdings.csv"
SECTOR_ALLOC = ROOT / "data" / "processed" / "fund_sector_allocation.csv"
MFAPI_DETAIL_URL = "https://api.mfapi.in/mf/{code}"
MFAPI_USER_AGENT = "FundLens/1.0 (mutual-fund-analyzer; track)"
NAV_MIN_HISTORY_DATE = date(2015, 1, 1)

_LABEL_CODE_RE = re.compile(r"^(\d+)\s*\|")


def mf_universe_path() -> Path | None:
    for path in MF_UNIVERSE_PATHS:
        if path.is_file():
            return path
    return None


def nav_data_status() -> dict[str, str]:
    """Which NAV source is available (local db, cloud CSV, or none)."""
    if NAV_DB.is_file():
        return {"source": "nav_db", "label": "local NAV database"}
    if NAV_LATEST_CSV.is_file():
        return {"source": "nav_latest_csv", "label": "cloud NAV snapshot"}
    return {"source": "none", "label": "no NAV data"}


def _parse_nav_date(raw: str) -> date | None:
    raw = str(raw or "").strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    try:
        return pd.Timestamp(raw).date()
    except Exception:
        return None


@lru_cache(maxsize=1)
def _nav_latest_table() -> dict[int, tuple[float, str]]:
    if not NAV_LATEST_CSV.is_file():
        return {}
    df = pd.read_csv(NAV_LATEST_CSV)
    if df.empty:
        return {}
    out: dict[int, tuple[float, str]] = {}
    for _, row in df.iterrows():
        try:
            code = int(row["mf_scheme_code"])
            nav = float(row["nav"])
            nd = str(row.get("nav_date") or "")[:10]
        except (TypeError, ValueError, KeyError):
            continue
        if nd and nav > 0:
            out[code] = (nav, nd)
    return out


@lru_cache(maxsize=256)
def _mfapi_nav_history(mf_scheme_code: int) -> tuple[tuple[str, float], ...]:
    """Fetch full NAV history from MFAPI (cached). Used when nav.db is absent."""
    url = MFAPI_DETAIL_URL.format(code=int(mf_scheme_code))
    req = urllib.request.Request(url, headers={"User-Agent": MFAPI_USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return ()
    data = body.get("data") or []
    if not isinstance(data, list):
        return ()
    rows: list[tuple[str, float]] = []
    for item in data:
        if isinstance(item, dict):
            d_raw = item.get("date")
            nav_raw = item.get("nav")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            d_raw, nav_raw = item[0], item[1]
        else:
            continue
        d = _parse_nav_date(str(d_raw))
        if d is None or d < NAV_MIN_HISTORY_DATE:
            continue
        try:
            rows.append((d.isoformat(), float(nav_raw)))
        except (TypeError, ValueError):
            continue
    rows.sort(key=lambda x: x[0])
    return tuple(rows)


def _nav_from_mfapi_on_or_before(mf_scheme_code: int, on_date) -> tuple[float | None, str | None]:
    try:
        target = pd.Timestamp(on_date).date()
    except Exception:
        return None, None
    hist = _mfapi_nav_history(int(mf_scheme_code))
    if not hist:
        return None, None
    best: tuple[float, str] | None = None
    for nd, nav in hist:
        d = _parse_nav_date(nd)
        if d is None or d > target:
            continue
        best = (nav, nd)
    return best if best else (None, None)


def _nav_from_latest_csv_on_or_before(
    mf_scheme_code: int, on_date
) -> tuple[float | None, str | None]:
    try:
        target = pd.Timestamp(on_date).date()
    except Exception:
        return None, None
    hit = _nav_latest_table().get(int(mf_scheme_code))
    if not hit:
        return None, None
    nav, nd = hit
    d = _parse_nav_date(nd)
    if d is None or d > target:
        return None, None
    return nav, nd


def scheme_display_fields(
    scheme_name_raw: str = "", fund_name_base: str = ""
) -> dict[str, str]:
    """Derive clean display name, plan, and option (Growth/IDCW/…) from MFAPI names."""
    raw = str(scheme_name_raw or "").strip()
    base_csv = str(fund_name_base or "").strip()
    source = raw or base_csv
    parsed = parse_scheme_name(source) if source else {}
    base = extract_fund_name_base(source) if source else ""
    if not base:
        base = str(parsed.get("fund_name_base") or "").strip()
        base = extract_fund_name_base(base) or base
    display = format_display_fund_name(base or source)
    plan = str(parsed.get("plan_type") or "").strip() or "Direct"
    option = str(parsed.get("option_type") or "").strip() or "Growth"
    return {
        "fund_name_base": base or display,
        "display_fund_name": display,
        "plan_type": plan,
        "option_type": option,
    }


def normalize_portfolio_fund_fields(
    fund_name: str, plan_type: str = "", option_type: str = ""
) -> tuple[str, str, str]:
    """Strip plan/option from fund_name; return (display_name, plan, option)."""
    fields = scheme_display_fields(fund_name)
    plan = str(plan_type or "").strip() or fields["plan_type"]
    option = str(option_type or "").strip() or fields["option_type"]
    if plan.lower() in ("direct", "dir", "d"):
        plan = "Direct"
    elif plan.lower() in ("regular", "reg", "r"):
        plan = "Regular"
    else:
        plan = fields["plan_type"]
    if not option:
        option = fields["option_type"]
    return fields["display_fund_name"], plan, option


@lru_cache(maxsize=1)
def _holdings_fund_names() -> frozenset[str]:
    if not HOLDINGS_NORM.is_file():
        return frozenset()
    df = pd.read_csv(HOLDINGS_NORM, usecols=["fund_name"])
    return frozenset(df["fund_name"].dropna().astype(str).str.strip())


@lru_cache(maxsize=1)
def _sector_alloc_fund_names() -> frozenset[str]:
    if not SECTOR_ALLOC.is_file():
        return frozenset()
    df = pd.read_csv(SECTOR_ALLOC, usecols=["fund_name"])
    return frozenset(df["fund_name"].dropna().astype(str).str.strip())


def et_analyse_tier(et_fund_name: str) -> str:
    """stock | sector_only | none from ET name vs holdings / sector sidecars."""
    et = str(et_fund_name or "").strip()
    if not et:
        return "none"
    hold = _holdings_fund_names()
    sector = _sector_alloc_fund_names()
    if et in hold:
        return "stock"
    if et in sector:
        return "sector_only"
    return "none"


@lru_cache(maxsize=1)
def _scheme_map_by_code() -> dict[int, dict]:
    if not SCHEME_MAP.is_file():
        return {}
    sm = pd.read_csv(SCHEME_MAP)
    out: dict[int, dict] = {}
    for _, r in sm.iterrows():
        code = r.get("mf_scheme_code")
        if pd.isna(code):
            continue
        out[int(float(code))] = {
            "scheme_id": int(r["scheme_id"]),
            "et_fund_name": str(r.get("et_fund_name") or "").strip(),
        }
    return out


@lru_cache(maxsize=1)
def load_mfapi_universe() -> pd.DataFrame:
    """881-scheme NAV universe with picker labels and capability flags."""
    path = mf_universe_path()
    if path is None:
        return pd.DataFrame()
    mf = pd.read_csv(path)
    hold = _holdings_fund_names()
    sector = _sector_alloc_fund_names()
    smap = _scheme_map_by_code()

    rows: list[dict] = []
    for _, r in mf.iterrows():
        code = int(r["mf_scheme_code"])
        raw = str(r.get("scheme_name_raw") or "").strip()
        base = str(r.get("fund_name_base") or "").strip()
        fields = scheme_display_fields(raw, base)
        display = fields["display_fund_name"]
        map_row = smap.get(code, {})
        et_name = map_row.get("et_fund_name", "")
        tier = et_analyse_tier(et_name) if et_name else "none"
        has_stock = tier == "stock"
        has_sector = tier == "sector_only"
        if has_stock:
            badge = "Analyse+Track"
        elif has_sector:
            badge = "Sector+Track"
        else:
            badge = "Track only"
        label = f"{code} | {badge} | {display[:72]}"
        rows.append(
            {
                "mf_scheme_code": code,
                "scheme_name_raw": raw,
                "fund_name_base": fields["fund_name_base"],
                "display_fund_name": display,
                "mfapi_scheme_name": display,
                "plan_type": fields["plan_type"],
                "option_type": fields["option_type"],
                "et_fund_name": et_name,
                "fund_house": str(r.get("fund_house") or ""),
                "scheme_category": str(r.get("scheme_category") or ""),
                "picker_label": label,
                "has_et_holdings": has_stock,
                "has_sector_alloc": has_sector,
                "data_tier": tier,
                "can_analyse": has_stock,
                "can_analyse_sector": has_sector,
                "can_track": True,
            }
        )
    return pd.DataFrame(rows)


def mfapi_picker_labels() -> list[str]:
    u = load_mfapi_universe()
    if u.empty:
        return []
    return u["picker_label"].tolist()


def parse_picker_label(label: str) -> int | None:
    if not label:
        return None
    m = _LABEL_CODE_RE.match(str(label).strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def resolve_mf_scheme_code(
    *,
    mf_scheme_code: int | None = None,
    picker_label: str | None = None,
    fund_name: str | None = None,
) -> dict | None:
    """Resolve to capability dict; None if not in MFAPI universe."""
    u = load_mfapi_universe()
    if u.empty:
        return None
    code = mf_scheme_code
    if code is None and picker_label:
        code = parse_picker_label(picker_label)
    if code is not None:
        hit = u[u["mf_scheme_code"].astype(int) == int(code)]
        if not hit.empty:
            return hit.iloc[0].to_dict()
    if fund_name:
        fn = str(fund_name).strip()
        if not fn:
            return None
        fn_display = format_display_fund_name(fn)
        for col in (
            "display_fund_name",
            "mfapi_scheme_name",
            "fund_name_base",
            "scheme_name_raw",
            "picker_label",
            "et_fund_name",
        ):
            if col not in u.columns:
                continue
            series = u[col].astype(str)
            hit = u[series.str.lower() == fn.lower()]
            if hit.empty and fn_display:
                hit = u[series.str.lower() == fn_display.lower()]
            if not hit.empty:
                return hit.iloc[0].to_dict()
        hit = u[u["picker_label"].astype(str).str.contains(fn, case=False, na=False)]
        if len(hit) == 1:
            return hit.iloc[0].to_dict()
    return None


def fuzzy_match_mfapi(name: str, n: int = 8, cutoff: float = 0.35) -> list[str]:
    labels = mfapi_picker_labels()
    if not labels:
        return []
    close = difflib.get_close_matches(name, labels, n=n, cutoff=cutoff)
    rest = [lab for lab in labels if lab not in close]
    return close + rest[: max(0, n - len(close))]


def holdings_join_name(row: pd.Series) -> str:
    """ET fund_name for holdings CSV join."""
    et = str(row.get("et_fund_name") or "").strip()
    if et:
        return et
    return str(row.get("fund_name") or "").strip()


def enrich_portfolio_row(row: pd.Series) -> pd.Series:
    """Add mf_scheme_code, et_fund_name, flags from MFAPI resolution."""
    out = row.copy()
    code = row.get("mf_scheme_code")
    resolved = None
    if pd.notna(code) and str(code).strip():
        try:
            resolved = resolve_mf_scheme_code(mf_scheme_code=int(float(code)))
        except (TypeError, ValueError):
            resolved = None
    if resolved is None:
        resolved = resolve_mf_scheme_code(fund_name=str(row.get("fund_name") or ""))
    if resolved:
        out["mf_scheme_code"] = int(resolved["mf_scheme_code"])
        disp = str(
            resolved.get("display_fund_name") or resolved.get("mfapi_scheme_name") or ""
        )
        out["display_fund_name"] = disp
        out["fund_name"] = disp
        out["plan_type"] = str(resolved.get("plan_type") or out.get("plan_type") or "Direct")
        out["option_type"] = str(
            resolved.get("option_type") or out.get("option_type") or "Growth"
        )
        out["et_fund_name"] = resolved.get("et_fund_name") or ""
        out["fund_house"] = str(resolved.get("fund_house") or "").strip()
        out["can_analyse"] = bool(resolved.get("can_analyse"))
        out["can_track"] = True
    else:
        fn, pl, op = normalize_portfolio_fund_fields(
            str(out.get("display_fund_name") or out.get("fund_name") or ""),
            str(out.get("plan_type") or ""),
            str(out.get("option_type") or ""),
        )
        out["display_fund_name"] = fn
        out["fund_name"] = fn
        out["plan_type"] = pl
        out["option_type"] = op
        out["can_analyse"] = False
        out["can_analyse_sector"] = False
        out["data_tier"] = "none"
        out["can_track"] = False
    return out


def enrich_portfolio_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    return df.apply(enrich_portfolio_row, axis=1)


def portfolio_summary(df: pd.DataFrame) -> dict[str, int]:
    if df is None or df.empty:
        return {
            "total": 0,
            "analyse_stock": 0,
            "analyse_sector": 0,
            "track_only": 0,
            "invalid": 0,
            "analyse": 0,
        }
    if "row_kind" in df.columns:
        kinds = df["row_kind"].astype(str).str.strip().str.lower()
        df = df[kinds != "transaction"].copy()
    if "data_tier" not in df.columns:
        df = enrich_portfolio_df(df)
    n = len(df)
    if "data_tier" in df.columns:
        tiers = df["data_tier"].astype(str)
        analyse_stock = int((tiers == "stock").sum())
        analyse_sector = int((tiers == "sector_only").sum())
    else:
        analyse_stock = int(df["can_analyse"].sum()) if "can_analyse" in df.columns else 0
        analyse_sector = (
            int(df["can_analyse_sector"].sum())
            if "can_analyse_sector" in df.columns
            else 0
        )
    track = int(df.get("can_track", pd.Series([True] * n)).sum())
    invalid = n - track
    analyse = analyse_stock + analyse_sector
    return {
        "total": n,
        "analyse_stock": analyse_stock,
        "analyse_sector": analyse_sector,
        "analyse": analyse,
        "track_only": max(0, track - analyse_stock - analyse_sector),
        "invalid": invalid,
    }


def get_nav_on_or_before_with_date(
    mf_scheme_code: int, on_date
) -> tuple[float | None, str | None]:
    """Last NAV <= on_date; nav.db, cloud CSV, then MFAPI."""
    try:
        d = pd.Timestamp(on_date).strftime("%Y-%m-%d")
    except Exception:
        return None, None
    code = int(mf_scheme_code)
    if NAV_DB.is_file():
        conn = sqlite3.connect(NAV_DB)
        try:
            row = conn.execute(
                """
                SELECT nav, nav_date FROM nav_prices
                WHERE mf_scheme_code = ? AND nav_date <= ?
                ORDER BY nav_date DESC LIMIT 1
                """,
                (code, d),
            ).fetchone()
        finally:
            conn.close()
        if row and row[0] is not None:
            try:
                return float(row[0]), str(row[1] or "")[:10] or None
            except (TypeError, ValueError):
                pass
    nav, nd = _nav_from_latest_csv_on_or_before(code, on_date)
    if nav is not None:
        return nav, nd
    return _nav_from_mfapi_on_or_before(code, on_date)


def get_nav_on_or_before(mf_scheme_code: int, on_date) -> float | None:
    """Last NAV <= on_date from nav.db."""
    nav, _ = get_nav_on_or_before_with_date(mf_scheme_code, on_date)
    return nav


def get_nav_history(
    mf_scheme_code: int,
    start_date=None,
    end_date=None,
) -> pd.DataFrame:
    """Daily NAV series for a scheme (columns: nav_date, nav)."""
    code = int(mf_scheme_code)
    if NAV_DB.is_file():
        clauses = ["mf_scheme_code = ?"]
        params: list = [code]
        if start_date is not None:
            try:
                clauses.append("nav_date >= ?")
                params.append(pd.Timestamp(start_date).strftime("%Y-%m-%d"))
            except Exception:
                pass
        if end_date is not None:
            try:
                clauses.append("nav_date <= ?")
                params.append(pd.Timestamp(end_date).strftime("%Y-%m-%d"))
            except Exception:
                pass
        sql = (
            f"SELECT nav_date, nav FROM nav_prices WHERE {' AND '.join(clauses)} "
            "ORDER BY nav_date"
        )
        conn = sqlite3.connect(NAV_DB)
        try:
            df = pd.read_sql_query(sql, conn, params=params)
        finally:
            conn.close()
        if not df.empty:
            df["nav_date"] = pd.to_datetime(df["nav_date"], errors="coerce")
            df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
            return df.dropna(subset=["nav_date", "nav"])
    hist = _mfapi_nav_history(code)
    if not hist:
        return pd.DataFrame(columns=["nav_date", "nav"])
    rows = [{"nav_date": nd, "nav": nav} for nd, nav in hist]
    df = pd.DataFrame(rows)
    df["nav_date"] = pd.to_datetime(df["nav_date"], errors="coerce")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df = df.dropna(subset=["nav_date", "nav"])
    if start_date is not None:
        try:
            df = df[df["nav_date"] >= pd.Timestamp(start_date)]
        except Exception:
            pass
    if end_date is not None:
        try:
            df = df[df["nav_date"] <= pd.Timestamp(end_date)]
        except Exception:
            pass
    return df.sort_values("nav_date").reset_index(drop=True)


@lru_cache(maxsize=1)
def et_expense_ratio_by_fund_name() -> dict[str, float]:
    """ET fund_name → expense_ratio (%) for ACTIVE funds in fund_master_auto."""
    if not ET_MASTER.is_file():
        return {}
    df = pd.read_csv(ET_MASTER, usecols=["fund_name", "expense_ratio", "status"])
    df = df[df["status"].astype(str).str.upper() == "ACTIVE"]
    out: dict[str, float] = {}
    for _, row in df.iterrows():
        name = str(row.get("fund_name") or "").strip()
        er = row.get("expense_ratio")
        if not name or pd.isna(er):
            continue
        try:
            out[name] = float(er)
        except (TypeError, ValueError):
            continue
    return out


def nav_db_refresh_info(scheme_codes: tuple[int, ...] | None = None) -> dict[str, str]:
    """
    Latest NAV coverage date and optional per-portfolio scheme sync time.
    Returns display_date (human), raw_date (ISO), source label.
    """
    if not NAV_DB.is_file():
        latest = _nav_latest_table()
        if scheme_codes:
            dates = [latest[c][1] for c in scheme_codes if c in latest]
        else:
            dates = [v[1] for v in latest.values()]
        if dates:
            raw = max(dates)
            return {
                "display_date": _format_nav_refresh_date(raw),
                "raw_date": raw,
                "source": "nav_latest_csv",
            }
        return {"display_date": "—", "raw_date": "", "source": "none"}
    conn = sqlite3.connect(NAV_DB)
    try:
        if scheme_codes:
            placeholders = ",".join("?" for _ in scheme_codes)
            row = conn.execute(
                f"""
                SELECT MAX(nav_date) FROM nav_prices
                WHERE mf_scheme_code IN ({placeholders})
                """,
                list(scheme_codes),
            ).fetchone()
            if row and row[0]:
                raw = str(row[0])[:10]
                return {
                    "display_date": _format_nav_refresh_date(raw),
                    "raw_date": raw,
                    "source": "portfolio_nav_prices",
                }
            row = conn.execute(
                f"""
                SELECT MAX(last_nav_date) FROM schemes
                WHERE mf_scheme_code IN ({placeholders})
                """,
                list(scheme_codes),
            ).fetchone()
            if row and row[0]:
                raw = str(row[0])[:10]
                return {
                    "display_date": _format_nav_refresh_date(raw),
                    "raw_date": raw,
                    "source": "portfolio_schemes",
                }
        row = conn.execute(
            "SELECT MAX(nav_date) FROM nav_prices"
        ).fetchone()
        if row and row[0]:
            raw = str(row[0])[:10]
            return {
                "display_date": _format_nav_refresh_date(raw),
                "raw_date": raw,
                "source": "nav_prices",
            }
    finally:
        conn.close()
    return {"display_date": "—", "raw_date": "", "source": "none"}


def _format_nav_refresh_date(raw: str) -> str:
    s = str(raw or "").strip()[:10]
    if not s:
        return "—"
    try:
        dt = pd.to_datetime(s)
        return dt.strftime("%d %b %Y")
    except Exception:
        return s


def get_latest_nav(mf_scheme_code: int) -> tuple[float | None, str | None]:
    if not NAV_DB.is_file():
        hit = _nav_latest_table().get(int(mf_scheme_code))
        if hit:
            return hit[0], hit[1]
        return _nav_from_mfapi_on_or_before(mf_scheme_code, date.today())
    conn = sqlite3.connect(NAV_DB)
    try:
        row = conn.execute(
            """
            SELECT nav, nav_date FROM nav_prices
            WHERE mf_scheme_code = ?
            ORDER BY nav_date DESC LIMIT 1
            """,
            (int(mf_scheme_code),),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None, None
    try:
        return float(row[0]), str(row[1])
    except (TypeError, ValueError):
        return None, None
