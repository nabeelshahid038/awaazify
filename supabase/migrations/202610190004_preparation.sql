-- Phase 4C: atomic free-credit reservation and private normalized job artifacts.
alter table public.generation_jobs drop constraint if exists generation_jobs_status_check;
alter table public.generation_jobs add constraint generation_jobs_status_check
check (status in ('queued','preparing','prepared','separating','converting','mixing','completed','failed','cancelled'));
alter table public.generation_jobs
  add column if not exists model_slug text not null default 'my-voice-model',
  add column if not exists normalized_storage_path text;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('job-artifacts', 'job-artifacts', false, 1073741824, array['audio/wav'])
on conflict (id) do update set public=excluded.public, file_size_limit=excluded.file_size_limit,
allowed_mime_types=excluded.allowed_mime_types;

create or replace function public.reserve_generation_job(
  p_user_id uuid, p_project_id uuid, p_model_slug text default 'my-voice-model'
) returns uuid language plpgsql security definer set search_path=public as $$
declare v_job_id uuid; v_credit smallint;
begin
  if current_user <> 'service_role' then raise exception 'server-only function'; end if;
  select free_song_credits into v_credit from public.trial_entitlements
  where user_id=p_user_id for update;
  if coalesce(v_credit,0)<1 then raise exception 'no free song credit available'; end if;
  perform 1 from public.studio_projects
  where id=p_project_id and user_id=p_user_id and status='ready' for update;
  if not found then raise exception 'project is missing, not owned, or not ready'; end if;
  update public.trial_entitlements set free_song_credits=free_song_credits-1 where user_id=p_user_id;
  insert into public.generation_jobs(user_id,project_id,status,progress,model_slug)
  values(p_user_id,p_project_id,'queued',0,p_model_slug) returning id into v_job_id;
  update public.studio_projects set status='queued',updated_at=now() where id=p_project_id;
  insert into public.job_events(job_id,user_id,stage,progress,message)
  values(v_job_id,p_user_id,'queued',0,'Job accepted and credit reserved');
  return v_job_id;
end; $$;

create or replace function public.fail_generation_job_and_refund(
  p_job_id uuid, p_error_code text, p_error_message text
) returns void language plpgsql security definer set search_path=public as $$
declare v_job public.generation_jobs%rowtype;
begin
  if current_user <> 'service_role' then raise exception 'server-only function'; end if;
  select * into v_job from public.generation_jobs where id=p_job_id for update;
  if not found or v_job.status in ('completed','failed','cancelled') then return; end if;
  update public.generation_jobs set status='failed',error_code=left(p_error_code,80),
  error_message=left(p_error_message,500),completed_at=now(),updated_at=now() where id=p_job_id;
  update public.studio_projects set status='failed',updated_at=now() where id=v_job.project_id;
  update public.trial_entitlements set free_song_credits=1
  where user_id=v_job.user_id and free_song_credits=0;
  insert into public.job_events(job_id,user_id,stage,progress,message)
  values(p_job_id,v_job.user_id,'failed',v_job.progress,left(p_error_message,500));
end; $$;

revoke all on function public.reserve_generation_job(uuid,uuid,text) from public,anon,authenticated;
revoke all on function public.fail_generation_job_and_refund(uuid,text,text) from public,anon,authenticated;
grant execute on function public.reserve_generation_job(uuid,uuid,text) to service_role;
grant execute on function public.fail_generation_job_and_refund(uuid,text,text) to service_role;
