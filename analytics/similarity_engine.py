import pandas as pd
from itertools import combinations

# -----------------------------------
# LOAD NORMALIZED DATA
# -----------------------------------

df = pd.read_csv(
    "data/processed/normalized_holdings.csv"
)

print(f"\nLoaded {len(df)} rows")

# -----------------------------------
# GET UNIQUE FUNDS
# -----------------------------------

funds = df["fund_name"].unique()

print(f"Found {len(funds)} funds")

# -----------------------------------
# BUILD SIMILARITY MATRIX
# -----------------------------------

# Pre-compute total allocation per fund once (avoids repeated groupby in loop)
fund_totals = (
    df.groupby("fund_name")["allocation_percent"]
    .sum()
    .to_dict()
)

results = []

for fund_a, fund_b in combinations(funds, 2):

    # -----------------------------
    # FILTER FUNDS
    # -----------------------------

    df_a = df[
        df["fund_name"] == fund_a
    ][[
        "stock_name",
        "allocation_percent"
    ]]

    df_b = df[
        df["fund_name"] == fund_b
    ][[
        "stock_name",
        "allocation_percent"
    ]]

    # -----------------------------
    # MERGE COMMON HOLDINGS
    # -----------------------------

    merged = pd.merge(
        df_a,
        df_b,
        on="stock_name",
        suffixes=("_a", "_b")
    )

    # -----------------------------
    # COMMON STOCK COUNT
    # -----------------------------

    common_stock_count = len(merged)

    # -----------------------------
    # RAW SIMILARITY SCORE
    # Weighted intersection: sum of min(alloc_a, alloc_b)
    # across all common stocks
    # -----------------------------

    similarity_score = (
        merged[
            [
                "allocation_percent_a",
                "allocation_percent_b"
            ]
        ]
        .min(axis=1)
        .sum()
    )

    # -----------------------------
    # NORMALIZED SIMILARITY SCORE
    # Divides by the smaller fund's total allocation
    # so the score means "% of the smaller fund's
    # portfolio weight that is shared" — comparable
    # across category pairs regardless of fund size
    # or number of holdings.
    # Range: 0–100
    # -----------------------------

    total_a = fund_totals.get(fund_a, 0)
    total_b = fund_totals.get(fund_b, 0)
    min_total = min(total_a, total_b)

    normalized_score = (
        round(similarity_score / min_total * 100, 2)
        if min_total > 0
        else 0.0
    )

    # -----------------------------
    # STORE RESULTS
    # -----------------------------

    results.append({
        "fund_a":             fund_a,
        "fund_b":             fund_b,
        "common_stocks":      common_stock_count,
        "similarity_score":   round(similarity_score, 2),
        "normalized_score":   normalized_score,
    })

# -----------------------------------
# CREATE DATAFRAME
# -----------------------------------

similarity_df = pd.DataFrame(results)

# -----------------------------------
# SORT
# -----------------------------------

similarity_df = similarity_df.sort_values(
    by="normalized_score",
    ascending=False
)

# -----------------------------------
# DISPLAY TOP RESULTS
# -----------------------------------

print("\n===================================")
print("TOP SIMILAR FUNDS")
print("===================================\n")

print(similarity_df.head(20))

# -----------------------------------
# SAVE OUTPUT
# -----------------------------------

output_path = (
    "data/processed/fund_similarity.csv"
)

similarity_df.to_csv(
    output_path,
    index=False
)

print("\n===================================")
print("SIMILARITY ENGINE COMPLETE")
print("===================================")

print(f"\nSaved to: {output_path}")