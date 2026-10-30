-- Three final choices per generation job. Existing completed songs remain valid.
alter table public.generation_jobs
  add column if not exists final_mp3_minus5_storage_path text,
  add column if not exists final_mp3_plus5_storage_path text,
  add column if not exists selected_pitch smallint not null default 0;

alter table public.generation_jobs
  drop constraint if exists generation_jobs_selected_pitch_check;

alter table public.generation_jobs
  add constraint generation_jobs_selected_pitch_check
  check (selected_pitch in (-5, 0, 5));

comment on column public.generation_jobs.selected_pitch is
  'User preferred final version: -5, 0 or +5 semitones.';
