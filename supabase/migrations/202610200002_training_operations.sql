-- Phase 13: production-safe custom voice training operations and audit history.
alter table public.voice_training_requests
  add column if not exists dataset_size_bytes bigint
    check (dataset_size_bytes is null or dataset_size_bytes between 1 and 262144000),
  add column if not exists dataset_mime_type text,
  add column if not exists consent_size_bytes bigint
    check (consent_size_bytes is null or consent_size_bytes between 1 and 10485760),
  add column if not exists consent_mime_type text;

create table if not exists public.voice_training_events (
  id bigint generated always as identity primary key,
  request_id uuid not null references public.voice_training_requests(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  status text not null check (status in ('submitted','approved','training','model_validation','ready','rejected')),
  message text not null check (char_length(message) between 1 and 500),
  created_at timestamptz not null default now()
);
create index if not exists voice_training_events_request_idx
  on public.voice_training_events(request_id,created_at);
alter table public.voice_training_events enable row level security;
drop policy if exists "Users read own training events" on public.voice_training_events;
create policy "Users read own training events" on public.voice_training_events
  for select to authenticated using ((select auth.uid())=user_id);

alter table public.admin_audit_log
  add column if not exists target_training_request_id uuid
    references public.voice_training_requests(id) on delete set null;
alter table public.admin_audit_log drop constraint if exists admin_audit_log_action_check;
alter table public.admin_audit_log add constraint admin_audit_log_action_check
  check (action in (
    'payment_approved','payment_rejected','bonus_credits_granted',
    'training_status_updated','private_voice_published'
  ));

create or replace function public.transition_training_request(
  p_request_id uuid,p_admin_id uuid,p_status text,p_note text default null
) returns jsonb language plpgsql security definer set search_path=public as $$
declare
  v_request public.voice_training_requests%rowtype;
  v_balance integer;
begin
  if coalesce((select auth.role()),'') <> 'service_role' then raise exception 'server-only function'; end if;
  if p_status not in ('approved','training','model_validation','rejected') then raise exception 'invalid target status'; end if;
  select * into v_request from public.voice_training_requests where id=p_request_id for update;
  if not found then raise exception 'training request not found'; end if;
  if not (
    (v_request.status='submitted' and p_status in ('approved','rejected')) or
    (v_request.status='approved' and p_status in ('training','rejected')) or
    (v_request.status='training' and p_status in ('model_validation','rejected')) or
    (v_request.status='model_validation' and p_status in ('training','rejected'))
  ) then raise exception 'invalid training status transition'; end if;
  if p_status='rejected' and coalesce(nullif(trim(p_note),''),'')='' then raise exception 'rejection reason required'; end if;

  update public.voice_training_requests set
    status=p_status,admin_note=left(p_note,500),reviewed_by=p_admin_id,reviewed_at=now(),
    updated_at=now(),credit_reserved=case when p_status='rejected' then false else credit_reserved end
    where id=p_request_id;

  if p_status='rejected' and v_request.credit_reserved then
    update public.wallets set training_credits=training_credits+1,updated_at=now()
      where user_id=v_request.user_id returning training_credits into v_balance;
    insert into public.wallet_ledger(user_id,delta,balance_after,reason,credit_type)
      values(v_request.user_id,1,v_balance,'training_refund','voice_training');
  end if;

  insert into public.voice_training_events(request_id,user_id,status,message)
    values(p_request_id,v_request.user_id,p_status,
      case when p_status='rejected' then 'Request rejected; training credit refunded. ' || left(p_note,430)
           else 'Request moved to ' || replace(p_status,'_',' ') || coalesce(': ' || left(nullif(trim(p_note),''),430),'') end);
  insert into public.admin_audit_log(admin_user_id,action,target_training_request_id,details)
    values(p_admin_id,'training_status_updated',p_request_id,jsonb_build_object('from',v_request.status,'to',p_status,'note',left(p_note,500)));
  return jsonb_build_object('id',p_request_id,'status',p_status,'refunded',p_status='rejected' and v_request.credit_reserved);
end; $$;

create or replace function public.publish_private_voice(
  p_request_id uuid,p_admin_id uuid,p_model_slug text,p_note text default null
) returns void language plpgsql security definer set search_path=public as $$
declare v_request public.voice_training_requests%rowtype;
begin
  if coalesce((select auth.role()),'') <> 'service_role' then raise exception 'server-only function'; end if;
  if p_model_slug !~ '^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$' then raise exception 'invalid model slug'; end if;
  select * into v_request from public.voice_training_requests where id=p_request_id for update;
  if not found then raise exception 'training request not found'; end if;
  if v_request.status <> 'model_validation' then raise exception 'request is not ready for publishing'; end if;
  insert into public.voice_models(slug,display_name,description,language,visibility,consent_status,is_active,owner_user_id,training_request_id)
    values(p_model_slug,v_request.voice_name,'Private custom voice trained from an owner-authorized dataset.',v_request.language,'private',
      case when v_request.rights_basis='self_voice' then 'owner_verified' else 'licensed' end,true,v_request.user_id,v_request.id)
  on conflict(slug) do update set display_name=excluded.display_name,description=excluded.description,language=excluded.language,
    visibility='private',consent_status=excluded.consent_status,is_active=true,owner_user_id=excluded.owner_user_id,
    training_request_id=excluded.training_request_id,updated_at=now();
  update public.voice_training_requests set status='ready',model_slug=p_model_slug,admin_note=left(p_note,500),
    reviewed_by=p_admin_id,reviewed_at=now(),updated_at=now(),credit_reserved=false where id=p_request_id;
  insert into public.voice_training_events(request_id,user_id,status,message)
    values(p_request_id,v_request.user_id,'ready','Private voice passed compatibility validation and is ready to use.');
  insert into public.admin_audit_log(admin_user_id,action,target_training_request_id,details)
    values(p_admin_id,'private_voice_published',p_request_id,jsonb_build_object('model_slug',p_model_slug));
end; $$;

revoke all on function public.transition_training_request(uuid,uuid,text,text) from public,anon,authenticated;
grant execute on function public.transition_training_request(uuid,uuid,text,text) to service_role;
revoke all on function public.publish_private_voice(uuid,uuid,text,text) from public,anon,authenticated;
grant execute on function public.publish_private_voice(uuid,uuid,text,text) to service_role;
