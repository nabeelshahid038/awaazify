# Phase 8 setup — production hardening and launch operations

Phase 8 adds persistent rate limits, correlated request logs, security headers, trusted-host enforcement, request-size limits, readiness checks, admin operational metrics, GPU cost estimates and full CI coverage. It also supplies an explicit deployment and recovery checklist.

## Local upgrade

1. Copy the working Phase 7 `backend/.env` and `frontend/.env.local` files.
2. Run `supabase/migrations/202610190012_production_controls.sql` once after migrations 001–011.
3. Keep local settings:

```env
ENVIRONMENT=development
ALLOWED_HOSTS=localhost,127.0.0.1,testserver
ESTIMATED_GPU_COST_USD_PER_SONG=0.08
MAX_REQUEST_BYTES=275000000
```

The cost value is an operator estimate, not a bill. Replace it after measuring real Modal usage.

## Production API on Modal

Create a Modal Secret named `awaazify-api-production` through the Modal dashboard. Copy every server-side setting from the verified backend environment, including Supabase keys, worker URLs/secret, admin/payment settings, and:

```env
ENVIRONMENT=production
FRONTEND_ORIGIN=https://YOUR-FRONTEND-DOMAIN
ALLOWED_HOSTS=YOUR-API-HOST.modal.run
```

Do not include `VITE_*` variables in the API secret. Deploy from `backend`:

```powershell
..\..\awaazify-phase3\backend\.venv\Scripts\modal.exe deploy modal_app.py
```

Verify both endpoints:

- `GET https://YOUR-API-HOST.modal.run/api/v1/health` returns HTTP 200.
- `GET https://YOUR-API-HOST.modal.run/api/v1/health/ready` returns `status: ready`.

## Frontend deployment

Use Cloudflare Pages with root directory `frontend`, build command `npm run build`, and output directory `dist`. Configure only:

```env
VITE_SUPABASE_URL=https://YOUR-PROJECT.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=YOUR-PUBLISHABLE-KEY
VITE_API_BASE_URL=https://YOUR-API-HOST.modal.run
```

Add the final frontend domain and `/auth/callback` URL to Supabase Authentication redirect allowlists. Update `FRONTEND_ORIGIN` in the Modal API secret to the exact HTTPS origin and redeploy the API.

## Controls now enforced

- Five generation reservations per user per hour.
- Three payment submissions per user per hour.
- Two training submissions per user per 24 hours.
- Rate-limit state is stored in Postgres and shared across API instances.
- API responses receive a request ID, CSP, anti-framing, MIME-sniffing, referrer and permissions protections.
- Production API documentation is disabled.
- Admin Wallet displays active jobs, 24-hour failures, pending queues, security events and estimated GPU spend.

## Backups and recovery

Database backups do not automatically guarantee Storage or Modal Volume recovery. Maintain three independently tested backups:

1. Supabase database: enable the plan's managed backups or scheduled `pg_dump`; protect encryption keys and connection credentials.
2. Supabase Storage: periodically copy `source-audio`, `job-artifacts`, `payment-proofs`, `voice-training-data` and `voice-consent-proofs` to a private versioned bucket.
3. Modal models: download or mirror `awaazify-rvc-models/models/` to encrypted durable storage after every approved model publication.

Quarterly, restore into a separate staging project and prove that login, ownership/RLS, one private artifact, wallet balance/ledger, one model pair and one generation job can be recovered. Never test restoration by overwriting production.

## Launch gate

Phase 8 code completion does not itself mean public launch. All items in `docs/LAUNCH_CHECKLIST.md` must be evidenced in the real production accounts.
