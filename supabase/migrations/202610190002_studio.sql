-- Phase 3: private source audio and user-owned studio project drafts.
create table if not exists public.studio_projects (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  source_type text not null check (source_type in ('youtube', 'upload')),
  title text not null check (char_length(title) between 1 and 160),
  status text not null default 'ready' check (status in ('ready', 'queued', 'processing', 'failed', 'completed')),
  rights_confirmed boolean not null check (rights_confirmed),
  trim_start_seconds numeric(8,3) not null default 0 check (trim_start_seconds >= 0 and trim_start_seconds <= 360),
  trim_end_seconds numeric(8,3) not null check (trim_end_seconds > trim_start_seconds and trim_end_seconds <= 360),
  youtube_url text,
  youtube_video_id text,
  youtube_title text,
  youtube_thumbnail_url text,
  storage_path text,
  original_filename text,
  mime_type text,
  size_bytes bigint check (size_bytes is null or (size_bytes > 0 and size_bytes <= 104857600)),
  source_duration_seconds numeric(8,3) check (source_duration_seconds is null or (source_duration_seconds > 0 and source_duration_seconds <= 360)),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (source_type = 'youtube' and youtube_url is not null and youtube_video_id is not null and storage_path is null)
    or
    (source_type = 'upload' and storage_path is not null and original_filename is not null and youtube_url is null)
  )
);

create index if not exists studio_projects_user_created_idx
  on public.studio_projects (user_id, created_at desc);

alter table public.studio_projects enable row level security;
create policy "Users read own studio projects" on public.studio_projects
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "Users create own studio projects" on public.studio_projects
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "Users update own ready studio projects" on public.studio_projects
  for update to authenticated using ((select auth.uid()) = user_id and status = 'ready')
  with check ((select auth.uid()) = user_id);
create policy "Users delete own ready studio projects" on public.studio_projects
  for delete to authenticated using ((select auth.uid()) = user_id and status = 'ready');

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'source-audio', 'source-audio', false, 104857600,
  array['audio/mpeg','audio/wav','audio/x-wav','audio/flac','audio/mp4','audio/x-m4a','audio/aac','audio/ogg']
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

create policy "Users upload own source audio" on storage.objects
  for insert to authenticated with check (
    bucket_id = 'source-audio' and (storage.foldername(name))[1] = (select auth.uid())::text
  );
create policy "Users read own source audio" on storage.objects
  for select to authenticated using (
    bucket_id = 'source-audio' and (storage.foldername(name))[1] = (select auth.uid())::text
  );
create policy "Users delete own source audio" on storage.objects
  for delete to authenticated using (
    bucket_id = 'source-audio' and (storage.foldername(name))[1] = (select auth.uid())::text
  );
