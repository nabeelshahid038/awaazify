"""Admin-only operational metrics for launch monitoring."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.jobs import service_headers
from app.api.v1.me import current_user
from app.api.v1.payments import require_admin
from app.core.config import settings

router = APIRouter(tags=["operations"])


@router.get("/admin/diagnostics")
async def diagnostics(identity: Annotated[dict, Depends(current_user)]) -> dict:
    """Read-only launch diagnostics; never returns secret values."""
    require_admin(identity)
    checks: dict[str, dict] = {
        "database": {"ok": False, "detail": "Not checked"},
        "private_storage": {"ok": False, "detail": "Not checked"},
        "worker_configuration": {
            "ok": all((settings.worker_prepare_url, settings.worker_convert_url, settings.worker_mix_url, settings.worker_shared_secret)),
            "detail": "All generation workers configured" if all((settings.worker_prepare_url, settings.worker_convert_url, settings.worker_mix_url, settings.worker_shared_secret)) else "One or more worker settings are missing",
        },
        "production_origin": {
            "ok": settings.environment != "production" or settings.frontend_origin.startswith("https://"),
            "detail": settings.frontend_origin,
        },
    }
    async with httpx.AsyncClient(timeout=10) as client:
        database = await client.get(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/profiles",
            headers=service_headers(), params={"select": "id", "limit": "1"},
        )
        checks["database"] = {"ok": database.status_code == 200, "detail": f"HTTP {database.status_code}"}
        storage = await client.get(
            f"{settings.supabase_url.rstrip('/')}/storage/v1/bucket/job-artifacts",
            headers=service_headers(),
        )
        storage_private = storage.status_code == 200 and not bool(storage.json().get("public", True))
        checks["private_storage"] = {
            "ok": storage_private,
            "detail": "Private job-artifacts bucket" if storage.status_code == 200 else f"HTTP {storage.status_code}",
        }
    return {"status": "pass" if all(item["ok"] for item in checks.values()) else "attention", "checks": checks}


async def exact_count(client: httpx.AsyncClient, table: str, **filters: str) -> int:
    result = await client.get(
        f"{settings.supabase_url.rstrip('/')}/rest/v1/{table}",
        headers={**service_headers(), "Prefer": "count=exact", "Range": "0-0"},
        params={"select": "id", **filters},
    )
    if result.status_code not in {200, 206}:
        raise HTTPException(503, f"Operational count unavailable for {table}")
    content_range = result.headers.get("content-range", "0-0/0")
    try:
        return int(content_range.rsplit("/", 1)[1])
    except (ValueError, IndexError):
        return len(result.json())


@router.get("/admin/ops")
async def operations(identity: Annotated[dict, Depends(current_user)]) -> dict:
    require_admin(identity)
    since = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
    async with httpx.AsyncClient(timeout=20) as client:
        completed = await exact_count(client, "generation_jobs", status="eq.completed")
        failed_24h = await exact_count(client, "generation_jobs", status="eq.failed", created_at=f"gte.{since}")
        active = await exact_count(client, "generation_jobs", status="in.(queued,preparing,prepared,separating,converting,converted,mixing)")
        pending_payments = await exact_count(client, "payment_requests", status="eq.pending")
        active_training = await exact_count(client, "voice_training_requests", status="in.(submitted,approved,training,model_validation)")
        security_24h = await exact_count(client, "security_events", severity="in.(warning,critical)", created_at=f"gte.{since}")
        recent = await client.get(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/generation_jobs", headers=service_headers(),
            params={"status": "eq.failed", "select": "id,error_code,error_message,created_at", "order": "created_at.desc", "limit": "5"},
        )
    return {
        "environment": settings.environment,
        "jobs": {"completed_total": completed, "active": active, "failed_24h": failed_24h},
        "queues": {"pending_payments": pending_payments, "active_training": active_training},
        "security_events_24h": security_24h,
        "estimated_gpu_cost_usd_total": round(completed * settings.estimated_gpu_cost_usd_per_song, 2),
        "estimated_gpu_cost_usd_per_song": settings.estimated_gpu_cost_usd_per_song,
        "recent_failures": recent.json() if recent.status_code == 200 else [],
        "generated_at": datetime.now(UTC).isoformat(),
    }
