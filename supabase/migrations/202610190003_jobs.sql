-- Phase 4A: durable, user-owned generation jobs and append-only progress events.
create table public.generation_jobs (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references public.profiles(id) on delete cascade,
 project_id uuid not null references public.studio_projects(id) on delete restrict,
 status text not null default 'queued' check (status in ('queued','preparing','separating','converting','mixing','completed','failed','cancelled')),
 progress smallint not null default 0 check (progress between 0 and 100),
 worker_job_id text unique,
 error_code text,
 error_message text,
 attempt_count smallint not null default 0 check (attempt_count between 0 and 3),
 started_at timestamptz,
 completed_at timestamptz,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique(project_id)
);
create table public.job_events (
 id bigint generated always as identity primary key,
 job_id uuid not null references public.generation_jobs(id) on delete cascade,
 user_id uuid not null references public.profiles(id) on delete cascade,
 stage text not null,
 progress smallint not null check (progress between 0 and 100),
 message text not null check (char_length(message) between 1 and 500),
 created_at timestamptz not null default now()
);
create index generation_jobs_user_created_idx on public.generation_jobs(user_id,created_at desc);
create index job_events_job_created_idx on public.job_events(job_id,created_at);
alter table public.generation_jobs enable row level security;
alter table public.job_events enable row level security;
create policy "Users read own jobs" on public.generation_jobs for select to authenticated using ((select auth.uid())=user_id);
create policy "Users read own job events" on public.job_events for select to authenticated using ((select auth.uid())=user_id);
-- Creation and all state transitions are server-only. No authenticated client write policies.
