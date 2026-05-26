# FundLens — Supabase setup (do this once)

Your sign-in error means **nothing was created in the database yet**.  
Tables are **not** in Table Editor until you run the SQL below.

## Before you start

1. Open the **same** project as in `.streamlit/secrets.toml`  
   URL should contain: `hqarctzqxnlvuftzkjvr`
2. Left sidebar → **SQL Editor** (not Table Editor)

## Step 1 — Run the main schema

1. Click **+ New query**
2. Open this file on your PC: `supabase/schema.sql`
3. **Select all** (Ctrl+A) → **Copy**
4. Paste into the Supabase SQL box (must be the **entire** file, ~100 lines)
5. Click **Run** (or Ctrl+Enter)
6. Bottom panel must say **Success** (not Error)

If you see **Error**, read the red message and stop — nothing was created.

## Step 2 — Verify

1. **New query** again
2. Paste contents of `supabase/verify_setup.sql` → **Run**
3. Result should be **3 rows**, each with `ok` = **true**

| check_item | ok |
|------------|-----|
| table profiles | true |
| table portfolios | true |
| function get_email_for_user_id | true |

If any `ok` is **false**, Step 1 did not succeed — repeat Step 1.

## Step 3 — See tables in the UI

1. Left sidebar → **Table Editor**
2. Schema dropdown: **public**
3. You should see **profiles** and **portfolios**

(Refresh the page if the list is empty.)

## Step 4 — Functions (not in Table Editor)

Functions are under:

**Database** → **Functions** → schema **public**

You should see `get_email_for_user_id`, `is_user_id_available`, `is_email_available`.

## Step 5 — Reload API cache (if sign-in still says PGRST202)

**New query** → paste `supabase/reload_api_schema.sql` → **Run**

## Step 1b — Auth trigger (recommended)

Run `supabase/schema_auth_trigger.sql` in SQL Editor (after `schema.sql`).  
This creates a `profiles` row when Supabase creates the auth user (even if email confirmation is on).

## Step 1c — Disable confirm email (easiest for testing)

**Authentication** → **Sign In / Providers** → **Email** → turn **off** **Confirm email**.

Without this, Supabase may send a confirmation mail (often delayed or in spam) and you cannot sign in until you click the link.

## Step 6 — Test the app

1. Restart Streamlit locally (Ctrl+C, then `streamlit run app.py`)
2. Use **Register** first (creates auth user + profile row)
3. Then **Sign in** with the same User ID + password

If you tried to sign in **before** Step 1, registration may have failed silently — use **Register** again after setup.

## Common mistakes

| Mistake | Result |
|---------|--------|
| Ran SQL in wrong Supabase project | Tables missing in FundLens project |
| Ran only part of `schema.sql` | Missing tables or functions |
| Ignored red Error after Run | Nothing created |
| Looking for functions in Table Editor | They live under Database → Functions |
