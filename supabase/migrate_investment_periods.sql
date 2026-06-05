-- Track v1 Phase 1: investment periods (global per user, holdings tagged in portfolios.records JSON)
-- Run in Supabase Dashboard → SQL → New query (after migrate_family_members_f1.sql)

create table if not exists public.investment_periods (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  label text not null,
  start_date date not null default (current_date),
  sort_order int not null default 0,
  created_at timestamptz not null default now()
);

create unique index if not exists investment_periods_owner_label_lower
  on public.investment_periods (owner_user_id, lower(label));

alter table public.investment_periods enable row level security;

grant select, insert, update, delete on table public.investment_periods to authenticated;

drop policy if exists "investment_periods_select_own" on public.investment_periods;
create policy "investment_periods_select_own" on public.investment_periods
  for select to authenticated
  using (auth.uid() = owner_user_id);

drop policy if exists "investment_periods_insert_own" on public.investment_periods;
create policy "investment_periods_insert_own" on public.investment_periods
  for insert to authenticated
  with check (auth.uid() = owner_user_id);

drop policy if exists "investment_periods_update_own" on public.investment_periods;
create policy "investment_periods_update_own" on public.investment_periods
  for update to authenticated
  using (auth.uid() = owner_user_id)
  with check (auth.uid() = owner_user_id);

drop policy if exists "investment_periods_delete_own" on public.investment_periods;
create policy "investment_periods_delete_own" on public.investment_periods
  for delete to authenticated
  using (auth.uid() = owner_user_id);
