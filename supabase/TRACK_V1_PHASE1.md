# Track v1

## Phase 1 — Manage + labels ✓

See migration `migrate_investment_labels.sql` and holdings fields in prior section.

## Phase 2 — Track page ✓

**`portfolio_track.py`** — holdings metrics, portfolio totals, XIRR, month-end value curve, allocation pie data.

**Track page (`page_portfolio_track`)**

- Family account + investment label filters (same as Manage)
- Summary: total invested, current value, gain/return %, portfolio XIRR
- Charts: allocation pie (invested vs current toggle), combined portfolio value (month-end)
- Holdings table: fund, account, label, invested, current, gain, return %

**Requires:** `nav.db` + MFAPI-mapped Direct–Growth schemes (`can_track`).

**XIRR:** All buy cashflows (including optional transaction lots in Manage) vs terminal value at latest NAVs.
