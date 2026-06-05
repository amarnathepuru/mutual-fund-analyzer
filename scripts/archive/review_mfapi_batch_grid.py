"""
Bulk table for batch-scrape auto-mappings (~206 funds).

Columns: MFAPI name | ET scraped name | Match % | ET mapping (dropdown) | Status

  streamlit run scripts/review_mfapi_batch_scrape.py --server.port 8503
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from match_mfapi_et import ET_MASTER, REPORT_OUT  # noqa: E402
from mfapi_et_decisions import DECISIONS_CSV, load_decisions, save_decisions, upsert_decision  # noqa: E402
from mfapi_scheme_name import et_significant_tokens, fund_name_match_score, mf_fund_name_cleaned, mf_significant_tokens  # noqa: E402
from review_mfapi_et_candidates import parse_et_alts  # noqa: E402

PROGRESS_CSV = ROOT / "data/reports/mfapi_et_scrape_batch_progress.csv"
MANUAL_CUTOFF = "2026-06-01T12:00:00"
STATUS_OPTIONS = ["—", "Accept", "No link"]


def _et_label(sid: int, name: str, score: float, *, tag: str = "") -> str:
    short = (name or "?")[:52] + ("…" if len(name or "") > 52 else "")
    suffix = f" [{tag}]" if tag else ""
    return f"{sid} — {short} ({score:.1f}%){suffix}"


def _parse_et_label(label: str) -> tuple[int | None, float, str]:
    if not label or not isinstance(label, str):
        return None, 0.0, ""
    label = label.strip()
    m = re.match(r"^(\d+)\s*—\s*(.+?)\s*\(([\d.]+)%\)", label)
    if not m:
        return None, 0.0, ""
    name = m.group(2).strip().rstrip("…")
    name = re.sub(r"\s*\[[^\]]+\]\s*$", "", name)
    return int(m.group(1)), float(m.group(3)), name


@st.cache_data(ttl=120)
def load_batch_queue() -> pd.DataFrame:
    prog = pd.read_csv(PROGRESS_CSV, encoding="utf-8-sig")
    ok = prog[prog["status"].astype(str).str.lower() == "ok"].copy()
    ok = ok[ok["scraped_at"].astype(str) < MANUAL_CUTOFF]
    ok["mf_scheme_code"] = ok["mf_scheme_code"].astype(int)
    ok["scraped_et_scheme_id"] = pd.to_numeric(ok["et_scheme_id"], errors="coerce")
    ok["scraped_et_fund_name"] = ok["et_fund_name"].fillna("").astype(str)
    ok["mfapi_cleaned"] = ok["mfapi_name_cleaned"].fillna("").astype(str).apply(
        lambda x: mf_fund_name_cleaned(x) if x else ""
    )

    report = pd.DataFrame()
    if REPORT_OUT.is_file():
        report = pd.read_csv(REPORT_OUT, encoding="utf-8-sig")
        report["mf_scheme_code"] = report["mf_scheme_code"].astype(int)
        ok = ok.merge(report, on="mf_scheme_code", how="left", suffixes=("", "_r"))
        for _, row in ok.iterrows():
            if row["mfapi_cleaned"]:
                continue
            name = mf_fund_name_cleaned(
                str(row.get("mfapi_fund_name_cleaned") or row.get("mfapi_scheme_name") or "")
            )
            ok.loc[ok["mf_scheme_code"] == row["mf_scheme_code"], "mfapi_cleaned"] = name

    ok["mfapi_full_name"] = ok.get("mfapi_scheme_name", ok["mfapi_cleaned"]).fillna(ok["mfapi_cleaned"])
    ok["name_match_pct"] = ok.apply(
        lambda r: round(
            fund_name_match_score(str(r["mfapi_cleaned"]), str(r["scraped_et_fund_name"])),
            1,
        ),
        axis=1,
    )
    return ok.sort_values("mfapi_cleaned").reset_index(drop=True)


def _build_remap_options(
    row: pd.Series,
    et_by_id: dict[int, pd.Series],
    *,
    max_options: int = 12,
) -> list[tuple[int, float, str, str]]:
    seen: set[int] = set()
    out: list[tuple[int, float, str, str]] = []

    def add(sid: int, score: float, name: str, tag: str = "") -> None:
        if sid in seen or sid <= 0:
            return
        seen.add(sid)
        out.append((sid, score, name, tag))

    scraped_sid = row.get("scraped_et_scheme_id")
    scraped_name = str(row.get("scraped_et_fund_name") or "")
    if pd.notna(scraped_sid):
        sid = int(float(scraped_sid))
        add(sid, 100.0, scraped_name or str(et_by_id.get(sid, {}).get("fund_name", "")), "scraped")

    if pd.notna(row.get("scheme_id")) and str(row.get("scheme_id", "")).strip():
        rep_sid = int(float(row["scheme_id"]))
        rep_sc = float(row["match_score"]) if pd.notna(row.get("match_score")) else 0.0
        rep_name = str(row.get("et_fund_name_r") or row.get("et_fund_name") or "")
        if not rep_name and rep_sid in et_by_id:
            rep_name = str(et_by_id[rep_sid].get("fund_name") or "")
        add(rep_sid, rep_sc, rep_name, "report")

    for sid, sc in parse_et_alts(str(row.get("alt_candidates") or "")):
        name = str(et_by_id[sid].get("fund_name") or "") if sid in et_by_id else ""
        add(sid, sc, name, "alt")

    mf_clean = str(row.get("mfapi_cleaned") or "")
    if mf_clean and len(out) < max_options:
        mf_toks = mf_significant_tokens(mf_clean)
        scored: list[tuple[int, float, str]] = []
        for sid, er in et_by_id.items():
            if sid in seen:
                continue
            et_name = str(er.get("fund_name") or "")
            if mf_toks and not (mf_toks & et_significant_tokens(et_name)):
                continue
            sc = fund_name_match_score(mf_clean, et_name)
            if sc >= 45.0:
                scored.append((sid, sc, et_name))
        scored.sort(key=lambda x: (-x[1], x[0]))
        for sid, sc, name in scored[: max_options - len(out)]:
            add(sid, sc, name, "name")

    out.sort(key=lambda x: (-x[1], x[0]))
    return out[:max_options]


def _prior_status(prior: dict | None) -> str:
    if not prior:
        return "—"
    dec = str(prior.get("decision") or "").lower()
    notes = str(prior.get("notes") or "").lower()
    if dec == "approved" and ("batch_scrape" in notes or "bulk_grid" in notes):
        return "Accept"
    if dec in ("rejected", "no_match"):
        return "No link"
    return "—"


def build_batch_grid(
    queue: pd.DataFrame,
    et_by_id: dict[int, pd.Series],
    decisions: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str], dict[str, tuple[int, float, str]], dict[int, set[str]]]:
    prior_by: dict[int, dict] = {}
    if not decisions.empty:
        for _, d in decisions.iterrows():
            prior_by[int(d["mf_scheme_code"])] = d.to_dict()

    pick_options: list[str] = [""]
    label_meta: dict[str, tuple[int, float, str]] = {}
    allowed: dict[int, set[str]] = {}

    rows: list[dict] = []
    for _, row in queue.iterrows():
        code = int(row["mf_scheme_code"])
        opts = _build_remap_options(row, et_by_id)
        labels = [_et_label(sid, name, sc, tag=tag) for sid, sc, name, tag in opts]
        allowed[code] = set(labels)
        default_label = labels[0] if labels else ""

        prior = prior_by.get(code)
        if prior and str(prior.get("decision", "")).lower() == "approved":
            psid = prior.get("scheme_id")
            if pd.notna(psid) and str(psid).strip():
                psid_i = int(float(psid))
                for lab in labels:
                    sid, _, _ = _parse_et_label(lab)
                    if sid == psid_i:
                        default_label = lab
                        break

        for sid, sc, name, tag in opts:
            lab = _et_label(sid, name, sc, tag=tag)
            if lab not in pick_options:
                pick_options.append(lab)
            label_meta[lab] = (sid, sc, name)

        scraped_sid = (
            int(float(row["scraped_et_scheme_id"]))
            if pd.notna(row["scraped_et_scheme_id"])
            else 0
        )
        rows.append(
            {
                "mf_scheme_code": code,
                "mfapi_fund_name": str(row["mfapi_cleaned"]),
                "et_scraped_name": str(row["scraped_et_fund_name"]),
                "name_match_pct": float(row.get("name_match_pct") or 0),
                "et_money_fund": default_label,
                "status": _prior_status(prior),
                "_scraped_sid": scraped_sid,
                "_mfapi_full": str(row.get("mfapi_full_name") or row["mfapi_cleaned"]),
                "_orig_status": _prior_status(prior),
                "_orig_et_pick": default_label,
            }
        )

    return pd.DataFrame(rows), pick_options, label_meta, allowed


def apply_batch_grid_save(
    edited: pd.DataFrame,
    baseline: pd.DataFrame,
    label_meta: dict[str, tuple[int, float, str]],
    allowed: dict[int, set[str]],
    et_by_id: dict[int, pd.Series],
    scheme_map: pd.DataFrame,
) -> tuple[int, int, list[str]]:
    decisions = load_decisions()
    saved = 0
    skipped = 0
    errors: list[str] = []

    mapped_et: dict[int, int] = {}
    if not scheme_map.empty:
        for _, m in scheme_map.iterrows():
            if pd.notna(m.get("scheme_id")) and pd.notna(m.get("mf_scheme_code")):
                mapped_et[int(m["scheme_id"])] = int(m["mf_scheme_code"])

    base_by = {int(r["mf_scheme_code"]): r for _, r in baseline.iterrows()}

    for _, row in edited.iterrows():
        code = int(row["mf_scheme_code"])
        base = base_by.get(code)
        if base is None:
            continue

        status = str(row.get("status") or "—").strip()
        pick = str(row.get("et_money_fund") or "").strip()
        orig_status = str(base.get("_orig_status") or "—").strip()
        orig_pick = str(base.get("_orig_et_pick") or "").strip()

        if status == orig_status and pick == orig_pick:
            skipped += 1
            continue

        mf_full = str(base.get("_mfapi_full") or "")

        if status in ("—", ""):
            errors.append(f"{base['mfapi_fund_name'][:42]}: set Status to Accept or No link")
            skipped += 1
            continue

        if status == "No link":
            decisions = upsert_decision(
                decisions,
                mf_scheme_code=code,
                decision="rejected",
                scheme_id=None,
                computed_score=None,
                mf_scheme_name=mf_full,
                et_fund_name="",
                notes="batch_scrape_review no link",
            )
            saved += 1
            continue

        if status == "Accept":
            if not pick:
                errors.append(f"{base['mfapi_fund_name'][:42]}: Accept needs ET mapping pick")
                skipped += 1
                continue
            if code in allowed and pick not in allowed[code]:
                errors.append(f"{base['mfapi_fund_name'][:42]}: ET pick not in suggestions")
                skipped += 1
                continue
            meta = label_meta.get(pick)
            if meta:
                et_sid, score, et_name = int(meta[0]), float(meta[1]), str(meta[2])
            else:
                et_sid, score, et_name = _parse_et_label(pick)
            if not et_sid:
                errors.append(f"{base['mfapi_fund_name'][:42]}: invalid ET pick")
                skipped += 1
                continue
            if et_sid in et_by_id:
                et_name = str(et_by_id[et_sid].get("fund_name") or et_name)
            if et_sid in mapped_et and mapped_et[et_sid] != code:
                errors.append(
                    f"{base['mfapi_fund_name'][:42]}: ET {et_sid} already mapped to MF {mapped_et[et_sid]}"
                )
                skipped += 1
                continue

            scraped_sid = int(base.get("_scraped_sid") or 0)
            note = "batch_scrape_review accept"
            if scraped_sid and et_sid != scraped_sid:
                note = "batch_scrape_review remap"
            decisions = upsert_decision(
                decisions,
                mf_scheme_code=code,
                decision="approved",
                scheme_id=et_sid,
                computed_score=score,
                mf_scheme_name=mf_full,
                et_fund_name=et_name,
                notes=note,
            )
            saved += 1
            continue

        skipped += 1

    save_decisions(decisions)
    return saved, skipped, errors


def render_batch_bulk_table(
    queue: pd.DataFrame,
    et_active: pd.DataFrame,
    scheme_map: pd.DataFrame,
    *,
    batch_decided: set[int],
) -> None:
    et_by_id = {int(r["scheme_id"]): r for _, r in et_active.iterrows()}
    decisions = load_decisions()

    with st.spinner("Building review table…"):
        grid, pick_options, label_meta, allowed = build_batch_grid(queue, et_by_id, decisions)

    if grid.empty:
        st.info("No funds to show.")
        return

    st.caption(
        "**All batch funds in one table.** "
        "Default **ET mapping** is the auto-scraped fund — leave it and set **Accept** to confirm. "
        "Change **ET mapping** if the scrape picked the wrong fund, then **Accept**. "
        "**No link** = MFAPI-only (no ET page). Click **Save all changes** when done."
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Accept all visible (unset → Accept)", use_container_width=True):
            mask = grid["status"].isin(["—", ""])
            grid.loc[mask, "status"] = "Accept"
            st.session_state["batch_grid_df"] = grid
            st.rerun()
    with c2:
        low_match = grid["name_match_pct"] < 70
        st.metric("Low name match (<70%)", int(low_match.sum()))
    with c3:
        pending = ~grid["mf_scheme_code"].astype(int).isin(batch_decided)
        st.metric("Not saved yet", int(pending.sum()))

    display = grid[
        [
            "mfapi_fund_name",
            "et_scraped_name",
            "name_match_pct",
            "et_money_fund",
            "status",
        ]
    ].copy()

    if "batch_grid_df" in st.session_state:
        prev = st.session_state["batch_grid_df"]
        if len(prev) == len(grid) and "mf_scheme_code" in prev.columns:
            display["status"] = prev["status"].values
            if "et_money_fund" in prev.columns:
                display["et_money_fund"] = prev["et_money_fund"].values

    table_height = min(900, 80 + len(display) * 32)

    with st.form("batch_all_form", clear_on_submit=False):
        edited = st.data_editor(
            display,
            column_config={
                "mfapi_fund_name": st.column_config.TextColumn(
                    "MFAPI fund name",
                    disabled=True,
                    width="large",
                ),
                "et_scraped_name": st.column_config.TextColumn(
                    "ET Money (auto-scraped)",
                    disabled=True,
                    width="large",
                ),
                "name_match_pct": st.column_config.NumberColumn(
                    "Name match %",
                    disabled=True,
                    format="%.1f",
                    width="small",
                    help="Similarity between MFAPI and scraped ET names (quick QA).",
                ),
                "et_money_fund": st.column_config.SelectboxColumn(
                    "ET mapping (confirm or change)",
                    options=pick_options,
                    width="large",
                    required=False,
                ),
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=STATUS_OPTIONS,
                    width="small",
                    required=True,
                ),
            },
            hide_index=True,
            use_container_width=True,
            height=table_height,
            key="batch_review_all_v2",
        )
        col_save, col_hint = st.columns([1, 3])
        with col_save:
            submitted = st.form_submit_button("Save all changes", type="primary")
        with col_hint:
            st.caption("Only rows you changed (status or ET mapping) are written.")

    st.session_state["batch_grid_df"] = edited.copy()
    st.session_state["batch_grid_df"]["mf_scheme_code"] = grid["mf_scheme_code"].values

    if submitted:
        full = edited.copy()
        full["mf_scheme_code"] = grid["mf_scheme_code"].values
        merged = full.merge(
            grid[
                [
                    "mf_scheme_code",
                    "_scraped_sid",
                    "_mfapi_full",
                    "_orig_status",
                    "_orig_et_pick",
                ]
            ],
            on="mf_scheme_code",
            how="left",
        )
        saved, skipped, errors = apply_batch_grid_save(
            merged, grid, label_meta, allowed, et_by_id, scheme_map
        )
        for e in errors[:20]:
            st.error(e)
        if saved:
            st.success(f"Saved **{saved}** row(s). Unchanged: **{skipped}**.")
            load_batch_queue.clear()
            if "batch_grid_df" in st.session_state:
                del st.session_state["batch_grid_df"]
            st.rerun()
        elif errors:
            st.warning(f"No rows saved. Unchanged: **{skipped}**.")
        else:
            st.info(f"No changes. Unchanged: **{skipped}**.")

    with st.expander("Preview decisions file"):
        dec = load_decisions()
        if dec.empty:
            st.write("No decisions yet.")
        else:
            mask = dec["notes"].astype(str).str.contains("batch_scrape", case=False, na=False)
            st.dataframe(dec.loc[mask].tail(30), use_container_width=True)
