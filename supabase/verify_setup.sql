-- Run AFTER schema.sql. You should see 3 rows, each with ok = true.

select 'table profiles' as check_item,
       exists (
         select 1 from information_schema.tables
         where table_schema = 'public' and table_name = 'profiles'
       ) as ok
union all
select 'table portfolios',
       exists (
         select 1 from information_schema.tables
         where table_schema = 'public' and table_name = 'portfolios'
       )
union all
select 'function get_email_for_user_id',
       exists (
         select 1 from pg_proc p
         join pg_namespace n on n.oid = p.pronamespace
         where n.nspname = 'public'
           and p.proname = 'get_email_for_user_id'
       );
