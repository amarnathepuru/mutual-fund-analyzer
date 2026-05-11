import pandas as pd

# -----------------------------------
# LOAD NORMALIZED DATA
# -----------------------------------

df = pd.read_csv(
    "data/processed/normalized_holdings.csv"
)

print(f"\nLoaded {len(df)} rows")

# -----------------------------------
# COUNT COMMON STOCKS
# -----------------------------------

common_df = (
    df.groupby("stock_name")
    .agg({
        "fund_name": "nunique",
        "allocation_percent": "mean"
    })
    .reset_index()
)

# -----------------------------------
# RENAME COLUMNS
# -----------------------------------

common_df.columns = [
    "stock_name",
    "fund_count",
    "avg_allocation_percent"
]

# -----------------------------------
# SORT
# -----------------------------------

common_df = common_df.sort_values(
    by=[
        "fund_count",
        "avg_allocation_percent"
    ],
    ascending=False
)

# -----------------------------------
# DISPLAY TOP HOLDINGS
# -----------------------------------

print("\n===================================")
print("MOST COMMON HOLDINGS")
print("===================================\n")

print(common_df.head(20))

# -----------------------------------
# SAVE OUTPUT
# -----------------------------------

output_path = (
    "data/processed/common_holdings.csv"
)

common_df.to_csv(
    output_path,
    index=False
)

print("\n===================================")
print("COMMON HOLDINGS COMPLETE")
print("===================================")

print(f"\nSaved to: {output_path}")