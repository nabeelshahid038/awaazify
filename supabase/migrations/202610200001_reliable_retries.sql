-- Phase 12: atomic, credit-safe retry paths for preparation and conversion failures.
create or replace function public.retry_failed_preparation(
  p_job_id uuid,p_user_id uuid
) returns jsonb language plpgsql security definer set search_path=public as $$
declare
  v_job public.generation_jobs%rowtype;
  v_trial smallint; v_bonus integer; v_wallet integer; v_balance integer; v_source text;
begin
  if coalesce((select auth.role()),'') <> 'service_role' then raise exception 'server-only function'; end if;
  select * into v_job from public.generation_jobs
    where id=p_job_id and user_id=p_user_id for update;
  if not found or v_job.status <> 'failed' or v_job.normalized_storage_path is not null then
    raise exception 'job is not retryable from preparation';
  end if;
  if v_job.attempt_count >= 3 then raise exception 'retry limit reached'; end if;

  select free_song_credits into v_trial from public.trial_entitlements
    where user_id=p_user_id for update;
  insert into public.wallets(user_id) values(p_user_id) on conflict(user_id) do nothing;
  select bonus_song_credits,song_credits into v_bonus,v_wallet from public.wallets
    where user_id=p_user_id for update;

  if coalesce(v_trial,0)>0 then
    update public.trial_entitlements set free_song_credits=free_song_credits-1 where user_id=p_user_id;
    v_source:='trial';
  elsif coalesce(v_bonus,0)>0 then
    update public.wallets set bonus_song_credits=bonus_song_credits-1,updated_at=now()
      where user_id=p_user_id returning bonus_song_credits into v_balance;
    v_source:='bonus';
  elsif coalesce(v_wallet,0)>0 then
    update public.wallets set song_credits=song_credits-1,updated_at=now()
      where user_id=p_user_id returning song_credits into v_balance;
    v_source:='wallet';
  else raise exception 'no song credit available'; end if;

  update public.generation_jobs set
    status='queued',progress=0,credit_source=v_source,error_code=null,error_message=null,
    completed_at=null,started_at=null,attempt_count=attempt_count+1,updated_at=now()
    where id=p_job_id;
  update public.studio_projects set status='queued',updated_at=now() where id=v_job.project_id;
  if v_source in ('bonus','wallet') then
    insert into public.wallet_ledger(user_id,delta,balance_after,reason,generation_job_id,credit_type)
      values(p_user_id,-1,v_balance,
        case when v_source='bonus' then 'bonus_generation_reserved' else 'generation_reserved' end,
        p_job_id,'song');
  end if;
  insert into public.job_events(job_id,user_id,stage,progress,message)
    values(p_job_id,p_user_id,'queued',0,'Failed audio preparation reopened for retry');
  return jsonb_build_object('job_id',p_job_id,'project_id',v_job.project_id,'model_slug',v_job.model_slug);
end; $$;

create or replace function public.retry_failed_conversion(
  p_job_id uuid,p_user_id uuid
) returns void language plpgsql security definer set search_path=public as $$
declare
  v_job public.generation_jobs%rowtype;
  v_trial smallint; v_bonus integer; v_wallet integer; v_balance integer; v_source text;
begin
  if coalesce((select auth.role()),'') <> 'service_role' then raise exception 'server-only function'; end if;
  select * into v_job from public.generation_jobs where id=p_job_id and user_id=p_user_id for update;
  if not found or v_job.status <> 'failed' or v_job.normalized_storage_path is null then raise exception 'job is not retryable'; end if;
  if v_job.attempt_count >= 3 then raise exception 'retry limit reached'; end if;
  select free_song_credits into v_trial from public.trial_entitlements where user_id=p_user_id for update;
  insert into public.wallets(user_id) values(p_user_id) on conflict(user_id) do nothing;
  select bonus_song_credits,song_credits into v_bonus,v_wallet from public.wallets where user_id=p_user_id for update;
  if coalesce(v_trial,0)>0 then
    update public.trial_entitlements set free_song_credits=free_song_credits-1 where user_id=p_user_id; v_source:='trial';
  elsif coalesce(v_bonus,0)>0 then
    update public.wallets set bonus_song_credits=bonus_song_credits-1,updated_at=now() where user_id=p_user_id returning bonus_song_credits into v_balance; v_source:='bonus';
  elsif coalesce(v_wallet,0)>0 then
    update public.wallets set song_credits=song_credits-1,updated_at=now() where user_id=p_user_id returning song_credits into v_balance; v_source:='wallet';
  else raise exception 'no song credit available'; end if;
  update public.generation_jobs set
    credit_source=v_source,status='prepared',progress=20,error_code=null,error_message=null,
    completed_at=null,started_at=null,attempt_count=attempt_count+1,updated_at=now()
    where id=p_job_id;
  if v_source in ('bonus','wallet') then
    insert into public.wallet_ledger(user_id,delta,balance_after,reason,generation_job_id,credit_type)
      values(p_user_id,-1,v_balance,
        case when v_source='bonus' then 'bonus_generation_reserved' else 'generation_reserved' end,
        p_job_id,'song');
  end if;
  update public.studio_projects set status='queued',updated_at=now() where id=v_job.project_id;
  insert into public.job_events(job_id,user_id,stage,progress,message)
    values(p_job_id,p_user_id,'prepared',20,'Failed conversion reopened for a safe retry');
end; $$;

revoke all on function public.retry_failed_preparation(uuid,uuid) from public,anon,authenticated;
grant execute on function public.retry_failed_preparation(uuid,uuid) to service_role;
revoke all on function public.retry_failed_conversion(uuid,uuid) from public,anon,authenticated;
grant execute on function public.retry_failed_conversion(uuid,uuid) to service_role;
