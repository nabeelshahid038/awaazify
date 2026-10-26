-- Phase 6: manual top-ups, immutable credit ledger, admin audit and paid-credit reservation.
create table if not exists public.wallets (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  song_credits integer not null default 0 check (song_credits >= 0),
  updated_at timestamptz not null default now()
);

create table if not exists public.payment_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  method text not null check (method in ('easypaisa','jazzcash')),
  amount_pkr integer not null check (amount_pkr between 100 and 100000),
  requested_credits integer not null check (requested_credits between 1 and 500),
  sender_name text not null check (char_length(sender_name) between 2 and 100),
  sender_phone text not null check (sender_phone ~ '^03[0-9]{9}$'),
  transaction_reference text not null check (char_length(transaction_reference) between 4 and 100),
  proof_path text not null,
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  admin_note text,
  reviewed_by uuid references public.profiles(id),
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  unique(method, transaction_reference)
);

create table if not exists public.wallet_ledger (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  delta integer not null check (delta <> 0),
  balance_after integer not null check (balance_after >= 0),
  reason text not null check (reason in ('topup_approved','generation_reserved','generation_refund')),
  payment_request_id uuid references public.payment_requests(id),
  generation_job_id uuid references public.generation_jobs(id),
  created_at timestamptz not null default now()
);

create table if not exists public.admin_audit_log (
  id uuid primary key default gen_random_uuid(),
  admin_user_id uuid not null references public.profiles(id),
  action text not null check (action in ('payment_approved','payment_rejected')),
  target_payment_id uuid not null references public.payment_requests(id),
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists payment_requests_user_created_idx on public.payment_requests(user_id,created_at desc);
create index if not exists payment_requests_status_created_idx on public.payment_requests(status,created_at asc);
create index if not exists wallet_ledger_user_created_idx on public.wallet_ledger(user_id,created_at desc);

insert into public.wallets(user_id) select id from public.profiles on conflict (user_id) do nothing;

create or replace function public.handle_new_user() returns trigger language plpgsql security definer set search_path='' as $$
begin
  insert into public.profiles(id,display_name,avatar_url)
    values(new.id,new.raw_user_meta_data ->> 'full_name',new.raw_user_meta_data ->> 'avatar_url') on conflict(id) do nothing;
  insert into public.trial_entitlements(user_id) values(new.id) on conflict(user_id) do nothing;
  insert into public.wallets(user_id) values(new.id) on conflict(user_id) do nothing;
  return new;
end; $$;

alter table public.wallets enable row level security;
alter table public.payment_requests enable row level security;
alter table public.wallet_ledger enable row level security;
alter table public.admin_audit_log enable row level security;
create policy "Users read own wallet" on public.wallets for select to authenticated using ((select auth.uid())=user_id);
create policy "Users read own payment requests" on public.payment_requests for select to authenticated using ((select auth.uid())=user_id);
create policy "Users create own payment requests" on public.payment_requests for insert to authenticated with check ((select auth.uid())=user_id and status='pending');
create policy "Users read own wallet ledger" on public.wallet_ledger for select to authenticated using ((select auth.uid())=user_id);

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('payment-proofs','payment-proofs',false,5242880,array['image/jpeg','image/png','image/webp','application/pdf'])
on conflict(id) do update set public=excluded.public,file_size_limit=excluded.file_size_limit,allowed_mime_types=excluded.allowed_mime_types;
create policy "Users upload own payment proofs" on storage.objects for insert to authenticated
with check(bucket_id='payment-proofs' and (storage.foldername(name))[1]=(select auth.uid())::text);
create policy "Users read own payment proofs" on storage.objects for select to authenticated
using(bucket_id='payment-proofs' and (storage.foldername(name))[1]=(select auth.uid())::text);
create policy "Users delete unsubmitted payment proofs" on storage.objects for delete to authenticated
using(
  bucket_id='payment-proofs'
  and (storage.foldername(name))[1]=(select auth.uid())::text
  and not exists(
    select 1 from public.payment_requests pr
    where pr.proof_path=storage.objects.name and pr.user_id=(select auth.uid())
  )
);

alter table public.generation_jobs add column if not exists credit_source text
check (credit_source in ('trial','wallet'));

create or replace function public.review_payment_request(
  p_payment_id uuid,p_admin_id uuid,p_approve boolean,p_note text default null
) returns void language plpgsql security definer set search_path=public as $$
declare v_payment public.payment_requests%rowtype; v_balance integer;
begin
  if coalesce((select auth.role()),'') <> 'service_role' then raise exception 'server-only function'; end if;
  select * into v_payment from public.payment_requests where id=p_payment_id for update;
  if not found then raise exception 'payment request not found'; end if;
  if v_payment.status <> 'pending' then raise exception 'payment request already reviewed'; end if;
  if p_approve then
    insert into public.wallets(user_id) values(v_payment.user_id) on conflict(user_id) do nothing;
    update public.wallets set song_credits=song_credits+v_payment.requested_credits,updated_at=now()
      where user_id=v_payment.user_id returning song_credits into v_balance;
    update public.payment_requests set status='approved',admin_note=left(p_note,500),reviewed_by=p_admin_id,reviewed_at=now() where id=p_payment_id;
    insert into public.wallet_ledger(user_id,delta,balance_after,reason,payment_request_id)
      values(v_payment.user_id,v_payment.requested_credits,v_balance,'topup_approved',p_payment_id);
    insert into public.admin_audit_log(admin_user_id,action,target_payment_id,details)
      values(p_admin_id,'payment_approved',p_payment_id,jsonb_build_object('credits',v_payment.requested_credits,'amount_pkr',v_payment.amount_pkr));
  else
    update public.payment_requests set status='rejected',admin_note=left(p_note,500),reviewed_by=p_admin_id,reviewed_at=now() where id=p_payment_id;
    insert into public.admin_audit_log(admin_user_id,action,target_payment_id,details)
      values(p_admin_id,'payment_rejected',p_payment_id,jsonb_build_object('note',left(p_note,500)));
  end if;
end; $$;

create or replace function public.reserve_generation_job(
  p_user_id uuid,p_project_id uuid,p_model_slug text default 'my-voice-model'
) returns uuid language plpgsql security definer set search_path=public as $$
declare v_job_id uuid; v_trial smallint; v_wallet integer; v_source text; v_balance integer;
begin
  if coalesce((select auth.role()),'') <> 'service_role' then raise exception 'server-only function'; end if;
  perform 1 from public.studio_projects where id=p_project_id and user_id=p_user_id and status='ready' for update;
  if not found then raise exception 'project is missing, not owned, or not ready'; end if;
  select free_song_credits into v_trial from public.trial_entitlements where user_id=p_user_id for update;
  insert into public.wallets(user_id) values(p_user_id) on conflict(user_id) do nothing;
  select song_credits into v_wallet from public.wallets where user_id=p_user_id for update;
  if coalesce(v_trial,0)>0 then
    update public.trial_entitlements set free_song_credits=free_song_credits-1 where user_id=p_user_id; v_source:='trial';
  elsif coalesce(v_wallet,0)>0 then
    update public.wallets set song_credits=song_credits-1,updated_at=now() where user_id=p_user_id returning song_credits into v_balance; v_source:='wallet';
  else raise exception 'no song credit available'; end if;
  insert into public.generation_jobs(user_id,project_id,status,progress,model_slug,credit_source)
    values(p_user_id,p_project_id,'queued',0,p_model_slug,v_source) returning id into v_job_id;
  if v_source='wallet' then insert into public.wallet_ledger(user_id,delta,balance_after,reason,generation_job_id)
    values(p_user_id,-1,v_balance,'generation_reserved',v_job_id); end if;
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
    insert into public.wallet_ledger(user_id,delta,balance_after,reason,generation_job_id) values(v_job.user_id,1,v_balance,'generation_refund',p_job_id);
  else update public.trial_entitlements set free_song_credits=1 where user_id=v_job.user_id and free_song_credits=0; end if;
  insert into public.job_events(job_id,user_id,stage,progress,message) values(p_job_id,v_job.user_id,'failed',v_job.progress,left(p_error_message,500));
end; $$;

create or replace function public.retry_failed_conversion(
  p_job_id uuid,p_user_id uuid
) returns void language plpgsql security definer set search_path=public as $$
declare v_job public.generation_jobs%rowtype; v_trial smallint; v_wallet integer; v_balance integer;
begin
  if coalesce((select auth.role()),'') <> 'service_role' then raise exception 'server-only function'; end if;
  select * into v_job from public.generation_jobs where id=p_job_id and user_id=p_user_id for update;
  if not found or v_job.status <> 'failed' or v_job.normalized_storage_path is null then raise exception 'job is not retryable'; end if;
  select free_song_credits into v_trial from public.trial_entitlements where user_id=p_user_id for update;
  insert into public.wallets(user_id) values(p_user_id) on conflict(user_id) do nothing;
  select song_credits into v_wallet from public.wallets where user_id=p_user_id for update;
  if coalesce(v_trial,0)>0 then
    update public.trial_entitlements set free_song_credits=free_song_credits-1 where user_id=p_user_id;
    update public.generation_jobs set credit_source='trial' where id=p_job_id;
  elsif coalesce(v_wallet,0)>0 then
    update public.wallets set song_credits=song_credits-1,updated_at=now() where user_id=p_user_id returning song_credits into v_balance;
    update public.generation_jobs set credit_source='wallet' where id=p_job_id;
    insert into public.wallet_ledger(user_id,delta,balance_after,reason,generation_job_id) values(p_user_id,-1,v_balance,'generation_reserved',p_job_id);
  else raise exception 'no song credit available'; end if;
  update public.generation_jobs set status='prepared',progress=20,error_code=null,error_message=null,completed_at=null,started_at=null,updated_at=now() where id=p_job_id;
  update public.studio_projects set status='queued',updated_at=now() where id=v_job.project_id;
  insert into public.job_events(job_id,user_id,stage,progress,message) values(p_job_id,p_user_id,'prepared',20,'Failed conversion reopened for a safe retry');
end; $$;

revoke all on function public.review_payment_request(uuid,uuid,boolean,text) from public,anon,authenticated;
grant execute on function public.review_payment_request(uuid,uuid,boolean,text) to service_role;
revoke all on function public.reserve_generation_job(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.reserve_generation_job(uuid,uuid,text) to service_role;
revoke all on function public.fail_generation_job_and_refund(uuid,text,text) from public,anon,authenticated;
grant execute on function public.fail_generation_job_and_refund(uuid,text,text) to service_role;
revoke all on function public.retry_failed_conversion(uuid,uuid) from public,anon,authenticated;
grant execute on function public.retry_failed_conversion(uuid,uuid) to service_role;
