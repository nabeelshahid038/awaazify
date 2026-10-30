# Awaazify

**Awaazify** is an AI-powered, credit-based SaaS platform for creating song covers with selectable and custom-trained voice models.

Users upload an audio file, choose an available voice, start a private cloud-processing job, preview the result, and download the completed cover as an MP3. The product is currently in beta; YouTube import is displayed as **Coming Soon** while audio upload remains the stable production flow.

**Live demo:** https://awaazify.pages.dev  
**Developed by:** Nabeel Shahid

## Main features

- Google authentication through Supabase Auth
- One free song credit for a new eligible user
- Credit wallet, bonus credits, and manual payment verification
- Responsive audio-upload studio with a six-minute limit
- Public and private AI voice catalogue with demo audio
- Demucs vocal separation and Applio/RVC voice conversion
- Three true Applio/RVC conversions per generation: Default (0), Deep (-3), and High (+3) pitch
- Balanced final mix with instrumental at 80% and converted vocal at 100%
- Private cloud job processing with progress and retry states
- Permanent private song library with preview and MP3 download
- One-credit generation with saved preferred version and access to all three variants
- Custom voice-training request and admin review workflow
- Admin tools for payments, credits, voices, training, support, and diagnostics
- Rate limiting, Row Level Security, private storage, and automatic credit refunds on processing failures

## Technology stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, Supabase JS |
| API | FastAPI, Pydantic, HTTPX |
| Database/Auth/Storage | Supabase PostgreSQL, Auth, Storage, RLS |
| AI processing | Modal, NVIDIA T4, Applio/RVC, RMVPE, ContentVec |
| Audio pipeline | FFmpeg, Demucs |
| Hosting | Cloudflare Pages and Modal |
| CI | GitHub Actions |

## Repository structure

```text
awaazify/
├── frontend/          React web application
├── backend/           FastAPI application and tests
├── worker/            Modal GPU/audio worker
├── supabase/          Ordered SQL migrations
├── training/          Dataset inspection utilities
├── scripts/           Production smoke test and RLS audit
└── docs/              Architecture, setup, QA, and operations notes
```

## Local setup

### Requirements

- Node.js 22+
- Python 3.11+
- A Supabase project
- Modal account and GPU access for real voice conversion
- Authorized RVC `.pth` and `.index` model files

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/awaazify.git
cd awaazify
```

### 2. Configure and run the backend

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

Linux/macOS:

```bash
source .venv/bin/activate
cp .env.example .env
pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8000
```

Fill the placeholders in `backend/.env`. Never expose `SUPABASE_SECRET_KEY` or `WORKER_SHARED_SECRET` in the frontend.

### 3. Configure and run the frontend

```bash
cd ../frontend
cp .env.example .env.local
npm install
npm run dev
```

On Windows PowerShell, use `Copy-Item .env.example .env.local` instead of `cp`.

### 4. Configure Supabase

Apply the SQL files in `supabase/migrations/` in filename order. Configure Google authentication, production redirect URLs, and the private storage buckets described in the setup documents.

### 5. Configure the worker

The GPU worker is in `worker/modal_worker.py`. It expects the Modal secret `awaazify-v1-production`, the private model volume `awaazify-rvc-models`, and the server-side environment variables shown in `backend/.env.example`.

```bash
modal deploy worker/modal_worker.py
```

The backend can run without GPU generation for UI/API development, but complete song generation requires the deployed worker and compatible voice-model files.

## Verification

Backend tests:

```bash
cd backend
pytest -q
```

Worker contract tests:

```bash
PYTHONPATH=worker pytest -q worker/tests
```

Frontend production build:

```bash
cd frontend
npm ci
npm run build
```

GitHub Actions runs these checks automatically on pushes and pull requests.

## Security and privacy

- Secrets and production `.env` files are intentionally excluded from Git.
- Generated files and source audio are stored in private buckets.
- Signed URLs are short-lived and ownership checked.
- Database access is protected through Supabase Row Level Security.
- Users must have the necessary rights or permission for uploaded audio and voice models.
- Do not commit trained model checkpoints, indexes, payment proofs, datasets, or user-generated audio.

## Product status

Awaazify is a working SaaS MVP/beta. The core audio-upload-to-cover workflow is operational. Voice quality, model coverage, automated payments, monitoring, and additional import options remain areas for continued development.

## License

No open-source licence has been granted yet. All rights are reserved by the project owner unless a licence is added later.
