# Architecture
Browser (React/Vite/Cloudflare Pages planned) -> FastAPI (local or Modal ASGI) -> Supabase (auth/database/storage). Modal GPU job pipeline added in Phase 4.

## Security boundaries
- Never expose Supabase secret/service keys in Vite-prefixed environment variables.
- This foundation exposes only an unauthenticated health endpoint. OAuth/JWT authorization is Phase 2; do not add admin endpoints before verified access checks.
- Supabase RLS is enabled on foundation tables. Trial writes are not available to browser clients.
- Upload and YouTube source ingestion are not implemented yet; any future adapters must validate access rights, duration, URLs and source availability.

## Permanent output retention
No time-based deletion. Private output buckets and durable storage funding are future prerequisites; retention is subject to user deletion, lawful takedown and infrastructure limits.
