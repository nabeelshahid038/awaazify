-- Phase 14: safe user-owned content deletion.
alter table public.generation_jobs
  drop constraint if exists generation_jobs_project_id_fkey;
alter table public.generation_jobs
  add constraint generation_jobs_project_id_fkey
  foreign key (project_id) references public.studio_projects(id) on delete cascade;

alter table public.wallet_ledger
  drop constraint if exists wallet_ledger_generation_job_id_fkey;
alter table public.wallet_ledger
  add constraint wallet_ledger_generation_job_id_fkey
  foreign key (generation_job_id) references public.generation_jobs(id) on delete set null;

create or replace function public.delete_own_song(p_user_id uuid, p_job_id uuid)
returns jsonb language plpgsql security definer set search_path=public as $$
declare v_job public.generation_jobs%rowtype;
begin
  if p_user_id <> auth.uid() then raise exception 'not authorized'; end if;
  select * into v_job from public.generation_jobs
    where id=p_job_id and user_id=p_user_id and status in ('completed','failed') for update;
  if not found then raise exception 'song not found or still processing'; end if;
  delete from public.studio_projects where id=v_job.project_id and user_id=p_user_id;
  return jsonb_build_object('deleted',true,'job_id',p_job_id);
end $$;
revoke all on function public.delete_own_song(uuid,uuid) from public;
grant execute on function public.delete_own_song(uuid,uuid) to authenticated;

