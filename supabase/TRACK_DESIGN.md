# Track my portfolio — design notes (saved for implementation)

## Goal

Support **multiple family accounts** (already in place via `family_members` + `portfolios`) and **multiple investment periods** (lumpsum “batches”) so the user can compare e.g. a 2014 deployment vs a 2026 deployment across accounts — **Track page only**.

Manage / Analyse can keep a **single current view** per account (or combined); period splits are not required there at first.

## Concept: investment period (tranche / lot)

A named bucket for money deployed in a time window, e.g.:

- `2014 lumpsum` — investments made in 2014 across Amar_Indiv, Amar_HUF, etc.
- `2026 lumpsum` — new money in 2026

Each **holding row** in Track belongs to:

| Dimension | Example |
|-----------|---------|
| `family_member_id` / `account_name` | Amar_Indiv |
| `fund_name` | HDFC Large Cap Fund |
| `investment_period_id` | 2014 lumpsum |
| `invested_date`, `invested_amount`, `plan_type`, optional `units` / `nav` | per lot |

Same fund + same account in **two periods** = **two rows** (not merged). Analyse already sums by fund across accounts when needed; Track can filter or group by period.

## Suggested Supabase shape (greenfield)

**`investment_periods`** (per user)

- `id` uuid PK  
- `owner_user_id` → auth.users  
- `label` text — e.g. "2014 lumpsum", "2026 SIP"  
- `start_date` / `end_date` optional — for display only  
- `sort_order` int  
- `created_at`

**`portfolio_holdings`** or **`track_holdings`** (time-series friendly; do not overload current `portfolios.records` JSON for v1 Track)

- `id` uuid PK  
- `owner_user_id`  
- `family_member_id` FK  
- `investment_period_id` FK  
- `fund_name`, `plan_type`, `invested_amount`, `invested_date`, `units`, `nav`  
- `created_at`, `updated_at`  
- Optional unique: `(family_member_id, investment_period_id, fund_name, plan_type, invested_date)` if duplicate lots same day are disallowed

**`portfolio_snapshots`** (optional phase 2)

- Point-in-time valuation for a period or whole portfolio (`as_of_date`, computed metrics JSON) for charts without recomputing everything.

Current **`portfolios`** table remains the **latest editable snapshot** for Manage (one row per `family_member_id`). Track can **import from** current portfolios when creating a period, or stay separate until sync is defined.

## UX (Track page)

1. Family account multiselect (same as Analyse).  
2. **Investment period** selector: list user-defined periods + “All periods” + “Add period”.  
3. Table / metrics filtered by selected account(s) + period(s).  
4. Compare mode (later): 2014 vs 2026 side-by-side.

Manage / CSV upload: **no period field required initially**; optional later as `investment_period` column on CSV for bulk load into Track.

## Open decisions for tomorrow

- [ ] Track-only DB vs also show period in Manage editor  
- [ ] Migrate existing `portfolios.records` into a default period (e.g. "Current")  
- [ ] One period spanning all accounts vs period defined once globally (recommend **global periods**, holdings tagged per account)  
- [ ] NAV/performance: fetch historical NAV by `invested_date` + `plan_type` (see `_apply_nav_units_autofill` TODO in app.py) — **see `NAV_DATA.md`**

## DB migration checklist (existing)

Confirm already applied:

- `schema.sql`, `migrate_family_members_f1.sql`, `fix_family_members_rls.sql`, auth trigger scripts  

Track tables: **not created yet** — implement per above.

## App state today

- `page_portfolio_track()` — placeholder “Coming soon”  
- Analyse: account filter + sum `invested_amount` by fund across accounts  
- No `investment_period` in schema or UI yet  
