-- Run this ONCE on your existing FundLens Supabase project (already has schema.sql tables).
-- Adds auto-profile trigger + upsert_profile so you never insert profiles manually.

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
  insert into public.profiles (id, user_id, email)
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
