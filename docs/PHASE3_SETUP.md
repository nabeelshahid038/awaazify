# Phase 3 — Studio sources and private drafts

## Upgrade from the verified Phase 2 project

1. In Supabase SQL Editor, run `supabase/migrations/202610190002_studio.sql` once. Keep the original Phase 2 migration in place; do not rerun it.
2. Confirm Table Editor contains `studio_projects` with RLS enabled.
3. Confirm Storage contains the private `source-audio` bucket. Do not make it public.
4. Keep the existing frontend and backend environment values. No secret/service-role key is required in Phase 3.
5. Restart both applications so the new code loads.

```powershell
# backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# frontend (separate terminal)
npm install
npm run build
npm run dev
```

## Acceptance test

- Google session restores and `/api/v1/me` still displays the real profile and single trial credit.
- Studio accepts a valid public YouTube URL and displays oEmbed title/thumbnail. It does not download or bypass access controls.
- Studio rejects invalid hosts and malformed video IDs.
- Audio upload accepts the documented audio MIME types, up to 100 MB and six minutes.
- Saving an upload writes the object under `<auth-user-id>/...` in the private bucket and creates one matching `studio_projects` row.
- A user cannot list, read, create, update or delete another user's project/object through client credentials.
- Repeated sign-in or draft creation does not change free-song credit. Credit reservation belongs to Phase 5.

## Current boundary

Phase 3 saves processing-ready source drafts. It does not download YouTube media, separate stems, run RVC, generate songs or consume credits. Those operations require the Phase 4 job/GPU pipeline and Phase 5 accounting transaction.
