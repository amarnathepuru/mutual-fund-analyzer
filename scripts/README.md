# Scripts — what you actually need

**67 → ~46** Python files in the repo; **21 active scripts** (+ 25 archived) after cleanup.

## Required to run FundLens (`streamlit run app.py`)

| File | Role |
|------|------|
| `app.py` | Main app |
| `fundlens_auth.py` | Auth |
| `portfolio_data.py` | Portfolio / MFAPI resolution |
| `analytics/normalize_holdings.py` | Build `normalized_holdings.csv` (after scrape) |
| `analytics/overlap_*.py` (6 modules) | Overlap matrix UI |
| `scraper/discover_funds.py` | Refresh ET fund list |
| `scraper/scrape_holdings.py` | Refresh holdings |

## Active scripts (maintenance — 21 files)

| Script | When |
|--------|------|
| `verify_data.py` | Sanity-check data |
| `audit_fund_scheme_map.py` | Map QA |
| `sync_map_master_metadata.py` | Fix blank names/ISIN on map |
| `fix_wrong_map.py` | Remove a bad mapping |
| `apply_mfapi_et_map.py` | Apply new review decisions |
| `match_mfapi_et.py` | Regenerate candidate report (new funds only) |
| `match_et_mfapi.py` | Shared match helpers (imported by `match_mfapi_et.py`) |
| `scrape_mfapi_et_one.py` | Scrape one new MFAPI→ET link |
| `et_mfapi_scrape_lib.py` | Library (imported) |
| `mfapi_scheme_name.py` | Library (imported) |
| `mfapi_et_decisions.py` | Library (imported) |
| `rebuild_fund_similarity.py` | Refresh overlap pairs |
| `write_master_sync_qc.py` | Post-sync summary |
| `cleanup_data_artifacts.py` | Wipe regenerable reports/backups |
| `validate_map_audit_app.py` | Streamlit map audit (port 8505) |
| `mfapi_fetch_schemes.py` | Rebuild raw MFAPI list |
| `mfapi_nav_universe.py` | Rebuild `nav_universe_schemes.csv` |
| `mfapi_fetch_nav.py` | Backfill `nav.db` |
| `mfapi_prune_nav_db.py` | Prune NAV DB |
| `et_defer_unmapped_index.py` | Optional: defer index ETFs in master |
| `et_mfapi_decisions.py` | Library (ET→MFAPI decisions) |
| `et_mfapi_match_scope.py` | Library (index filter) |

## Archived (`scripts/archive/` — 25 files)

Completed mapping sprint: batch/manual scrape, both review UIs, slug tools, ET→MFAPI apply/review, etc.

See [`archive/README.md`](archive/README.md). Restore a file only if you need that workflow again.

## Refresh pipeline (after data change)

```bash
python scripts/sync_map_master_metadata.py
python analytics/normalize_holdings.py
python scripts/rebuild_fund_similarity.py
python scripts/write_master_sync_qc.py
```
