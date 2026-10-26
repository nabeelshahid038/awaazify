-- Atomically reserve the refunded credit and reopen a failed conversion from
-- its already prepared private audio artifact.
create or replace function public.retry_failed_conversion(
  p_job_id uuid, p_user_id uuid
) returns void language plpgsql security definer set search_path=public as $$
declare v_job public.generation_jobs%rowtype; v_credit smallint;
begin
  if coalesce((select auth.role()), '') <> 'service_role' then
    raise exception 'server-only function';
  end if;
  select * into v_job from public.generation_jobs
  where id=p_job_id and user_id=p_user_id for update;
  if not found or v_job.status <> 'failed' or v_job.normalized_storage_path is null then
    raise exception 'job is not retryable';
  end if;
  select free_song_credits into v_credit from public.trial_entitlements
  where user_id=p_user_id for update;
  if coalesce(v_credit,0)<1 then raise exception 'no free song credit available'; end if;
  update public.trial_entitlements set free_song_credits=free_song_credits-1
  where user_id=p_user_id;
  update public.generation_jobs set status='prepared',progress=20,error_code=null,
    error_message=null,completed_at=null,started_at=null,updated_at=now()
  where id=p_job_id;
  update public.studio_projects set status='queued',updated_at=now()
  where id=v_job.project_id;
  insert into public.job_events(job_id,user_id,stage,progress,message)
  values(p_job_id,p_user_id,'prepared',20,'Failed conversion reopened for a safe retry');
end; $$;

revoke all on function public.retry_failed_conversion(uuid,uuid) from public,anon,authenticated;
grant execute on function public.retry_failed_conversion(uuid,uuid) to service_role;
