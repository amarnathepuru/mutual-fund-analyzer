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
    # SIMILARITY SCORE
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
    # STORE RESULTS
    # -----------------------------

    results.append({
        "fund_a": fund_a,
        "fund_b": fund_b,
        "common_stocks": common_stock_count,
        "similarity_score": round(
            similarity_score,
            2
        )
    })

# -----------------------------------
# CREATE DATAFRAME
# -----------------------------------

similarity_df = pd.DataFrame(results)

# -----------------------------------
# SORT
# -----------------------------------

similarity_df = similarity_df.sort_values(
    by="similarity_score",
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