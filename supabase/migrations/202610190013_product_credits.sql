-- Phase 10: separate song and custom-voice credits with server-owned pricing.
alter table public.wallets
  add column if not exists training_credits integer not null default 0 check (training_credits >= 0);

alter table public.payment_requests
  add column if not exists product_type text not null default 'song'
  check (product_type in ('song','voice_training'));

alter table public.payment_requests drop constraint if exists payment_requests_amount_pkr_check;
alter table public.payment_requests add constraint payment_requests_amount_pkr_check
  check (amount_pkr between 50 and 100000);

alter table public.wallet_ledger
  add column if not exists credit_type text not null default 'song'
  check (credit_type in ('song','voice_training'));

alter table public.wallet_ledger drop constraint if exists wallet_ledger_reason_check;
alter table public.wallet_ledger add constraint wallet_ledger_reason_check
  check (reason in ('topup_approved','generation_reserved','generation_refund','training_reserved','training_refund'));

alter table public.voice_training_requests
  add column if not exists credit_reserved boolean not null default false;

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
    if v_payment.product_type='voice_training' then
      update public.wallets set training_credits=training_credits+v_payment.requested_credits,updated_at=now()
        where user_id=v_payment.user_id returning training_credits into v_balance;
    else
      update public.wallets set song_credits=song_credits+v_payment.requested_credits,updated_at=now()
        where user_id=v_payment.user_id returning song_credits into v_balance;
    end if;
    update public.payment_requests set status='approved',admin_note=left(p_note,500),reviewed_by=p_admin_id,reviewed_at=now() where id=p_payment_id;
    insert into public.wallet_ledger(user_id,delta,balance_after,reason,payment_request_id,credit_type)
      values(v_payment.user_id,v_payment.requested_credits,v_balance,'topup_approved',p_payment_id,v_payment.product_type);
    insert into public.admin_audit_log(admin_user_id,action,target_payment_id,details)
      values(p_admin_id,'payment_approved',p_payment_id,jsonb_build_object('credits',v_payment.requested_credits,'product',v_payment.product_type,'amount_pkr',v_payment.amount_pkr));
  else
    update public.payment_requests set status='rejected',admin_note=left(p_note,500),reviewed_by=p_admin_id,reviewed_at=now() where id=p_payment_id;
    insert into public.admin_audit_log(admin_user_id,action,target_payment_id,details)
      values(p_admin_id,'payment_rejected',p_payment_id,jsonb_build_object('note',left(p_note,500)));
  end if;
end; $$;

create or replace function public.reserve_training_credit(p_user_id uuid)
returns void language plpgsql security definer set search_path=public as $$
declare v_balance integer;
begin
  if coalesce((select auth.role()),'') <> 'service_role' then raise exception 'server-only function'; end if;
  insert into public.wallets(user_id) values(p_user_id) on conflict(user_id) do nothing;
  update public.wallets set training_credits=training_credits-1,updated_at=now()
    where user_id=p_user_id and training_credits>0 returning training_credits into v_balance;
  if not found then raise exception 'no voice training credit available'; end if;
  insert into public.wallet_ledger(user_id,delta,balance_after,reason,credit_type)
    values(p_user_id,-1,v_balance,'training_reserved','voice_training');
end; $$;

create or replace function public.refund_training_credit(p_user_id uuid)
returns void language plpgsql security definer set search_path=public as $$
declare v_balance integer;
begin
  if coalesce((select auth.role()),'') <> 'service_role' then raise exception 'server-only function'; end if;
  update public.wallets set training_credits=training_credits+1,updated_at=now()
    where user_id=p_user_id returning training_credits into v_balance;
  insert into public.wallet_ledger(user_id,delta,balance_after,reason,credit_type)
    values(p_user_id,1,v_balance,'training_refund','voice_training');
end; $$;

revoke all on function public.reserve_training_credit(uuid) from public,anon,authenticated;
grant execute on function public.reserve_training_credit(uuid) to service_role;
revoke all on function public.refund_training_credit(uuid) from public,anon,authenticated;
grant execute on function public.refund_training_credit(uuid) to service_role;
