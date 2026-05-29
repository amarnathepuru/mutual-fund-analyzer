"""Data integrity checks for mutual-fund-analyzer datasets."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROC = DATA / "processed"

BATCH2_CATS = {
    "Large Cap Index", "Mid Cap Index", "Small Cap Index", "International",
    "Aggressive Hybrid", "Balanced Hybrid", "Arbitrage",
    "Dynamic Asset Allocation", "Multi Asset Allocation",
    "Sectoral Banking", "Sectoral Technology",
}
ORIGINAL_CATS = {
    "Large Cap", "Large & Mid Cap", "Mid Cap", "Small Cap",
    "Multi Cap", "Flexi Cap", "ELSS",
}
STALE_RISK = (0.4249, -1.9646, 0.8908, 14.7342)  # old category-benchmark fingerprint


def ok(msg: str) -> None:
    print(f"  OK  {msg}")


def warn(msg: str) -> None:
    print(f"  WARN {msg}")


def fail(msg: str) -> None:
    print(f"  FAIL {msg}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    issues = 0

    print("=" * 60)
    print("DATA VERIFICATION REPORT")
    print("=" * 60)

    # ── Load ─────────────────────────────────────────────────────
    master = pd.read_csv(DATA / "fund_master_auto.csv")
    invalid = pd.read_csv(DATA / "fund_master_invalid.csv")
    holdings = pd.read_csv(PROC / "master_holdings.csv")
    norm = pd.read_csv(PROC / "normalized_holdings.csv")
    sim = pd.read_csv(PROC / "simplicity_engine.csv") if False else pd.read_csv(PROC / "fund_similarity.csv")

    active = master[master["status"] == "ACTIVE"].copy()
    n = len(active)
    print(f"\n[1] fund_master_auto.csv — {len(master)} rows, {n} ACTIVE\n")

    # Required columns
    req = ["fund_name", "category", "scheme_id", "url", "status"]
    missing_cols = [c for c in req if c not in master.columns]
    if missing_cols:
        fail(f"Missing columns: {missing_cols}")
        issues += 1
    else:
        ok("Required columns present")

    # Uniqueness
    dup_names = active[active.duplicated("fund_name", keep=False)]["fund_name"].unique()
    dup_sids = active[active.duplicated("scheme_id", keep=False)]["scheme_id"].unique()
    if len(dup_names):
        fail(f"Duplicate fund_name: {list(dup_names)[:5]}")
        issues += 1
    else:
        ok("fund_name unique among ACTIVE")
    if len(dup_sids):
        fail(f"Duplicate scheme_id: {list(dup_sids)[:5]}")
        issues += 1
    else:
        ok("scheme_id unique among ACTIVE")

    # URL / portfolio link
    bad_url = active[~active["url"].astype(str).str.contains("portfolio-details", na=False)]
    if len(bad_url):
        fail(f"{len(bad_url)} ACTIVE funds without portfolio-details URL")
        issues += 1
    else:
        ok("All ACTIVE urls point to portfolio-details")

    # Categories
    cats = set(active["category"].unique())
    unexpected = cats - ORIGINAL_CATS - BATCH2_CATS
    if unexpected:
        warn(f"Unexpected categories: {unexpected}")
    ok(f"Categories: {len(cats)} ({', '.join(sorted(cats)[:5])}...)")

    print("\n  Per-category ACTIVE counts:")
    for cat, cnt in active.groupby("category").size().sort_values(ascending=False).items():
        tag = "batch2" if cat in BATCH2_CATS else "orig"
        print(f"    {cat:<28} {cnt:>4}  [{tag}]")

    # Performance / risk coverage
    for col in ["return_1y", "sharpe_ratio", "expense_ratio", "star_rating"]:
        if col in active.columns:
            filled = active[col].notna().sum()
            pct = 100 * filled / n
            if pct < 30 and col in ("return_1y",):
                warn(f"{col}: only {filled}/{n} ({pct:.0f}%) filled")
            else:
                ok(f"{col}: {filled}/{n} ({pct:.0f}%) filled")

    # Stale benchmark fingerprint
    if all(c in active.columns for c in ["sharpe_ratio", "alpha", "beta", "std_dev"]):
        stale = active[
            (active["sharpe_ratio"].round(4) == STALE_RISK[0])
            & (active["alpha"].round(4) == STALE_RISK[1])
            & (active["beta"].round(4) == STALE_RISK[2])
            & (active["std_dev"].round(4) == STALE_RISK[3])
        ]
        if len(stale):
            fail(f"{len(stale)} funds still have stale category-benchmark risk metrics")
            issues += 1
        else:
            ok("No stale duplicate benchmark risk fingerprint")

    # Risk diversity within a category (Large Cap Index sample)
    lci = active[active["category"] == "Large Cap Index"].dropna(subset=["sharpe_ratio"])
    if len(lci) >= 5:
        uniq_sharpe = lci["sharpe_ratio"].nunique()
        if uniq_sharpe < 3:
            fail(f"Large Cap Index: only {uniq_sharpe} unique sharpe values (likely bad scrape)")
            issues += 1
        else:
            ok(f"Large Cap Index: {uniq_sharpe} distinct sharpe values among {len(lci)} funds")

    print(f"\n[2] fund_master_invalid.csv — {len(invalid)} rows\n")
    if invalid["status"].isin(["NO_HOLDINGS", "ERROR"]).all():
        ok("All invalid rows are NO_HOLDINGS or ERROR")
    else:
        warn(f"Status values: {invalid['status'].unique().tolist()}")

    overlap_inv = set(invalid["scheme_id"]) & set(active["scheme_id"])
    if overlap_inv:
        fail(f"{len(overlap_inv)} scheme_ids in both ACTIVE and invalid")
        issues += 1
    else:
        ok("No scheme_id overlap between ACTIVE and invalid")

    print(f"\n[3] master_holdings.csv — {len(holdings)} rows, {holdings['fund_name'].nunique()} funds\n")

    hold_funds = set(holdings["fund_name"].unique())
    active_funds = set(active["fund_name"].unique())
    missing_hold = active_funds - hold_funds
    extra_hold = hold_funds - active_funds
    if missing_hold:
        fail(f"{len(missing_hold)} ACTIVE funds missing from holdings")
        for f in sorted(missing_hold)[:8]:
            print(f"      - {f}")
        issues += 1
    else:
        ok("Every ACTIVE fund has holdings")
    if extra_hold:
        warn(f"{len(extra_hold)} funds in holdings but not ACTIVE master")

    # Allocation sanity per fund
    totals = holdings.groupby("fund_name")["allocation_percent"].sum()
    bad_low = totals[totals < 50]
    bad_high = totals[totals > 105]
    if len(bad_low):
        warn(f"{len(bad_low)} funds with allocation sum < 50% (top: {bad_low.head(3).to_dict()})")
    else:
        ok("No funds with allocation sum < 50%")
    if len(bad_high):
        warn(f"{len(bad_high)} funds with allocation sum > 105%")
    else:
        ok("No funds with allocation sum > 105%")

    med = totals.median()
    ok(f"Median allocation sum per fund: {med:.1f}%")

    empty_stocks = holdings[holdings["stock_name"].isna() | (holdings["stock_name"].astype(str).str.strip() == "")]
    if len(empty_stocks):
        fail(f"{len(empty_stocks)} rows with empty stock_name")
        issues += 1
    else:
        ok("No empty stock_name rows")

    dup_hold = holdings.duplicated(subset=["fund_name", "stock_name"]).sum()
    if dup_hold:
        warn(f"{dup_hold} duplicate fund+stock rows in holdings")
    else:
        ok("No duplicate fund+stock in holdings")

    print(f"\n[4] normalized_holdings.csv — {len(norm)} rows\n")
    if len(norm) != len(holdings):
        warn(f"Row count differs from master_holdings ({len(holdings)} vs {len(norm)})")
    else:
        ok("Row count matches master_holdings")
    if set(norm["fund_name"].unique()) == hold_funds:
        ok("Fund set matches master_holdings")
    else:
        fail("Fund set mismatch vs master_holdings")
        issues += 1

    print(f"\n[5] fund_similarity.csv — {len(sim)} pairs\n")
    expected_pairs = n * (n - 1) // 2
    if len(sim) != expected_pairs:
        fail(f"Expected {expected_pairs} pairs for {n} funds, got {len(sim)}")
        issues += 1
    else:
        ok(f"Pair count correct: {expected_pairs}")

    sim_funds = set(sim["fund_a"].unique()) | set(sim["fund_b"].unique())
    if sim_funds != active_funds:
        only_sim = sim_funds - active_funds
        only_act = active_funds - sim_funds
        if only_act:
            fail(f"{len(only_act)} ACTIVE funds missing from similarity matrix")
            issues += 1
        if only_sim:
            fail(f"{len(only_sim)} funds in similarity but not ACTIVE")
            issues += 1
    else:
        ok("Similarity matrix covers exactly ACTIVE fund set")

    for col in ["similarity_score", "normalized_score"]:
        if col in sim.columns:
            s = pd.to_numeric(sim[col], errors="coerce")
            if s.isna().any():
                warn(f"{col}: {s.isna().sum()} NaN values")
            if col == "similarity_score" and (s > 100).any():
                warn(f"{col}: raw weighted score can exceed 100 ({int((s > 100).sum())} rows); use normalized_score for UI")
            elif (s < 0).any() or (s > 100).any():
                bad = int(((s < 0) | (s > 100)).sum())
                warn(f"{col}: {bad} values outside 0–100")
            else:
                ok(f"{col} in range 0–100")

    if "common_stocks" in sim.columns:
        cs = sim["common_stocks"]
        neg = (cs < 0).sum()
        if neg:
            fail(f"{neg} pairs with negative common_stocks")
            issues += 1
        else:
            ok("common_stocks non-negative")

    # One row per undirected pair (no A,B and B,A duplicates)
    undirected = sim.apply(
        lambda r: tuple(sorted((r["fund_a"], r["fund_b"]))), axis=1
    )
    if undirected.duplicated().any():
        fail(f"{int(undirected.duplicated().sum())} duplicate undirected pairs")
        issues += 1
    else:
        ok("Each fund pair appears once (undirected)")

    print(f"\n[6] fund_scheme_map.csv (ET ↔ MFAPI bridge)\n")
    map_path = DATA / "fund_scheme_map.csv"
    if not map_path.is_file():
        warn("Missing fund_scheme_map.csv — run apply_et_mfapi_map.py after review")
    else:
        smap = pd.read_csv(map_path)
        print(f"  Rows: {len(smap)}")
        if smap.duplicated("scheme_id").any():
            fail(f"{int(smap.duplicated('scheme_id').sum())} duplicate scheme_id in map")
            issues += 1
        else:
            ok("scheme_id unique in fund_scheme_map")
        if "mf_scheme_code" in smap.columns:
            dup_mf = smap[smap.duplicated("mf_scheme_code", keep=False)]
            if len(dup_mf):
                fail(
                    f"{dup_mf['mf_scheme_code'].nunique()} duplicate mf_scheme_code pairs "
                    f"({len(dup_mf)} rows)"
                )
                issues += 1
            else:
                ok("mf_scheme_code unique in fund_scheme_map")
            nav_db = DATA / "nav" / "nav.db"
            if nav_db.is_file():
                import sqlite3

                conn = sqlite3.connect(nav_db)
                try:
                    nav_codes = set(
                        pd.read_sql_query(
                            "SELECT mf_scheme_code FROM schemes", conn
                        )["mf_scheme_code"].astype(int)
                    )
                finally:
                    conn.close()
                bad = smap[~smap["mf_scheme_code"].astype(int).isin(nav_codes)]
                if len(bad):
                    fail(f"{len(bad)} map codes not found in nav.db")
                    issues += 1
                else:
                    ok("All mapped mf_scheme_code values exist in nav.db")
            else:
                warn("nav.db not found — skipped NAV code check")
        mapped_ids = set(smap["scheme_id"].astype(int)) if "scheme_id" in smap.columns else set()
        non_index = active[~active["category"].astype(str).str.contains("Index", case=False, na=False)]
        unmapped = set(non_index["scheme_id"].astype(int)) - mapped_ids
        if len(unmapped) > 30:
            warn(f"{len(unmapped)} non-index ACTIVE ET funds not in scheme map")
        else:
            ok(f"{len(mapped_ids)} ET funds mapped; {len(unmapped)} non-index ACTIVE without map")

    print(f"\n[7] Cross-file category consistency\n")
    m_cat = active.set_index("fund_name")["category"]
    h_cat = holdings.groupby("fund_name")["category"].first()
    mismatch = []
    for fn in active_funds & set(h_cat.index):
        if m_cat.get(fn) != h_cat.get(fn):
            mismatch.append(fn)
    if mismatch:
        fail(f"{len(mismatch)} funds with category mismatch master vs holdings")
        for f in mismatch[:5]:
            print(f"      {f}: master={m_cat.get(f)} holdings={h_cat.get(f)}")
        issues += 1
    else:
        ok("Category labels consistent (master vs holdings)")

    print("\n" + "=" * 60)
    if issues == 0:
        print("RESULT: PASS — no critical failures")
    else:
        print(f"RESULT: {issues} CRITICAL FAILURE(S) — review FAIL lines above")
    print("=" * 60)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
