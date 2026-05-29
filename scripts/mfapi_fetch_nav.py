"""
Batch 2: Backfill NAV history (>= 2015-01-01) for Direct-Growth schemes into data/nav/nav.db.

Resumable: skips schemes already synced with status=ok unless --refresh.
Does not modify app.py or fund master files.

Usage (repo root):
  python scripts/mfapi_fetch_nav.py --limit 5          # smoke test
  python scripts/mfapi_fetch_nav.py                    # resume / continue all
  python scripts/mfapi_fetch_nav.py --refresh          # re-fetch every scheme
  python scripts/mfapi_fetch_nav.py --retry-failed     # only error rows
  python scripts/mfapi_fetch_nav.py --code 120503        # single scheme
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mfapi_nav_universe import scheme_in_nav_universe

DATA = ROOT / "data"
DG_CSV = DATA / "raw" / "mfapi" / "direct_growth_schemes.csv"
NAV_UNIVERSE_CSV = DATA / "raw" / "mfapi" / "nav_universe_schemes.csv"
NAV_DIR = DATA / "nav"
NAV_DB = NAV_DIR / "nav.db"
REPORTS = DATA / "reports"

MFAPI_DETAIL_URL = "https://api.mfapi.in/mf/{code}"
USER_AGENT = "FundLens/1.0 (mutual-fund-analyzer; batch2)"
NAV_MIN_DATE = date(2015, 1, 1)
DEFAULT_DELAY_SEC = 0.35


def _parse_nav_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;

        CREATE TABLE IF NOT EXISTS schemes (
            mf_scheme_code INTEGER PRIMARY KEY,
            scheme_name_raw TEXT,
            fund_name_base TEXT,
            isin_growth TEXT,
            fund_house TEXT,
            scheme_category TEXT,
            scheme_type TEXT,
            sync_status TEXT NOT NULL DEFAULT 'pending',
            error_message TEXT,
            nav_rows INTEGER NOT NULL DEFAULT 0,
            first_nav_date TEXT,
            last_nav_date TEXT,
            synced_at TEXT
        );

        CREATE TABLE IF NOT EXISTS nav_prices (
            mf_scheme_code INTEGER NOT NULL,
            nav_date TEXT NOT NULL,
            nav REAL NOT NULL,
            PRIMARY KEY (mf_scheme_code, nav_date),
            FOREIGN KEY (mf_scheme_code) REFERENCES schemes(mf_scheme_code)
        );

        CREATE INDEX IF NOT EXISTS idx_nav_prices_date
            ON nav_prices(nav_date);
        """
    )
    conn.commit()


def _default_codes_csv() -> Path:
    if NAV_UNIVERSE_CSV.is_file():
        return NAV_UNIVERSE_CSV
    return DG_CSV


def _load_direct_growth_codes(
    csv_path: Path, *, only_code: int | None, limit: int | None
) -> pd.DataFrame:
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"Missing {csv_path}. Run: python scripts/mfapi_fetch_schemes.py"
        )
    df = pd.read_csv(csv_path)
    if csv_path.resolve() != NAV_UNIVERSE_CSV.resolve():
        if "scheme_category" in df.columns:
            mask = df.apply(
                lambda r: scheme_in_nav_universe(
                    r.get("scheme_category"), r.get("scheme_name_raw")
                ),
                axis=1,
            )
        else:
            mask = df["scheme_name_raw"].apply(
                lambda n: scheme_in_nav_universe(None, n)
            )
        df = df[mask].copy()
    if only_code is not None:
        df = df[df["mf_scheme_code"].astype(int) == only_code]
    if limit is not None and limit > 0:
        df = df.head(limit)
    return df


def _pending_codes(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    *,
    refresh: bool,
    retry_failed: bool,
) -> list[int]:
    codes = [int(c) for c in df["mf_scheme_code"].dropna().astype(int)]
    if refresh or not codes:
        return codes

    placeholders = ",".join("?" * len(codes))
    cur = conn.execute(
        f"SELECT mf_scheme_code, sync_status FROM schemes WHERE mf_scheme_code IN ({placeholders})",
        codes,
    )
    status_map = {int(r[0]): r[1] for r in cur.fetchall()}

    if retry_failed:
        return [c for c in codes if status_map.get(c) == "error"]
    return [c for c in codes if status_map.get(c) != "ok"]


def _fetch_detail(code: int) -> dict:
    url = MFAPI_DETAIL_URL.format(code=code)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if not isinstance(body, dict):
        raise ValueError("Unexpected response type")
    if body.get("status") not in (None, 200, "SUCCESS"):
        # MFApi sometimes omits or uses string status
        pass
    return body


def _upsert_scheme_meta(
    conn: sqlite3.Connection,
    row: pd.Series,
    meta: dict,
    *,
    sync_status: str,
    error_message: str | None = None,
    nav_rows: int = 0,
    first_nav: str | None = None,
    last_nav: str | None = None,
) -> None:
    isin = (meta.get("isin_growth") or row.get("isin_growth") or "") or None
    if isin:
        isin = str(isin).strip()
    conn.execute(
        """
        INSERT INTO schemes (
            mf_scheme_code, scheme_name_raw, fund_name_base, isin_growth,
            fund_house, scheme_category, scheme_type,
            sync_status, error_message, nav_rows, first_nav_date, last_nav_date, synced_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(mf_scheme_code) DO UPDATE SET
            scheme_name_raw=excluded.scheme_name_raw,
            fund_name_base=excluded.fund_name_base,
            isin_growth=COALESCE(excluded.isin_growth, schemes.isin_growth),
            fund_house=excluded.fund_house,
            scheme_category=excluded.scheme_category,
            scheme_type=excluded.scheme_type,
            sync_status=excluded.sync_status,
            error_message=excluded.error_message,
            nav_rows=excluded.nav_rows,
            first_nav_date=excluded.first_nav_date,
            last_nav_date=excluded.last_nav_date,
            synced_at=excluded.synced_at
        """,
        (
            int(row["mf_scheme_code"]),
            str(row.get("scheme_name_raw") or meta.get("scheme_name") or ""),
            str(row.get("fund_name_base") or ""),
            isin,
            meta.get("fund_house"),
            meta.get("scheme_category"),
            meta.get("scheme_type"),
            sync_status,
            error_message,
            nav_rows,
            first_nav,
            last_nav,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def _sync_one_scheme(
    conn: sqlite3.Connection, row: pd.Series, *, min_date: date
) -> tuple[str, int, str | None]:
    code = int(row["mf_scheme_code"])
    body = _fetch_detail(code)
    meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
    data = body.get("data") or []
    if not isinstance(data, list):
        raise ValueError("Missing data array in MFApi response")

    if body.get("status") == 404 or (not data and not meta):
        raise ValueError("No NAV data returned")

    rows_to_insert: list[tuple[int, str, float]] = []
    for item in data:
        if isinstance(item, dict):
            d_raw = item.get("date")
            nav_raw = item.get("nav")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            d_raw, nav_raw = item[0], item[1]
        else:
            continue
        d = _parse_nav_date(str(d_raw))
        if d is None or d < min_date:
            continue
        try:
            nav_val = float(nav_raw)
        except (TypeError, ValueError):
            continue
        rows_to_insert.append((code, d.isoformat(), nav_val))

    conn.execute("DELETE FROM nav_prices WHERE mf_scheme_code = ?", (code,))

    if rows_to_insert:
        conn.executemany(
            "INSERT OR REPLACE INTO nav_prices (mf_scheme_code, nav_date, nav) VALUES (?, ?, ?)",
            rows_to_insert,
        )

    first_nav = min(r[1] for r in rows_to_insert) if rows_to_insert else None
    last_nav = max(r[1] for r in rows_to_insert) if rows_to_insert else None
    _upsert_scheme_meta(
        conn,
        row,
        meta,
        sync_status="ok",
        nav_rows=len(rows_to_insert),
        first_nav=first_nav,
        last_nav=last_nav,
    )
    return "ok", len(rows_to_insert), None


def _write_qc_report(conn: sqlite3.Connection, path: Path, run_stats: dict) -> None:
    total = conn.execute("SELECT COUNT(*) FROM schemes").fetchone()[0]
    ok = conn.execute("SELECT COUNT(*) FROM schemes WHERE sync_status='ok'").fetchone()[0]
    err = conn.execute("SELECT COUNT(*) FROM schemes WHERE sync_status='error'").fetchone()[0]
    nav_rows = conn.execute("SELECT COUNT(*) FROM nav_prices").fetchone()[0]
    with_isin = conn.execute(
        "SELECT COUNT(*) FROM schemes WHERE sync_status='ok' AND isin_growth IS NOT NULL"
    ).fetchone()[0]
    lines = [
        "MFApi Batch 2 — NAV sync QC",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Run: attempted={run_stats.get('attempted', 0)} "
        f"ok={run_stats.get('ok', 0)} error={run_stats.get('error', 0)}",
        "",
        f"DB schemes rows: {total} (ok={ok}, error={err})",
        f"NAV price rows (>= {NAV_MIN_DATE.isoformat()}): {nav_rows}",
        f"OK schemes with isin_growth: {with_isin}",
        "",
    ]
    errors = conn.execute(
        "SELECT mf_scheme_code, error_message FROM schemes WHERE sync_status='error' LIMIT 20"
    ).fetchall()
    if errors:
        lines.append("Sample errors:")
        for c, msg in errors:
            lines.append(f"  {c}: {msg}")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="MFApi Batch 2: NAV backfill to SQLite")
    parser.add_argument("--limit", type=int, default=None, help="Max schemes to process this run")
    parser.add_argument("--code", type=int, default=None, help="Single mf_scheme_code")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SEC, help="Seconds between API calls")
    parser.add_argument("--refresh", action="store_true", help="Re-fetch all schemes (replace NAV rows)")
    parser.add_argument("--retry-failed", action="store_true", help="Only schemes with sync_status=error")
    parser.add_argument(
        "--from-date",
        default=NAV_MIN_DATE.isoformat(),
        help="Minimum NAV date to store (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--dg-csv",
        type=Path,
        default=None,
        help="Scheme list CSV (default: nav_universe_schemes.csv if present else direct_growth)",
    )
    args = parser.parse_args()

    try:
        min_date = datetime.strptime(args.from_date, "%Y-%m-%d").date()
    except ValueError:
        print(f"Invalid --from-date: {args.from_date}")
        return 1

    NAV_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    codes_csv = args.dg_csv or _default_codes_csv()
    df = _load_direct_growth_codes(codes_csv, only_code=args.code, limit=args.limit)
    if df.empty:
        print("No schemes to process.")
        return 1

    stats = {"attempted": 0, "ok": 0, "error": 0}
    conn = sqlite3.connect(NAV_DB)
    try:
        _init_db(conn)
        pending_codes = _pending_codes(
            conn, df, refresh=args.refresh, retry_failed=args.retry_failed
        )
        if args.code is not None:
            pending_codes = [args.code]

        code_set = set(pending_codes)
        work = df[df["mf_scheme_code"].astype(int).isin(code_set)].copy()
        if args.limit is not None and args.limit > 0:
            work = work.head(args.limit)

        total_work = len(work)
        if total_work == 0:
            ok_n = conn.execute("SELECT COUNT(*) FROM schemes WHERE sync_status='ok'").fetchone()[0]
            print(f"Nothing pending. {ok_n} schemes already synced (ok). Use --refresh to redo.")
            _write_qc_report(conn, REPORTS / "mfapi_batch2_qc.txt", {"attempted": 0, "ok": 0, "error": 0})
            return 0

        est_min = (total_work * args.delay) / 60.0
        print(f"NAV DB: {NAV_DB}")
        print(f"Schemes this run: {total_work} (delay={args.delay}s, ~{est_min:.0f} min)")
        print(f"Store NAV dates >= {min_date.isoformat()}")

        t0 = time.time()

        for i, (_, row) in enumerate(work.iterrows(), start=1):
            code = int(row["mf_scheme_code"])
            stats["attempted"] += 1
            try:
                status, n_rows, _ = _sync_one_scheme(conn, row, min_date=min_date)
                conn.commit()
                stats["ok"] += 1
                if i % 25 == 0 or i == total_work:
                    elapsed = time.time() - t0
                    print(f"  [{i}/{total_work}] {code} ok ({n_rows} rows) — {elapsed:.0f}s elapsed")
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                conn.rollback()
                stats["error"] += 1
                meta = {}
                _upsert_scheme_meta(
                    conn,
                    row,
                    meta,
                    sync_status="error",
                    error_message=str(exc)[:500],
                )
                conn.commit()
                print(f"  [{i}/{total_work}] {code} ERROR: {exc}")

            if i < total_work:
                time.sleep(args.delay)

        _write_qc_report(conn, REPORTS / "mfapi_batch2_qc.txt", stats)
        nav_total = conn.execute("SELECT COUNT(*) FROM nav_prices").fetchone()[0]
        print()
        print("=" * 60)
        print("BATCH 2 RUN COMPLETE")
        print("=" * 60)
        print(f"  ok={stats['ok']} error={stats['error']} attempted={stats['attempted']}")
        print(f"  nav_prices rows in DB: {nav_total}")
        print(f"  QC: {REPORTS / 'mfapi_batch2_qc.txt'}")
        print("  Re-run without --limit to resume pending schemes.")
    finally:
        conn.close()

    return 0 if stats.get("error", 0) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
