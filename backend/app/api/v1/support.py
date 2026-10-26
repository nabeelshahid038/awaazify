"""Authenticated support tickets and admin review."""
from datetime import UTC, datetime
from hashlib import sha256
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.jobs import service_headers
from app.api.v1.me import current_user
from app.api.v1.payments import require_admin
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit

router = APIRouter(tags=["support"])

Category = Literal["song", "payment", "voice_training", "account", "copyright", "other"]
Status = Literal["open", "in_review", "resolved", "closed"]


class SupportInput(BaseModel):
    category: Category
    subject: str = Field(min_length=5, max_length=120)
    message: str = Field(min_length=10, max_length=2000)


class SupportReview(BaseModel):
    status: Status
    note: str | None = Field(default=None, max_length=1000)


class ContactInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    subject: str = Field(min_length=5, max_length=120)
    message: str = Field(min_length=10, max_length=2000)


@router.post("/contact", status_code=201)
async def create_contact(request: ContactInput) -> dict:
    email = request.email.strip().lower()
    fingerprint = sha256(f"contact:{email}".encode()).hexdigest()
    await enforce_rate_limit(fingerprint, "public_contact", 3, 3600)
    payload = {"name": request.name.strip(), "email": email, "subject": request.subject.strip(), "message": request.message.strip()}
    async with httpx.AsyncClient(timeout=12) as client:
        result = await client.post(f"{settings.supabase_url.rstrip('/')}/rest/v1/contact_messages", headers={**service_headers(), "Prefer": "return=representation"}, json=payload)
    if result.status_code not in {200, 201}:
        raise HTTPException(503, "Unable to send your message")
    return {"id": result.json()[0]["id"], "status": "received"}


@router.get("/admin/contact")
async def admin_contact(identity: Annotated[dict, Depends(current_user)]) -> list[dict]:
    require_admin(identity)
    async with httpx.AsyncClient(timeout=12) as client:
        result = await client.get(f"{settings.supabase_url.rstrip('/')}/rest/v1/contact_messages", headers=service_headers(), params={"status": "in.(open)", "select": "id,name,email,subject,message,status,admin_note,created_at", "order": "created_at.asc", "limit": "100"})
    if result.status_code != 200:
        raise HTTPException(503, "Unable to load contact inbox")
    return result.json()


@router.post("/admin/contact/{message_id}/resolve")
async def resolve_contact(message_id: str, review: SupportReview, identity: Annotated[dict, Depends(current_user)]) -> dict:
    require_admin(identity)
    status = "resolved" if review.status == "resolved" else "closed"
    async with httpx.AsyncClient(timeout=12) as client:
        result = await client.patch(f"{settings.supabase_url.rstrip('/')}/rest/v1/contact_messages", headers={**service_headers(), "Prefer": "return=representation"}, params={"id": f"eq.{message_id}"}, json={"status": status, "admin_note": review.note, "updated_at": datetime.now(UTC).isoformat()})
    if result.status_code != 200 or not result.json():
        raise HTTPException(404, "Contact message not found")
    return result.json()[0]


@router.get("/support/requests")
async def my_requests(identity: Annotated[dict, Depends(current_user)]) -> list[dict]:
    async with httpx.AsyncClient(timeout=12) as client:
        result = await client.get(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/support_requests",
            headers=service_headers(), params={"user_id": f"eq.{identity['user']['id']}", "select": "id,category,subject,message,status,admin_note,created_at,updated_at", "order": "created_at.desc", "limit": "25"},
        )
    if result.status_code != 200:
        raise HTTPException(503, "Unable to load support requests")
    return result.json()


@router.post("/support/requests", status_code=201)
async def create_request(request: SupportInput, identity: Annotated[dict, Depends(current_user)]) -> dict:
    await enforce_rate_limit(identity["user"]["id"], "support", 5, 3600)
    payload = {"user_id": identity["user"]["id"], "category": request.category, "subject": request.subject.strip(), "message": request.message.strip()}
    async with httpx.AsyncClient(timeout=12) as client:
        result = await client.post(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/support_requests",
            headers={**service_headers(), "Prefer": "return=representation"}, json=payload,
        )
    if result.status_code not in {200, 201}:
        raise HTTPException(503, "Unable to submit support request")
    return result.json()[0]


@router.get("/admin/support/requests")
async def admin_requests(identity: Annotated[dict, Depends(current_user)]) -> list[dict]:
    require_admin(identity)
    async with httpx.AsyncClient(timeout=12) as client:
        result = await client.get(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/support_requests",
            headers=service_headers(), params={"select": "id,user_id,category,subject,message,status,admin_note,created_at,updated_at,profiles(display_name)", "status": "in.(open,in_review)", "order": "created_at.asc", "limit": "100"},
        )
    if result.status_code != 200:
        raise HTTPException(503, "Unable to load support queue")
    return result.json()


@router.post("/admin/support/requests/{request_id}/review")
async def review_request(request_id: str, review: SupportReview, identity: Annotated[dict, Depends(current_user)]) -> dict:
    require_admin(identity)
    async with httpx.AsyncClient(timeout=12) as client:
        result = await client.patch(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/support_requests",
            headers={**service_headers(), "Prefer": "return=representation"},
            params={"id": f"eq.{request_id}"},
            json={"status": review.status, "admin_note": review.note, "updated_at": datetime.now(UTC).isoformat()},
        )
    if result.status_code != 200 or not result.json():
        raise HTTPException(404, "Support request not found")
    return result.json()[0]

