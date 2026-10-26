# Phase 4E — final mix and secure download

Phase 4E mixes the private RVC-converted vocal with the private instrumental,
applies clipping protection and loudness normalization, and stores lossless WAV
plus 192 kbps MP3 outputs in the private `job-artifacts` bucket.

## Setup

1. Apply `supabase/migrations/202610190008_final_mix.sql` once.
2. Deploy `worker/modal_worker.py`.
3. Save the `dispatch-mix-final` endpoint as `WORKER_MIX_URL` in backend `.env`.
4. Restart the Phase 4E backend and frontend.
5. On an existing `converted · 75%` job, click **Create final song** once.

Expected status: `converted 75%` → `mixing 85%` → `completed 100%`.
The download endpoint verifies job ownership and returns 15-minute private signed
URLs. Worker credentials and storage paths never enter frontend configuration.
