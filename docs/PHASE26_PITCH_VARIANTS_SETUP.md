# Phase 26 — Three Pitch Versions

> Superseded by Phase 27 for production: the current worker runs true Applio/RVC
> inference independently at 0, -5, and +5 pitch.

Each new successful song generation now produces:

- **Default:** 0 pitch
- **Deep:** -5 pitch
- **High:** +5 pitch

The expensive Demucs/RVC GPU pipeline still runs once. The final CPU mixing worker
creates the three private MP3 variants, so one generation continues to consume one
song credit. The user can preview all variants, save a preferred version, change it
later in My Songs, and download the selected MP3.

## Production deployment order

Deploy in this exact order so the worker and API never write columns that do not
exist yet.

### 1. Apply the Supabase migration

Open **Supabase Dashboard → SQL Editor → New query**, paste the complete contents
of `supabase/migrations/202610300001_pitch_variants.sql`, and run it once.

### 2. Deploy the Modal worker

From the project root in PowerShell:

```powershell
cd C:\Users\Lenovo\Downloads\awaazify-phase26-pitch-variants

..\awaazify-phase3\backend\.venv\Scripts\modal.exe deploy .\worker\modal_worker.py
```

Keep the existing worker URLs and secrets. No new secret is required.

### 3. Deploy the API

```powershell
cd .\backend

..\..\awaazify-phase3\backend\.venv\Scripts\modal.exe deploy modal_app.py
```

### 4. Build and deploy the frontend

Copy your existing production frontend environment file if this extracted folder
does not contain one:

```powershell
Copy-Item `
  C:\Users\Lenovo\Downloads\awaazify-phase25-final-ui\frontend\.env.production `
  C:\Users\Lenovo\Downloads\awaazify-phase26-pitch-variants\frontend\.env.production
```

Then:

```powershell
cd C:\Users\Lenovo\Downloads\awaazify-phase26-pitch-variants\frontend

npm.cmd install
npm.cmd run build
npx.cmd wrangler pages deploy dist --project-name awaazify --branch production
```

### 5. Production test

Generate one short uploaded-audio cover. At 100%, confirm:

1. The version chooser opens automatically.
2. Default, Deep (-5), and High (+5) each play.
3. Selecting a version visually marks it as selected.
4. My Songs → Versions shows the same three choices.
5. Selected MP3 downloads the currently chosen version.
6. Only one song credit was deducted.

## Compatibility

Old songs remain usable and show their original Default version. Only songs
generated after the Phase 26 worker deployment receive all three variants.
