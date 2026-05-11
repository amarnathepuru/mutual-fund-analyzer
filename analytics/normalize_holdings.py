import pandas as pd

# -----------------------------------
# LOAD MASTER DATA
# -----------------------------------

df = pd.read_csv(
    "data/processed/master_holdings.csv"
)

print(f"\nLoaded {len(df)} rows")

# -----------------------------------
# CLEAN STOCK NAMES
# -----------------------------------

df["stock_name"] = (
    df["stock_name"]
    .str.strip()
    .str.replace("Ltd.", "", regex=False)
    .str.replace("Limited", "", regex=False)
    .str.replace("Ltd", "", regex=False)
    .str.replace(",", "", regex=False)
    .str.upper()
)

# -----------------------------------
# CLEAN SECTORS
# -----------------------------------

df["sector"] = (
    df["sector"]
    .fillna("UNKNOWN")
    .str.strip()
    .str.upper()
)

# -----------------------------------
# REMOVE INVALID ROWS
# -----------------------------------

invalid_values = [
    "NAN",
    "NULL",
    "",
    "UNKNOWN"
]

df = df[
    ~df["stock_name"].isin(invalid_values)
]

# -----------------------------------
# REMOVE DUPLICATES
# -----------------------------------

df = df.drop_duplicates()

# -----------------------------------
# VALIDATE ALLOCATION %
# -----------------------------------

df = df[
    df["allocation_percent"] > 0
]

# -----------------------------------
# CHECK FUND ALLOCATION TOTALS
# -----------------------------------

summary = (
    df.groupby("fund_name")[
        "allocation_percent"
    ]
    .sum()
    .reset_index()
)

print("\nAllocation Totals\n")
print(summary)

# -----------------------------------
# SAVE CLEAN DATA
# -----------------------------------

output_path = (
    "data/processed/normalized_holdings.csv"
)

df.to_csv(
    output_path,
    index=False
)

print("\n===================================")
print("NORMALIZATION COMPLETE")
print("===================================")

print(f"Final Rows: {len(df)}")

print(f"Saved to: {output_path}")