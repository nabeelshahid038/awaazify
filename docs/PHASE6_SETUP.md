# Phase 6 setup — wallet, manual payments and admin review

Phase 6 adds paid song credits without pretending that a card gateway exists. Users send an EasyPaisa or JazzCash payment, upload a private receipt, and receive credits only after the configured admin verifies it. Every approval, reservation and refund is recorded in an immutable ledger.

## 1. Copy the working Phase 5 environment

```powershell
Copy-Item ..\awaazify-phase5\backend\.env .\backend\.env
Copy-Item ..\awaazify-phase5\frontend\.env.local .\frontend\.env.local
```

## 2. Configure payment ownership

Add these values to `backend/.env`. Use the same Google email used to sign into Awaazify as the admin.

```env
ADMIN_EMAIL=your-admin-email@example.com
CREDIT_PRICE_PKR=300
EASYPAISA_ACCOUNT_TITLE=Your Account Title
EASYPAISA_ACCOUNT_NUMBER=03XXXXXXXXX
JAZZCASH_ACCOUNT_TITLE=Your Account Title
JAZZCASH_ACCOUNT_NUMBER=03XXXXXXXXX
```

`CREDIT_PRICE_PKR` is the exact price of one generation credit. Payment amounts must be exact multiples of that value. Never place these settings or the Supabase secret key in `frontend/.env.local`.

## 3. Apply the migration

Run the full contents of `supabase/migrations/202610190010_wallet_payments.sql` once in the Supabase SQL Editor after migrations 001–009.

It creates wallets, payment requests, the immutable wallet ledger, admin audit logs, the private `payment-proofs` bucket, atomic approval, and paid-credit reservation/refund support.

## 4. Restart the local services

Backend:

```powershell
cd backend
..\..\awaazify-phase3\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

The Phase 4E Modal worker is unchanged and does not need redeployment.

## 5. Acceptance test

1. Sign in with a normal user and open **Wallet**.
2. Confirm the configured payment account and price are correct.
3. Submit an exact payment amount, sender details, unique transaction ID and screenshot/PDF proof.
4. Sign in with `ADMIN_EMAIL`, open **Wallet**, inspect the private proof and approve or reject it.
5. On approval, the user's paid balance must increase exactly once and the request must disappear from the pending admin queue.
6. Generate a song after the trial credit is exhausted. One paid credit must be reserved; a worker failure must refund it.

## Production note

Manual verification is appropriate for the current V1, but it is operational work—not an automated payment gateway. Before public launch, document refund rules, proof retention, support handling, abuse monitoring, backups and legal/tax obligations applicable in Pakistan.
