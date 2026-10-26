-- Phase 8: persistent server-side rate limiting and operational security events.
create table if not exists public.api_rate_limits (
  subject text not null,
  action text not null,
  window_started_at timestamptz not null,
  request_count integer not null default 0 check (request_count >= 0),
  primary key(subject,action,window_started_at)
);

create table if not exists public.security_events (
  id bigint generated always as identity primary key,
  user_id uuid references public.profiles(id) on delete set null,
  event_type text not null,
  severity text not null default 'info' check (severity in ('info','warning','critical')),
  request_id text,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists security_events_created_idx on public.security_events(created_at desc);
create index if not exists security_events_user_created_idx on public.security_events(user_id,created_at desc);
alter table public.api_rate_limits enable row level security;
alter table public.security_events enable row level security;
-- No client policies: both tables are server-only.

create or replace function public.consume_api_rate_limit(
  p_subject text,p_action text,p_limit integer,p_window_seconds integer
) returns table(allowed boolean,remaining integer,reset_at timestamptz)
language plpgsql security definer set search_path=public as $$
declare v_start timestamptz; v_count integer;
begin
  if coalesce((select auth.role()),'') <> 'service_role' then raise exception 'server-only function'; end if;
  if p_limit < 1 or p_window_seconds < 1 then raise exception 'invalid rate limit'; end if;
  delete from public.api_rate_limits where subject=left(p_subject,200) and action=left(p_action,100)
    and window_started_at < now()-interval '7 days';
  v_start := to_timestamp(floor(extract(epoch from now())/p_window_seconds)*p_window_seconds);
  insert into public.api_rate_limits(subject,action,window_started_at,request_count)
    values(left(p_subject,200),left(p_action,100),v_start,1)
  on conflict(subject,action,window_started_at) do update
    set request_count=public.api_rate_limits.request_count+1
  returning request_count into v_count;
  return query select v_count<=p_limit,greatest(p_limit-v_count,0),v_start+make_interval(secs=>p_window_seconds);
end; $$;

revoke all on function public.consume_api_rate_limit(text,text,integer,integer) from public,anon,authenticated;
grant execute on function public.consume_api_rate_limit(text,text,integer,integer) to service_role;
