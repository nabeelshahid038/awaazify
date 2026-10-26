# Phase 4A — secure orchestration foundation

1. Run `supabase/migrations/202610190003_jobs.sql` once after Phase 3.
2. Confirm `generation_jobs` and `job_events` exist with RLS enabled and no client write policies.
3. Confirm Modal secret `awaazify-v1-production` contains `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, and `WORKER_SHARED_SECRET`.
4. Deploy `worker/modal_worker.py` using `worker/README.md`.
5. Do not stop the prior worker until the new authenticated boundary is verified.

This package does not claim that audio generation is active. It establishes durable job state and a zero-GPU security probe first.
