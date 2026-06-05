"""
Batch 3: Match ET Money ACTIVE funds to MFAPI NAV universe (881 schemes).

Report only — does not write fund_scheme_map.csv until user reviews and runs apply.

Usage (repo root):
  python scripts/match_et_mfapi.py
  python scripts/match_et_mfapi.py --min-auto-score 95 --ambiguity-gap 3
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from et_mfapi_decisions import decisions_as_override_map, load_decisions
from et_mfapi_match_scope import is_et_index_fund
from mfapi_scheme_name import fund_name_match_score, mf_match_key, normalize_match_key

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = DATA / "reports"
RAW_MFAPI = DATA / "raw" / "mfapi"

ET_MASTER = DATA / "fund_master_auto.csv"
MF_UNIVERSE = RAW_MFAPI / "nav_universe_schemes.csv"
NAV_DB = DATA / "nav" / "nav.db"
DECISIONS_CSV = DATA / "et_mfapi_decisions.csv"
OVERRIDES_IN = DATA / "mfapi_et_manual_overrides.csv"

REPORT_OUT = REPORTS / "et_mfapi_match_report.csv"
EXCLUDED_OUT = REPORTS / "et_mfapi_excluded_index.csv"
QC_OUT = REPORTS / "mfapi_batch3_qc.txt"

DEFAULT_MIN_AUTO = 95
DEFAULT_AMBIGUITY_GAP = 3
DEFAULT_REVIEW_FLOOR = 70

# Loose ET category -> tokens expected in MF scheme_category
_CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    "large cap": ("large cap",),
    "large & mid cap": ("large", "mid cap"),
    "mid cap": ("mid cap",),
    "small cap": ("small cap",),
    "flexi cap": ("flexi cap",),
    "multi cap": ("multi cap",),
    "elss": ("elss",),
    "value": ("value",),
    "contra": ("contra",),
    "focused": ("focused",),
    "dividend yield": ("dividend yield",),
    "aggressive hybrid": ("aggressive hybrid",),
    "balanced hybrid": ("conservative hybrid", "balanced"),
    "arbitrage": ("arbitrage",),
    "dynamic asset allocation": ("dynamic asset allocation", "balanced advantage"),
    "multi asset allocation": ("multi asset",),
    "equity savings": ("equity savings",),
    "sectoral": ("sectoral", "thematic"),
    "thematic": ("thematic", "sectoral"),
    "international": ("international", "overseas", "fof"),
    "index": ("index",),
    "liquid": ("liquid",),
}


def _nfkc_house(name: str | None) -> str:
    if not name or not isinstance(name, str):
        return ""
    s = name.lower().strip()
    s = re.sub(r"\s*mutual\s*fund\s*", " ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _token_sort_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    ta = " ".join(sorted(a.split()))
    tb = " ".join(sorted(b.split()))
    return SequenceMatcher(None, ta, tb).ratio() * 100.0


def _category_boost(et_category: str | None, mf_category: str | None) -> float:
    if not et_category or not mf_category:
        return 0.0
    et_lo = str(et_category).lower().strip()
    mf_lo = str(mf_category).lower().strip()
    for key, tokens in _CATEGORY_HINTS.items():
        if key in et_lo or et_lo in key:
            if any(t in mf_lo for t in tokens):
                return 5.0
    return 0.0


def _house_boost(et_house: str | None, mf_house: str | None) -> float:
    eh, mh = _nfkc_house(et_house), _nfkc_house(mf_house)
    if not eh or not mh:
        return 0.0
    if eh == mh:
        return 5.0
    if eh in mh or mh in eh:
        return 3.0
    return 0.0


def _house_penalty(et_house: str | None, mf_house: str | None) -> float:
    if _house_boost(et_house, mf_house) >= 3:
        return 0.0
    eh, mh = _nfkc_house(et_house), _nfkc_house(mf_house)
    if not eh or not mh:
        return 0.0
    if eh == mh or eh in mh or mh in eh:
        return 0.0
    return -12.0


def _composite_score(
    et_fund_name: str,
    mf_scheme_or_base: str,
    et_category: str | None,
    mf_category: str | None,
    et_house: str | None,
    mf_house: str | None,
) -> float:
    base = fund_name_match_score(mf_scheme_or_base, et_fund_name)
    boost = _category_boost(et_category, mf_category) + _house_boost(et_house, mf_house)
    penalty = _house_penalty(et_house, mf_house)
    return min(100.0, max(0.0, base + boost + penalty))


def _load_approved_map() -> tuple[dict[int, int], dict[int, float]]:
    """Approved links from review app (et_mfapi_decisions.csv)."""
    df = load_decisions(DECISIONS_CSV)
    code_map = decisions_as_override_map(df)
    score_map: dict[int, float] = {}
    if not df.empty:
        approved = df[df["decision"].astype(str).str.lower() == "approved"]
        for _, row in approved.iterrows():
            sid = int(row["scheme_id"])
            sc = row.get("computed_score")
            if pd.notna(sc) and str(sc).strip() != "":
                try:
                    score_map[sid] = float(sc)
                except (TypeError, ValueError):
                    pass
    return code_map, score_map


def _rank_candidates(
    et_row: pd.Series, mf_df: pd.DataFrame
) -> list[tuple[int, float, str, str]]:
    et_name = str(et_row.get("fund_name") or "")
    scored: list[tuple[int, float, str, str]] = []
    for _, mf in mf_df.iterrows():
        code = int(mf["mf_scheme_code"])
        mf_raw = str(mf.get("scheme_name_raw") or mf.get("fund_name_base") or "")
        score = _composite_score(
            et_name,
            mf_raw,
            et_row.get("category"),
            mf.get("scheme_category"),
            et_row.get("fund_house"),
            mf.get("fund_house"),
        )
        scored.append(
            (
                code,
                score,
                str(mf.get("scheme_name_raw") or ""),
                str(mf.get("scheme_category") or ""),
            )
        )
    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored


def _classify_match(
    scored: list[tuple[int, float, str, str]],
    *,
    min_auto: float,
    ambiguity_gap: float,
    review_floor: float,
) -> tuple[str, int | None, float, str, str, int, str]:
    if not scored:
        return "no_match", None, 0.0, "", "", 0, ""

    best_code, best_score, best_name, best_cat = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else 0.0
    gap = best_score - second_score

    alt_parts = []
    for code, sc, name, _ in scored[1:4]:
        alt_parts.append(f"{code}:{sc:.1f}")
    alt_str = "; ".join(alt_parts)

    if best_score < review_floor:
        return "no_match", None, best_score, best_name, best_cat, len(scored), alt_str

    # Perfect name match: auto-apply even when #2 is close (generic category names).
    if round(best_score, 2) >= 100.0:
        return "auto_ok", best_code, best_score, best_name, best_cat, len(scored), alt_str

    if best_score >= min_auto and gap < ambiguity_gap:
        return "ambiguous", best_code, best_score, best_name, best_cat, len(scored), alt_str

    if best_score >= min_auto:
        return "auto_ok", best_code, best_score, best_name, best_cat, len(scored), alt_str

    if best_score >= review_floor:
        return "review", best_code, best_score, best_name, best_cat, len(scored), alt_str

    return "no_match", None, best_score, best_name, best_cat, len(scored), alt_str


def _load_mf_universe(path: Path, nav_db: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Run mfapi_prune_nav_db.py first.")
    mf = pd.read_csv(path)
    if "fund_name_match_key" not in mf.columns:
        mf["fund_name_match_key"] = mf["fund_name_base"].map(
            lambda x: normalize_match_key(str(x) if pd.notna(x) else "")
        )
    if nav_db.is_file():
        conn = sqlite3.connect(nav_db)
        try:
            meta = pd.read_sql_query(
                """
                SELECT mf_scheme_code, isin_growth, scheme_category AS db_category
                FROM schemes
                """,
                conn,
            )
        finally:
            conn.close()
        mf = mf.merge(meta, on="mf_scheme_code", how="left")
        if "db_category" in mf.columns:
            mf["scheme_category"] = mf["scheme_category"].fillna(mf["db_category"])
    return mf


def _print_review_hint() -> None:
    print("  Review UI: streamlit run scripts/review_et_mfapi_app.py")
    print(f"  Saves decisions -> {DECISIONS_CSV}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Batch 3: ET ↔ MFAPI match report")
    parser.add_argument(
        "--min-auto-score",
        type=float,
        default=DEFAULT_MIN_AUTO,
        help="Score >= this and clear gap => auto_ok in report",
    )
    parser.add_argument(
        "--ambiguity-gap",
        type=float,
        default=DEFAULT_AMBIGUITY_GAP,
        help="Min score gap between #1 and #2 else ambiguous",
    )
    parser.add_argument(
        "--review-floor",
        type=float,
        default=DEFAULT_REVIEW_FLOOR,
        help="Below this => no_match",
    )
    args = parser.parse_args()

    if not ET_MASTER.is_file():
        print(f"Missing {ET_MASTER}")
        return 1

    et = pd.read_csv(ET_MASTER)
    et = et[et["status"].astype(str).str.upper() == "ACTIVE"].copy()
    et["_is_index"] = et.apply(
        lambda r: is_et_index_fund(r.get("category"), r.get("fund_name")), axis=1
    )
    et_index = et[et["_is_index"]].copy()
    et_match = et[~et["_is_index"]].copy()

    mf = _load_mf_universe(MF_UNIVERSE, NAV_DB)
    approved_map, approved_scores = _load_approved_map()

    mf_by_code = {int(r["mf_scheme_code"]): r for _, r in mf.iterrows()}

    report_rows: list[dict] = []
    for _, et_row in et_index.iterrows():
        sid = int(et_row["scheme_id"])
        report_rows.append(
            {
                "scheme_id": sid,
                "et_fund_name": et_row["fund_name"],
                "et_category": et_row.get("category"),
                "et_fund_house": et_row.get("fund_house"),
                "mf_scheme_code": "",
                "mf_scheme_name": "",
                "mf_scheme_category": "",
                "isin_growth": "",
                "match_score": "",
                "match_status": "excluded_index",
                "match_tier": "out_of_scope",
                "score_gap": "",
                "candidate_count": 0,
                "alt_candidates": "",
            }
        )

    for _, et_row in et_match.iterrows():
        sid = int(et_row["scheme_id"])
        if sid in approved_map:
            code = approved_map[sid]
            mf_row = mf_by_code.get(code)
            report_rows.append(
                {
                    "scheme_id": sid,
                    "et_fund_name": et_row["fund_name"],
                    "et_category": et_row.get("category"),
                    "et_fund_house": et_row.get("fund_house"),
                    "mf_scheme_code": code,
                    "mf_scheme_name": mf_row["scheme_name_raw"] if mf_row is not None else "",
                    "mf_scheme_category": mf_row["scheme_category"] if mf_row is not None else "",
                    "isin_growth": mf_row.get("isin_growth") if mf_row is not None else "",
                    "match_score": approved_scores.get(sid, ""),
                    "match_status": "approved",
                    "match_tier": "review_app",
                    "score_gap": "",
                    "candidate_count": 1,
                    "alt_candidates": "",
                }
            )
            continue

        scored = _rank_candidates(et_row, mf)
        status, code, score, mf_name, mf_cat, n_cand, alts = _classify_match(
            scored,
            min_auto=args.min_auto_score,
            ambiguity_gap=args.ambiguity_gap,
            review_floor=args.review_floor,
        )
        gap = ""
        if len(scored) >= 2:
            gap = f"{scored[0][1] - scored[1][1]:.1f}"
        mf_row = mf_by_code.get(code) if code is not None else None
        report_rows.append(
            {
                "scheme_id": sid,
                "et_fund_name": et_row["fund_name"],
                "et_category": et_row.get("category"),
                "et_fund_house": et_row.get("fund_house"),
                "mf_scheme_code": code if code is not None else "",
                "mf_scheme_name": mf_name,
                "mf_scheme_category": mf_cat,
                "isin_growth": mf_row.get("isin_growth") if mf_row is not None else "",
                "match_score": round(score, 2) if score else "",
                "match_status": status,
                "match_tier": "name_fuzzy",
                "score_gap": gap,
                "candidate_count": n_cand,
                "alt_candidates": alts,
            }
        )

    report = pd.DataFrame(report_rows)
    REPORTS.mkdir(parents=True, exist_ok=True)
    report.to_csv(REPORT_OUT, index=False, encoding="utf-8")
    et_index[
        ["scheme_id", "fund_name", "category", "fund_house"]
    ].rename(columns={"fund_name": "et_fund_name"}).to_csv(
        EXCLUDED_OUT, index=False, encoding="utf-8"
    )

    counts = report["match_status"].value_counts()
    match_counts = report[~report["match_status"].eq("excluded_index")][
        "match_status"
    ].value_counts()
    mapped_codes = set(
        int(c)
        for c in report.loc[
            report["match_status"].isin(("auto_ok", "approved")), "mf_scheme_code"
        ]
        if pd.notna(c) and str(c).strip() != ""
    )
    mf_unmapped = len(mf) - len(mapped_codes)

    lines = [
        "MFApi Batch 3 — ET ↔ MFAPI match QC",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"ET ACTIVE funds: {len(et)}",
        f"  excluded index (no MFAPI match): {len(et_index)}",
        f"  in match scope: {len(et_match)}",
        f"MFAPI NAV universe: {len(mf)}",
        f"min_auto_score: {args.min_auto_score}",
        f"ambiguity_gap: {args.ambiguity_gap}",
        "",
        "Match status counts (all rows):",
    ]
    for st, n in counts.items():
        lines.append(f"  {st}: {n}")
    lines.append("")
    lines.append("In-scope only (excludes excluded_index):")
    for st, n in match_counts.items():
        lines.append(f"  {st}: {n}")
    lines.append(f"  excluded_index list: {EXCLUDED_OUT}")
    lines.extend(
        [
            "",
            f"MF schemes with auto_ok/approved mapping: {len(mapped_codes)}",
            f"MF schemes not linked to any ET ACTIVE: {mf_unmapped}",
            "",
            f"Report: {REPORT_OUT}",
            "",
            "Next: streamlit run scripts/review_et_mfapi_app.py → export overrides → apply_et_mfapi_map.py",
        ]
    )
    QC_OUT.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    _print_review_hint()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
