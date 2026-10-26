# Phase 4D — stem separation and GPU RVC conversion

Phase 4D turns the private normalized WAV into three private artifacts:

1. `vocals.wav` — vocals isolated by Demucs `htdemucs`.
2. `instrumental.wav` — accompaniment retained for final mixing.
3. `converted-vocals.wav` — isolated vocals converted by Applio/RVC.

The worker pins Applio `3.6.5`, uses the existing T4 GPU, the matching `.pth` and
`.index` from `awaazify-rvc-models`, RMVPE pitch extraction, ContentVec features,
and a 0.5 retrieval blend. All artifacts stay in the private `job-artifacts` bucket.

## Setup order

1. Apply `supabase/migrations/202610190006_voice_conversion.sql` once.
2. From `worker`, deploy `modal_worker.py`. The first image build downloads the
   pinned RVC/Demucs dependencies and can take substantially longer than Phase 4C.
3. Copy the new `dispatch-convert-voice` endpoint URL into backend `.env`:
   `WORKER_CONVERT_URL=https://...`
4. Keep the existing `WORKER_PREPARE_URL`, `WORKER_SHARED_SECRET`, Supabase values,
   and model Volume unchanged.
5. Restart the local backend and frontend from this Phase 4D package.
6. For the existing job at `prepared · 20%`, click **Continue voice conversion** once.

Future jobs automatically continue from preparation into conversion. The worker
atomically claims a prepared job, so repeated dispatches cannot start duplicate GPU
conversion. A conversion failure marks the job failed and restores the free credit.

## Expected status sequence

`prepared 20%` → `separating 25%` → `converting 50%` → `converted 75%`

`converted` means Phase 4D succeeded. Final stem mixing and downloadable output are
implemented in Phase 4E.

## Security and operational notes

- Never place worker endpoint URLs or `WORKER_SHARED_SECRET` in frontend variables.
- Model slugs and artifact paths are validated and scoped to the owning user/job.
- Source, stems, and converted vocals remain private.
- Applio is used under its MIT license and responsible-use terms. Users must have
  permission for source audio and target voices.

