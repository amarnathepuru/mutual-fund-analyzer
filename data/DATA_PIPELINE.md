# Fund master + NAV data pipeline (v2)

Locked decisions from planning session. Implements Track prerequisites; see also `supabase/NAV_DATA.md` and `supabase/TRACK_DESIGN.md`.

## Active data sources (current)

| Role | Source | Notes |
|------|--------|--------|
| NAV + scheme master | **MFApi** (`api.mfapi.in`) | Direct–Growth universe; `mf_scheme_code` is the AMFI scheme code returned by MFApi (not scraped from AMFI site) |
| Holdings + fund master (ET) | **ET Money** | Existing `scraper/` → `fund_master_auto.csv`, `master_holdings.csv` |
| Analyze portfolio metrics | Derived from MFApi NAV + ET holdings/master | No separate AMFI/AMC ingest |

**Deferred / abandoned for now:** AMFI website exports, AMC disclosure HTML, third-party mirrors (e.g. RightAdvise). Revisit only when replacing ET holdings.

### Feature-specific universes

| Feature | Fund universe | Holdings required? |
|---------|---------------|------------------|
| **Analyze / Compare** | ET Money ACTIVE with scraped holdings only | Yes |
| **Track / Portfolio** | **881** MFAPI schemes (dropdown pick); ET map when available | No — NAV-only funds allowed |
| **ET ↔ MFAPI match (Batch 3)** | ET ACTIVE **minus index** ↔ **881** MFAPI pruned | Index ETFs excluded (`excluded_index`) |

- Auto-link threshold: **≥ 95%** score with gap **≥ 3** vs #2 → `auto_ok`; **100%** match → `auto_ok` even if gap &lt; 3.
- Ambiguous ties (95–99.99% and gap &lt; 3): flagged for manual review.
- Portfolio NAV path: `fund_name` → ET master → `fund_scheme_map` → `mf_scheme_code`.
- Track fund picker: **dropdown** from 881 MFAPI names (no free-text fuzzy pick).
- **ET→MFAPI match review:** `streamlit run scripts/review_et_mfapi_app.py` → `data/et_mfapi_decisions.csv`; export → `mfapi_et_manual_overrides.csv`.
- **MFAPI→ET match review (unmapped MFAPI-only):** `python scripts/match_mfapi_et.py` → `data/reports/mfapi_et_candidate_report.csv`; `streamlit run scripts/review_mfapi_et_app.py` → `data/mfapi_et_decisions.csv`; export → `data/mfapi_to_et_approved.csv`; apply → `python scripts/apply_mfapi_et_map.py` (after ET scrape for approved pairs).
- **MFAPI→ET scrape (sample / one fund):** `python scripts/scrape_mfapi_et_one.py --mf-code 103490` (Quantum Value); validate → `streamlit run scripts/validate_mfapi_et_scrape_app.py --server.port 8503`. Library: `scripts/et_mfapi_scrape_lib.py`. Queue = `nav_universe_schemes` minus `fund_scheme_map` (Direct–Growth only).
- **MFAPI→ET scrape (batch, no map yet):** `python scripts/scrape_mfapi_et_batch.py --resume` → `data/reports/mfapi_et_scrape_batch_progress.csv`; then `match_mfapi_et.py` + review + `apply_mfapi_et_map.py`. Batch review UI archived under `scripts/archive/`.
- **MFAPI→ET map audit:** `python scripts/audit_fund_scheme_map.py` → `data/reports/fund_scheme_map_audit_review.csv`; browse → `streamlit run scripts/validate_map_audit_app.py --server.port 8505`.
- **Close NAV universe (no ET / duplicates):** `python scripts/close_out_nav_unmapped.py` → rejects remaining unmapped MFAPI codes for track/NAV-only (`data/reports/nav_unmapped_closed.csv`). Mapping target for Analyze: **741** ET-linked rows in `fund_scheme_map.csv` (Jun 2026).
- **Refresh analyse downstream (after map/scrape):** `python scripts/sync_map_master_metadata.py` → `python analytics/normalize_holdings.py` → `python scripts/rebuild_fund_similarity.py` → `python scripts/write_master_sync_qc.py` (see `data/reports/master_sync_qc.txt`).

## Locked decisions

| Topic | Decision |
|--------|----------|
| MFApi universe | **Direct + Growth** schemes only (one AMFI scheme per logical fund for mapping) |
| ET match scope | **`fund_master_auto.csv` where `status=ACTIVE` only** (~500); skip `fund_master_invalid.csv` |
| ET identifiers | Keep ET `scheme_id`, `url`, etc. on ET master |
| MF identifiers | **`isin` + `mf_scheme_code` (AMFI)** via sidecar, not scraped into ET file by default |
| ISIN / AMFI mapping storage | **Option A:** `data/fund_scheme_map.csv` keyed by `scheme_id` (ET) — survives `discover_funds.py` rewrites |
| MF-only funds | `data/fund_master_mfapi.csv`, `status=NAV_ONLY`, `data_source=mfapi`, blank ET fields |
| Runtime master | **Union on read** (ET master + scheme map join + MF supplement); no static `fund_master_unified.csv` |
| Union dedupe | If same ISIN in both ET and supplement, **prefer ET row** |
| Match apply | **Report first** — user reviews `et_mfapi_match_report.csv` before writing map / supplement |
| Auto-match threshold | TBD after first match % run |
| Manual fixes | `data/mfapi_et_manual_overrides.csv` for ambiguous rows |
| NAV | Full history **from 2015-01-01** for **Equity + Hybrid + Liquid** Direct–Growth schemes → `data/nav/nav.db` |
| DB | **Deferred** until Track works locally |
| Scrapers | `discover_funds.py` / `scrape_holdings` only touch **`fund_master_auto.csv`**; never delete map or MF supplement |
| Invalid CSV | No matching in this phase |
| Plans (users) | Direct–Growth only for now (no Regular / IDCW in universe) |

## File layout

```
data/
  backups/                              # dated fund_master_auto.csv before risky ops
  raw/mfapi/                            # API JSON snapshots
  reports/                              # match reports (read-only review)
  fund_master_auto.csv                  # ET discovery (ACTIVE / NO_HOLDINGS / ERROR)
  fund_scheme_map.csv                   # scheme_id → isin, mf_scheme_code, match_*
  fund_master_mfapi.csv                 # NAV_ONLY MFApi-only funds
  mfapi_et_manual_overrides.csv           # user-filled corrections (template from script)
  nav/nav.db                            # (scheme_code|isin), nav_date, nav  (date >= 2015-01-01)
```

### `fund_scheme_map.csv` (sidecar)

Suggested columns:

- `scheme_id` (ET, int, PK)
- `mf_scheme_code`
- `isin`
- `match_score`, `match_method` (`auto` | `manual`)
- `matched_at`, `notes`

### `fund_master_mfapi.csv`

Same columns as ET master where applicable; ET-only fields blank; `status=NAV_ONLY`, `data_source=mfapi`.

## Capability flags (app)

After union in `load_master()`:

- `has_holdings` — fund in `master_holdings.csv` / ET ACTIVE with scraped holdings
- `has_nav` — row in scheme map or MF supplement with `mf_scheme_code`

**Analyse Funds tab:** ET holdings only (`master_for_analyze()`). MFAPI not used.

**My Portfolio (single upload in Manage):**

- Validate fund names against **MFAPI 881** (`portfolio_data.py` + `nav_universe_schemes.csv`).
- Persist `mf_scheme_code`, `display_fund_name` (clean UI label), `fund_name` (same value for resolution), `plan_type`, `option_type`, `et_fund_name` when mapped.
- **Analyse my portfolio:** holdings overlap only when `can_analyse` (ET holdings exist).
- **Track my portfolio:** NAV from `nav.db` for all `can_track` rows.

**Analyze / Compare / overlap:** exclude `has_holdings=false`; show which funds excluded; optional NAV-only metrics where data exists.

## Execution batches

| Batch | Work | App changes |
|-------|------|-------------|
| **0** | `backups/`, gitignore `data/nav/`, `data/raw/mfapi/` | No — **done** |
| **1** | MFApi scheme list → parse plan/option → Direct–Growth CSV + field inventory | No — **done** |
| **2** | NAV backfill 2015+ → `nav.db` (resumable, throttled) | No — **in progress / run locally** |
| **3** | `match_et_mfapi.py` → **`reports/et_mfapi_match_report.csv` only** | No |
| — | **STOP — user reviews report; then** overrides + apply map + build supplement | No |
| **4** | Apply approved matches → `fund_scheme_map.csv`; build `fund_master_mfapi.csv` | No |
| **5** | Extend `scripts/verify_data.py` | No |
| **6** | `load_master()` union + holdings/NAV UX | Yes (minimal) |
| **7** | Track (`TRACK_DESIGN.md`) | Yes |

## Step 3 gate (human)

Do **not** write `fund_scheme_map.csv` or `fund_master_mfapi.csv` until:

1. User has reviewed `data/reports/et_mfapi_match_report.csv`
2. User has filled `mfapi_et_manual_overrides.csv` if needed
3. User confirms auto-apply rules or row-by-row approval

## Rollback

- Backup ET master to `data/backups/` before any manual apply
- Delete or rename `fund_scheme_map.csv` / `fund_master_mfapi.csv` to revert mapping/supplement
- `nav.db` is independent; safe to rebuild from MFApi

## Batch 1 outputs (generated)

- `data/raw/mfapi/mf_scheme_list_YYYYMMDD.json` — raw list API snapshot
- `data/raw/mfapi/all_schemes_parsed.csv` — all schemes with `fund_name_base`, `plan_type`, `option_type`
- `data/raw/mfapi/direct_growth_schemes.csv` — `is_direct_growth == true` (full MFApi DG list)
- `data/raw/mfapi/nav_universe_schemes.csv` — pruned NAV universe (~881 schemes; Equity/Hybrid/Liquid)
- `data/raw/mfapi/scheme_meta_all.csv` — from `nav.db` (`scheme_category`, `fund_house`, `scheme_type`, …)
- `data/raw/mfapi/scheme_meta_direct_growth.csv` — same, filtered to Direct–Growth codes

Run: `python scripts/mfapi_export_scheme_meta.py`
- `data/raw/mfapi/MFAPI_FIELD_INVENTORY.md` — API + parsed column reference
- `data/reports/mfapi_batch1_qc.txt` — counts and samples (local only, gitignored)

Run: `python scripts/mfapi_fetch_schemes.py` (add `--refresh` to re-download)

## Batch 2 outputs

- `data/nav/nav.db` — SQLite: `schemes` (meta + sync status), `nav_prices` (daily NAV >= 2015-01-01)
- `data/reports/mfapi_batch2_qc.txt` — row counts, errors sample (local only, gitignored)

Run (repo root):

```bash
python scripts/mfapi_fetch_nav.py --limit 5    # smoke test
python scripts/mfapi_prune_nav_db.py           # one-time: trim DB to Equity/Hybrid/Liquid
python scripts/mfapi_fetch_nav.py              # resume (~881 NAV universe schemes)
python scripts/mfapi_fetch_nav.py --retry-failed
python scripts/mfapi_fetch_nav.py --refresh    # full re-download
```

~30–45 min for full universe at default 0.35s delay. Safe to interrupt; re-run resumes.

## Related scripts (to add)

- `scripts/mfapi_fetch_schemes.py` — Batch 1 ✓
- `scripts/mfapi_scheme_name.py` — name/plan/option parser ✓
- `scripts/mfapi_fetch_nav.py` — Batch 2 ✓
- `scripts/mfapi_nav_universe.py` — Equity/Hybrid/Liquid filter ✓
- `scripts/mfapi_prune_nav_db.py` — trim `nav.db` to NAV universe ✓
- `scripts/match_et_mfapi.py` — Batch 3 (report only) ✓
- `scripts/apply_et_mfapi_map.py` — Batch 4 (merge auto_ok + decisions → `fund_scheme_map.csv`) ✓
- `scripts/review_et_mfapi_app.py` — review UI (card + grid) ✓
