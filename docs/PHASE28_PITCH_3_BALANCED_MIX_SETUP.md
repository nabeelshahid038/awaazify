# Phase 28 — True RVC ±3 and Balanced Mix

New generations run Applio/RVC independently at pitch `0`, `-3`, and `+3`.
The final mix uses:

- Instrumental: 80% (`volume=0.80`)
- Converted vocal: 100% (`volume=1.0`)

This keeps the vocal clear without making the accompaniment feel too weak. The
limiter and loudness normalization remain enabled to control clipping and produce
a consistent final MP3.

## Deployment order

1. Run `supabase/migrations/202610300003_pitch_3_balanced_mix.sql` in Supabase.
2. Deploy `worker/modal_worker.py`.
3. Deploy `backend/modal_app.py`.
4. Build and deploy the frontend because labels and API types changed to ±3.

Old ±5 files remain private and are still removed when an old song is deleted.
Their saved preferred choice is reset to Default during migration. New generations
receive only 0, -3 and +3.
