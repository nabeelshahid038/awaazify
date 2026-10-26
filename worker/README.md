# Awaazify Modal worker

This worker keeps the Phase 4A zero-GPU security probe and adds one authenticated T4 endpoint that validates the active Applio/RVC `.pth` and `.index` pair from the private `awaazify-rvc-models` Volume.

```powershell
cd worker
..\backend\.venv\Scripts\modal.exe deploy modal_worker.py
```

The deployment exposes authenticated probes plus preparation and voice-conversion dispatchers. Every web endpoint must return HTTP 401 without the bearer secret. Do not share endpoint URLs or secrets.

The model probe uses `torch.load(..., weights_only=True)` and never enables arbitrary checkpoint code execution. It checks checkpoint metadata, FAISS dimensions and CUDA availability but does not generate audio.

Phase 4D pins Applio 3.6.5 and Demucs 4.0.1 in the GPU image. It separates the normalized song with `htdemucs`, converts only the isolated vocals with RMVPE + ContentVec + the private FAISS index, and uploads all stems to the private Supabase bucket. The first deployment builds a large image and can take several minutes.
