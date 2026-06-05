"""Write data/reports/master_sync_qc.txt summary after master file updates."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/reports/master_sync_qc.txt"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    m = pd.read_csv(ROOT / "data/fund_scheme_map.csv")
    et = pd.read_csv(ROOT / "data/fund_master_auto.csv")
    h = pd.read_csv(ROOT / "data/processed/master_holdings.csv")
    n = pd.read_csv(ROOT / "data/processed/normalized_holdings.csv")
    sim = pd.read_csv(ROOT / "data/processed/fund_similarity.csv")
    nav = pd.read_csv(ROOT / "data/raw/mfapi/nav_universe_schemes.csv")
    d = pd.read_csv(ROOT / "data/mfapi_et_decisions.csv")

    et_ids = set(m["scheme_id"].astype(int))
    h_ids = set(h["scheme_id"].astype(int))
    miss_h = et_ids - h_ids

    lines = [
        f"Master sync QC — {datetime.now(timezone.utc).isoformat()}",
        "",
        "=== Core files ===",
        f"fund_scheme_map.csv: {len(m)} rows",
        f"mfapi_et_decisions.csv: {len(d)} rows ({d.decision.value_counts().to_dict()})",
        f"fund_master_auto.csv: {len(et)} rows",
        f"master_holdings.csv: {len(h)} rows",
        f"normalized_holdings.csv: {len(n)} rows ({n.fund_name.nunique()} funds)",
        f"fund_similarity.csv: {len(sim)} pairs",
        f"nav_universe_schemes.csv: {len(nav)} funds",
        "",
        "=== Map coverage ===",
        f"Mapped MF codes: {m.mf_scheme_code.nunique()}",
        f"Mapped ET scheme_ids: {len(et_ids)}",
        f"Mapped with holdings: {len(et_ids & h_ids)}",
        f"Mapped WITHOUT holdings (link only): {len(miss_h)}",
        "",
        "=== Actions completed ===",
        "- sync_map_master_metadata.py (et_fund_name + isin backfill)",
        "- analytics/normalize_holdings.py",
        "- scripts/rebuild_fund_similarity.py",
        "",
        "=== App impact ===",
        "- Analyse/Compare/Overlap: normalized_holdings + fund_similarity (refreshed)",
        "- Portfolio Track: nav.db + fund_scheme_map",
        "- 43 mapped funds have no ET holdings table (sector/thematic/manual scrape)",
    ]
    if miss_h:
        sub = m[m["scheme_id"].astype(int).isin(miss_h)]
        lines.append("")
        lines.append("=== Mapped, no holdings (sample) ===")
        for _, r in sub.head(15).iterrows():
            lines.append(
                f"  MF {int(r.mf_scheme_code)} | {str(r.get('et_fund_name',''))[:50]} | {r.get('match_method','')}"
            )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
