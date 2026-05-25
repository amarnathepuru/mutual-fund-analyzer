"""Restore performance columns wiped by partial enrich merge."""
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PERF_COLS = [
    "return_1y", "return_3y", "return_5y", "return_since_inception",
    "consistency_score", "category_rank",
    "sharpe_ratio", "alpha", "beta", "std_dev",
]


def load_git_master(rev: str = "8e71722") -> pd.DataFrame:
    raw = subprocess.check_output(
        ["git", "show", f"{rev}:data/fund_master_auto.csv"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )
    return pd.read_csv(StringIO(raw))


def main():
    cur = pd.read_csv(ROOT / "data" / "fund_master_auto.csv")
    old = load_git_master()
    old_perf = old[["scheme_id"] + [c for c in PERF_COLS if c in old.columns]].copy()

    # Batch2 scrape values currently in cur (partial)
    cur_perf = cur[["scheme_id"] + [c for c in PERF_COLS if c in cur.columns]].copy()

    merged = cur.drop(columns=[c for c in PERF_COLS if c in cur.columns])
    merged = merged.merge(old_perf, on="scheme_id", how="left", suffixes=("", "_git"))
    merged = merged.merge(cur_perf, on="scheme_id", how="left", suffixes=("", "_cur"))

    for col in PERF_COLS:
        parts = []
        if f"{col}_cur" in merged.columns:
            parts.append(merged[f"{col}_cur"])
        if f"{col}_git" in merged.columns:
            parts.append(merged[f"{col}_git"])
        if col in merged.columns and col not in (f"{col}_cur", f"{col}_git"):
            parts.append(merged[col])
        if parts:
            combined = parts[0]
            for s in parts[1:]:
                combined = s.combine_first(combined)
            merged[col] = combined
        for drop in (f"{col}_git", f"{col}_cur"):
            if drop in merged.columns:
                merged.drop(columns=[drop], inplace=True)

    out = ROOT / "data" / "fund_master_auto.csv"
    merged.to_csv(out, index=False)
    print(f"Saved {len(merged)} rows -> {out}")
    print(f"return_1y filled: {merged['return_1y'].notna().sum()}/{len(merged)}")
    print(f"sharpe_ratio filled: {merged['sharpe_ratio'].notna().sum()}/{len(merged)}")


if __name__ == "__main__":
    main()
