# Phase 17 — Responsive UI and voice marketplace

This phase separates the voice marketplace from custom training, adds public voice previews and admin model controls, modernizes the core product pages, and changes the displayed Pakistan payment methods to HBL and NayaPay.

## 1. Apply the database migration

In Supabase → SQL Editor, open and run the complete file:

`supabase/migrations/202610200005_voice_marketplace.sql`

Run this before deploying the backend. It adds category, picture, demo and ordering fields without deleting existing models.

## 2. Update payment settings

In `backend/.env.production`, add:

```env
HBL_ACCOUNT_TITLE=YOUR_ACCOUNT_TITLE
HBL_ACCOUNT_NUMBER=YOUR_ACCOUNT_NUMBER
NAYAPAY_ACCOUNT_TITLE=YOUR_ACCOUNT_TITLE
NAYAPAY_ACCOUNT_NUMBER=YOUR_ACCOUNT_NUMBER
```

The old database method keys are intentionally retained so previous payment records remain valid. Recreate the Modal secret after editing the file:

```powershell
cd C:\Users\Lenovo\Downloads\awaazify-phase17-ui-voice-marketplace
..\awaazify-phase3\backend\.venv\Scripts\modal.exe secret create awaazify-api-production --from-dotenv .\backend\.env.production --force
```

If the installed Modal CLI does not support `--force`, delete/recreate the secret in the Modal dashboard or use the overwrite confirmation shown by the CLI.

## 3. Deploy the API

```powershell
cd C:\Users\Lenovo\Downloads\awaazify-phase17-ui-voice-marketplace\backend
..\..\awaazify-phase3\backend\.venv\Scripts\modal.exe deploy modal_app.py
```

## 4. Build and deploy the frontend

Copy the production frontend environment file from Phase 16, then build and deploy:

```powershell
Copy-Item C:\Users\Lenovo\Downloads\awaazify-phase16-production-qa\frontend\.env.production C:\Users\Lenovo\Downloads\awaazify-phase17-ui-voice-marketplace\frontend\.env.production
cd C:\Users\Lenovo\Downloads\awaazify-phase17-ui-voice-marketplace\frontend
npm.cmd install
npm.cmd run build
npx.cmd wrangler pages deploy dist --project-name awaazify --branch production
```

## 5. Publish a voice safely

Sign in as the admin, open **Admin → Voice marketplace**, select an existing model or enter a worker model slug, then add its category, picture and two HTTPS demo-audio URLs. Keep **Active & usable** off until the matching model folder exists on the worker and rights are verified. A development-only model cannot be activated.

For an approved model, choose **Licensed** or **Owner verified**, set visibility, enable **Active & usable**, and save. It then appears on the landing page and authenticated Voices page.

## 6. Final checks

- Landing menu scrolls to Voices, How it works and Pricing.
- Selecting a landing-page voice opens Google sign-in and returns to Create Song with that voice selected.
- Voices and Custom Voice are separate pages.
- HBL and NayaPay display only the account details configured through private server environment variables.
- Inputs have visible borders and focus states; Delete has readable contrast.
- Test desktop and a narrow mobile viewport.
- Generate one short cover and confirm one credit is charged only after the job is reserved.
