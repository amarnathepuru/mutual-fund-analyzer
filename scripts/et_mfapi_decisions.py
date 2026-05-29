"""
Persist ET ↔ MFAPI match review decisions (approve / reject).

Used by review_et_mfapi_app.py and match_et_mfapi.py / apply (Batch 4).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DECISIONS_CSV = ROOT / "data" / "et_mfapi_decisions.csv"
OVERRIDES_CSV = ROOT / "data" / "mfapi_et_manual_overrides.csv"

DECISION_COLUMNS = [
    "scheme_id",
    "decision",
    "mf_scheme_code",
    "computed_score",
    "et_fund_name",
    "mf_scheme_name",
    "decided_at",
    "notes",
]


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
    out = df[DECISION_COLUMNS].copy()
    out.to_csv(path, index=False, encoding="utf-8")


def decisions_as_override_map(df: pd.DataFrame) -> dict[int, int]:
    """Only explicit approvals with a scheme code."""
    out: dict[int, int] = {}
    if df.empty:
        return out
    approved = df[df["decision"].astype(str).str.lower() == "approved"]
    for _, row in approved.iterrows():
        sid = row.get("scheme_id")
        code = row.get("mf_scheme_code")
        if pd.isna(sid) or pd.isna(code) or str(code).strip() == "":
            continue
        try:
            out[int(sid)] = int(code)
        except (TypeError, ValueError):
            continue
    return out


def upsert_decision(
    df: pd.DataFrame,
    *,
    scheme_id: int,
    decision: str,
    mf_scheme_code: int | None,
    computed_score: float | None,
    et_fund_name: str,
    mf_scheme_name: str,
    notes: str = "",
) -> pd.DataFrame:
    decision = decision.strip().lower()
    if decision not in ("approved", "rejected"):
        raise ValueError(f"Invalid decision: {decision}")

    row = {
        "scheme_id": int(scheme_id),
        "decision": decision,
        "mf_scheme_code": int(mf_scheme_code) if decision == "approved" and mf_scheme_code else "",
        "computed_score": round(computed_score, 2) if computed_score is not None else "",
        "et_fund_name": et_fund_name,
        "mf_scheme_name": mf_scheme_name if decision == "approved" else "",
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }
    df = df[df["scheme_id"].astype(int) != int(scheme_id)].copy()
    return pd.concat([df, pd.DataFrame([row])], ignore_index=True)


def export_overrides_from_decisions(
    decisions: pd.DataFrame, path: Path = OVERRIDES_CSV
) -> int:
    """Write mfapi_et_manual_overrides.csv from approved decisions only."""
    approved = decisions[decisions["decision"].astype(str).str.lower() == "approved"]
    rows = []
    for _, r in approved.iterrows():
        code = r.get("mf_scheme_code")
        if pd.isna(code) or str(code).strip() == "":
            continue
        rows.append(
            {
                "scheme_id": int(r["scheme_id"]),
                "mf_scheme_code": int(code),
                "et_fund_name": r.get("et_fund_name", ""),
                "notes": r.get("notes") or "approved via review app",
            }
        )
    out = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8")
    return len(out)
