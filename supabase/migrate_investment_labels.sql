-- Investment labels (optional tags on holdings — not dates or periods)
-- Run in Supabase SQL Editor. If you ran migrate_investment_periods.sql, you may drop that table after migrating.

-- drop table if exists public.investment_periods;

create table if not exists public.investment_labels (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  label text not null,
  sort_order int not null default 0,
  created_at timestamptz not null default now()
);

create unique index if not exists investment_labels_owner_label_lower
  on public.investment_labels (owner_user_id, lower(label));

alter table public.investment_labels enable row level security;

grant select, insert, update, delete on table public.investment_labels to authenticated;

drop policy if exists "investment_labels_select_own" on public.investment_labels;
create policy "investment_labels_select_own" on public.investment_labels
  for select to authenticated using (auth.uid() = owner_user_id);

drop policy if exists "investment_labels_insert_own" on public.investment_labels;
create policy "investment_labels_insert_own" on public.investment_labels
  for insert to authenticated with check (auth.uid() = owner_user_id);

drop policy if exists "investment_labels_update_own" on public.investment_labels;
create policy "investment_labels_update_own" on public.investment_labels
  for update to authenticated
  using (auth.uid() = owner_user_id) with check (auth.uid() = owner_user_id);

drop policy if exists "investment_labels_delete_own" on public.investment_labels;
create policy "investment_labels_delete_own" on public.investment_labels
  for delete to authenticated using (auth.uid() = owner_user_id);
