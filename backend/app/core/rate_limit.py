"""Persistent rate limits shared by every API instance."""

import httpx
from fastapi import HTTPException

from app.core.config import settings


async def enforce_rate_limit(subject: str, action: str, limit: int, window_seconds: int) -> None:
    if not settings.supabase_secret_key:
        raise HTTPException(503, "Server database credential is not configured")
    headers = {
        "apikey": settings.supabase_secret_key,
        "Authorization": f"Bearer {settings.supabase_secret_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            result = await client.post(
                f"{settings.supabase_url.rstrip('/')}/rest/v1/rpc/consume_api_rate_limit",
                headers=headers,
                json={"p_subject": subject, "p_action": action, "p_limit": limit, "p_window_seconds": window_seconds},
            )
    except httpx.RequestError:
        raise HTTPException(503, "Rate-limit service unavailable") from None
    if result.status_code != 200 or not result.json():
        raise HTTPException(503, "Rate-limit service unavailable; verify the Phase 8 migration")
    decision = result.json()[0]
    if not decision["allowed"]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    f"{settings.supabase_url.rstrip('/')}/rest/v1/security_events",
                    headers=headers,
                    json={
                        "user_id": subject, "event_type": "rate_limit_exceeded", "severity": "warning",
                        "details": {"action": action, "window_seconds": window_seconds},
                    },
                )
        except httpx.RequestError:
            pass
        raise HTTPException(429, "Too many requests; try again after the current limit window")
