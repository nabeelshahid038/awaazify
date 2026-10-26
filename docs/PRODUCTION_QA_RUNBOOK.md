# Awaazify production QA and launch runbook

## Automated smoke test

Run after every API or frontend deployment:

```powershell
cd C:\Users\Lenovo\Downloads\awaazify-phase16-production-qa
py .\scripts\production_smoke.py
```

The release passes only when all eight checks pass. The script performs read-only public checks and does not launch GPU jobs.

## Admin live diagnostics

Open Admin → Production Readiness → Run checks. Database, private job storage, worker configuration and HTTPS frontend origin must all show green. This endpoint is admin-only and never returns secrets.

## Two-account privacy test

Use two disposable Google accounts A and B.

1. A uploads audio, creates a song, submits a payment proof and support request.
2. B must not see A's Studio project, song, proof, ticket, training dataset or private voice.
3. Copying an expired/signed A download URL into B's session must not expose a fresh permanent URL.
4. Run `scripts/rls_audit.sql`; its unsafe-table query must return zero rows.

## Billing and failure matrix

| Test | Expected result |
|---|---|
| New Google identity | Exactly 1 free song credit |
| Same Gmail recreated by Auth admin | 0 free credits |
| Gmail dot or + alias | 0 additional free credits |
| Double-click Create | One job and one credit reservation |
| Worker dispatch failure | Failed job and exactly one refund |
| Retry failed job | Maximum three retries; no duplicate refund |
| Duplicate payment approval | Credits granted once |
| Rejected payment | No credits granted; admin reason visible |
| Rejected voice request | Exactly one training credit returned |
| Completed song deletion | Song and private artifacts removed; ledger retained without job link |

## Launch-day monitoring

- Run the smoke test before launch, immediately after launch, and after each deployment.
- Check Admin every few hours during the pilot for failed jobs, pending payments, support and security events.
- Check Modal GPU spend and Supabase database/storage usage daily during the first week.
- Pause paid promotion if readiness fails, failure rate rises unexpectedly, refunds duplicate, or cross-account privacy fails.

## Rollback

Frontend: redeploy the previous known-good Cloudflare Pages deployment. Backend: redeploy `modal_app.py` from the previous known-good phase folder. Database migrations are forward-only: do not manually drop tables or functions during an incident. Disable the affected feature in the UI/API and prepare a reviewed corrective migration.

