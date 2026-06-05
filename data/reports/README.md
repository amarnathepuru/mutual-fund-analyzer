# Reports (regenerable)

This folder is intentionally **empty in git** except this file. Pipeline scripts write QC and match CSVs here locally.

| Regenerate | Command |
|------------|---------|
| ET→MFAPI match | `python scripts/archive/match_et_mfapi.py` (archived; copy to `scripts/` if needed) |
| MFAPI→ET candidates | `python scripts/match_mfapi_et.py` |
| Map audit | `python scripts/audit_fund_scheme_map.py` |
| Batch scrape progress | `python scripts/scrape_mfapi_et_batch.py --resume` |
| Holdings QC | `python scripts/analyze_scrape_holdings_quality.py` |
| Master sync summary | `python scripts/write_master_sync_qc.py` |
| Close unmapped NAV | `python scripts/close_out_nav_unmapped.py` |

Bulk cleanup: `python scripts/cleanup_data_artifacts.py`
