# Phase 27 — True Applio/RVC Pitch Variants

> Superseded by Phase 28: production now uses -3/0/+3 with an 80% instrumental
> and 100% converted-vocal mix.

Phase 27 replaces the Phase 26 FFmpeg pitch shortcut. Demucs stem separation runs
once, then Applio/RVC inference runs independently with pitch values `0`, `-5`,
and `+5`. Each converted vocal is mixed with the original instrumental.

This provides higher-quality, model-aware pitch behavior. It also increases the
RVC portion of GPU time because inference runs three times. One generation still
uses one Awaazify song credit.

## Deployment order

1. Run `supabase/migrations/202610300002_true_rvc_pitch_variants.sql` in the
   Supabase SQL Editor.
2. Deploy `worker/modal_worker.py` to Modal.
3. Deploy `backend/modal_app.py` to Modal.
4. No frontend redeployment is required when Phase 26 frontend is already live.

## Validation

Generate a short new cover and inspect Modal logs. The conversion stage should
report three completed Applio runs: pitch `+0`, pitch `-5`, and pitch `+5`.
