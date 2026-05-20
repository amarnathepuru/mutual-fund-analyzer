"""Re-fetch per-fund risk metrics and update fund_master_auto.csv."""

import sys
import time

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from enrich_fund_ratings import DELAY, fetch_ratings  # noqa: E402


def _slug_from_url(url: str) -> str:
    parts = str(url).split("/mutual-funds/")
    if len(parts) < 2:
        return ""
    return parts[1].split("/")[0]


def main():
    master_path = "data/fund_master_auto.csv"
    df = pd.read_csv(master_path)
    active = df[df["status"] == "ACTIVE"].copy()
    print(f"Backfilling risk metrics for {len(active)} active funds...\n")

    rows = []
    for i, (_, fund) in enumerate(active.iterrows(), 1):
        slug = _slug_from_url(fund["url"])
        scheme_id = int(fund["scheme_id"])
        print(f"[{i:>3}/{len(active)}] {fund['fund_name'][:55]}")
        ratings = fetch_ratings(slug, scheme_id)
        rows.append(
            {
                "scheme_id": scheme_id,
                "sharpe_ratio": ratings["sharpe_ratio"],
                "alpha": ratings["alpha"],
                "beta": ratings["beta"],
                "std_dev": ratings["std_dev"],
            }
        )
        print(
            f"  sharpe={ratings['sharpe_ratio']} alpha={ratings['alpha']} "
            f"beta={ratings['beta']} std={ratings['std_dev']}"
        )
        time.sleep(DELAY)

    risk_df = pd.DataFrame(rows)
    df = df.merge(risk_df, on="scheme_id", how="left", suffixes=("", "_new"))
    for col in ("sharpe_ratio", "alpha", "beta", "std_dev"):
        new_col = f"{col}_new"
        if new_col in df.columns:
            # Only overwrite when a fresh per-fund value was fetched
            df[col] = df[new_col].where(df[new_col].notna(), df[col])
            df.drop(columns=[new_col], inplace=True)

    df.to_csv(master_path, index=False)
    ok = risk_df["sharpe_ratio"].notna().sum()
    print(f"\nDone. {ok}/{len(active)} funds have risk metrics.")
    print(f"Unique sharpe values: {df['sharpe_ratio'].nunique()}")


if __name__ == "__main__":
    main()
