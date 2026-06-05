"""Import pasted slug_construct CSV from stdin or file."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reports" / "mfapi_et_slug_construct.csv"


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    text = src.read_text(encoding="utf-8") if src else sys.stdin.read()
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        print("No input")
        return 1
    header = lines[0].lower()
    if "mf_scheme_code" not in header:
        print("Expected header mf_scheme_code,...")
        return 1
    rows = []
    for ln in lines[1:]:
        parts = ln.split(",", 3)
        if len(parts) < 4:
            continue
        code, name, cat, slug = parts[0], parts[1], parts[2], parts[3].strip()
        rows.append(
            {
                "mf_scheme_code": int(code),
                "mfapi_name_cleaned": name,
                "mf_category": cat,
                "slug_construct": slug,
            }
        )
    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"Wrote {len(df)} rows -> {OUT}")
    print(f"  with slug: {(df['slug_construct'].astype(str).str.strip() != '').sum()}")
    print(f"  blank slug: {(df['slug_construct'].astype(str).str.strip() == '').sum()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
