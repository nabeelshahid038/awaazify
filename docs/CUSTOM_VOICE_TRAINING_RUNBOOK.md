# Awaazify V1 custom voice training runbook

V1 uses trusted manual Colab training. Never train a child, a public figure without documented permission, or a voice whose owner cannot give informed consent.

## 1. Review

Open **Admin → Voice requests**. Download the dataset and consent evidence. Confirm the voice owner is an adult, the request purpose is legitimate, and an authorized-voice request includes credible permission. Reject unclear requests; the reserved training credit is refunded atomically.

## 2. Inspect the dataset

Upload `training/inspect_dataset.py` and the private dataset into a trusted Colab runtime. Install FFmpeg, then run:

```bash
!apt-get -qq update && apt-get -qq install -y ffmpeg
!python inspect_dataset.py /content/dataset.zip --output /content/awaazify-training-audio
```

The helper blocks unsafe ZIP paths and symlinks, ignores non-audio files, probes valid audio, and reports total duration. Three minutes is the hard review floor; 10–30 minutes of clean, dry vocals is recommended. Manually listen for clipping, music, effects, multiple speakers, long silence, and personally sensitive material before training.

## 3. Train

After approval, move the request to **training**. Use the trusted Applio/RVC Colab workflow with the inspected audio. Keep the model private. Export exactly one `.pth` checkpoint and one `.index` file.

## 4. Install the private model

Choose a unique lowercase slug, for example `user-name-v1`. From PowerShell:

```powershell
..awaazify-phase3ackend.venvScriptsmodal.exe volume put awaazify-rvc-models C:\path\model.pth models/user-name-v1/model.pth
..awaazify-phase3ackend.venvScriptsmodal.exe volume put awaazify-rvc-models C:\path\model.index models/user-name-v1/model.index
```

The folder must contain exactly one `.pth` and one `.index` file.

## 5. Validate and publish

In Admin:

1. Move **training → model validation**.
2. Click **Validate & publish**.
3. Enter the exact Modal folder slug.

The authenticated Modal probe loads the checkpoint with `weights_only=True`, validates the FAISS index and verifies GPU compatibility. Only after it passes does the database publish the model as a private voice owned by the requesting user.

## 6. Acceptance check

- The owner sees the voice in **Voices** after refresh.
- Another user cannot see or select it.
- A test conversion completes successfully.
- The request timeline shows `ready`.
- Rejection refunds exactly one training credit; successful publication does not refund it.
