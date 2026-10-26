-- Phase 4D: persist separated stems and RVC-converted vocals.
alter table public.generation_jobs drop constraint if exists generation_jobs_status_check;
alter table public.generation_jobs add constraint generation_jobs_status_check
check (status in ('queued','preparing','prepared','separating','converting','converted','mixing','completed','failed','cancelled'));

alter table public.generation_jobs
  add column if not exists vocals_storage_path text,
  add column if not exists instrumental_storage_path text,
  add column if not exists converted_vocals_storage_path text,
  add column if not exists conversion_settings jsonb not null default '{}'::jsonb;

comment on column public.generation_jobs.vocals_storage_path is
  'Private job-artifacts path for the separated source vocal stem.';
comment on column public.generation_jobs.instrumental_storage_path is
  'Private job-artifacts path for the separated accompaniment stem.';
comment on column public.generation_jobs.converted_vocals_storage_path is
  'Private job-artifacts path for the RVC-converted vocal stem.';

