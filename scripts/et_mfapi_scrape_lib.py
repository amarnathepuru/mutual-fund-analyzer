"""
MFAPI Direct-Growth fund → ET Money discover + holdings scrape (single-fund flow).

Used by scrape_mfapi_et_one.py and validate_mfapi_et_scrape_app.py.
"""
from __future__ import annotations

import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRAPER = ROOT / "scraper"
DATA = ROOT / "data"
PROC = DATA / "processed"
BACKUPS = DATA / "backups"

MF_UNIVERSE = DATA / "raw" / "mfapi" / "nav_universe_schemes.csv"
DG_CSV = DATA / "raw" / "mfapi" / "direct_growth_schemes.csv"
ET_MASTER = DATA / "fund_master_auto.csv"
ET_INVALID = DATA / "fund_master_invalid.csv"
SCHEME_MAP = DATA / "fund_scheme_map.csv"
HOLDINGS = PROC / "master_holdings.csv"
REPORTS = DATA / "reports"
SCRAPE_HINTS = DATA / "mfapi_et_scrape_hints.csv"

if str(SCRAPER) not in sys.path:
    sys.path.insert(0, str(SCRAPER))

from discover_funds import (  # noqa: E402
    BASE_URL,
    STATUS_ACTIVE,
    _get,
    scrape_fund_detail,
    scrape_listing_page,
    validate_portfolio_url,
)
from scrape_holdings import scrape_fund  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mfapi_scheme_name import fund_name_match_score, mf_fund_name_cleaned  # noqa: E402

# MFAPI scheme_category → ET listing (category label, path)
MF_CATEGORY_ET_LISTING: dict[str, tuple[str, str]] = {
    "Equity Scheme - Value Fund": ("Value", "/mutual-funds/equity/value/37"),
    "Equity Scheme - Focused Fund": ("Focused", "/mutual-funds/equity/focused/40"),
    "Equity Scheme - Contra Fund": ("Contra", "/mutual-funds/equity/contra/41"),
    "Equity Scheme - Dividend Yield Fund": ("Dividend Yield", "/mutual-funds/equity/dividend-yield/42"),
    "Equity Scheme - Large Cap Fund": ("Large Cap", "/mutual-funds/equity/large-cap/32"),
    "Equity Scheme - Mid Cap Fund": ("Mid Cap", "/mutual-funds/equity/mid-cap/35"),
    "Equity Scheme - Small Cap Fund": ("Small Cap", "/mutual-funds/equity/small-cap/36"),
    "Equity Scheme - Multi Cap Fund": ("Multi Cap", "/mutual-funds/equity/multi-cap/34"),
    "Equity Scheme - Flexi Cap Fund": ("Flexi Cap", "/mutual-funds/equity/flexi-cap/79"),
    "Equity Scheme - Large & Mid Cap Fund": ("Large & Mid Cap", "/mutual-funds/equity/large-and-midcap/33"),
    "Equity Scheme - ELSS": ("ELSS", "/mutual-funds/equity/elss/38"),
    "Equity Scheme - Sectoral/ Thematic": ("Thematic", "/mutual-funds/equity/thematic/44"),
    "Debt Scheme - Liquid Fund": ("Liquid", "/mutual-funds/debt/liquid/28"),
    "Liquid": ("Liquid", "/mutual-funds/debt/liquid/28"),
    "Hybrid Scheme - Equity Savings": ("Equity Savings", "/mutual-funds/hybrid/equity-savings/76"),
    "Hybrid Scheme - Conservative Hybrid Fund": (
        "Conservative Hybrid",
        "/mutual-funds/hybrid/conservative-hybrid/70",
    ),
    "Hybrid Scheme - Aggressive Hybrid Fund": (
        "Aggressive Hybrid",
        "/mutual-funds/hybrid/aggressive-hybrid/68",
    ),
    "Hybrid Scheme - Arbitrage Fund": ("Arbitrage", "/mutual-funds/hybrid/arbitrage/73"),
    "Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage": (
        "Dynamic Asset Allocation",
        "/mutual-funds/hybrid/dynamic-asset-allocation/74",
    ),
    "Hybrid Scheme - Multi Asset Allocation": (
        "Multi Asset Allocation",
        "/mutual-funds/hybrid/multi-asset-allocation/75",
    ),
    "Hybrid Scheme - Balanced Hybrid Fund": ("Balanced Hybrid", "/mutual-funds/hybrid/balanced-hybrid/69"),
    "Income": ("Corporate Bond", "/mutual-funds/debt/corporate-bond/31"),
    "Solution Oriented Scheme - Retirement Fund": (
        "Retirement",
        "/mutual-funds/solution-oriented/retirement-fund/82",
    ),
}

# Extra sectoral listing pages (Sectoral/Thematic MFAPI category)
SECTORAL_EXTRA_LISTINGS: list[tuple[str, str]] = [
    ("Sectoral Banking", "/mutual-funds/equity/sectoral-banking/39"),
    ("Sectoral Technology", "/mutual-funds/equity/sectoral-technology/43"),
    ("Sectoral Pharma", "/mutual-funds/equity/sectoral-pharma/45"),
    ("Sectoral Infrastructure", "/mutual-funds/equity/sectoral-infrastructure/46"),
    ("Sectoral Consumption", "/mutual-funds/equity/sectoral-consumption/47"),
    ("Sectoral Energy", "/mutual-funds/equity/sectoral-energy/48"),
]

FALLBACK_LISTINGS: list[tuple[str, str]] = [
    ("Value", "/mutual-funds/equity/value/37"),
    ("Thematic", "/mutual-funds/equity/thematic/44"),
    ("Large Cap", "/mutual-funds/equity/large-cap/32"),
    ("Focused", "/mutual-funds/equity/focused/40"),
    ("Liquid", "/mutual-funds/debt/liquid/28"),
]

_LISTING_CACHE: dict[str, list[dict]] = {}


def clear_scrape_hints_cache() -> None:
    global _HINTS_CACHE
    _HINTS_CACHE = None


def clear_listing_cache() -> None:
    _LISTING_CACHE.clear()


def get_cached_listing_stubs(et_cat: str, path: str) -> list[dict]:
    if path not in _LISTING_CACHE:
        _LISTING_CACHE[path] = scrape_listing_page(et_cat, path)
    return _LISTING_CACHE[path]


def listings_for_mf_category(mf_category: str | None) -> list[tuple[str, str]]:
    """ET listing pages to scan for one MFAPI scheme_category."""
    cat = (mf_category or "").strip()
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(label: str, path: str) -> None:
        if path not in seen:
            seen.add(path)
            out.append((label, path))

    if cat in MF_CATEGORY_ET_LISTING:
        label, path = MF_CATEGORY_ET_LISTING[cat]
        add(label, path)
    if cat == "Equity Scheme - Sectoral/ Thematic":
        for label, path in SECTORAL_EXTRA_LISTINGS:
            add(label, path)
    for label, path in FALLBACK_LISTINGS:
        add(label, path)
    return out


def prefetch_listings(paths: list[str], *, label_by_path: dict[str, str] | None = None) -> int:
    """Warm listing cache (one HTTP fetch per path). Returns paths fetched."""
    label_by_path = label_by_path or {}
    fetched = 0
    for path in paths:
        if path in _LISTING_CACHE:
            continue
        et_cat = label_by_path.get(path, path.split("/")[-2].replace("-", " ").title())
        get_cached_listing_stubs(et_cat, path)
        fetched += 1
        time.sleep(0.5)
    return fetched


def collect_listing_paths_for_categories(categories: list[str]) -> tuple[list[str], dict[str, str]]:
    paths: list[str] = []
    label_by_path: dict[str, str] = {}
    seen: set[str] = set()
    for cat in categories:
        for label, path in listings_for_mf_category(cat):
            if path not in seen:
                seen.add(path)
                paths.append(path)
                label_by_path[path] = label
    return paths, label_by_path


def all_batch_listing_paths() -> tuple[list[str], dict[str, str]]:
    """All category listing paths used for batch prefetch (not just queue categories)."""
    paths: list[str] = []
    label_by_path: dict[str, str] = {}
    seen: set[str] = set()

    def add(label: str, path: str) -> None:
        if path not in seen:
            seen.add(path)
            paths.append(path)
            label_by_path[path] = label

    for label, path in MF_CATEGORY_ET_LISTING.values():
        add(label, path)
    for label, path in SECTORAL_EXTRA_LISTINGS:
        add(label, path)
    for label, path in FALLBACK_LISTINGS:
        add(label, path)
    return paths, label_by_path


def load_unmapped_mf_codes(*, include_mapped: bool = False) -> list[int]:
    """MFAPI nav-universe codes not in fund_scheme_map (scrape queue)."""
    if not MF_UNIVERSE.is_file():
        raise FileNotFoundError(MF_UNIVERSE)
    nav = pd.read_csv(MF_UNIVERSE)
    codes = nav["mf_scheme_code"].astype(int).tolist()
    if include_mapped or not SCHEME_MAP.is_file():
        return codes
    mapped = set(pd.read_csv(SCHEME_MAP)["mf_scheme_code"].dropna().astype(int))
    return [c for c in codes if c not in mapped]


def _slugify(name: str) -> str:
    s = mf_fund_name_cleaned(name).lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"\s+", "-", s).strip("-")


def _name_from_slug(slug: str) -> str:
    return slug.replace("-", " ").title()


def load_mfapi_row(mf_scheme_code: int) -> pd.Series:
    if not MF_UNIVERSE.is_file():
        raise FileNotFoundError(f"Missing {MF_UNIVERSE}")
    mf = pd.read_csv(MF_UNIVERSE)
    m = mf[mf["mf_scheme_code"].astype(int) == int(mf_scheme_code)]
    if m.empty:
        raise ValueError(f"mf_scheme_code {mf_scheme_code} not in nav_universe_schemes.csv")
    row = m.iloc[0]
    if DG_CSV.is_file():
        dg = set(pd.read_csv(DG_CSV)["mf_scheme_code"].astype(int))
        if int(mf_scheme_code) not in dg:
            raise ValueError(f"mf_scheme_code {mf_scheme_code} is not Direct-Growth in {DG_CSV.name}")
    return row


def load_mfapi_row_by_name(cleaned_name: str) -> pd.Series:
    mf = pd.read_csv(MF_UNIVERSE)
    target = mf_fund_name_cleaned(cleaned_name)
    for _, row in mf.iterrows():
        raw = str(row.get("scheme_name_raw") or row.get("fund_name_base") or "")
        if mf_fund_name_cleaned(raw) == target:
            return row
    raise ValueError(f"No nav-universe fund matching cleaned name: {cleaned_name}")


def lookup_et_listing(
    mf_cleaned_name: str,
    mf_category: str | None,
    *,
    min_score: float = 85.0,
) -> dict | None:
    """
    Find ET slug + scheme_id by scanning category listing page(s).
    Returns dict with scheme_id, slug, et_fund_name, et_category, match_score, listing.
    """
    best_stub: dict | None = None
    best_meta: dict | None = None
    for et_cat, path in listings_for_mf_category(mf_category):
        stubs = get_cached_listing_stubs(et_cat, path)
        for stub in stubs:
            slug = stub["slug"]
            et_name = _name_from_slug(slug)
            score = fund_name_match_score(mf_cleaned_name, et_name)
            if score < min_score:
                continue
            cand = {
                "scheme_id": int(stub["scheme_id"]),
                "slug": slug,
                "et_fund_name": et_name,
                "et_category": et_cat,
                "match_score": round(score, 2),
                "listing_path": path,
                "_stub": stub,
            }
            if best_meta is None or cand["match_score"] > best_meta["match_score"]:
                best_meta = cand
                best_stub = stub
        if best_meta and best_meta["match_score"] >= 99.0:
            break
    if not best_meta or not best_stub:
        return None
    detail = scrape_fund_detail(best_stub)
    if detail and detail.get("fund_name"):
        best_meta["et_fund_name"] = detail["fund_name"]
        best_meta["match_score"] = round(
            fund_name_match_score(mf_cleaned_name, best_meta["et_fund_name"]), 2
        )
    best_meta.pop("_stub", None)
    return best_meta


def _direct_growth_slug_variants(base_slug: str) -> list[str]:
    variants = [
        f"{base_slug}-direct-growth",
        f"{base_slug}-direct-plan-growth",
    ]
    if base_slug.endswith("-fund"):
        stem = base_slug[: -len("-fund")]
        variants.extend(
            [
                f"{stem}-fund-direct-growth",
                f"{stem}-fund-direct-plan-growth",
            ]
        )
    return variants


def _resolve_direct_growth_from_plan_page(
    slug: str,
    scheme_id: int,
    et_cat: str,
    mf_cleaned_name: str,
    listing_path: str,
) -> dict | None:
    """
    MFAPI universe is Direct-Growth. ET listing often shows the Regular plan slug;
    the fund overview page links to the Direct-Growth plan (slug + scheme_id).
    """
    url = f"{BASE_URL}/mutual-funds/{slug}/{scheme_id}"
    r = _get(url)
    if r is None or r.status_code != 200:
        return None
    base = _slugify(mf_cleaned_name)
    targets = set(_direct_growth_slug_variants(base))
    best: dict | None = None
    for dg_slug, dg_sid in re.findall(r"/mutual-funds/([a-z0-9\-]+)/(\d+)", r.text):
        if dg_slug not in targets and not (
            dg_slug.startswith(base) and "direct" in dg_slug and "growth" in dg_slug
        ):
            continue
        et_name = _name_from_slug(dg_slug)
        score = fund_name_match_score(mf_cleaned_name, et_name)
        if score < 85.0:
            continue
        cand = {
            "scheme_id": int(dg_sid),
            "slug": dg_slug,
            "et_fund_name": et_name,
            "et_category": et_cat,
            "match_score": round(score, 2),
            "listing_path": listing_path,
        }
        if best is None or cand["match_score"] > best["match_score"]:
            best = cand
    if not best:
        return None
    detail = scrape_fund_detail(
        {"slug": best["slug"], "scheme_id": best["scheme_id"], "category": et_cat}
    )
    if detail and detail.get("fund_name"):
        best["et_fund_name"] = detail["fund_name"]
        best["match_score"] = round(
            fund_name_match_score(mf_cleaned_name, best["et_fund_name"]), 2
        )
    return best


def lookup_et_by_slug_guess(mf_cleaned_name: str, mf_category: str | None) -> dict | None:
    """Match listing links whose slug equals slugified MFAPI cleaned name."""
    slug = _slugify(mf_cleaned_name)
    if not slug:
        return None
    for et_cat, path in listings_for_mf_category(mf_category):
        for stub in get_cached_listing_stubs(et_cat, path):
            if stub["slug"] != slug:
                continue
            dg = _resolve_direct_growth_from_plan_page(
                slug,
                int(stub["scheme_id"]),
                et_cat,
                mf_cleaned_name,
                path,
            )
            if dg:
                return dg
            et_name = _name_from_slug(slug)
            score = fund_name_match_score(mf_cleaned_name, et_name)
            detail = scrape_fund_detail(stub)
            if detail and detail.get("fund_name"):
                et_name = detail["fund_name"]
                score = fund_name_match_score(mf_cleaned_name, et_name)
            return {
                "scheme_id": int(stub["scheme_id"]),
                "slug": slug,
                "et_fund_name": et_name,
                "et_category": et_cat,
                "match_score": round(score, 2),
                "listing_path": path,
            }
    return None


def lookup_et_by_direct_growth_slug_in_cache(
    mf_cleaned_name: str,
    mf_category: str | None,
) -> dict | None:
    """Find Direct-Growth slug (+id) already present in warmed listing cache."""
    base = _slugify(mf_cleaned_name)
    if not base:
        return None
    targets = set(_direct_growth_slug_variants(base))
    best: dict | None = None
    best_stub: dict | None = None
    for et_cat, path in listings_for_mf_category(mf_category):
        for stub in get_cached_listing_stubs(et_cat, path):
            s = stub["slug"]
            if s not in targets and not (
                s.startswith(base) and "direct" in s and "growth" in s
            ):
                continue
            et_name = _name_from_slug(s)
            score = fund_name_match_score(mf_cleaned_name, et_name)
            if score < 85.0:
                continue
            cand = {
                "scheme_id": int(stub["scheme_id"]),
                "slug": s,
                "et_fund_name": et_name,
                "et_category": et_cat,
                "match_score": round(score, 2),
                "listing_path": path,
                "_stub": stub,
            }
            if best is None or cand["match_score"] > best["match_score"]:
                best = cand
                best_stub = stub
    if not best or not best_stub:
        return None
    detail = scrape_fund_detail(best_stub)
    if detail and detail.get("fund_name"):
        best["et_fund_name"] = detail["fund_name"]
        best["match_score"] = round(
            fund_name_match_score(mf_cleaned_name, best["et_fund_name"]), 2
        )
    best.pop("_stub", None)
    return best


def lookup_et_from_listing_cache(
    mf_cleaned_name: str,
    *,
    min_score: float = 85.0,
) -> dict | None:
    """Last resort: best name match across all cached listing pages."""
    best_meta: dict | None = None
    best_stub: dict | None = None
    for path, stubs in _LISTING_CACHE.items():
        et_cat = path.rstrip("/").split("/")[-2].replace("-", " ").title()
        for stub in stubs:
            slug = stub["slug"]
            et_name = _name_from_slug(slug)
            score = fund_name_match_score(mf_cleaned_name, et_name)
            if score < min_score:
                continue
            cand = {
                "scheme_id": int(stub["scheme_id"]),
                "slug": slug,
                "et_fund_name": et_name,
                "et_category": et_cat,
                "match_score": round(score, 2),
                "listing_path": path,
                "_stub": stub,
            }
            if best_meta is None or cand["match_score"] > best_meta["match_score"]:
                best_meta = cand
                best_stub = stub
    if not best_meta or not best_stub:
        return None
    detail = scrape_fund_detail(best_stub)
    if detail and detail.get("fund_name"):
        best_meta["et_fund_name"] = detail["fund_name"]
        best_meta["match_score"] = round(
            fund_name_match_score(mf_cleaned_name, best_meta["et_fund_name"]), 2
        )
    best_meta.pop("_stub", None)
    return best_meta


def lookup_et_fuzzy_regular_then_direct_growth(
    mf_cleaned_name: str,
    mf_category: str | None,
    *,
    min_score: float = 92.0,
) -> dict | None:
    """
    Find a non-Direct-Growth listing stub with a strong name match, then read
  the Regular plan page for the Direct-Growth link (liquid / small listings).
    """
    best_stub: dict | None = None
    best_meta: dict | None = None
    for et_cat, path in listings_for_mf_category(mf_category):
        for stub in get_cached_listing_stubs(et_cat, path):
            slug = stub["slug"]
            if "direct-growth" in slug or "direct-plan-growth" in slug:
                continue
            score = fund_name_match_score(mf_cleaned_name, _name_from_slug(slug))
            if score < min_score:
                continue
            if best_meta is None or score > best_meta["match_score"]:
                best_meta = {
                    "score": score,
                    "et_cat": et_cat,
                    "path": path,
                    "stub": stub,
                }
                best_stub = stub
    if not best_stub or not best_meta:
        return None
    dg = _resolve_direct_growth_from_plan_page(
        best_stub["slug"],
        int(best_stub["scheme_id"]),
        best_meta["et_cat"],
        mf_cleaned_name,
        best_meta["path"],
    )
    return dg


_HINTS_CACHE: dict[int, dict] | None = None


def _load_scrape_hints() -> dict[int, dict]:
    global _HINTS_CACHE
    if _HINTS_CACHE is not None:
        return _HINTS_CACHE
    if not SCRAPE_HINTS.is_file():
        _HINTS_CACHE = {}
        return _HINTS_CACHE
    df = pd.read_csv(SCRAPE_HINTS)
    out: dict[int, dict] = {}
    for _, r in df.iterrows():
        if pd.isna(r.get("mf_scheme_code")):
            continue
        code = int(float(r["mf_scheme_code"]))
        slug = str(r.get("et_slug") or "").strip()
        sid = r.get("et_scheme_id")
        if not slug or pd.isna(sid):
            continue
        out[code] = {
            "scheme_id": int(float(sid)),
            "slug": slug,
            "et_fund_name": str(r.get("et_fund_name") or "").strip(),
            "et_category": str(r.get("et_category") or "").strip(),
            "match_score": 100.0,
            "listing_path": "hints_csv",
        }
    _HINTS_CACHE = out
    return out


def lookup_et_from_hints(mf_scheme_code: int) -> dict | None:
    hints = _load_scrape_hints()
    hit = hints.get(int(mf_scheme_code))
    if not hit:
        return None
    stub = {
        "slug": hit["slug"],
        "scheme_id": int(hit["scheme_id"]),
        "category": hit.get("et_category") or "Unknown",
    }
    detail = scrape_fund_detail(stub)
    if detail and detail.get("fund_name"):
        hit = {
            **hit,
            "et_fund_name": detail["fund_name"],
            "et_category": detail.get("category") or hit.get("et_category") or "Unknown",
        }
    elif not hit.get("et_fund_name"):
        hit["et_fund_name"] = _name_from_slug(hit["slug"])
    return hit


def resolve_et_for_mfapi(row: pd.Series) -> dict:
    """Resolve ET Money fund for one MFAPI universe row."""
    mf_code = int(row["mf_scheme_code"])
    hint_hit = lookup_et_from_hints(mf_code)
    if hint_hit:
        return hint_hit
    raw = str(row.get("scheme_name_raw") or "")
    cleaned = mf_fund_name_cleaned(raw or str(row.get("fund_name_base") or ""))
    cat = str(row.get("scheme_category") or "")
    hit = lookup_et_by_slug_guess(cleaned, cat)
    if not hit:
        hit = lookup_et_by_direct_growth_slug_in_cache(cleaned, cat)
    if not hit:
        hit = lookup_et_listing(cleaned, cat)
    if not hit and _LISTING_CACHE:
        hit = lookup_et_from_listing_cache(cleaned)
    if not hit:
        hit = lookup_et_from_listing_cache(cleaned, min_score=92.0)
    if not hit:
        hit = lookup_et_fuzzy_regular_then_direct_growth(cleaned, cat)
    if not hit:
        raise LookupError(
            f"No ET listing match for '{cleaned}' (category={cat}). "
            "Try manual scheme_id or expand category listings."
        )
    return hit


def scrape_et_fund_to_master(
    et_hit: dict,
    *,
    dry_run: bool = False,
) -> dict:
    """Discover metadata + portfolio URL; merge into fund_master_auto.csv."""
    stub = {
        "slug": et_hit["slug"],
        "scheme_id": int(et_hit["scheme_id"]),
        "category": et_hit.get("et_category") or "Unknown",
    }
    detail = scrape_fund_detail(stub)
    if not detail:
        raise RuntimeError("ET fund detail page fetch failed")

    time.sleep(0.8)
    status, portfolio_url, row_count = validate_portfolio_url(stub["slug"], stub["scheme_id"])

    fund_row = {
        "fund_name": detail["fund_name"],
        "category": detail.get("category") or stub["category"],
        "fund_house": detail.get("fund_house") or "",
        "scheme_id": int(detail["scheme_id"]),
        "url": portfolio_url,
        "status": status,
        "benchmark": detail.get("benchmark") or "",
        "aum_cr": detail.get("aum_cr") or "",
        "expense_ratio": detail.get("expense_ratio") or "",
        "launch_date": detail.get("launch_date") or "",
    }

    result = {
        **fund_row,
        "holdings_rows": row_count,
        "portfolio_url": portfolio_url,
    }

    if dry_run:
        return result

    if ET_MASTER.is_file():
        master = pd.read_csv(ET_MASTER)
    else:
        master = pd.DataFrame()

    sid = int(fund_row["scheme_id"])
    master = master[master["scheme_id"].astype(int) != sid]
    if status == STATUS_ACTIVE:
        master = pd.concat([master, pd.DataFrame([fund_row])], ignore_index=True)
    master = master.sort_values(["category", "fund_name"]).reset_index(drop=True)

    BACKUPS.mkdir(parents=True, exist_ok=True)
    if ET_MASTER.is_file():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(ET_MASTER, BACKUPS / f"fund_master_auto_{stamp}.csv")
    master.to_csv(ET_MASTER, index=False)
    return result


def scrape_holdings_for_et_fund(fund_row: dict, *, dry_run: bool = False) -> pd.DataFrame:
    if fund_row.get("status") != STATUS_ACTIVE:
        return pd.DataFrame()
    if dry_run:
        return pd.DataFrame()
    df = scrape_fund(fund_row)
    if df.empty:
        return df
    PROC.mkdir(parents=True, exist_ok=True)
    if HOLDINGS.is_file():
        existing = pd.read_csv(HOLDINGS)
        existing = existing[existing["scheme_id"].astype(int) != int(fund_row["scheme_id"])]
        combined = pd.concat([existing, df], ignore_index=True).drop_duplicates()
    else:
        combined = df
    combined.to_csv(HOLDINGS, index=False)
    return df


def upsert_scheme_map(
    mf_scheme_code: int,
    et_scheme_id: int,
    et_fund_name: str,
    mf_scheme_name: str,
    *,
    dry_run: bool = False,
    match_method: str = "mfapi_et_scrape",
    notes: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "scheme_id": int(et_scheme_id),
        "mf_scheme_code": int(mf_scheme_code),
        "isin": "",
        "et_fund_name": et_fund_name,
        "match_score": "",
        "match_method": match_method,
        "matched_at": now,
        "notes": notes or f"sample_scrape {mf_scheme_name[:60]}",
    }
    if dry_run:
        return
    if SCHEME_MAP.is_file():
        m = pd.read_csv(SCHEME_MAP)
        m = m[m["mf_scheme_code"].astype(int) != int(mf_scheme_code)]
        m = m[m["scheme_id"].astype(int) != int(et_scheme_id)]
    else:
        m = pd.DataFrame()
    m = pd.concat([m, pd.DataFrame([row])], ignore_index=True)
    BACKUPS.mkdir(parents=True, exist_ok=True)
    if SCHEME_MAP.is_file():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(SCHEME_MAP, BACKUPS / f"fund_scheme_map_{stamp}.csv")
    m.to_csv(SCHEME_MAP, index=False)


def run_one_fund_scrape(
    mf_scheme_code: int,
    *,
    dry_run: bool = False,
    skip_holdings: bool = False,
    skip_map: bool = False,
    match_method: str = "mfapi_et_scrape",
    map_notes: str | None = None,
) -> dict:
    """Full pipeline for one MFAPI Direct-Growth code."""
    mf_row = load_mfapi_row(mf_scheme_code)
    mf_cleaned = mf_fund_name_cleaned(str(mf_row.get("scheme_name_raw") or ""))
    et_hit = resolve_et_for_mfapi(mf_row)
    master_row = scrape_et_fund_to_master(et_hit, dry_run=dry_run)
    holdings_df = pd.DataFrame()
    if not skip_holdings and master_row.get("status") == STATUS_ACTIVE:
        holdings_df = scrape_holdings_for_et_fund(master_row, dry_run=dry_run)
    if not skip_map and not dry_run:
        upsert_scheme_map(
            mf_scheme_code,
            int(et_hit["scheme_id"]),
            str(master_row["fund_name"]),
            mf_cleaned,
            dry_run=dry_run,
            match_method=match_method,
            notes=map_notes,
        )
    return {
        "mf_scheme_code": int(mf_scheme_code),
        "mfapi_name_cleaned": mf_cleaned,
        "mfapi_name_raw": str(mf_row.get("scheme_name_raw") or ""),
        "mf_category": str(mf_row.get("scheme_category") or ""),
        "et_lookup": et_hit,
        "et_master": master_row,
        "holdings_rows": len(holdings_df),
        "holdings_sample": holdings_df.head(10) if not holdings_df.empty else pd.DataFrame(),
    }
