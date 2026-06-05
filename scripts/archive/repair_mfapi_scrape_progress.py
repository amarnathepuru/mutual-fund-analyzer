"""Repair mfapi_et_scrape_batch_progress.csv after comma/newline corruption."""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scrape_mfapi_et_batch import PROGRESS_COLS, PROGRESS_CSV  # noqa: E402

ROW_START = re.compile(r"^(\d{5,7}),")


def main() -> int:
    if not PROGRESS_CSV.is_file():
        print(f"Missing {PROGRESS_CSV}")
        return 1
    raw = PROGRESS_CSV.read_text(encoding="utf-8-sig", errors="replace")
    lines = raw.splitlines()
    if not lines:
        return 0
    header = lines[0]
    buf = ""
    rows: list[str] = []
    for line in lines[1:]:
        if ROW_START.match(line):
            if buf:
                rows.append(buf)
            buf = line
        else:
            buf = buf + " " + line.strip() if buf else line
    if buf:
        rows.append(buf)

    out_rows: list[dict] = []
    for chunk in rows:
        try:
            parsed = next(csv.reader([chunk]))
        except csv.Error:
            continue
        if len(parsed) < len(PROGRESS_COLS):
            continue
        parsed = parsed[: len(PROGRESS_COLS)]
        if len(parsed) < len(PROGRESS_COLS):
            parsed.extend([""] * (len(PROGRESS_COLS) - len(parsed)))
        rec = dict(zip(PROGRESS_COLS, parsed, strict=False))
        try:
            rec["mf_scheme_code"] = int(float(rec["mf_scheme_code"]))
        except (TypeError, ValueError):
            continue
        out_rows.append(rec)

    by_code: dict[int, dict] = {}
    for rec in out_rows:
        by_code[int(rec["mf_scheme_code"])] = rec

    backup = PROGRESS_CSV.with_suffix(".csv.bak")
    backup.write_text(raw, encoding="utf-8-sig")
    import pandas as pd

    df = pd.DataFrame(list(by_code.values()), columns=PROGRESS_COLS)
    df.to_csv(
        PROGRESS_CSV,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_NONNUMERIC,
    )
    print(f"Repaired {len(df)} rows -> {PROGRESS_CSV}")
    print(f"Backup: {backup}")
    if not df.empty:
        print(df["status"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
