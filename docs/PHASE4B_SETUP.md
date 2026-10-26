# Phase 4B — GPU/model compatibility gate

Prerequisites:

- Modal Secret: `awaazify-v1-production`
- Modal Volume: `awaazify-rvc-models`
- Exactly one `.pth` and one `.index` in `models/my-voice-model/`

## Deploy

From the project root in PowerShell:

```powershell
..\awaazify-phase3\backend\.venv\Scripts\modal.exe deploy .\worker\modal_worker.py
```

Copy the displayed `probe-voice-model` URL into the current PowerShell session only:

```powershell
$modelProbeUrl = "PASTE_PROBE_VOICE_MODEL_URL_HERE"
$headers = @{ Authorization = "Bearer $workerSecret" }
$body = @{ model_slug = "my-voice-model" } | ConvertTo-Json

Invoke-RestMethod `
  -Uri $modelProbeUrl `
  -Method Post `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

Success requires `ok: True`, `cuda_available: True`, positive checkpoint/index sizes, and positive FAISS dimensions. A GPU cold start can make the first request take several minutes.

Do not paste the bearer secret into source files, screenshots, chat, or Supabase client-visible settings.
