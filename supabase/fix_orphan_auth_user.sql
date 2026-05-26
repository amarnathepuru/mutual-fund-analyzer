-- Use if you registered before profiles/trigger existed.
-- 1. Supabase → Authentication → Users → copy the user's UUID and email
-- 2. Replace the three placeholders below, then Run.

insert into public.profiles (id, user_id, email)
values (
  'PASTE-AUTH-USER-UUID-HERE'::uuid,
  'amarnathepuru',  -- your User ID (lowercase)
  'you@example.com' -- same email used at registration
)
on conflict (id) do update
  set user_id = excluded.user_id,
      email   = excluded.email;
