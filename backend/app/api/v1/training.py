"""Consent-gated manual custom voice training workflow."""

from typing import Annotated, Literal
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.api.v1.jobs import service_headers
from app.api.v1.me import current_user
from app.api.v1.payments import require_admin
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit

router = APIRouter(tags=["voice-training"])


def rest() -> str:
    return f"{settings.supabase_url.rstrip('/')}/rest/v1"


class TrainingRequestInput(BaseModel):
    voice_name: str = Field(min_length=2, max_length=80)
    language: str = Field(min_length=2, max_length=80)
    rights_basis: Literal["self_voice", "authorized_voice"]
    consent_confirmed: bool
    dataset_path: str = Field(min_length=10, max_length=500)
    consent_proof_path: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_consent(self):
        if not self.consent_confirmed:
            raise ValueError("Explicit voice-owner consent confirmation is required")
        if self.rights_basis == "authorized_voice" and not self.consent_proof_path:
            raise ValueError("Documented consent proof is required for another person's voice")
        return self


class TrainingStatusInput(BaseModel):
    status: Literal["approved", "training", "model_validation", "rejected", "ready"]
    note: str | None = Field(default=None, max_length=500)
    model_slug: str | None = Field(default=None, pattern=r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


async def object_info(client: httpx.AsyncClient, bucket: str, path: str) -> dict | None:
    result = await client.get(
        f"{settings.supabase_url.rstrip('/')}/storage/v1/object/info/{bucket}/{quote(path, safe='/')}",
        headers=service_headers(),
    )
    return result.json() if result.status_code == 200 else None


def storage_metadata(info: dict) -> tuple[int, str]:
    metadata = info.get("metadata") if isinstance(info.get("metadata"), dict) else {}
    raw_size = metadata.get("size", info.get("size", 0))
    raw_type = metadata.get("mimetype") or metadata.get("contentType") or info.get("mimetype") or ""
    try:
        size = int(raw_size)
    except (TypeError, ValueError):
        size = 0
    return size, str(raw_type).lower().split(";", 1)[0]


@router.get("/voice-training")
async def list_training(identity: Annotated[dict, Depends(current_user)]) -> dict:
    user_id = identity["user"]["id"]
    async with httpx.AsyncClient(timeout=15) as client:
        result = await client.get(f"{rest()}/voice_training_requests", headers=service_headers(), params={
            "user_id": f"eq.{user_id}",
            "select": "id,voice_name,language,rights_basis,status,model_slug,admin_note,dataset_size_bytes,dataset_mime_type,created_at,updated_at",
            "order": "created_at.desc", "limit": "25",
        })
        events = await client.get(f"{rest()}/voice_training_events", headers=service_headers(), params={
            "user_id": f"eq.{user_id}", "select": "id,request_id,status,message,created_at",
            "order": "created_at.asc", "limit": "200",
        })
        wallet = await client.get(f"{rest()}/wallets", headers=service_headers(), params={
            "user_id": f"eq.{user_id}", "select": "training_credits", "limit": "1",
        })
    if result.status_code != 200 or wallet.status_code != 200 or events.status_code != 200:
        raise HTTPException(503, "Training requests unavailable; verify the Phase 7 migration")
    email = (identity["user"].get("email") or "").lower()
    wallet_rows = wallet.json()
    return {"requests": result.json(), "events": events.json(), "training_credits": wallet_rows[0]["training_credits"] if wallet_rows else 0,
            "training_price_pkr": settings.training_credit_price_pkr,
            "is_admin": bool(settings.admin_email and email == settings.admin_email.lower())}


@router.post("/voice-training", status_code=201)
async def create_training(request: TrainingRequestInput, identity: Annotated[dict, Depends(current_user)]) -> dict:
    user_id = identity["user"]["id"]
    await enforce_rate_limit(user_id, "training_submit", 2, 86400)
    if not request.dataset_path.startswith(f"{user_id}/"):
        raise HTTPException(422, "Invalid dataset path")
    if request.consent_proof_path and not request.consent_proof_path.startswith(f"{user_id}/"):
        raise HTTPException(422, "Invalid consent proof path")
    async with httpx.AsyncClient(timeout=20) as client:
        dataset_info = await object_info(client, "voice-training-data", request.dataset_path)
        if not dataset_info:
            raise HTTPException(422, "Upload a valid training dataset first")
        dataset_size, dataset_type = storage_metadata(dataset_info)
        allowed_dataset_types = {"application/zip", "audio/mpeg", "audio/wav", "audio/x-wav", "audio/flac"}
        if dataset_size < 1024 or dataset_size > 262_144_000 or dataset_type not in allowed_dataset_types:
            raise HTTPException(422, "Training dataset type or size is invalid")
        consent_size, consent_type = 0, ""
        if request.consent_proof_path:
            consent_info = await object_info(client, "voice-consent-proofs", request.consent_proof_path)
            if not consent_info:
                raise HTTPException(422, "Upload a valid consent proof first")
            consent_size, consent_type = storage_metadata(consent_info)
            allowed_consent_types = {"image/jpeg", "image/png", "image/webp", "application/pdf", "audio/mpeg", "audio/wav", "video/mp4"}
            if consent_size < 256 or consent_size > 10_485_760 or consent_type not in allowed_consent_types:
                raise HTTPException(422, "Consent proof type or size is invalid")
        pending = await client.get(f"{rest()}/voice_training_requests", headers=service_headers(), params={
            "user_id": f"eq.{user_id}", "status": "in.(submitted,approved,training,model_validation)", "select": "id", "limit": "3",
        })
        if pending.status_code != 200:
            raise HTTPException(503, "Unable to validate request limits")
        if len(pending.json()) >= 2:
            raise HTTPException(429, "You can have at most two active training requests")
        reserved = await client.post(f"{rest()}/rpc/reserve_training_credit", headers=service_headers(), json={"p_user_id": user_id})
        if reserved.status_code not in {200, 204}:
            raise HTTPException(402, "One voice training credit is required")
        payload = {
            **request.model_dump(), "user_id": user_id, "credit_reserved": True,
            "dataset_size_bytes": dataset_size, "dataset_mime_type": dataset_type,
            "consent_size_bytes": consent_size or None, "consent_mime_type": consent_type or None,
        }
        created = await client.post(f"{rest()}/voice_training_requests", headers={**service_headers(), "Prefer": "return=representation"}, json=payload)
    if created.status_code not in {200, 201}:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(f"{rest()}/rpc/refund_training_credit", headers=service_headers(), json={"p_user_id": user_id})
        raise HTTPException(503, "Unable to submit voice training request")
    created_row = created.json()[0]
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(f"{rest()}/voice_training_events", headers=service_headers(), json={
            "request_id": created_row["id"], "user_id": user_id, "status": "submitted",
            "message": "Training request submitted; dataset and consent review pending.",
        })
    return created_row


@router.get("/admin/voice-training")
async def admin_training(identity: Annotated[dict, Depends(current_user)]) -> list[dict]:
    require_admin(identity)
    async with httpx.AsyncClient(timeout=15) as client:
        result = await client.get(f"{rest()}/voice_training_requests", headers=service_headers(), params={
            "select": "id,user_id,voice_name,language,rights_basis,dataset_path,consent_proof_path,status,model_slug,admin_note,dataset_size_bytes,dataset_mime_type,created_at,updated_at",
            "order": "created_at.asc", "limit": "100",
        })
    if result.status_code != 200:
        raise HTTPException(503, "Unable to load training queue")
    return result.json()


@router.get("/admin/voice-training/{request_id}/asset/{kind}")
async def training_asset(request_id: str, kind: Literal["dataset", "consent"], identity: Annotated[dict, Depends(current_user)]) -> dict:
    require_admin(identity)
    field = "dataset_path" if kind == "dataset" else "consent_proof_path"
    bucket = "voice-training-data" if kind == "dataset" else "voice-consent-proofs"
    async with httpx.AsyncClient(timeout=15) as client:
        row = await client.get(f"{rest()}/voice_training_requests", headers=service_headers(), params={"id": f"eq.{request_id}", "select": field, "limit": "1"})
        if row.status_code != 200 or not row.json() or not row.json()[0].get(field):
            raise HTTPException(404, "Training asset not found")
        path = row.json()[0][field]
        signed = await client.post(f"{settings.supabase_url.rstrip('/')}/storage/v1/object/sign/{bucket}/{quote(path, safe='/')}", headers=service_headers(), json={"expiresIn": 600})
    if signed.status_code != 200 or not signed.json().get("signedURL"):
        raise HTTPException(503, "Unable to authorize training asset")
    return {"url": f"{settings.supabase_url.rstrip('/')}/storage/v1{signed.json()['signedURL']}"}


@router.post("/admin/voice-training/{request_id}/status")
async def update_training(request_id: str, request: TrainingStatusInput, identity: Annotated[dict, Depends(current_user)]) -> dict:
    require_admin(identity)
    if request.status == "rejected" and not (request.note or "").strip():
        raise HTTPException(422, "A rejection reason is required")
    if request.status == "ready":
        if not request.model_slug or not settings.worker_model_probe_url:
            raise HTTPException(503, "Model slug and worker model probe are required for publishing")
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                probe = await client.post(settings.worker_model_probe_url, headers={"Authorization": f"Bearer {settings.worker_shared_secret}"}, json={"model_slug": request.model_slug})
                if probe.status_code != 200 or not probe.json().get("ok"):
                    raise HTTPException(422, "The trained model failed compatibility validation")
                published = await client.post(f"{rest()}/rpc/publish_private_voice", headers=service_headers(), json={
                    "p_request_id": request_id, "p_admin_id": identity["user"]["id"], "p_model_slug": request.model_slug, "p_note": request.note,
                })
        except httpx.RequestError:
            raise HTTPException(503, "Model validation worker is unavailable") from None
        if published.status_code not in {200, 204}:
            raise HTTPException(409, "Training request could not be published")
        return {"id": request_id, "status": "ready", "probe": probe.json()}
    async with httpx.AsyncClient(timeout=15) as client:
        result = await client.post(f"{rest()}/rpc/transition_training_request", headers=service_headers(), json={
            "p_request_id": request_id, "p_admin_id": identity["user"]["id"],
            "p_status": request.status, "p_note": request.note,
        })
    if result.status_code not in {200, 201, 204}:
        detail = result.text.lower()
        if "not found" in detail:
            raise HTTPException(404, "Training request not found")
        if "transition" in detail:
            raise HTTPException(409, "Invalid training status transition")
        raise HTTPException(503, "Unable to update training request")
    return result.json()
