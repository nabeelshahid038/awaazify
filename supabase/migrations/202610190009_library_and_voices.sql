-- Phase 5: database-backed voice catalog. Generated songs remain represented by
-- completed generation_jobs and their permanent private artifact paths.
create table if not exists public.voice_models (
  slug text primary key check (slug ~ '^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$'),
  display_name text not null check (char_length(display_name) between 1 and 80),
  description text not null default '',
  language text,
  visibility text not null default 'public' check (visibility in ('public','private')),
  consent_status text not null check (consent_status in ('development_only','licensed','owner_verified')),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.voice_models enable row level security;
create policy "Authenticated users read active public voices" on public.voice_models
for select to authenticated using (is_active and visibility='public');

insert into public.voice_models(slug,display_name,description,language,consent_status)
values(
  'my-voice-model',
  'Babar Azam — Development Test',
  'Current RVC compatibility model. Development testing only; not approved for public commercial impersonation.',
  'Urdu / multilingual',
  'development_only'
)
on conflict (slug) do update set
  display_name=excluded.display_name,
  description=excluded.description,
  language=excluded.language,
  consent_status=excluded.consent_status,
  is_active=true,
  updated_at=now();
