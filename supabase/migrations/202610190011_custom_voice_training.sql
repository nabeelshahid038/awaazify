-- Phase 7: consent-gated, manual custom voice training requests and private models.
create table if not exists public.voice_training_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  voice_name text not null check (char_length(voice_name) between 2 and 80),
  language text not null check (char_length(language) between 2 and 80),
  rights_basis text not null check (rights_basis in ('self_voice','authorized_voice')),
  consent_confirmed boolean not null check (consent_confirmed),
  dataset_path text not null,
  consent_proof_path text,
  status text not null default 'submitted' check (status in ('submitted','approved','training','model_validation','ready','rejected')),
  model_slug text check (model_slug is null or model_slug ~ '^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$'),
  admin_note text,
  reviewed_by uuid references public.profiles(id),
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (rights_basis='self_voice' or consent_proof_path is not null)
);

alter table public.voice_models add column if not exists owner_user_id uuid references public.profiles(id) on delete cascade;
alter table public.voice_models add column if not exists training_request_id uuid unique references public.voice_training_requests(id) on delete set null;

create index if not exists voice_training_user_created_idx on public.voice_training_requests(user_id,created_at desc);
create index if not exists voice_training_status_created_idx on public.voice_training_requests(status,created_at asc);
create index if not exists voice_models_owner_idx on public.voice_models(owner_user_id) where owner_user_id is not null;

alter table public.voice_training_requests enable row level security;
create policy "Users read own training requests" on public.voice_training_requests
  for select to authenticated using ((select auth.uid())=user_id);
create policy "Users create own training requests" on public.voice_training_requests
  for insert to authenticated with check ((select auth.uid())=user_id and status='submitted' and consent_confirmed);
create policy "Users read own private voices" on public.voice_models
  for select to authenticated using (is_active and owner_user_id=(select auth.uid()));

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('voice-training-data','voice-training-data',false,262144000,array['application/zip','audio/mpeg','audio/wav','audio/x-wav','audio/flac'])
on conflict(id) do update set public=excluded.public,file_size_limit=excluded.file_size_limit,allowed_mime_types=excluded.allowed_mime_types;
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('voice-consent-proofs','voice-consent-proofs',false,10485760,array['image/jpeg','image/png','image/webp','application/pdf','audio/mpeg','audio/wav','video/mp4'])
on conflict(id) do update set public=excluded.public,file_size_limit=excluded.file_size_limit,allowed_mime_types=excluded.allowed_mime_types;

create policy "Users upload own training data" on storage.objects for insert to authenticated
  with check(bucket_id='voice-training-data' and (storage.foldername(name))[1]=(select auth.uid())::text);
create policy "Users read own training data" on storage.objects for select to authenticated
  using(bucket_id='voice-training-data' and (storage.foldername(name))[1]=(select auth.uid())::text);
create policy "Users delete unsubmitted training data" on storage.objects for delete to authenticated
  using(bucket_id='voice-training-data' and (storage.foldername(name))[1]=(select auth.uid())::text and not exists(
    select 1 from public.voice_training_requests r where r.dataset_path=storage.objects.name and r.user_id=(select auth.uid())
  ));
create policy "Users upload own consent proof" on storage.objects for insert to authenticated
  with check(bucket_id='voice-consent-proofs' and (storage.foldername(name))[1]=(select auth.uid())::text);
create policy "Users read own consent proof" on storage.objects for select to authenticated
  using(bucket_id='voice-consent-proofs' and (storage.foldername(name))[1]=(select auth.uid())::text);
create policy "Users delete unsubmitted consent proof" on storage.objects for delete to authenticated
  using(bucket_id='voice-consent-proofs' and (storage.foldername(name))[1]=(select auth.uid())::text and not exists(
    select 1 from public.voice_training_requests r where r.consent_proof_path=storage.objects.name and r.user_id=(select auth.uid())
  ));

create or replace function public.publish_private_voice(
  p_request_id uuid,p_admin_id uuid,p_model_slug text,p_note text default null
) returns void language plpgsql security definer set search_path=public as $$
declare v_request public.voice_training_requests%rowtype;
begin
  if coalesce((select auth.role()),'') <> 'service_role' then raise exception 'server-only function'; end if;
  if p_model_slug !~ '^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$' then raise exception 'invalid model slug'; end if;
  select * into v_request from public.voice_training_requests where id=p_request_id for update;
  if not found then raise exception 'training request not found'; end if;
  if v_request.status not in ('approved','training','model_validation') then raise exception 'request is not publishable'; end if;
  insert into public.voice_models(slug,display_name,description,language,visibility,consent_status,is_active,owner_user_id,training_request_id)
    values(p_model_slug,v_request.voice_name,'Private custom voice trained from an owner-authorized dataset.',v_request.language,'private',
      case when v_request.rights_basis='self_voice' then 'owner_verified' else 'licensed' end,true,v_request.user_id,v_request.id)
  on conflict(slug) do update set display_name=excluded.display_name,description=excluded.description,language=excluded.language,
    visibility='private',consent_status=excluded.consent_status,is_active=true,owner_user_id=excluded.owner_user_id,
    training_request_id=excluded.training_request_id,updated_at=now();
  update public.voice_training_requests set status='ready',model_slug=p_model_slug,admin_note=left(p_note,500),reviewed_by=p_admin_id,
    reviewed_at=now(),updated_at=now() where id=p_request_id;
end; $$;

revoke all on function public.publish_private_voice(uuid,uuid,text,text) from public,anon,authenticated;
grant execute on function public.publish_private_voice(uuid,uuid,text,text) to service_role;
