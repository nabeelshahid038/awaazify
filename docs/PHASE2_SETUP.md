# Phase 2 — Google OAuth and authenticated workspace

## Supabase setup
1. Create a Supabase project. In SQL Editor run `supabase/migrations/202610190001_initial.sql` once on the **fresh** project.
2. Google Cloud Console: create an OAuth Web Application; add Supabase's Google callback URL as the **Authorized redirect URI**: `https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback` (copy the exact URL from Supabase Auth provider configuration).
3. Supabase → Authentication → Providers → Google: enable and configure Google client ID + secret. Never put the Google secret in frontend code.
4. Supabase → Authentication → URL Configuration: Site URL `http://localhost:5173`; additional redirect URLs `http://localhost:5173/auth/callback` and optionally `http://127.0.0.1:5173/auth/callback` (match the URL used in browser). Configure production URLs before deployment.
5. Copy `frontend/.env.example` to `frontend/.env.local` and fill VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY using your own project's public/publishable key. Do not use a service-role/secret key in Vite.
6. Copy `backend/.env.example` to `backend/.env`. Fill SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY. Backend `/me` validates user bearer tokens with Supabase Auth and reads profile/trial through that user's RLS. Secret key is not used in Phase 2.
7. Run FastAPI on port 8000 and Vite on port 5173. Prefer `http://localhost:5173` consistently. Sign in with Google. Profile and one free song credit should appear.

## Current functional scope
- Google OAuth, session restoration, sign-out, real account profile and trial counter from Supabase.
- Responsive light workspace navigation and backend health status.
- Studio, voices, songs and wallet are intentionally labeled future functionality.
- A trial entitlement is created by a database trigger, **not consumed** in Phase 2.
- For Google OAuth configuration, use official current Supabase documentation: https://supabase.com/docs/guides/auth/social-login/auth-google

## Troubleshooting
- Provider error: check client ID, secret, the exact Google Authorized redirect URI and Supabase allowed redirect URLs.
- Profile request 409: migration/trigger was not installed before sign-up; test using a new development user or fix migration.
- CORS: ensure frontend origin matches backend FRONTEND_ORIGIN; default localhost and 127.0.0.1 are included for local development only.
- Never check `.env`, `.env.local`, tokens or secret keys into Git.
