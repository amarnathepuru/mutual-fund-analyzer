-- FundLens Supabase schema (Free tier)
-- Run in: Supabase Dashboard → SQL → New query

-- ── Profiles (public userid + email; links to auth.users) ─────────────────────
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  user_id text not null,
  email text not null,
  created_at timestamptz not null default now(),
  constraint profiles_user_id_unique unique (user_id),
  constraint profiles_email_unique unique (email)
);

create unique index if not exists profiles_user_id_lower
  on public.profiles (lower(user_id));

-- ── One portfolio per user (v1) ───────────────────────────────────────────────
create table if not exists public.portfolios (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  saved_at timestamptz not null default now(),
  records jsonb not null default '[]'::jsonb,
  columns jsonb not null default '[]'::jsonb,
  constraint portfolios_one_per_user unique (user_id)
);

alter table public.profiles enable row level security;
alter table public.portfolios enable row level security;

-- Profiles: own row only
drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own" on public.profiles
  for select using (auth.uid() = id);

drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own" on public.profiles
  for insert with check (auth.uid() = id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own" on public.profiles
  for update using (auth.uid() = id);

-- Portfolios: own row only
drop policy if exists "portfolios_select_own" on public.portfolios;
create policy "portfolios_select_own" on public.portfolios
  for select using (auth.uid() = user_id);

drop policy if exists "portfolios_insert_own" on public.portfolios;
create policy "portfolios_insert_own" on public.portfolios
  for insert with check (auth.uid() = user_id);

drop policy if exists "portfolios_update_own" on public.portfolios;
create policy "portfolios_update_own" on public.portfolios
  for update using (auth.uid() = user_id);

drop policy if exists "portfolios_delete_own" on public.portfolios;
create policy "portfolios_delete_own" on public.portfolios
  for delete using (auth.uid() = user_id);

-- ── RPC: login / register helpers (anon can call; security definer) ───────────
create or replace function public.get_email_for_user_id(p_user_id text)
returns text
language sql
security definer
set search_path = public
stable
as $$
  select email
  from public.profiles
  where lower(user_id) = lower(trim(p_user_id))
  limit 1;
$$;

create or replace function public.is_user_id_available(p_user_id text)
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select not exists (
    select 1 from public.profiles
    where lower(user_id) = lower(trim(p_user_id))
  );
$$;

create or replace function public.is_email_available(p_email text)
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select not exists (
    select 1 from public.profiles
    where lower(email) = lower(trim(p_email))
  );
$$;

grant execute on function public.get_email_for_user_id(text) to anon, authenticated;
grant execute on function public.is_user_id_available(text) to anon, authenticated;
grant execute on function public.is_email_available(text) to anon, authenticated;

-- Upsert profile when the app has an authenticated session (safety net after sign-up / sign-in)
create or replace function public.upsert_profile(p_id uuid, p_user_id text, p_email text)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, user_id, email)
  values (
    p_id,
    lower(trim(p_user_id)),
    lower(trim(p_email))
  )
  on conflict (id) do update
    set user_id = excluded.user_id,
        email   = excluded.email;
end;
$$;

grant execute on function public.upsert_profile(uuid, text, text) to authenticated;

-- Auto-create profiles when Supabase creates auth.users (no manual SQL needed)
create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  _uid text;
begin
  _uid := lower(trim(coalesce(new.raw_user_meta_data ->> 'user_id', '')));
  if _uid = '' or length(_uid) < 8 then
    return new;
  end if;
  insert into public.profiles ( id, user_id, email)
  values (new.id, _uid, lower(new.email))
  on conflict (id) do update
    set user_id = excluded.user_id,
        email   = excluded.email;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_auth_user();
