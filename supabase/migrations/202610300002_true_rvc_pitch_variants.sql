-- Persist all three true Applio/RVC intermediate vocal variants for cleanup.
alter table public.generation_jobs
  add column if not exists converted_vocals_minus5_storage_path text,
  add column if not exists converted_vocals_plus5_storage_path text;

comment on column public.generation_jobs.converted_vocals_minus5_storage_path is
  'Private Applio/RVC vocal output generated with pitch -5.';

comment on column public.generation_jobs.converted_vocals_plus5_storage_path is
  'Private Applio/RVC vocal output generated with pitch +5.';
