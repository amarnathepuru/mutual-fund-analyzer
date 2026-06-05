"""Apply fund_scheme_map rows for manual ET links already scraped (no re-fetch)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from et_mfapi_scrape_lib import upsert_scheme_map  # noqa: E402
from mfapi_scheme_name import mf_fund_name_cleaned  # noqa: E402
from scrape_mfapi_et_manual_links import (  # noqa: E402
    DEFAULT_CSV,
    load_manual_csv,
    parse_et_link,
)

PROGRESS = Path(__file__).resolve().parents[1] / "data/reports/mfapi_et_scrape_batch_progress.csv"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    manual = load_manual_csv(DEFAULT_CSV)
    has = manual["et_link"].str.contains("etmoney.com", case=False, na=False)
    mapped = manual[has]
    prog = pd.read_csv(PROGRESS, encoding="utf-8-sig")
    prog_ok = prog[prog["status"].astype(str).str.lower() == "ok"]
    by_code = mapped.set_index(mapped["mf_scheme_code"].astype(int))

    n = 0
    for _, row in prog_ok.iterrows():
        code = int(row["mf_scheme_code"])
        if code not in by_code.index:
            continue
        et_url = str(by_code.loc[code, "et_link"])
        parsed = parse_et_link(et_url)
        if not parsed:
            continue
        _, sid = parsed
        mf_name = mf_fund_name_cleaned(str(by_code.loc[code, "mfapi_name_cleaned"]))
        et_name = str(row.get("et_fund_name") or "")
        upsert_scheme_map(
            code,
            int(sid),
            et_name,
            mf_name,
            match_method="manual_et_link",
            notes=f"manual ET link {et_url[:100]}",
        )
        n += 1
    print(f"Applied {n} rows to fund_scheme_map.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
