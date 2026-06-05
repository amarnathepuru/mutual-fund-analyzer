"""
MFAPI-only → ET Money candidate report (reverse of match_et_mfapi.py).

For each MFAPI scheme not in fund_scheme_map.csv, rank ACTIVE ET funds and export
top 5 ET candidates for manual review.

Usage (repo root):
  python scripts/match_mfapi_et.py
  streamlit run scripts/review_mfapi_et_app.py
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from match_et_mfapi import (  # noqa: E402
    _CATEGORY_HINTS,
    _house_boost,
    _house_penalty,
    _load_mf_universe,
)
from mfapi_et_decisions import DECISIONS_CSV, load_decisions  # noqa: E402
from mfapi_scheme_name import (  # noqa: E402
    et_significant_tokens,
    mf_fund_name_cleaned,
    mf_significant_tokens,
    fund_name_match_score,
)
from review_mfapi_et_candidates import format_top5_labels  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = DATA / "reports"
ET_MASTER = DATA / "fund_master_auto.csv"
MF_UNIVERSE = DATA / "raw" / "mfapi" / "nav_universe_schemes.csv"
SCHEME_MAP = DATA / "fund_scheme_map.csv"
NAV_DB = DATA / "nav" / "nav.db"
REPORT_OUT = REPORTS / "mfapi_et_candidate_report.csv"
QC_OUT = REPORTS / "mfapi_et_batch_qc.txt"

DEFAULT_MIN_AUTO = 95.0
DEFAULT_AMBIGUITY_GAP = 3.0
DEFAULT_REVIEW_FLOOR = 70.0
TOP_N = 5


def _category_boost(mf_category: str | None, et_category: str | None) -> float:
    mf_lo = str(mf_category or "").lower().strip()
    et_lo = str(et_category or "").lower().strip()
    for key, tokens in _CATEGORY_HINTS.items():
        if key in mf_lo or mf_lo in key:
            if any(t in et_lo for t in tokens):
                return 5.0
        if key in et_lo or et_lo in key:
            if any(t in mf_lo for t in tokens):
                return 5.0
    return 0.0


def _mf_name_for_match(mf_row: pd.Series) -> str:
    """MFAPI Fund Name Cleaned — same as audit CSV / ET Money search."""
    raw = str(mf_row.get("scheme_name_raw") or "")
    base = str(mf_row.get("fund_name_base") or "")
    return mf_fund_name_cleaned(raw or base)


def _composite_score(
    mf_name: str,
    et_fund_name: str,
    mf_category: str | None,
    et_category: str | None,
    mf_house: str | None,
    et_house: str | None,
) -> float:
    base = fund_name_match_score(mf_name, et_fund_name)
    boost = _category_boost(mf_category, et_category) + _house_boost(et_house, mf_house)
    penalty = _house_penalty(et_house, mf_house)
    return min(100.0, max(0.0, base + boost + penalty))


def _rank_et_candidates(
    mf_row: pd.Series, et_df: pd.DataFrame
) -> list[tuple[int, float, str, str]]:
    mf_name = _mf_name_for_match(mf_row)
    mf_toks = mf_significant_tokens(mf_name)
    scored: list[tuple[int, float, str, str]] = []
    for _, et in et_df.iterrows():
        sid = int(et["scheme_id"])
        et_name = str(et.get("fund_name") or "")
        if mf_toks and not (mf_toks & et_significant_tokens(et_name)):
            continue
        score = _composite_score(
            mf_name,
            et_name,
            mf_row.get("scheme_category"),
            et.get("category"),
            mf_row.get("fund_house"),
            et.get("fund_house"),
        )
        scored.append(
            (
                sid,
                score,
                et_name,
                str(et.get("category") or ""),
            )
        )
    if len(scored) < TOP_N:
        for _, et in et_df.iterrows():
            sid = int(et["scheme_id"])
            if any(s[0] == sid for s in scored):
                continue
            et_name = str(et.get("fund_name") or "")
            score = _composite_score(
                mf_name,
                et_name,
                mf_row.get("scheme_category"),
                et.get("category"),
                mf_row.get("fund_house"),
                et.get("fund_house"),
            )
            scored.append((sid, score, et_name, str(et.get("category") or "")))
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

    best_sid, best_score, best_name, best_cat = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else 0.0
    gap = best_score - second_score

    top5_main = "; ".join(f"{sid}:{sc:.1f}" for sid, sc, _, _ in scored[:TOP_N])

    if best_score < review_floor:
        return "no_match", None, best_score, best_name, best_cat, len(scored), top5_main

    if round(best_score, 2) >= 100.0:
        return "auto_ok", best_sid, best_score, best_name, best_cat, len(scored), top5_main

    if best_score >= min_auto and gap < ambiguity_gap:
        return "ambiguous", best_sid, best_score, best_name, best_cat, len(scored), top5_main

    if best_score >= min_auto:
        return "auto_ok", best_sid, best_score, best_name, best_cat, len(scored), top5_main

    if best_score >= review_floor:
        return "review", best_sid, best_score, best_name, best_cat, len(scored), top5_main

    return "no_match", None, best_score, best_name, best_cat, len(scored), top5_main


def _load_approved_mf_decisions() -> dict[int, dict]:
    df = load_decisions(DECISIONS_CSV)
    out: dict[int, dict] = {}
    if df.empty:
        return out
    for _, row in df.iterrows():
        try:
            code = int(row["mf_scheme_code"])
        except (TypeError, ValueError):
            continue
        out[code] = row.to_dict()
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="MFAPI-only → ET candidate report")
    parser.add_argument("--min-auto-score", type=float, default=DEFAULT_MIN_AUTO)
    parser.add_argument("--ambiguity-gap", type=float, default=DEFAULT_AMBIGUITY_GAP)
    parser.add_argument("--review-floor", type=float, default=DEFAULT_REVIEW_FLOOR)
    args = parser.parse_args()

    if not ET_MASTER.is_file():
        print(f"Missing {ET_MASTER}")
        return 1
    if not MF_UNIVERSE.is_file():
        print(f"Missing {MF_UNIVERSE}")
        return 1

    et = pd.read_csv(ET_MASTER)
    et = et[et["status"].astype(str).str.upper() == "ACTIVE"].copy()

    mf = _load_mf_universe(MF_UNIVERSE, NAV_DB)
    mapped_codes: set[int] = set()
    if SCHEME_MAP.is_file():
        mapped_codes = set(pd.read_csv(SCHEME_MAP)["mf_scheme_code"].astype(int))

    mf_only = mf[~mf["mf_scheme_code"].astype(int).isin(mapped_codes)].copy()
    approved_dec = _load_approved_mf_decisions()
    et_by_sid = {int(r["scheme_id"]): r for _, r in et.iterrows()}

    report_rows: list[dict] = []
    for _, mf_row in mf_only.iterrows():
        code = int(mf_row["mf_scheme_code"])
        mf_name_raw = str(mf_row.get("scheme_name_raw") or "")
        mf_base = _mf_name_for_match(mf_row)

        if code in approved_dec:
            dec = approved_dec[code]
            dec_status = str(dec.get("decision") or "").lower()
            if dec_status == "approved":
                try:
                    et_sid = int(dec.get("scheme_id") or 0)
                except (TypeError, ValueError):
                    et_sid = 0
                et_row = et_by_sid.get(et_sid)
                report_rows.append(
                    {
                        "mf_scheme_code": code,
                        "mfapi_scheme_name": mf_name_raw,
                        "mfapi_fund_name_cleaned": mf_base,
                        "mf_scheme_category": mf_row.get("scheme_category"),
                        "mf_fund_house": mf_row.get("fund_house"),
                        "scheme_id": et_sid if et_sid else "",
                        "et_fund_name": dec.get("et_fund_name") or "",
                        "et_category": et_row.get("category") if et_row is not None else "",
                        "et_fund_house": et_row.get("fund_house") if et_row is not None else "",
                        "match_score": dec.get("computed_score") or "",
                        "match_status": "approved",
                        "match_tier": "review_app",
                        "score_gap": "",
                        "candidate_count": 1,
                        "alt_candidates": "",
                    }
                )
                continue
            if dec_status in ("rejected", "no_match"):
                report_rows.append(
                    {
                        "mf_scheme_code": code,
                        "mfapi_scheme_name": mf_name_raw,
                        "mfapi_fund_name_cleaned": mf_base,
                        "mf_scheme_category": mf_row.get("scheme_category"),
                        "mf_fund_house": mf_row.get("fund_house"),
                        "scheme_id": "",
                        "et_fund_name": "",
                        "et_category": "",
                        "et_fund_house": "",
                        "match_score": dec.get("computed_score") or "",
                        "match_status": dec_status,
                        "match_tier": "review_app",
                        "score_gap": "",
                        "candidate_count": 0,
                        "alt_candidates": "",
                    }
                )
                continue

        scored = _rank_et_candidates(mf_row, et)
        status, et_sid, score, et_name, et_cat, n_cand, alts_top5 = _classify_match(
            scored,
            min_auto=args.min_auto_score,
            ambiguity_gap=args.ambiguity_gap,
            review_floor=args.review_floor,
        )
        gap = ""
        if len(scored) >= 2:
            gap = f"{scored[0][1] - scored[1][1]:.1f}"
        et_row = et_by_sid.get(et_sid) if et_sid is not None else None
        report_rows.append(
            {
                "mf_scheme_code": code,
                "mfapi_scheme_name": mf_name_raw,
                "mfapi_fund_name_cleaned": mf_base,
                "mf_scheme_category": mf_row.get("scheme_category"),
                "mf_fund_house": mf_row.get("fund_house"),
                "scheme_id": et_sid if et_sid is not None else "",
                "et_fund_name": et_name,
                "et_category": et_cat,
                "et_fund_house": et_row.get("fund_house") if et_row is not None else "",
                "match_score": round(score, 2) if score else "",
                "match_status": status,
                "match_tier": "name_fuzzy",
                "score_gap": gap,
                "candidate_count": min(TOP_N, len(scored)),
                "alt_candidates": alts_top5,
                "top5_labels": format_top5_labels(
                    [(s[0], s[1], s[2]) for s in scored[:TOP_N]]
                ),
            }
        )

    report = pd.DataFrame(report_rows)
    REPORTS.mkdir(parents=True, exist_ok=True)
    report.to_csv(REPORT_OUT, index=False, encoding="utf-8-sig")

    pending = report[~report["match_status"].isin(("approved", "rejected", "no_match"))]
    counts = report["match_status"].value_counts()
    lines = [
        "MFAPI-only → ET Money candidate report",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"MFAPI NAV universe: {len(mf)}",
        f"Already in fund_scheme_map: {len(mapped_codes)}",
        f"MFAPI-only queue: {len(mf_only)}",
        f"ET ACTIVE (match targets): {len(et)}",
        f"Top ET candidates per row: {TOP_N}",
        "",
        "Status counts:",
    ]
    for st, n in counts.items():
        lines.append(f"  {st}: {n}")
    lines.extend(
        [
            "",
            f"Pending review (not decided): {len(pending)}",
            f"Report: {REPORT_OUT}",
            "",
            "Next: streamlit run scripts/review_mfapi_et_app.py",
        ]
    )
    QC_OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
