"""
discover_funds.py
-----------------
Automatically discover mutual funds from ET Money category listing pages,
extract fund metadata, and validate that each fund's portfolio-details page
actually has holdings data before including it in fund_master_auto.csv.

Usage:
  python -X utf8 scraper/discover_funds.py                  # all 7 categories (replaces master)
  python -X utf8 scraper/discover_funds.py --batch2          # Tier 1+2 expansion (merges into master)
  python -X utf8 scraper/discover_funds.py --large-cap-only # Large Cap only (fast validation)
  python -X utf8 scraper/discover_funds.py --validate       # also compare vs fund_master.csv

Output:
  data/fund_master_auto.csv   — all funds with valid portfolio links (status=ACTIVE)
  data/fund_master_invalid.csv — funds where portfolio link returned no holdings
"""

import requests
import re
import json
import sys
import time
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime

# ── Config ─────────────────────────────────────────────────────────────────────

BASE_URL = "https://www.etmoney.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Category name -> ET Money listing page path
CATEGORIES = {
    "Large Cap":      "/mutual-funds/equity/large-cap/32",
    "Large & Mid Cap":"/mutual-funds/equity/large-and-midcap/33",
    "Mid Cap":        "/mutual-funds/equity/mid-cap/35",
    "Small Cap":      "/mutual-funds/equity/small-cap/36",
    "Multi Cap":      "/mutual-funds/equity/multi-cap/34",
    "Flexi Cap":      "/mutual-funds/equity/flexi-cap/79",
    "ELSS":           "/mutual-funds/equity/elss/38",
}

# Batch 2 — Tier 1 (index, hybrid, international) + Tier 2 (allocation, sectoral)
BATCH2_CATEGORIES = {
    "Large Cap Index":          "/mutual-funds/equity/large-cap-index/99",
    "Mid Cap Index":            "/mutual-funds/equity/mid-cap-index/100",
    "Small Cap Index":          "/mutual-funds/equity/small-cap-index/101",
    "International":            "/mutual-funds/equity/international/50",
    "Aggressive Hybrid":        "/mutual-funds/hybrid/aggressive-hybrid/68",
    "Balanced Hybrid":          "/mutual-funds/hybrid/balanced-hybrid/69",
    "Arbitrage":                "/mutual-funds/hybrid/arbitrage/73",
    "Dynamic Asset Allocation": "/mutual-funds/hybrid/dynamic-asset-allocation/74",
    "Multi Asset Allocation":   "/mutual-funds/hybrid/multi-asset-allocation/75",
    "Sectoral Banking":         "/mutual-funds/equity/sectoral-banking/39",
    "Sectoral Technology":      "/mutual-funds/equity/sectoral-technology/43",
}

# Matches /mutual-funds/{slug}/{scheme_id}  (no further path segments)
FUND_LINK_RE = re.compile(r"^/mutual-funds/([a-z0-9\-]+)/(\d+)$")

# Acronyms to keep uppercased during fund-house title-casing
_ACRONYMS = {
    "hdfc", "icici", "sbi", "uti", "dsp", "lic", "mf", "amc",
    "bnp", "pgim", "iti", "hsbc", "jm", "nj", "ppfas",
}

DELAY_BETWEEN_FUNDS   = 1.5   # seconds between fund detail + portfolio fetches
DELAY_BETWEEN_REQS    = 0.8   # seconds between detail page and portfolio page for same fund

# Portfolio statuses
STATUS_ACTIVE      = "ACTIVE"        # portfolio-details has holdings rows
STATUS_NO_HOLDINGS = "NO_HOLDINGS"   # page loads but no holdings table found
STATUS_ERROR       = "ERROR"         # HTTP error or timeout


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get(url: str, timeout: int = 20) -> requests.Response | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        return r
    except requests.RequestException as exc:
        print(f"\n    [ERR] {url}: {exc}", end="")
        return None


def _normalize_fund_house(raw: str) -> str:
    """Title-case the fund house string, preserving known acronyms."""
    words = raw.strip().title().split()
    return " ".join(w.upper() if w.lower() in _ACRONYMS else w for w in words)


def _parse_date(raw: str) -> str | None:
    """Convert DD/MM/YYYY -> YYYY-MM-DD; pass YYYY-MM-DD through unchanged."""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw.strip() or None


# ── Step 1 : Listing page ──────────────────────────────────────────────────────

def scrape_listing_page(category: str, path: str) -> list[dict]:
    """
    Fetch a category listing page and return fund stubs:
    [{slug, scheme_id, category}, ...]

    Scopes to div#fundListing to exclude sidebar / popular-fund widgets.
    """
    url = BASE_URL + path
    r = _get(url)
    if r is None or r.status_code != 200:
        print(f"  WARNING: {category} listing returned "
              f"{getattr(r, 'status_code', 'N/A')}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # #fundListing is the main fund table; anything outside is sidebar noise
    container = soup.find("div", id="fundListing")
    if container is None:
        container = soup
        print(f"  WARNING: #fundListing not found for {category} — searching full page")

    seen: set[int] = set()
    funds: list[dict] = []

    for a in container.find_all("a", href=True):
        m = FUND_LINK_RE.match(a["href"])
        if m:
            sid = int(m.group(2))
            if sid not in seen:
                seen.add(sid)
                funds.append({
                    "slug":      m.group(1),
                    "scheme_id": sid,
                    "category":  category,
                })

    return funds


# ── Step 2 : Fund detail metadata ─────────────────────────────────────────────

def scrape_fund_detail(stub: dict) -> dict | None:
    """
    Fetch the fund's overview page and extract:
      fund_name, fund_house, benchmark, launch_date, aum_cr, expense_ratio

    Returns None if the page cannot be fetched or parsed.
    """
    slug      = stub["slug"]
    scheme_id = stub["scheme_id"]
    category  = stub["category"]

    url = f"{BASE_URL}/mutual-funds/{slug}/{scheme_id}"
    r = _get(url)
    if r is None or r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    # Fund name: JSON-LD InvestmentFund schema is most reliable
    fund_name = None
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "")
            if isinstance(data, dict) and data.get("@type") == "InvestmentFund":
                fund_name = data.get("name")
                break
        except (json.JSONDecodeError, TypeError):
            pass
    if not fund_name:
        title_tag = soup.find("title")
        if title_tag:
            fund_name = re.sub(r"\s*[:|].+$", "", title_tag.text).strip()

    # Build flat text for regex extraction
    lines = [l.strip() for l in soup.get_text(separator="\n", strip=True).split("\n") if l.strip()]
    flat  = " ".join(lines)

    # Benchmark: the label "Benchmark" appears as its own line; value follows
    benchmark = None
    for i, line in enumerate(lines):
        if line == "Benchmark" and i + 1 < len(lines):
            bm = lines[i + 1].strip()
            if bm and bm != "Benchmark":
                benchmark = bm
            break

    # Fund house: overview paragraph "… mutual fund scheme from <FundHouse>"
    fh_match = re.search(
        r"mutual fund scheme from\s+([\w][^\.,]+?(?:Mutual Fund|Asset Management(?:\s+Company)?|AMC))",
        flat, re.IGNORECASE,
    )
    fund_house = _normalize_fund_house(fh_match.group(1)) if fh_match else None

    # Launch date: "launched on DD/MM/YYYY"
    ld_match = re.search(r"launched on\s+([\d/]+)", flat, re.IGNORECASE)
    launch_date = _parse_date(ld_match.group(1)) if ld_match else None

    # AUM: "NN,NNN Crores worth of assets under management"
    aum_match = re.search(
        r"([\d,]+)\s*Crore[s]?\s*worth of assets under management", flat, re.IGNORECASE
    )
    if not aum_match:
        aum_match = re.search(r"valued at approximately\s*([\d,]+)\s*Cr", flat, re.IGNORECASE)
    aum_cr = int(aum_match.group(1).replace(",", "")) if aum_match else None

    # Expense ratio: "expense ratio of N.NN%"
    er_match = re.search(r"expense ratio of\s+([\d.]+)%", flat, re.IGNORECASE)
    expense_ratio = float(er_match.group(1)) if er_match else None

    return {
        "fund_name":     fund_name,
        "category":      category,
        "fund_house":    fund_house,
        "scheme_id":     scheme_id,
        "slug":          slug,
        "benchmark":     benchmark,
        "aum_cr":        aum_cr,
        "expense_ratio": expense_ratio,
        "launch_date":   launch_date,
    }


# ── Step 3 : Portfolio link validation ────────────────────────────────────────

def validate_portfolio_url(slug: str, scheme_id: int) -> tuple[str, str, int]:
    """
    Fetch the portfolio-details page and check that it has an equity holdings
    table with at least one data row.

    Returns: (status, portfolio_url, row_count)
      status = ACTIVE | NO_HOLDINGS | ERROR
    """
    portfolio_url = f"{BASE_URL}/mutual-funds/{slug}/portfolio-details/{scheme_id}"
    r = _get(portfolio_url)

    if r is None or r.status_code != 200:
        return STATUS_ERROR, portfolio_url, 0

    soup     = BeautifulSoup(r.text, "html.parser")
    section  = soup.find("div", class_="portfolio-stk-section")
    if section is None:
        return STATUS_NO_HOLDINGS, portfolio_url, 0

    table = section.find("table")
    if table is None:
        return STATUS_NO_HOLDINGS, portfolio_url, 0

    tbody = table.find("tbody")
    rows  = (tbody or table).find_all("tr")
    data_rows = [row for row in rows if len(row.find_all("td")) >= 3]

    if not data_rows:
        return STATUS_NO_HOLDINGS, portfolio_url, 0

    return STATUS_ACTIVE, portfolio_url, len(data_rows)


# ── Validation vs existing CSV ────────────────────────────────────────────────

def validate_against_existing(auto_df: pd.DataFrame) -> None:
    """Compare auto-discovered funds against the hand-maintained fund_master.csv."""
    try:
        existing = pd.read_csv("data/fund_master.csv")
    except FileNotFoundError:
        print("  fund_master.csv not found -- skipping comparison")
        return

    existing_ids = set(existing["scheme_id"].astype(int))
    auto_ids     = set(auto_df["scheme_id"].astype(int))

    found   = existing_ids & auto_ids
    missing = existing_ids - auto_ids
    new_    = auto_ids    - existing_ids

    print(f"\n{'='*60}")
    print("COMPARISON vs existing fund_master.csv")
    print(f"{'='*60}")
    print(f"  Existing (manual)  : {len(existing_ids)}")
    print(f"  Auto-discovered    : {len(auto_ids)}")
    print(f"  Matched            : {len(found)}")

    if missing:
        print(f"\n  NOT found in auto-discovery ({len(missing)}):")
        for sid in sorted(missing):
            row = existing[existing["scheme_id"] == sid].iloc[0]
            print(f"    - {row['fund_name']}  (scheme_id={sid})")
    else:
        print("  All existing funds matched!")

    if new_:
        print(f"\n  Newly discovered funds ({len(new_)}):")
        for sid in sorted(list(new_))[:15]:
            row = auto_df[auto_df["scheme_id"] == sid].iloc[0]
            print(f"    + {row['fund_name']}  [{row['category']}]  (scheme_id={sid})")
        if len(new_) > 15:
            print(f"    ... and {len(new_) - 15} more")

    if found:
        print(f"\n  Field differences for matched funds:")
        any_diff = False
        for sid in sorted(found):
            old = existing[existing["scheme_id"] == sid].iloc[0]
            new = auto_df[auto_df["scheme_id"] == sid].iloc[0]
            diffs = []
            for col in ["fund_name", "fund_house", "benchmark"]:
                ov = str(old.get(col, "") or "").strip()
                nv = str(new.get(col, "") or "").strip()
                if ov.lower() != nv.lower() and ov and nv:
                    diffs.append(f"    {col}: '{ov}' -> '{nv}'")
            if diffs:
                any_diff = True
                print(f"  {old['fund_name']}:")
                for d in diffs:
                    print(d)
        if not any_diff:
            print("  No field differences found!")


# ── Main ───────────────────────────────────────────────────────────────────────

def _parse_categories_arg() -> dict | None:
    """--categories 'Large Cap Index,International'"""
    for i, arg in enumerate(sys.argv):
        if arg == "--categories" and i + 1 < len(sys.argv):
            names = [n.strip() for n in sys.argv[i + 1].split(",") if n.strip()]
            pool = {**CATEGORIES, **BATCH2_CATEGORIES}
            missing = [n for n in names if n not in pool]
            if missing:
                print(f"Unknown categories: {missing}")
                print(f"Available: {sorted(pool.keys())}")
                sys.exit(1)
            return {n: pool[n] for n in names}
    return None


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    large_cap_only = "--large-cap-only" in sys.argv
    batch2_only    = "--batch2" in sys.argv
    run_compare    = "--validate" in sys.argv or large_cap_only
    merge_existing = batch2_only or "--merge" in sys.argv

    custom = _parse_categories_arg()
    if custom:
        cats_to_run = custom
        merge_existing = True
    elif large_cap_only:
        cats_to_run = {"Large Cap": CATEGORIES["Large Cap"]}
    elif batch2_only:
        cats_to_run = BATCH2_CATEGORIES
    else:
        cats_to_run = CATEGORIES

    active_funds:   list[dict] = []
    invalid_funds:  list[dict] = []

    total_funds   = 0
    total_active  = 0
    total_no_hold = 0
    total_error   = 0

    for category, path in cats_to_run.items():
        print(f"\n{'='*60}")
        print(f"[{category}]  Discovering fund list from listing page...")
        stubs = scrape_listing_page(category, path)
        print(f"  Found {len(stubs)} unique funds")

        for stub in stubs:
            total_funds += 1
            slug      = stub["slug"]
            scheme_id = stub["scheme_id"]

            print(f"\n  [{total_funds:03d}] {slug}", end="  ")

            # --- metadata ---
            detail = scrape_fund_detail(stub)
            if not detail or not detail.get("fund_name"):
                print("SKIP (metadata fetch failed)")
                total_error += 1
                time.sleep(DELAY_BETWEEN_FUNDS)
                continue

            print(f"-> {detail['fund_name']}", end="  ")

            # Small pause before the second request for this fund
            time.sleep(DELAY_BETWEEN_REQS)

            # --- portfolio validation ---
            status, portfolio_url, row_count = validate_portfolio_url(slug, scheme_id)

            aum  = f"AUM:{detail['aum_cr']:,}Cr" if detail["aum_cr"] else "AUM:N/A"
            er   = f"ER:{detail['expense_ratio']}%" if detail["expense_ratio"] else "ER:N/A"

            fund_row = {
                "fund_name":     detail["fund_name"],
                "category":      detail["category"],
                "fund_house":    detail["fund_house"],
                "scheme_id":     detail["scheme_id"],
                "url":           portfolio_url,
                "status":        status,
                "benchmark":     detail["benchmark"],
                "aum_cr":        detail["aum_cr"],
                "expense_ratio": detail["expense_ratio"],
                "launch_date":   detail["launch_date"],
                "holdings_rows": row_count,
            }

            if status == STATUS_ACTIVE:
                total_active += 1
                active_funds.append(fund_row)
                print(f"[OK  {row_count} holdings | {aum} | {er}]")
            elif status == STATUS_NO_HOLDINGS:
                total_no_hold += 1
                invalid_funds.append(fund_row)
                print(f"[NO_HOLDINGS | {aum} | {er}]")
            else:
                total_error += 1
                invalid_funds.append(fund_row)
                print(f"[PORTFOLIO ERROR]")

            time.sleep(DELAY_BETWEEN_FUNDS)

    # ── Save outputs ──
    print(f"\n{'='*60}")
    print("DISCOVERY COMPLETE")
    print(f"{'='*60}")
    print(f"  Total discovered  : {total_funds}")
    print(f"  ACTIVE (holdings) : {total_active}")
    print(f"  NO_HOLDINGS       : {total_no_hold}")
    print(f"  ERRORS            : {total_error}")

    active_df = pd.DataFrame(active_funds)
    if not active_df.empty:
        active_df = (
            active_df
            .drop(columns=["holdings_rows"], errors="ignore")
            .sort_values(["category", "fund_name"])
            .reset_index(drop=True)
        )

        if merge_existing:
            master_path = "data/fund_master_auto.csv"
            try:
                prev = pd.read_csv(master_path)
                active_df = (
                    pd.concat([prev, active_df], ignore_index=True)
                    .drop_duplicates(subset=["scheme_id"], keep="last")
                    .sort_values(["category", "fund_name"])
                    .reset_index(drop=True)
                )
                print(f"\n  Merged with existing master -> {len(active_df)} total active funds")
            except FileNotFoundError:
                print("\n  No existing fund_master_auto.csv — writing fresh file")

        active_df.to_csv("data/fund_master_auto.csv", index=False)
        print(f"\n  Saved {len(active_df)} active funds -> data/fund_master_auto.csv")

        print("\n  Breakdown by category:")
        for cat, grp in active_df.groupby("category"):
            print(f"    {cat:<28} : {len(grp)} funds")

    if invalid_funds:
        invalid_df = pd.DataFrame(invalid_funds).sort_values(["category", "fund_name"])
        invalid_path = "data/fund_master_invalid.csv"
        if merge_existing:
            try:
                prev_inv = pd.read_csv(invalid_path)
                invalid_df = (
                    pd.concat([prev_inv, invalid_df], ignore_index=True)
                    .drop_duplicates(subset=["scheme_id"], keep="last")
                    .sort_values(["category", "fund_name"])
                )
            except FileNotFoundError:
                pass
        invalid_df.to_csv(invalid_path, index=False)
        print(f"\n  Saved {len(invalid_df)} invalid funds -> data/fund_master_invalid.csv")
        print("  Invalid funds (no portfolio holdings):")
        for _, row in invalid_df.iterrows():
            print(f"    [{row['status']:<12}]  {row['fund_name']}  ({row['category']})")

    if run_compare and not active_df.empty:
        validate_against_existing(active_df)

    return active_df


if __name__ == "__main__":
    main()
