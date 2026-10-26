-- Read-only RLS inventory. Run in Supabase SQL Editor after every migration.
select n.nspname as schema_name, c.relname as table_name, c.relrowsecurity as rls_enabled,
       count(p.policyname) as policy_count
from pg_class c
join pg_namespace n on n.oid=c.relnamespace
left join pg_policies p on p.schemaname=n.nspname and p.tablename=c.relname
where n.nspname='public' and c.relkind='r'
group by n.nspname,c.relname,c.relrowsecurity
order by c.relname;

-- This query must return zero rows. A result means a public table has RLS disabled.
select c.relname as unsafe_table
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='public' and c.relkind='r' and not c.relrowsecurity
order by c.relname;

-- Sensitive private tables intentionally have zero client policies.
select schemaname,tablename,policyname,roles,cmd
from pg_policies
where schemaname='public'
order by tablename,policyname;

