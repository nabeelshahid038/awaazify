# Phase 16 — Production QA

No new database migration or secret is required. Deploy backend and frontend, then run the automated smoke test and follow `PRODUCTION_QA_RUNBOOK.md`.

```powershell
cd C:\Users\Lenovo\Downloads\awaazify-phase16-production-qa\backend
..\..\awaazify-phase3\backend\.venv\Scripts\modal.exe deploy modal_app.py

Copy-Item C:\Users\Lenovo\Downloads\awaazify-phase15-support-antiabuse\frontend\.env.production C:\Users\Lenovo\Downloads\awaazify-phase16-production-qa\frontend\.env.production
cd C:\Users\Lenovo\Downloads\awaazify-phase16-production-qa\frontend
npm.cmd install
npm.cmd run build
npx.cmd wrangler pages deploy dist --project-name awaazify --branch production

cd C:\Users\Lenovo\Downloads\awaazify-phase16-production-qa
py .\scripts\production_smoke.py
```

