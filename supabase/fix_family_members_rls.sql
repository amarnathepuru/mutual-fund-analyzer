-- Fix family_members / portfolios API access for logged-in users (run in Supabase SQL Editor)
-- Use when the app shows: "row-level security policy for table family_members"

-- Table privileges (SQL-created tables sometimes miss these)
grant usage on schema public to authenticated;
grant select, insert, update, delete on table public.family_members to authenticated;
grant select, insert, update, delete on table public.portfolios to authenticated;

-- RLS policies (authenticated role, explicit WITH CHECK on update)
alter table public.family_members enable row level security;

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

-- Portfolios (per auth user; optional family_member_id)
drop policy if exists "portfolios_select_own" on public.portfolios;
create policy "portfolios_select_own" on public.portfolios
  for select to authenticated
  using (auth.uid() = user_id);

drop policy if exists "portfolios_insert_own" on public.portfolios;
create policy "portfolios_insert_own" on public.portfolios
  for insert to authenticated
  with check (auth.uid() = user_id);

drop policy if exists "portfolios_update_own" on public.portfolios;
create policy "portfolios_update_own" on public.portfolios
  for update to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "portfolios_delete_own" on public.portfolios;
create policy "portfolios_delete_own" on public.portfolios
  for delete to authenticated
  using (auth.uid() = user_id);
