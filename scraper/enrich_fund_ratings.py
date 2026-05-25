"""
enrich_fund_ratings.py
----------------------
Fetches the return-analysis page for each fund in fund_master_auto.csv and
extracts publicly available ratings and performance data from ET Money:

  - return_1y, return_3y, return_5y   : trailing returns (%)
  - consistency_score                  : ET Money consistency rating (1–5)
  - category_rank                      : rank within the fund's category
  - sharpe_ratio, alpha, beta          : risk metrics (3-year)
  - std_dev                            : annualised standard deviation

Usage:
  python -X utf8 scraper/enrich_fund_ratings.py

Output:
  data/fund_master_auto.csv  (updated in-place with new columns)
"""

import re
import sys
import json
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "https://www.etmoney.com"
HEADERS  = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

DELAY = 1.2   # seconds between requests

# Duration keys used in ET Money's return data
DUR_1Y = "365"
DUR_3Y = "1095"
DUR_5Y = "1825"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get(url: str) -> requests.Response | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        return r
    except requests.RequestException as exc:
        print(f"  [ERR] {exc}")
        return None


def _extract_js_var(content: str, var_name: str) -> dict | None:
    """Pull a JavaScript variable assignment of the form var foo = {...}; out of page source."""
    pattern = rf"var\s+{re.escape(var_name)}\s*=\s*(\{{.*?\}});"
    m = re.search(pattern, content, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _find_fund_in_returns(duration_data: list, scheme_id: int) -> dict | None:
    """Find this fund's entry in the list of all-category returns for a duration."""
    for entry in duration_data:
        if int(entry.get("schemeId", -1)) == scheme_id:
            return entry
    return None


def _extract_report_card_data(content: str) -> dict:
    """Parse reportCardData JSON blob keyed by scheme_id (string keys)."""
    marker = '"reportCardData":'
    idx = content.find(marker)
    if idx < 0:
        return {}
    start = content.find("{", idx)
    if start < 0:
        return {}
    depth = 0
    for j in range(start, min(start + 120_000, len(content))):
        ch = content[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(content[start : j + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


# ── Core fetch ─────────────────────────────────────────────────────────────────

def fetch_ratings(slug: str, scheme_id: int) -> dict:
    """
    Fetch the return-analysis page and extract:
      return_1y, return_3y, return_5y,
      consistency_score, category_rank,
      sharpe_ratio, alpha, beta, std_dev
    Returns a dict with None for any field that could not be extracted.
    """
    result = {
        "return_1y":             None,
        "return_3y":             None,
        "return_5y":             None,
        "return_since_inception": None,
        "consistency_score":     None,
        "category_rank":         None,
        "sharpe_ratio":          None,
        "alpha":                 None,
        "beta":                  None,
        "std_dev":               None,
    }

    url = f"{BASE_URL}/mutual-funds/{slug}/return-analysis/{scheme_id}"
    r = _get(url)
    if r is None or r.status_code != 200:
        print(f"  [SKIP] HTTP {getattr(r, 'status_code', 'N/A')}")
        return result

    content = r.text

    # ── Trailing returns + consistency + rank ─────────────────────────────────
    trailing = _extract_js_var(content, "getTrailingReturnData")
    if trailing:
        duration_map = (
            trailing
            .get("mfCategoryReturnDTO", {})
            .get("directReturnsByDuration", {})
        )

        for dur_key, return_field in [
            (DUR_1Y, "return_1y"),
            (DUR_3Y, "return_3y"),
            (DUR_5Y, "return_5y"),
        ]:
            entries = duration_map.get(dur_key, [])
            entry   = _find_fund_in_returns(entries, scheme_id)
            if entry:
                val = entry.get("mfReturn")
                if val is not None:
                    result[return_field] = round(float(val), 2)
                # Consistency score and rank are the same across durations;
                # take from the first duration that has a match
                if result["consistency_score"] is None:
                    cs = entry.get("consistencyScore")
                    if cs is not None:
                        result["consistency_score"] = int(cs)
                if result["category_rank"] is None:
                    rk = entry.get("rank")
                    if rk is not None:
                        result["category_rank"] = int(rk)

    # ── Risk metrics (per-fund via reportCardData[scheme_id]) ────────────────
    report_cards = _extract_report_card_data(content)
    card = report_cards.get(str(scheme_id)) or report_cards.get(scheme_id)
    if card:
        if card.get("standardDeviation") is not None:
            result["std_dev"] = round(float(card["standardDeviation"]), 4)
        if card.get("sharpeRatio") is not None:
            result["sharpe_ratio"] = round(float(card["sharpeRatio"]), 4)
        if card.get("alpha") is not None:
            result["alpha"] = round(float(card["alpha"]), 4)
        if card.get("beta") is not None:
            result["beta"] = round(float(card["beta"]), 4)

    # ── Return since inception ────────────────────────────────────────────────
    si_match = re.search(r'"returnSinceInception"\s*:\s*([-\d.]+)', content)
    if si_match:
        result["return_since_inception"] = round(float(si_match.group(1)), 2)

    return result


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    master_path = "data/fund_master_auto.csv"
    df = pd.read_csv(master_path)
    active = df[df["status"] == "ACTIVE"].copy()

    if "--missing-only" in sys.argv:
        need_cols = ["return_1y", "sharpe_ratio"]
        mask = pd.Series(False, index=active.index)
        for col in need_cols:
            if col in active.columns:
                mask = mask | active[col].isna()
            else:
                mask = pd.Series(True, index=active.index)
        active = active[mask].copy()
        print(f"Missing-only mode: {len(active)} funds need enrichment")

    print(f"Enriching {len(active)} active funds with ratings and returns...\n")

    # Build slug from url column  (url = https://...etmoney.com/mutual-funds/{slug}/portfolio-details/{id})
    def _slug_from_url(url: str) -> str:
        parts = str(url).split("/mutual-funds/")
        if len(parts) < 2:
            return ""
        return parts[1].split("/")[0]

    active["_slug"] = active["url"].apply(_slug_from_url)

    rows = []
    for i, (_, fund) in enumerate(active.iterrows(), 1):
        slug      = fund["_slug"]
        scheme_id = int(fund["scheme_id"])
        print(f"[{i:>3}/{len(active)}] {fund['fund_name'][:55]}")

        ratings = fetch_ratings(slug, scheme_id)

        summary = (
            f"  1Y={ratings['return_1y']}% "
            f"3Y={ratings['return_3y']}% "
            f"5Y={ratings['return_5y']}% "
            f"consistency={ratings['consistency_score']} "
            f"rank={ratings['category_rank']} "
            f"sharpe={ratings['sharpe_ratio']}"
        )
        print(summary)

        rows.append({"scheme_id": scheme_id, **ratings})
        time.sleep(DELAY)

    ratings_df = pd.DataFrame(rows)

    # Merge back into master
    df = df.merge(
        ratings_df,
        on="scheme_id",
        how="left",
        suffixes=("", "_new")
    )

    # Merge new values without wiping existing data for funds not in this run
    for col in ["return_1y","return_3y","return_5y",
                "consistency_score","category_rank",
                "sharpe_ratio","alpha","beta","std_dev"]:
        new_col = f"{col}_new"
        if new_col in df.columns:
            if col in df.columns:
                df[col] = df[new_col].combine_first(df[col])
            else:
                df[col] = df[new_col]
            df.drop(columns=[new_col], inplace=True)

    df.to_csv(master_path, index=False)

    enriched = ratings_df.dropna(subset=["return_1y"])
    print(f"\nDone. {len(enriched)}/{len(active)} funds enriched with returns data.")
    print(f"Saved to {master_path}")


if __name__ == "__main__":
    main()
