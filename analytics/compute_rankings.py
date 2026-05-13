"""
compute_rankings.py
-------------------
Computes category-level rankings from the enriched fund_master_auto.csv
and adds:

  rank_3y   : rank within category by 3Y return (1 = best)
  rank_1y   : rank within category by 1Y return
  rating    : 1–5 star rating based on rank percentile within category

Run after enrich_fund_ratings.py:
  python analytics/compute_rankings.py
"""

import pandas as pd

MASTER_PATH = "data/fund_master_auto.csv"


def percentile_rating(rank: int, total: int) -> int:
    """Convert a 1-based rank out of total to a 1–5 star rating.
    Top 10% → 5 stars, next 22.5% → 4, next 35% → 3, next 22.5% → 2, bottom 10% → 1.
    Follows the standard CRISIL / Value Research percentile band.
    """
    if total <= 0 or pd.isna(rank):
        return None
    pct = rank / total          # 0 → best, 1 → worst
    if pct <= 0.10:
        return 5
    elif pct <= 0.325:
        return 4
    elif pct <= 0.675:
        return 3
    elif pct <= 0.90:
        return 2
    else:
        return 1


def main():
    df = pd.read_csv(MASTER_PATH)
    active = df["status"] == "ACTIVE"

    for period, col_return, col_rank in [
        ("3Y", "return_3y", "rank_3y"),
        ("1Y", "return_1y", "rank_1y"),
    ]:
        df[col_rank] = None
        for cat, grp in df[active].groupby("category"):
            valid = grp.dropna(subset=[col_return])
            if valid.empty:
                continue
            ranked = valid[col_return].rank(ascending=False, method="min")
            df.loc[ranked.index, col_rank] = ranked.astype(int)

    # Star rating: based on 3Y rank (fall back to 1Y if 3Y unavailable)
    df["star_rating"] = None
    for cat, grp in df[active].groupby("category"):
        cat_total = len(grp.dropna(subset=["return_3y"]))
        for idx, row in grp.iterrows():
            rank = row.get("rank_3y")
            total = cat_total
            if pd.isna(rank) or rank is None:
                rank  = row.get("rank_1y")
                total = len(grp.dropna(subset=["return_1y"]))
            if rank is not None and not pd.isna(rank) and total > 0:
                df.at[idx, "star_rating"] = percentile_rating(int(rank), total)

    df.to_csv(MASTER_PATH, index=False)

    # Summary
    print("Rankings computed.\n")
    print("Star rating distribution:")
    print(df[active]["star_rating"].value_counts().sort_index().to_string())
    print()
    print("Sample (top 10 by 3Y return):")
    sample = (
        df[active]
        .dropna(subset=["return_3y"])
        .nlargest(10, "return_3y")[
            ["fund_name", "category", "return_1y", "return_3y",
             "return_5y", "rank_3y", "star_rating", "consistency_score"]
        ]
    )
    print(sample.to_string(index=False))
    print(f"\nSaved to {MASTER_PATH}")


if __name__ == "__main__":
    main()
