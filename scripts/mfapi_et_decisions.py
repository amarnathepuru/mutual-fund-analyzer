"""
Persist MFAPI → ET Money candidate review (approve / reject / no match).

Used by review_mfapi_et_app.py and apply_mfapi_et_map.py (after scrape phase).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DECISIONS_CSV = ROOT / "data" / "mfapi_et_decisions.csv"
EXPORT_CSV = ROOT / "data" / "mfapi_to_et_approved.csv"

DECISION_COLUMNS = [
    "mf_scheme_code",
    "decision",
    "scheme_id",
    "computed_score",
    "mf_scheme_name",
    "et_fund_name",
    "decided_at",
    "notes",
]

NO_MATCH_SCHEME_ID = 0


def load_decisions(path: Path = DECISIONS_CSV) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=DECISION_COLUMNS)
    df = pd.read_csv(path)
    for col in DECISION_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[DECISION_COLUMNS]


def save_decisions(df: pd.DataFrame, path: Path = DECISIONS_CSV) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df[DECISION_COLUMNS].to_csv(path, index=False, encoding="utf-8")


def decisions_as_map_rows(df: pd.DataFrame) -> list[dict]:
    """Approved rows for fund_scheme_map apply (ET scheme_id → mf code)."""
    rows: list[dict] = []
    if df.empty:
        return rows
    approved = df[df["decision"].astype(str).str.lower() == "approved"]
    for _, r in approved.iterrows():
        sid = r.get("scheme_id")
        code = r.get("mf_scheme_code")
        if pd.isna(code) or pd.isna(sid):
            continue
        try:
            et_sid = int(sid)
            mf_code = int(code)
        except (TypeError, ValueError):
            continue
        if et_sid <= 0 or mf_code <= 0:
            continue
        rows.append(
            {
                "scheme_id": et_sid,
                "mf_scheme_code": mf_code,
                "et_fund_name": str(r.get("et_fund_name") or ""),
                "notes": str(r.get("notes") or "mfapi_et_review"),
            }
        )
    return rows


def upsert_decision(
    df: pd.DataFrame,
    *,
    mf_scheme_code: int,
    decision: str,
    scheme_id: int | None,
    computed_score: float | None,
    mf_scheme_name: str,
    et_fund_name: str,
    notes: str = "",
) -> pd.DataFrame:
    decision = decision.strip().lower()
    if decision not in ("approved", "rejected", "no_match"):
        raise ValueError(f"Invalid decision: {decision}")

    row = {
        "mf_scheme_code": int(mf_scheme_code),
        "decision": decision,
        "scheme_id": int(scheme_id) if decision == "approved" and scheme_id else "",
        "computed_score": round(computed_score, 2) if computed_score is not None else "",
        "mf_scheme_name": mf_scheme_name,
        "et_fund_name": et_fund_name if decision == "approved" else "",
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }
    df = df[df["mf_scheme_code"].astype(int) != int(mf_scheme_code)].copy()
    return pd.concat([df, pd.DataFrame([row])], ignore_index=True)


def export_approved_for_apply(
    decisions: pd.DataFrame, path: Path = EXPORT_CSV
) -> int:
    """Write scheme_id,mf_scheme_code,et_fund_name,notes for map merge."""
    rows = decisions_as_map_rows(decisions)
    out = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["scheme_id", "mf_scheme_code", "et_fund_name", "notes"]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8")
    return len(out)
