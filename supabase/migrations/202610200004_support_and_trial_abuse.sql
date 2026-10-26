-- Phase 15: one lifetime trial per Google identity/email and support tickets.
create extension if not exists pgcrypto with schema extensions;

create or replace function public.canonical_trial_email(p_email text) returns text
language sql immutable set search_path='' as $$
  select case
    when split_part(lower(trim(coalesce(p_email,''))),'@',2) in ('gmail.com','googlemail.com')
      then replace(split_part(split_part(lower(trim(p_email)),'@',1),'+',1),'.','') || '@gmail.com'
    else lower(trim(coalesce(p_email,'')))
  end
$$;

create table if not exists public.trial_identity_registry (
  identity_hash text primary key,
  first_user_id uuid not null,
  first_claimed_at timestamptz not null default now()
);
alter table public.trial_identity_registry enable row level security;
-- No client policies: only the auth trigger/service role can access this registry.

-- Treat every existing account as having already received its one-time signup eligibility.
insert into public.trial_identity_registry(identity_hash,first_user_id,first_claimed_at)
select encode(extensions.digest(public.canonical_trial_email(email) || ':awaazify-trial-v1','sha256'),'hex'), id, created_at
from auth.users where email is not null
on conflict(identity_hash) do nothing;

create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path='' as $$
declare v_hash text; v_inserted integer;
begin
  insert into public.profiles(id,display_name,avatar_url)
  values(new.id,new.raw_user_meta_data ->> 'full_name',new.raw_user_meta_data ->> 'avatar_url')
  on conflict(id) do nothing;

  v_hash := encode(extensions.digest(public.canonical_trial_email(new.email) || ':awaazify-trial-v1','sha256'),'hex');
  insert into public.trial_identity_registry(identity_hash,first_user_id)
  values(v_hash,new.id) on conflict(identity_hash) do nothing;
  get diagnostics v_inserted = row_count;

  insert into public.trial_entitlements(user_id,free_song_credits)
  values(new.id,case when v_inserted=1 then 1 else 0 end)
  on conflict(user_id) do nothing;
  return new;
end $$;

create table if not exists public.support_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  category text not null check(category in ('song','payment','voice_training','account','copyright','other')),
  subject text not null check(char_length(subject) between 5 and 120),
  message text not null check(char_length(message) between 10 and 2000),
  status text not null default 'open' check(status in ('open','in_review','resolved','closed')),
  admin_note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists support_requests_user_created_idx on public.support_requests(user_id,created_at desc);
alter table public.support_requests enable row level security;
create policy "Users read own support requests" on public.support_requests for select to authenticated
using((select auth.uid())=user_id);
-- Writes are server-controlled for validation, throttling and admin authorization.

