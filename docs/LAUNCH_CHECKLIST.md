# Awaazify V1 launch checklist

## Security and privacy

- [ ] Rotate all secrets that appeared in terminals, screenshots or chat.
- [ ] Confirm the Supabase secret key and worker secret exist only in server/Modal secrets.
- [ ] Run every migration 001–012 on production and re-test RLS with two separate user accounts.
- [ ] Verify private audio, songs, proofs, datasets and private voices cannot cross user boundaries.
- [ ] Confirm production CORS origin and trusted API host are exact; no wildcard origins.
- [ ] Review payment-proof and consent-evidence retention/deletion policy with local legal advice.

## Reliability and recovery

- [ ] Enable database backups and create separate Storage/model backups.
- [ ] Complete one staging restoration drill and record recovery time and data loss window.
- [ ] Test worker failure refund, duplicate payment approval, duplicate generation click and expired signed URLs.
- [ ] Configure external uptime checks for `/api/v1/health` and `/api/v1/health/ready`.
- [ ] Define who responds to failed jobs, payment disputes, abuse reports and consent revocation.

## Cost and capacity

- [ ] Measure real GPU seconds and cost for 1-, 3- and 6-minute songs, then update the estimate.
- [ ] Set Modal and Supabase budget alerts/limits.
- [ ] Load-test the API without launching GPU jobs and confirm rate limits across multiple instances.
- [ ] Estimate private Storage growth and decide user capacity/retention terms.

## Product and compliance

- [ ] Replace the development-only celebrity model with licensed/owner-verified launch models.
- [x] Publish Terms, Privacy Policy and copyright/voice-consent rules (Phase 14 operational templates).
- [ ] Obtain Pakistan-qualified legal review and add a final refund policy/contact address before broad paid marketing.
- [ ] Verify EasyPaisa/JazzCash account ownership and accounting/tax obligations.
- [ ] Test responsive UX, accessibility, supported browsers and clear error recovery.
- [ ] Complete one invited-user pilot before public signup or paid marketing.
