# Phase 14 — Launch safety and user data controls

This phase adds responsive Terms, Privacy and Copyright/Voice Rights pages, permanent deletion for completed/failed songs, self-service account deletion, and owner-admin deletion protection.

## 1. Apply the database migration

In Supabase Dashboard → SQL Editor, open and run the complete file:

`supabase/migrations/202610200003_user_data_controls.sql`

Run it once before deploying the new backend. It changes the song/project foreign keys so a user's song can be deleted safely while wallet history keeps a null job reference.

## 2. Deploy the API

```powershell
cd C:\Users\Lenovo\Downloads\awaazify-phase14-launch-safety\backend
..\..\awaazify-phase3\backend\.venv\Scripts\modal.exe deploy modal_app.py
```

No new Modal secret is required. Verify:

```powershell
$apiUrl = "https://nabeeljarwar022--awaazify-api-web.us-east.modal.run"
Invoke-RestMethod -Uri "$apiUrl/api/v1/health"
Invoke-RestMethod -Uri "$apiUrl/api/v1/health/ready"
```

## 3. Build and deploy the frontend

Copy the existing production environment file if it was not included during extraction:

```powershell
Copy-Item C:\Users\Lenovo\Downloads\awaazify-phase13-voice-training\frontend\.env.production C:\Users\Lenovo\Downloads\awaazify-phase14-launch-safety\frontend\.env.production
```

Then build and publish:

```powershell
cd C:\Users\Lenovo\Downloads\awaazify-phase14-launch-safety\frontend
npm.cmd install
npm.cmd run build
npx.cmd wrangler pages deploy dist --project-name awaazify --branch production
```

## 4. Production checks

1. Open the Terms, Privacy and Copyright links while signed out and signed in.
2. Create a short test song, download it, then delete it from My Songs. Confirm it disappears after refresh.
3. Test account deletion only with a disposable non-admin account. Type `DELETE`, confirm, and verify that the session ends.
4. Confirm the configured owner-admin account sees deletion blocked in Settings.
5. Have a Pakistan-qualified lawyer review the operational legal templates before broad paid marketing.

## Important

- Song deletion is intentionally unavailable while a job is still processing.
- Account deletion removes the Supabase auth user, related database rows, and referenced private Storage files.
- If the user had a custom model published to the Modal model volume, remove that model manually after a verified deletion/consent-revocation request; this is explicitly disclosed in the Privacy Policy.

