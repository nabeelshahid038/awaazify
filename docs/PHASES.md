# Phases and acceptance criteria
1. Foundation: React/Vite light UI builds; GET /api/v1/health returns 200; automated backend test; GitHub CI; SQL migration reviewed.
2. Auth and data model: Google OAuth, verified JWT, RLS, atomic entitlements, wallets and transaction schemas.
3. Studio: private uploads, YouTube metadata, source validation, six-minute range selection and persistent user-owned drafts. **Implemented.** Authorized media retrieval and voice catalog remain Phase 4 inputs.
4. GPU: source prep, separation, RVC, mix, persistent jobs, benchmark COGS. **Implemented.**
5. Library and free credit reservation: authenticated voice catalog, permanent private output access, signed previews/downloads and idempotent accounting. **Implemented.**
6. Payments/admin: verified manual topups, ledger, admin audit, rate limits. **Implemented.**
7. Colab training request, consent review, compatibility validation and owner-private publishing. **Implemented.**
8. Production QA: persistent controls, monitoring, backup/restore, cost, CI and deployment runbooks. **Implementation complete; real-account launch gates remain.**
