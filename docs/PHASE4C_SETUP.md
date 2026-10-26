# Phase 4C — authenticated audio preparation

This phase proves the real job path before source separation and voice conversion:

1. The backend authenticates the user and verifies project ownership.
2. A PostgreSQL function atomically reserves the single free credit and creates the job.
3. Upload sources receive a 15-minute signed URL; YouTube sources retain the rights-confirmed URL.
4. The authenticated Modal dispatcher starts a CPU preparation task.
5. FFmpeg enforces the real duration, trims to at most six minutes, normalizes to stereo 44.1 kHz WAV, and uploads to the private `job-artifacts` bucket.
6. Supabase records `prepared` at 20% or records failure and restores the reserved credit.

## Setup order

1. Apply `supabase/migrations/202610190004_preparation.sql`, then `202610190005_service_role_guard.sql`, once each.
2. Redeploy `worker/modal_worker.py`.
3. Copy the `dispatch-prepare-audio` endpoint into backend `.env` as `WORKER_PREPARE_URL`.
4. Keep `WORKER_SHARED_SECRET` identical to the Modal Secret.
5. Restart the backend after editing `.env`.

Do not expose the preparation endpoint or worker secret in frontend variables.
