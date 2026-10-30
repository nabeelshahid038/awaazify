-- Phase 28: use true Applio -3/0/+3 variants and keep old artifacts removable.
alter table public.generation_jobs
  add column if not exists converted_vocals_minus3_storage_path text,
  add column if not exists converted_vocals_plus3_storage_path text,
  add column if not exists final_mp3_minus3_storage_path text,
  add column if not exists final_mp3_plus3_storage_path text;

-- Old non-default selections point to -5/+5 artifacts. Reset their preferred
-- choice to the always-available default before changing the allowed values.
update public.generation_jobs
set selected_pitch = 0
where selected_pitch not in (-3, 0, 3);

alter table public.generation_jobs
  drop constraint if exists generation_jobs_selected_pitch_check;

alter table public.generation_jobs
  add constraint generation_jobs_selected_pitch_check
  check (selected_pitch in (-3, 0, 3));

comment on column public.generation_jobs.selected_pitch is
  'User preferred final version: -3, 0 or +3 semitones.';
