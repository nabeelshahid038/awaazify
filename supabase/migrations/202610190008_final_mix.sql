-- Phase 4E: private final WAV/MP3 artifacts and permanent completed jobs.
alter table public.generation_jobs
  add column if not exists final_wav_storage_path text,
  add column if not exists final_mp3_storage_path text;

update storage.buckets
set allowed_mime_types=array['audio/wav','audio/mpeg']
where id='job-artifacts';

comment on column public.generation_jobs.final_wav_storage_path is
  'Private lossless final mix path.';
comment on column public.generation_jobs.final_mp3_storage_path is
  'Private downloadable MP3 final mix path.';
