import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# -----------------------------------
# HELPER FUNCTIONS
# -----------------------------------

def clean_percentage(value):
    """
    Convert percentage string to float

    Example:
    '9.39 %' -> 9.39
    """

    if value is None:
        return None

    value = (
        value.replace("%", "")
        .replace("+", "")
        .replace(",", "")
        .strip()
    )

    try:
        return float(value)
    except:
        return None


# -----------------------------------
# SCRAPE SINGLE FUND
# -----------------------------------

def scrape_fund(fund):

    print("\n===================================")
    print(f"Scraping: {fund['fund_name']}")
    print("===================================")

    try:

        response = requests.get(
            fund["url"],
            headers=HEADERS
        )

        print("Status Code:", response.status_code)

        if response.status_code != 200:
            print("Failed to fetch page")
            return pd.DataFrame()

        # -----------------------------------
        # PARSE HTML
        # -----------------------------------

        soup = BeautifulSoup(response.text, "lxml")

        # -----------------------------------
        # FIND HOLDINGS SECTION
        # -----------------------------------

        holdings_section = soup.find(
            "div",
            class_="portfolio-stk-section"
        )

        if holdings_section is None:
            print("Could not find portfolio holdings section")
            return pd.DataFrame()

        print("Found portfolio holdings section")

        # -----------------------------------
        # FIND TABLE
        # -----------------------------------

        table = holdings_section.find("table")

        if table is None:
            print("Could not find holdings table")
            return pd.DataFrame()

        print("Found holdings table")

        tbody = table.find("tbody")

        if tbody is None:
            print("Could not find table body")
            return pd.DataFrame()

        rows = tbody.find_all("tr")

        print(f"Found {len(rows)} holding rows")

        # -----------------------------------
        # PARSE ROWS
        # -----------------------------------

        all_holdings = []

        for row in rows:

            cols = row.find_all("td")

            # Debug column count
            print(f"Columns Found: {len(cols)}")

            # Skip invalid rows
            if len(cols) < 3:
                continue

            try:

                # -----------------------------
                # BASIC FIELDS
                # -----------------------------

                stock_name = cols[0].get_text(strip=True)

                sector = cols[1].get_text(strip=True)

                allocation_text = cols[2].get_text(strip=True)

                allocation = clean_percentage(
                    allocation_text
                )

                if allocation is None:
                    continue

                # -----------------------------
                # OPTIONAL FIELDS
                # -----------------------------

                value_text = None
                change_3m = None
                change_6m = None
                change_1y = None

                if len(cols) > 3:
                    value_text = cols[3].get_text(strip=True)

                if len(cols) > 4:
                    change_3m = clean_percentage(
                        cols[4].get_text(strip=True)
                    )

                if len(cols) > 5:
                    change_6m = clean_percentage(
                        cols[5].get_text(strip=True)
                    )

                if len(cols) > 6:
                    change_1y = clean_percentage(
                        cols[6].get_text(strip=True)
                    )

                # -----------------------------
                # APPEND ROW
                # -----------------------------

                all_holdings.append({
                    "fund_name": fund["fund_name"],
                    "category": fund["category"],
                    "fund_house": fund["fund_house"],
                    "scheme_id": fund["scheme_id"],
                    "stock_name": stock_name,
                    "sector": sector,
                    "allocation_percent": allocation,
                    "value": value_text,
                    "change_3m_percent": change_3m,
                    "change_6m_percent": change_6m,
                    "change_1y_percent": change_1y,
                    "scrape_date": datetime.today().strftime("%Y-%m-%d"),
                    "source": "ETMoney"
                })

            except Exception as e:
                print("Error parsing row:", e)

        # -----------------------------------
        # CREATE DATAFRAME
        # -----------------------------------

        df = pd.DataFrame(all_holdings)

        if len(df) == 0:
            print("No holdings extracted")
            return pd.DataFrame()

        # Remove duplicates
        df = df.drop_duplicates()

        # Sort descending
        df = df.sort_values(
            by="allocation_percent",
            ascending=False
        )

        # Reset index
        df = df.reset_index(drop=True)

        print(
            f"Successfully extracted {len(df)} rows"
        )

        print(
            df[['stock_name', 'allocation_percent']].head()
        )

        return df

    except Exception as e:
        print("SCRAPER ERROR:", e)
        return pd.DataFrame()


# -----------------------------------
# LOAD FUND MASTER
# -----------------------------------

funds_df = pd.read_csv(
    "data/fund_master.csv"
)

print(f"\nLoaded {len(funds_df)} funds")

# -----------------------------------
# SCRAPE ALL FUNDS
# -----------------------------------

master_df = pd.DataFrame()

for _, fund in funds_df.iterrows():

    fund_data = scrape_fund(fund)

    if len(fund_data) > 0:

        master_df = pd.concat(
            [master_df, fund_data],
            ignore_index=True
        )

    # Small delay
    time.sleep(2)

# -----------------------------------
# FINAL CLEANUP
# -----------------------------------

if len(master_df) == 0:
    print("\nNo data extracted")
    exit()

master_df = master_df.drop_duplicates()

master_df = master_df.reset_index(drop=True)

# -----------------------------------
# DISPLAY SAMPLE
# -----------------------------------

print("\n===================================")
print("FINAL DATASET SAMPLE")
print("===================================\n")

print(master_df.head(20))

print("\n===================================")
print(f"TOTAL ROWS: {len(master_df)}")
print("===================================\n")

# -----------------------------------
# SAVE MASTER CSV
# -----------------------------------

output_path = (
    "data/processed/master_holdings.csv"
)

master_df.to_csv(
    output_path,
    index=False
)

print(f"Saved master holdings to:")
print(output_path)