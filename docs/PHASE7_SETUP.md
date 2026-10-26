# Phase 7 setup — consent-gated custom voice training

Phase 7 adds a manual Colab training-request workflow. Users can submit an owner-authorized dataset, administrators can review consent, track manual training stages, validate the resulting RVC model on Modal, and publish it as a private voice visible only to its owner.

## 1. Preserve the Phase 6 environment

```powershell
Copy-Item ..\awaazify-phase6\backend\.env .\backend\.env
Copy-Item ..\awaazify-phase6\frontend\.env.local .\frontend\.env.local
```

Add the already-deployed Modal `probe-voice-model` endpoint to `backend/.env`:

```env
WORKER_MODEL_PROBE_URL=https://YOUR-MODAL-ENDPOINT.modal.run
```

Keep `WORKER_SHARED_SECRET` unchanged. The URL and bearer secret are server-only and must never be placed in frontend configuration, screenshots or public source control.

## 2. Apply the migration

Run `supabase/migrations/202610190011_custom_voice_training.sql` once in the Supabase SQL Editor after migrations 001–010.

It creates the request state machine, private training-data and consent-proof buckets, private voice ownership, and the atomic publish function.

## 3. Restart the services

Start the same FastAPI and Vite commands used in Phase 6. The Modal worker source is unchanged, so redeployment is not required if its existing model-probe endpoint URL is available.

## 4. Manual review and Colab training

1. The user opens **Voices**, chooses `My own voice` or `Another consenting adult`, uploads clean vocal data, accepts the explicit consent statement, and submits.
2. The admin downloads the private dataset and, when applicable, consent proof. Reject unclear ownership or unsafe/incomplete consent.
3. After approval, the admin moves the request to `training` and trains it in the trusted manual Colab notebook/workflow.
4. The output must contain exactly one safe RVC `.pth` checkpoint and one FAISS `.index` file.
5. Pick a unique lowercase slug, for example `nabeel-private-v1`, and upload both files to the existing Modal Volume:

```powershell
..\awaazify-phase3\backend\.venv\Scripts\modal.exe volume put awaazify-rvc-models C:\path\model.pth models/nabeel-private-v1/model.pth
..\awaazify-phase3\backend\.venv\Scripts\modal.exe volume put awaazify-rvc-models C:\path\model.index models/nabeel-private-v1/model.index
```

Modal's CLI accepts `modal volume put VOLUME_NAME LOCAL_PATH [REMOTE_PATH]`; remote parent directories are created when required. See the [official Modal Volume CLI reference](https://modal.com/docs/cli/latest/volume).

6. Move the request to `model validation`, then choose **Validate & publish** and enter the exact slug.
7. Awaazify calls the authenticated T4 probe. Only a compatible model is atomically published, with `private` visibility and owner-scoped access.

## Acceptance check

- Other users cannot see the request, dataset, consent proof or published private voice.
- An arbitrary/unpublished model slug cannot be submitted to generation.
- A ready private voice appears in its owner's catalog and can use the existing conversion worker.
- Public/commercial publication is intentionally not available in V1.

## Consent boundary

Do not train children, non-consenting people, deceptive impersonation models, or datasets obtained without permission. An `authorized_voice` request requires documented consent; an admin should still verify that the evidence is credible before training.
