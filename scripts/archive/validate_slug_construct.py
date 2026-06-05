"""
Validate mfapi_et_slug_construct.csv (slug_construct column).

  python scripts/validate_slug_construct.py
  python scripts/validate_slug_construct.py --quick
  python scripts/validate_slug_construct.py --limit 30
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(ROOT / "scraper") not in sys.path:
    sys.path.insert(0, str(ROOT / "scraper"))

from discover_funds import BASE_URL, _get, scrape_fund_detail, validate_portfolio_url  # noqa: E402
from et_mfapi_scrape_lib import (  # noqa: E402
    ET_MASTER,
    _name_from_slug,
    _resolve_direct_growth_from_plan_page,
    all_batch_listing_paths,
    clear_listing_cache,
    get_cached_listing_stubs,
    lookup_et_by_direct_growth_slug_in_cache,
    lookup_et_by_slug_guess,
    lookup_et_fuzzy_regular_then_direct_growth,
    lookup_et_from_listing_cache,
    lookup_et_listing,
    prefetch_listings,
)
from mfapi_scheme_name import fund_name_match_score, mf_fund_name_cleaned  # noqa: E402

IN_CSV = ROOT / "data" / "reports" / "mfapi_et_slug_construct.csv"
OUT_CSV = ROOT / "data" / "reports" / "mfapi_et_slug_construct_validation.csv"
HINTS_CSV = ROOT / "data" / "mfapi_et_scrape_hints.csv"

SLUG_IN_PAGE = re.compile(r"/mutual-funds/([a-z0-9\-]+)/(\d+)", re.IGNORECASE)
PORTFOLIO_RE = re.compile(
    r"/mutual-funds/([a-z0-9\-]+)/portfolio-details/(\d+)", re.IGNORECASE
)


def build_slug_index() -> dict[str, int]:
    clear_listing_cache()
    paths, labels = all_batch_listing_paths()
    prefetch_listings(paths, label_by_path=labels)
    idx: dict[str, int] = {}
    for path in paths:
        stubs = get_cached_listing_stubs(labels.get(path, ""), path)
        for s in stubs:
            idx[s["slug"]] = int(s["scheme_id"])
    if ET_MASTER.is_file():
        master = pd.read_csv(ET_MASTER)
        for url in master["url"].astype(str):
            m = PORTFOLIO_RE.search(url)
            if m:
                idx[m.group(1)] = int(m.group(2))
    return idx


def _slug_construct_variants(slug: str) -> list[str]:
    """ET slug order varies (e.g. axis-liquid-direct-fund-growth vs …-fund-direct-growth)."""
    out: list[str] = []
    for s in (slug, slug.replace("--", "-")):
        if s and s not in out:
            out.append(s)
    if "-fund-direct-growth" in slug:
        alt = slug.replace("-fund-direct-growth", "-direct-fund-growth")
        if alt not in out:
            out.append(alt)
    return out


def _scheme_id_from_fund_page(html: str, slug: str) -> int | None:
    pat = re.compile(rf"/mutual-funds/{re.escape(slug)}/(\d+)", re.IGNORECASE)
    m = pat.search(html)
    if m:
        return int(m.group(1))
    for m in SLUG_IN_PAGE.finditer(html):
        if m.group(1) == slug:
            return int(m.group(2))
    return None


def _get_with_retry(url: str, *, attempts: int = 3) -> object | None:
    for i in range(attempts):
        r = _get(url)
        if r is not None and r.status_code == 200:
            return r
        if r is not None and r.status_code in (429, 503):
            time.sleep(2.0 * (i + 1))
            continue
        if r is None:
            time.sleep(1.0 * (i + 1))
            continue
        break
    return r


def _slugs_equivalent(user_slug: str, et_slug: str) -> bool:
    if user_slug == et_slug:
        return True
    for u, e in (
        (user_slug, et_slug),
        (user_slug.replace("--", "-"), et_slug),
        (user_slug.replace("-fund-direct-growth", "-direct-fund-growth"), et_slug),
        (user_slug, et_slug.replace("-direct-fund-growth", "-fund-direct-growth")),
    ):
        if u == e:
            return True
    return False


def resolve_for_scrape(
    mf_name: str,
    mf_category: str,
    user_slug: str,
    idx: dict[str, int],
) -> tuple[str, int, str] | None:
    """Resolve ET Direct-Growth slug+id; prefer paths that confirm the user's slug."""
    cleaned = mf_fund_name_cleaned(mf_name)

    hit = resolve_slug(user_slug, idx)
    if hit:
        return hit[0], hit[1], "user_slug"

    for fn in (
        lookup_et_by_direct_growth_slug_in_cache,
        lookup_et_by_slug_guess,
    ):
        h = fn(cleaned, mf_category or None)
        if h and _slugs_equivalent(user_slug, h["slug"]):
            return h["slug"], int(h["scheme_id"]), fn.__name__

    reg = lookup_et_listing(cleaned, mf_category or None)
    if reg and "direct-growth" not in reg["slug"]:
        dg = _resolve_direct_growth_from_plan_page(
            reg["slug"],
            int(reg["scheme_id"]),
            reg["et_category"],
            cleaned,
            reg.get("listing_path") or "",
        )
        if dg and _slugs_equivalent(user_slug, dg["slug"]):
            return dg["slug"], int(dg["scheme_id"]), "category_listing"

    reg = lookup_et_from_listing_cache(cleaned, min_score=92.0)
    if reg and "direct-growth" not in reg["slug"]:
        dg = _resolve_direct_growth_from_plan_page(
            reg["slug"],
            int(reg["scheme_id"]),
            reg.get("et_category") or "Unknown",
            cleaned,
            reg.get("listing_path") or "",
        )
        if dg and _slugs_equivalent(user_slug, dg["slug"]):
            return dg["slug"], int(dg["scheme_id"]), "global_listing"

    fuzzy = lookup_et_fuzzy_regular_then_direct_growth(cleaned, mf_category or None)
    if fuzzy and _slugs_equivalent(user_slug, fuzzy["slug"]):
        return fuzzy["slug"], int(fuzzy["scheme_id"]), "fuzzy_listing"
    return None


def resolve_slug(slug: str, idx: dict[str, int]) -> tuple[str, int] | None:
    for candidate in _slug_construct_variants(slug):
        if candidate in idx:
            return candidate, idx[candidate]

    bases: list[str] = []
    for candidate in _slug_construct_variants(slug):
        base = candidate.replace("-direct-growth", "").replace("-direct-plan-growth", "")
        if base and base not in bases:
            bases.append(base)

    for base in bases:
        if base not in idx:
            continue
        hit = _resolve_direct_growth_from_plan_page(
            base, idx[base], "Unknown", slug, ""
        )
        if hit:
            return hit["slug"], int(hit["scheme_id"])
        for s, sid in idx.items():
            if s.startswith(base) and "direct-growth" in s:
                return s, sid

    for candidate in _slug_construct_variants(slug):
        url = f"{BASE_URL}/mutual-funds/{candidate}"
        r = _get_with_retry(url)
        if r is not None and r.status_code == 200:
            sid = _scheme_id_from_fund_page(r.text, candidate)
            if sid:
                return candidate, sid
        time.sleep(0.35)
    return None


def validate_row(
    mf_code: int,
    mf_name: str,
    slug: str,
    scheme_id: int,
    *,
    quick: bool,
) -> dict:
    base = {
        "mf_scheme_code": mf_code,
        "mfapi_name_cleaned": mf_name,
        "slug_construct": slug,
        "et_scheme_id": scheme_id,
    }
    if quick:
        return {
            **base,
            "validation": "resolved",
            "reason": "slug+id resolved",
            "et_fund_name": "",
            "name_match_pct": "",
            "portfolio_status": "",
            "holdings_rows": "",
        }
    stub = {"slug": slug, "scheme_id": scheme_id, "category": "Unknown"}
    detail = scrape_fund_detail(stub)
    if not detail:
        return {
            **base,
            "validation": "fail",
            "reason": "ET page 404",
            "et_fund_name": "",
            "name_match_pct": 0.0,
            "portfolio_status": "",
            "holdings_rows": 0,
        }
    et_name = str(detail.get("fund_name") or "")
    score = fund_name_match_score(mf_fund_name_cleaned(mf_name), et_name)
    time.sleep(0.5)
    status, _, rows = validate_portfolio_url(slug, scheme_id)
    ok = score >= 85.0 and status == "ACTIVE" and int(rows or 0) > 0
    return {
        **base,
        "validation": "ok" if ok else "review",
        "reason": "" if ok else f"name={score:.0f}% port={status} rows={rows}",
        "et_fund_name": et_name,
        "name_match_pct": round(score, 2),
        "portfolio_status": status,
        "holdings_rows": int(rows or 0),
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--delay", type=float, default=1.2)
    args = parser.parse_args()

    if not IN_CSV.is_file():
        print(f"Missing {IN_CSV}")
        return 1

    df = pd.read_csv(IN_CSV, encoding="utf-8-sig")
    for col in df.columns:
        if col.lower() == "slug_construct":
            df = df.rename(columns={col: "slug_construct"})
    if "slug_construct" not in df.columns:
        print("Missing slug_construct column")
        return 1
    df["slug_construct"] = df["slug_construct"].fillna("").astype(str).str.strip()
    if "mfapi_name_cleaned" not in df.columns:
        for c in df.columns:
            if "name" in c.lower():
                df["mfapi_name_cleaned"] = df[c]
                break

    print("Building slug index (listings + fund_master_auto)…")
    idx = build_slug_index()
    print(f"  {len(idx)} slugs indexed")

    results: list[dict] = []
    n = len(df) if not args.limit else min(args.limit, len(df))

    for _, row in df.head(n).iterrows():
        mf_code = int(row["mf_scheme_code"])
        mf_name = str(row.get("mfapi_name_cleaned") or "")
        slug = str(row["slug_construct"]).strip()

        if not slug or slug.lower() in ("nan", "none"):
            results.append(
                {
                    "mf_scheme_code": mf_code,
                    "mfapi_name_cleaned": mf_name,
                    "slug_construct": "",
                    "et_slug": "",
                    "et_scheme_id": "",
                    "validation": "no_et_page",
                    "reason": "blank slug",
                    "et_fund_name": "",
                    "name_match_pct": "",
                    "portfolio_status": "",
                    "holdings_rows": "",
                }
            )
            continue

        user_slug = slug
        mf_cat = str(row.get("mf_category") or "")
        resolved = resolve_for_scrape(mf_name, mf_cat, user_slug, idx)
        if not resolved:
            results.append(
                {
                    "mf_scheme_code": mf_code,
                    "mfapi_name_cleaned": mf_name,
                    "slug_construct": slug,
                    "et_slug": "",
                    "et_scheme_id": "",
                    "validation": "slug_not_found",
                    "reason": "could not resolve scheme_id",
                    "et_fund_name": "",
                    "name_match_pct": "",
                    "portfolio_status": "",
                    "holdings_rows": "",
                }
            )
            continue

        use_slug, sid, resolve_via = resolved
        rec = validate_row(mf_code, mf_name, use_slug, sid, quick=args.quick)
        rec["slug_construct"] = user_slug
        rec["et_slug"] = use_slug
        rec["resolve_via"] = resolve_via
        rec["user_slug_ok"] = _slugs_equivalent(user_slug, use_slug)
        results.append(rec)
        if not args.quick and args.delay > 0:
            time.sleep(args.delay)

    out = pd.DataFrame(results)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    total = len(out)
    blank = int((out["validation"] == "no_et_page").sum())
    with_slug = total - blank
    resolved_n = int(out["validation"].isin(["ok", "review", "resolved"]).sum())
    ok = int((out["validation"] == "ok").sum())
    review = int((out["validation"] == "review").sum())
    not_found = int((out["validation"] == "slug_not_found").sum())

    scrape_ready = out[out["validation"].isin(["ok", "review", "resolved"])]
    if not scrape_ready.empty:
        slug_col = "et_slug" if "et_slug" in scrape_ready.columns else "slug_construct"
        hints = scrape_ready[["mf_scheme_code", slug_col, "et_scheme_id"]].copy()
        hints.columns = ["mf_scheme_code", "et_slug", "et_scheme_id"]
        hints["notes"] = "slug_construct validated"
        hints = hints[hints["et_scheme_id"].astype(str).str.strip() != ""]
        hints["et_scheme_id"] = hints["et_scheme_id"].astype(int)
        if HINTS_CSV.is_file():
            prev = pd.read_csv(HINTS_CSV, encoding="utf-8-sig")
            hints = (
                pd.concat([prev, hints], ignore_index=True)
                .drop_duplicates(subset=["mf_scheme_code"], keep="last")
                .sort_values("mf_scheme_code")
            )
        hints.to_csv(HINTS_CSV, index=False, encoding="utf-8-sig")

    print("\n=== Summary ===")
    print(f"Total rows:                 {total}")
    print(f"No ET page (blank slug):    {blank}")
    print(f"With slug provided:         {with_slug}")
    print(f"Resolved slug -> scheme_id: {resolved_n}")
    print(f"  confirmed scrape-ready:   {ok}")
    print(f"  review (name/portfolio):  {review}")
    print(f"Slug not resolved:          {not_found}")
    print(f"\nCan scrape (resolved):      {resolved_n}")
    print(f"Wrote {OUT_CSV}")
    if not scrape_ready.empty:
        print(f"Wrote hints -> {HINTS_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
