-- Phase 1 foundation only. Apply to a fresh Supabase project.
-- Auth trigger creates a private profile and initial trial entitlement atomically.
create table if not exists public.profiles (
 id uuid primary key references auth.users(id) on delete cascade,
 display_name text,
 avatar_url text,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create table if not exists public.trial_entitlements (
 user_id uuid primary key references public.profiles(id) on delete cascade,
 free_song_credits smallint not null default 1 check (free_song_credits between 0 and 1),
 created_at timestamptz not null default now()
);
alter table public.profiles enable row level security;
alter table public.trial_entitlements enable row level security;
create policy "Users read own profile" on public.profiles for select to authenticated using ((select auth.uid()) = id);
create policy "Users read own trial" on public.trial_entitlements for select to authenticated using ((select auth.uid()) = user_id);
-- No client-side INSERT/UPDATE/DELETE policy for trial credits.
create or replace function public.handle_new_user() returns trigger language plpgsql security definer set search_path = '' as $$
begin
 insert into public.profiles (id, display_name, avatar_url)
 values (new.id, new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'avatar_url')
 on conflict (id) do nothing;
 insert into public.trial_entitlements (user_id) values (new.id) on conflict (user_id) do nothing;
 return new;
end;
$$;
create trigger on_auth_user_created after insert on auth.users for each row execute function public.handle_new_user();
-- Future phases add atomic reservation, billing ledger, generation jobs and ownership policies.
