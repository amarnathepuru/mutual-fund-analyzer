# FundLens + Supabase setup

## 1. Create project (free)

1. [supabase.com](https://supabase.com) → **New project** → **Free** plan.
2. Save your database password.

## 2. Auth settings

**Authentication → Providers → Email**: enabled.

**Authentication → URL configuration**:

| Field | Value |
|--------|--------|
| Site URL | `https://YOUR_APP.streamlit.app` |
| Redirect URLs | Same URL + `http://localhost:8501` |

For testing, disable **Confirm email** under Email provider (optional).

## 3. Run schema

**SQL → New query** → paste and run `schema.sql` in this folder.

## 4. API keys

**Project Settings → API**:

- `SUPABASE_URL` = Project URL  
- `SUPABASE_ANON_KEY` = anon public key (not service_role)

## 5. Streamlit secrets

Local: copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml` and fill in values.

Cloud: **App settings → Secrets** with the same keys.

## 6. Password reset email

Uses Supabase’s built-in mailer on the free tier. For production, configure **Project Settings → Auth → SMTP**.

Forgot password: user enters **User ID**; app looks up email and sends Supabase reset link.
