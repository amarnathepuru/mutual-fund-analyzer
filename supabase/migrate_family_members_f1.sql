-- F1: Family members + per-member portfolios (run once in Supabase SQL Editor)

create table if not exists public.family_members (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  account_name text not null,
  sort_order int not null default 0,
  created_at timestamptz not null default now()
);

create unique index if not exists family_members_owner_name_lower
  on public.family_members (owner_user_id, lower(account_name));

alter table public.portfolios
  add column if not exists family_member_id uuid references public.family_members(id) on delete cascade;

alter table public.portfolios drop constraint if exists portfolios_one_per_user;

create unique index if not exists portfolios_one_per_member
  on public.portfolios (user_id, family_member_id);

alter table public.family_members enable row level security;

grant usage on schema public to authenticated;
grant select, insert, update, delete on table public.family_members to authenticated;
grant select, insert, update, delete on table public.portfolios to authenticated;

drop policy if exists "family_members_select_own" on public.family_members;
create policy "family_members_select_own" on public.family_members
  for select to authenticated
  using (auth.uid() = owner_user_id);

drop policy if exists "family_members_insert_own" on public.family_members;
create policy "family_members_insert_own" on public.family_members
  for insert to authenticated
  with check (auth.uid() = owner_user_id);

drop policy if exists "family_members_update_own" on public.family_members;
create policy "family_members_update_own" on public.family_members
  for update to authenticated
  using (auth.uid() = owner_user_id)
  with check (auth.uid() = owner_user_id);

drop policy if exists "family_members_delete_own" on public.family_members;
create policy "family_members_delete_own" on public.family_members
  for delete to authenticated
  using (auth.uid() = owner_user_id);
