# Phase 15 — Support, refunds and trial anti-abuse

Phase 15 removes self-service account deletion, keeps Google-only authentication, adds an in-app support desk and admin queue, publishes a refund/credit policy, and prevents repeated free signup credits for the same normalized Google email.

## Trial protection

Migration `202610200004_support_and_trial_abuse.sql` creates a private hashed identity registry. It backfills all existing Supabase Auth users before replacing the signup trigger. A first-seen email receives one free song credit; a later account using the same normalized email receives zero trial credits. Gmail dots, `+aliases`, and `googlemail.com` are canonicalized to the same identity. The registry has RLS enabled and no client policies.

## Deployment

1. Run the complete `supabase/migrations/202610200004_support_and_trial_abuse.sql` file in Supabase SQL Editor.
2. Deploy the API from the Phase 15 backend folder.
3. Copy the known-good `.env.production` into the Phase 15 frontend folder.
4. Build and deploy the frontend to the existing Cloudflare Pages production branch.

```powershell
cd C:\Users\Lenovo\Downloads\awaazify-phase15-support-antiabuse\backend
..\..\awaazify-phase3\backend\.venv\Scripts\modal.exe deploy modal_app.py

$apiUrl = "https://nabeeljarwar022--awaazify-api-web.us-east.modal.run"
Invoke-RestMethod -Uri "$apiUrl/api/v1/health"
Invoke-RestMethod -Uri "$apiUrl/api/v1/health/ready"

Copy-Item C:\Users\Lenovo\Downloads\awaazify-phase14-launch-safety\frontend\.env.production C:\Users\Lenovo\Downloads\awaazify-phase15-support-antiabuse\frontend\.env.production
cd C:\Users\Lenovo\Downloads\awaazify-phase15-support-antiabuse\frontend
npm.cmd install
npm.cmd run build
npx.cmd wrangler pages deploy dist --project-name awaazify --branch production
```

## Verification

1. Settings shows the Google profile and Help & Support; there is no account-delete control.
2. Submit a test support ticket and confirm it appears in the user's Support history.
3. Open Admin Console, start review, then resolve it with a note. Confirm the user sees the note.
4. Open the Refunds link in the public and authenticated footer.
5. Trial replay should be tested only with a disposable Google account: create it, remove that test user through Supabase Auth Admin, then sign in again with the same Google email. The recreated account must show `0 free` credits.

Do not delete the owner/admin Auth user during testing.

