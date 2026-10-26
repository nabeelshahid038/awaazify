# Phase 5 setup — voice catalog and song library

Phase 5 turns the completed Phase 4E pipeline into a usable personal library. It adds an authenticated voice catalog, persists the selected voice in the browser, and lists the signed-in user's completed or failed generations with private preview and MP3 download actions.

## 1. Copy the existing environment files

Keep the working Phase 4E credentials. From the extracted Phase 5 folder in PowerShell:

```powershell
Copy-Item ..\awaazify-phase4e\backend\.env .\backend\.env
Copy-Item ..\awaazify-phase4e\frontend\.env.local .\frontend\.env.local
```

Do not place the Supabase secret key in the frontend environment.

## 2. Apply the database migration

Open the Supabase SQL Editor and run the complete contents of:

`supabase/migrations/202610190009_library_and_voices.sql`

Run it once after migrations `001` through `008`. The migration creates the public voice catalog and seeds the existing development-test voice entry.

## 3. Start the API and frontend

Backend terminal:

```powershell
cd backend
..\..\awaazify-phase3\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Frontend terminal:

```powershell
cd frontend
npm install
npm run dev
```

No Modal redeployment is required when upgrading directly from the working Phase 4E package because the worker is unchanged.

## 4. Acceptance check

1. Sign in and open **Voices**. The active development-test voice should be visible and selectable.
2. Open **Studio** and confirm the selected voice appears in the generation workflow.
3. Open **My Songs**. Your completed song should appear.
4. Select **Preview** and then **Download MP3**. Both use short-lived, ownership-checked signed URLs.
5. Failed jobs, if any, should be visible under the Failed filter with their stored error message.

## Current limitation

The seeded Babar Azam checkpoint remains explicitly marked `development_only`. It is not an approval for public or commercial impersonation. Production publishing requires a licensed or owner-verified voice model and a documented consent process.
