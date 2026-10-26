import httpx
from fastapi import APIRouter, HTTPException

from app.core.config import settings

router = APIRouter(tags=["health"])

@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "awaazify-api", "version": "0.11.0"}


@router.get("/health/ready")
async def readiness() -> dict:
    required = {
        "supabase_url": settings.supabase_url, "supabase_publishable_key": settings.supabase_publishable_key,
        "supabase_secret_key": settings.supabase_secret_key, "worker_prepare_url": settings.worker_prepare_url,
        "worker_convert_url": settings.worker_convert_url, "worker_mix_url": settings.worker_mix_url,
        "worker_shared_secret": settings.worker_shared_secret,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise HTTPException(503, detail={"status": "not_ready", "missing": missing})
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            result = await client.get(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/settings",
                headers={"apikey": settings.supabase_publishable_key},
            )
    except httpx.RequestError:
        raise HTTPException(503, "Supabase readiness check failed") from None
    if result.status_code != 200:
        raise HTTPException(503, "Supabase readiness check failed")
    return {"status": "ready", "environment": settings.environment, "database": "reachable", "workers": "configured"}
