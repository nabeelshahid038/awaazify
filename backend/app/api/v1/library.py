"""Authenticated song library and approved voice catalog."""

from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.jobs import service_headers
from app.api.v1.me import current_user
from app.core.config import settings

router = APIRouter(tags=["library"])

VOICE_FIELDS = "slug,display_name,description,language,category,image_url,demo_url_1,demo_url_2,consent_status,visibility,is_active,sort_order"


class VoiceModelInput(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    language: str | None = Field(default=None, max_length=80)
    category: str = Field(default="Featured", min_length=1, max_length=40)
    image_url: str | None = Field(default=None, max_length=500)
    demo_url_1: str | None = Field(default=None, max_length=500)
    demo_url_2: str | None = Field(default=None, max_length=500)
    consent_status: Literal["development_only", "licensed", "owner_verified"]
    visibility: Literal["public", "private"] = "public"
    is_active: bool = False
    sort_order: int = Field(default=100, ge=0, le=10000)


def is_admin(identity: dict) -> bool:
    email = (identity["user"].get("email") or "").lower()
    return bool(settings.admin_email and email == settings.admin_email.lower())


def require_admin(identity: dict) -> None:
    if not is_admin(identity):
        raise HTTPException(403, "Admin access required")


@router.get("/public/voices")
async def public_voices() -> list[dict]:
    """Only publish active, public and consent-approved voices."""
    async with httpx.AsyncClient(timeout=12) as client:
        result = await client.get(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/voice_models",
            headers=service_headers(),
            params={
                "is_active": "eq.true", "visibility": "eq.public",
                "consent_status": "in.(licensed,owner_verified)",
                "select": VOICE_FIELDS, "order": "sort_order.asc,display_name.asc",
            },
        )
    if result.status_code != 200:
        raise HTTPException(503, "Unable to load voice catalog")
    return result.json()


@router.get("/voices")
async def list_voices(identity: Annotated[dict, Depends(current_user)]) -> list[dict]:
    base = settings.supabase_url.rstrip("/")
    async with httpx.AsyncClient(timeout=12) as client:
        result = await client.get(
            f"{base}/rest/v1/voice_models",
            headers=service_headers(),
            params={
                "is_active": "eq.true",
                "or": f"(visibility.eq.public,owner_user_id.eq.{identity['user']['id']})",
                "select": VOICE_FIELDS,
                "order": "sort_order.asc,display_name.asc",
            },
        )
    if result.status_code != 200:
        raise HTTPException(503, "Unable to load voice catalog")
    rows = result.json()
    return [row for row in rows if row.get("consent_status") != "development_only"]


@router.get("/admin/voices")
async def admin_voices(identity: Annotated[dict, Depends(current_user)]) -> list[dict]:
    require_admin(identity)
    async with httpx.AsyncClient(timeout=12) as client:
        result = await client.get(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/voice_models",
            headers=service_headers(),
            params={"select": VOICE_FIELDS, "order": "sort_order.asc,display_name.asc"},
        )
    if result.status_code != 200:
        raise HTTPException(503, "Unable to load admin voice catalog")
    return result.json()


@router.post("/admin/voices/{slug}")
async def save_voice(slug: str, request: VoiceModelInput, identity: Annotated[dict, Depends(current_user)]) -> dict:
    require_admin(identity)
    if not slug or len(slug) > 64 or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in slug):
        raise HTTPException(422, "Slug may contain lowercase letters, numbers and hyphens only")
    if request.is_active and request.consent_status == "development_only":
        raise HTTPException(422, "A development-only voice cannot be published")
    payload = {"slug": slug, **request.model_dump()}
    async with httpx.AsyncClient(timeout=15) as client:
        if request.is_active:
            if not settings.worker_model_probe_url or not settings.worker_shared_secret:
                raise HTTPException(503, "Voice model validation worker is not configured")
            try:
                probe = await client.post(
                    settings.worker_model_probe_url,
                    headers={"Authorization": f"Bearer {settings.worker_shared_secret}"},
                    json={"model_slug": slug},
                    timeout=300,
                )
            except httpx.RequestError:
                raise HTTPException(503, "Voice model validation worker is unavailable") from None
            if probe.status_code != 200 or not probe.json().get("ok"):
                detail = probe.json().get("detail", "Worker model files failed validation")
                raise HTTPException(422, detail)
        result = await client.post(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/voice_models",
            headers={**service_headers(), "Prefer": "resolution=merge-duplicates,return=representation"},
            json=payload,
        )
    if result.status_code not in {200, 201}:
        raise HTTPException(503, "Unable to save voice model")
    return result.json()[0]


@router.get("/library/songs")
async def list_songs(identity: Annotated[dict, Depends(current_user)]) -> list[dict]:
    base = settings.supabase_url.rstrip("/")
    user_id = identity["user"]["id"]
    async with httpx.AsyncClient(timeout=20) as client:
        jobs_result = await client.get(
            f"{base}/rest/v1/generation_jobs",
            headers=service_headers(),
            params={
                "user_id": f"eq.{user_id}",
                "status": "in.(completed,failed)",
                "select": "id,project_id,status,progress,model_slug,error_message,created_at,completed_at",
                "order": "created_at.desc", "limit": "100",
            },
        )
        projects_result = await client.get(
            f"{base}/rest/v1/studio_projects",
            headers=service_headers(),
            params={
                "user_id": f"eq.{user_id}",
                "select": "id,title,source_type,trim_start_seconds,trim_end_seconds",
                "limit": "100",
            },
        )
    if jobs_result.status_code != 200 or projects_result.status_code != 200:
        raise HTTPException(503, "Unable to load song library")
    projects = {item["id"]: item for item in projects_result.json()}
    songs = []
    for job in jobs_result.json():
        project = projects.get(job["project_id"], {})
        songs.append({
            **job,
            "title": project.get("title") or "Untitled song",
            "source_type": project.get("source_type"),
            "duration_seconds": (
                float(project["trim_end_seconds"]) - float(project["trim_start_seconds"])
                if project.get("trim_end_seconds") is not None else None
            ),
        })
    return songs
