# NAV data — architecture notes (saved for implementation)

Companion to `TRACK_DESIGN.md`. Track needs **purchase NAV** (on/before `invested_date`) and **mark-to-market** (latest + optional history for charts).

## Do not put full market NAV in Supabase

- Daily NAV for all Indian schemes × years = **millions of rows** — wrong fit for user Postgres (RLS, cost, bulk reads).
- Supabase: **user holdings, investment periods**, optional **`latest_nav` / `nav_as_of`** per held scheme only — not full time series.
- **Time series**: local **SQLite** or **Parquet** under `data/nav/` (same pattern as `fund_master` / processed CSVs).

## Scale reference

| Scope | Order of magnitude | Storage |
|--------|-------------------|---------|
| User portfolio (~20–50 schemes × ~10y daily) | ~10⁴–10⁵ rows | Trivial local |
| All active schemes × full history | ~10⁷+ rows | OK as compressed Parquet/SQLite; avoid Postgres row store |
| Live MFApi on every Streamlit rerun | Bad | Batch job + cache |

## Recommended hybrid

| Layer | Contents | Where |
|--------|----------|--------|
| Identity | `fund_name` + `plan_type` → MFApi/AMFI `scheme_code`, ISIN | `nav_scheme_map` (CSV or extend `fund_master`) |
| NAV series | `(scheme_code, nav_date, nav)` | `data/nav/` — SQLite `nav.db` and/or `{scheme_code}.parquet` |
| Hot cache | latest NAV, last sync | `@st.cache_data`, SQLite meta table |
| User data | holdings, periods | Supabase (`portfolios` / future `track_holdings`) |

## MFApi (v1 source)

- List: `GET https://api.mfapi.in/mf`
- History: `GET https://api.mfapi.in/mf/{scheme_code}`

**Pros:** Simple JSON, AMFI-aligned codes, no API key.  
**Cons:** Third-party uptime/TOS; names differ from ETMoney; **Direct / Regular / Growth / IDCW** = different scheme codes.

**Ingestion (batch, not UI):**

1. Build/refresh `nav_scheme_map` (MFApi list + fuzzy match to `fund_name`; manual overrides).
2. Per mapped code: pull full history or incremental from `last_synced_date`.
3. Throttle (e.g. 200–500 ms between schemes); run nightly/weekly.

**Runtime lookups:**

- `get_nav(scheme_code, on_or_before_date)` — last NAV ≤ `invested_date` (handle non-trading days).
- `get_latest_nav(scheme_code)` — refresh if stale (>1 business day).
- Charts: load series only for schemes in selected portfolio/period.

## Mapping is the hard part

- App uses **ETMoney `scheme_id`** in `fund_master` — not the same as **MFApi scheme code**.
- Map **`fund_name` + `plan_type`** → `mf_scheme_code` (and optional ISIN).
- Table fields: `fund_name`, `plan_type`, `mf_scheme_code`, `isin`, `match_confidence`, `source` (`mfapi` | `manual`).

## Wire to app

- `_apply_nav_units_autofill` in `app.py`: TODO — when `units` and `nav` empty, `units = invested_amount / purchase_nav`.
- Track: current value = `units × latest_nav`; performance vs cost; optional snapshots (`TRACK_DESIGN.md` phase 2).

## Phasing

| Phase | Deliverable |
|--------|-------------|
| **A** | Map funds in master/portfolios; sync NAV for those codes; purchase + latest in Track |
| **B** | Incremental daily sync; stale detection |
| **C** | Optional full-universe local Parquet for screening (not required for Track v1) |

## Alternatives (later)

- Paid vendors — merged schemes, corporate actions.
- Other official feeds only if MFApi gaps appear (not in current scope).

## Suggested files (greenfield)

```
data/
  nav_scheme_map.csv
  nav/
    nav.db                    # or per-scheme .parquet
scripts/
  sync_nav.py                 # MFApi ingest + incremental
```

## Open decisions

- [ ] SQLite single DB vs one Parquet per scheme
- [ ] Fuzzy match rules + UI to fix unmapped funds
- [ ] Cloud deploy: sync `data/nav/` bundle to object storage vs rebuild on server
- [ ] Store `latest_nav` on Supabase for multi-device vs local-only

## Related code

- `app.py` — `_apply_nav_units_autofill`, portfolio columns `nav`, `units`, `invested_date`
- `scripts/verify_data.py` — `scheme_id` in fund master (ETMoney, not MFApi)
- **`data/DATA_PIPELINE.md`** — ET ↔ MFApi match, sidecar map, MF supplement, execution batches
