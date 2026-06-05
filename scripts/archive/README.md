# Archived scripts

Not needed for day-to-day app use. Kept for history and rare re-runs.

## MFAPI→ET sprint (Jun 2026)

| Script | Notes |
|--------|--------|
| `seed_manual_links.py` | One-time manual URL CSV |
| `import_slug_construct_csv.py`, `validate_slug_construct.py`, `validate_et_slugs.py` | Slug experiments |
| `review_mfapi_et_scrape_failures.py` | Batch failure UI |
| `apply_batch_scrape_review.py` | Rebuild decisions from progress CSV |
| `export_et_mfapi_audit.py` | Ad-hoc export |
| `review_mfapi_batch_scrape.py`, `review_mfapi_batch_grid.py` | 206-fund batch review |
| `scrape_mfapi_et_batch.py`, `scrape_mfapi_et_manual_links.py`, `apply_manual_et_map.py` | Batch/manual scrape |
| `close_out_nav_unmapped.py` | Closed 141 NAV-only funds |
| `analyze_scrape_holdings_quality.py`, `repair_mfapi_scrape_progress.py` | QC utilities |
| `review_mfapi_et_app.py`, `review_mfapi_et_grid.py`, `review_mfapi_et_candidates.py`, `review_mfapi_et_validation.py` | Match review UI stack |

## ET→MFAPI (Batch 3)

| Script | Notes |
|--------|--------|
| `apply_et_mfapi_map.py` | Apply approvals |
| `review_et_mfapi_app.py`, `review_et_mfapi_grid.py`, `review_queue.py` | Review UI |

`match_et_mfapi.py` stays in **`scripts/`** (imported by `match_mfapi_et.py`).

## Misc

| Script | Notes |
|--------|--------|
| `mfapi_export_scheme_meta.py` | Scheme meta export |

**Active replacements:** `audit_fund_scheme_map.py`, `validate_map_audit_app.py`, `scrape_mfapi_et_one.py`, `apply_mfapi_et_map.py`, `fix_wrong_map.py`.
