-- Phase 11: auditable admin bonus/giveaway song credits.
alter table public.wallets
  add column if not exists bonus_song_credits integer not null default 0
  check (bonus_song_credits >= 0);

alter table public.generation_jobs
  drop constraint if exists generation_jobs_credit_source_check;
alter table public.generation_jobs
  add constraint generation_jobs_credit_source_check
  check (credit_source in ('trial','bonus','wallet'));

alter table public.wallet_ledger drop constraint if exists wallet_ledger_reason_check;
alter table public.wallet_ledger add constraint wallet_ledger_reason_check
  check (reason in (
    'topup_approved','generation_reserved','generation_refund',
    'training_reserved','training_refund','admin_bonus',
    'bonus_generation_reserved','bonus_generation_refund'
  ));

alter table public.admin_audit_log drop constraint if exists admin_audit_log_action_check;
alter table public.admin_audit_log add constraint admin_audit_log_action_check
  check (action in ('payment_approved','payment_rejected','bonus_credits_granted'));
alter table public.admin_audit_log alter column target_payment_id drop not null;

create or replace function public.grant_bonus_song_credits(
  p_admin_id uuid,
  p_user_email text,
  p_amount integer,
  p_reason text default 'Admin bonus'
) returns jsonb language plpgsql security definer set search_path=public as $$
declare v_user_id uuid; v_balance integer; v_email text;
begin
  if coalesce((select auth.role()),'') <> 'service_role' then
    raise exception 'server-only function';
  end if;
  if p_amount < 1 or p_amount > 100 then raise exception 'bonus amount must be between 1 and 100'; end if;
  v_email := lower(trim(p_user_email));
  select id into v_user_id from auth.users where lower(email)=v_email limit 1;
  if v_user_id is null then raise exception 'user email not found'; end if;
  insert into public.wallets(user_id) values(v_user_id) on conflict(user_id) do nothing;
  update public.wallets
    set bonus_song_credits=bonus_song_credits+p_amount,updated_at=now()
    where user_id=v_user_id returning bonus_song_credits into v_balance;
  insert into public.wallet_ledger(user_id,delta,balance_after,reason,credit_type)
    values(v_user_id,p_amount,v_balance,'admin_bonus','song');
  insert into public.admin_audit_log(admin_user_id,action,details)
    values(p_admin_id,'bonus_credits_granted',jsonb_build_object('user_id',v_user_id,'email',v_email,'credits',p_amount,'reason',left(p_reason,120)));
  return jsonb_build_object('user_id',v_user_id,'email',v_email,'granted',p_amount,'bonus_balance',v_balance);
end; $$;

create or replace function public.reserve_generation_job(
  p_user_id uuid,p_project_id uuid,p_model_slug text default 'my-voice-model'
) returns uuid language plpgsql security definer set search_path=public as $$
declare v_job_id uuid; v_trial smallint; v_bonus integer; v_wallet integer; v_source text; v_balance integer;
begin
  if coalesce((select auth.role()),'') <> 'service_role' then raise exception 'server-only function'; end if;
  perform 1 from public.studio_projects where id=p_project_id and user_id=p_user_id and status='ready' for update;
  if not found then raise exception 'project is missing, not owned, or not ready'; end if;
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
  insert into public.generation_jobs(user_id,project_id,status,progress,model_slug,credit_source)
    values(p_user_id,p_project_id,'queued',0,p_model_slug,v_source) returning id into v_job_id;
  if v_source in ('bonus','wallet') then
    insert into public.wallet_ledger(user_id,delta,balance_after,reason,generation_job_id,credit_type)
      values(p_user_id,-1,v_balance,case when v_source='bonus' then 'bonus_generation_reserved' else 'generation_reserved' end,v_job_id,'song');
  end if;
  update public.studio_projects set status='queued',updated_at=now() where id=p_project_id;
  insert into public.job_events(job_id,user_id,stage,progress,message) values(v_job_id,p_user_id,'queued',0,'Job accepted and credit reserved');
  return v_job_id;
end; $$;

create or replace function public.fail_generation_job_and_refund(
  p_job_id uuid,p_error_code text,p_error_message text
) returns void language plpgsql security definer set search_path=public as $$
declare v_job public.generation_jobs%rowtype; v_balance integer;
begin
  if coalesce((select auth.role()),'') <> 'service_role' then raise exception 'server-only function'; end if;
  select * into v_job from public.generation_jobs where id=p_job_id for update;
  if not found or v_job.status in ('completed','failed','cancelled') then return; end if;
  update public.generation_jobs set status='failed',error_code=left(p_error_code,80),error_message=left(p_error_message,500),completed_at=now(),updated_at=now() where id=p_job_id;
  update public.studio_projects set status='failed',updated_at=now() where id=v_job.project_id;
  if v_job.credit_source='wallet' then
    update public.wallets set song_credits=song_credits+1,updated_at=now() where user_id=v_job.user_id returning song_credits into v_balance;
    insert into public.wallet_ledger(user_id,delta,balance_after,reason,generation_job_id,credit_type) values(v_job.user_id,1,v_balance,'generation_refund',p_job_id,'song');
  elsif v_job.credit_source='bonus' then
    update public.wallets set bonus_song_credits=bonus_song_credits+1,updated_at=now() where user_id=v_job.user_id returning bonus_song_credits into v_balance;
    insert into public.wallet_ledger(user_id,delta,balance_after,reason,generation_job_id,credit_type) values(v_job.user_id,1,v_balance,'bonus_generation_refund',p_job_id,'song');
  else
    update public.trial_entitlements set free_song_credits=1 where user_id=v_job.user_id and free_song_credits=0;
  end if;
  insert into public.job_events(job_id,user_id,stage,progress,message) values(p_job_id,v_job.user_id,'failed',v_job.progress,left(p_error_message,500));
end; $$;

create or replace function public.retry_failed_conversion(
  p_job_id uuid,p_user_id uuid
) returns void language plpgsql security definer set search_path=public as $$
declare v_job public.generation_jobs%rowtype; v_trial smallint; v_bonus integer; v_wallet integer; v_balance integer; v_source text;
begin
  if coalesce((select auth.role()),'') <> 'service_role' then raise exception 'server-only function'; end if;
  select * into v_job from public.generation_jobs where id=p_job_id and user_id=p_user_id for update;
  if not found or v_job.status <> 'failed' or v_job.normalized_storage_path is null then raise exception 'job is not retryable'; end if;
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
  update public.generation_jobs set credit_source=v_source,status='prepared',progress=20,error_code=null,error_message=null,completed_at=null,started_at=null,updated_at=now() where id=p_job_id;
  if v_source in ('bonus','wallet') then
    insert into public.wallet_ledger(user_id,delta,balance_after,reason,generation_job_id,credit_type)
      values(p_user_id,-1,v_balance,case when v_source='bonus' then 'bonus_generation_reserved' else 'generation_reserved' end,p_job_id,'song');
  end if;
  update public.studio_projects set status='queued',updated_at=now() where id=v_job.project_id;
  insert into public.job_events(job_id,user_id,stage,progress,message) values(p_job_id,p_user_id,'prepared',20,'Failed conversion reopened for a safe retry');
end; $$;

revoke all on function public.grant_bonus_song_credits(uuid,text,integer,text) from public,anon,authenticated;
grant execute on function public.grant_bonus_song_credits(uuid,text,integer,text) to service_role;
revoke all on function public.reserve_generation_job(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.reserve_generation_job(uuid,uuid,text) to service_role;
revoke all on function public.fail_generation_job_and_refund(uuid,text,text) from public,anon,authenticated;
grant execute on function public.fail_generation_job_and_refund(uuid,text,text) to service_role;
revoke all on function public.retry_failed_conversion(uuid,uuid) from public,anon,authenticated;
grant execute on function public.retry_failed_conversion(uuid,uuid) to service_role;
