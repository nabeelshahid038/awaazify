"""Manual payment proof workflow with server-side pricing and admin review."""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.jobs import service_headers
from app.api.v1.me import current_user
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit

router = APIRouter(tags=["wallet"])


def base() -> str:
    return f"{settings.supabase_url.rstrip('/')}/rest/v1"


def require_admin(identity: dict) -> dict:
    email = (identity["user"].get("email") or "").lower()
    if not settings.admin_email or email != settings.admin_email.lower():
        raise HTTPException(403, "Admin access required")
    return identity


class PaymentRequestInput(BaseModel):
    method: Literal["easypaisa", "jazzcash"]
    product_type: Literal["song", "voice_training"] = "song"
    amount_pkr: int = Field(ge=50, le=100000)
    sender_name: str = Field(min_length=2, max_length=100)
    sender_phone: str = Field(pattern=r"^03[0-9]{9}$")
    transaction_reference: str = Field(min_length=4, max_length=100)
    proof_path: str = Field(min_length=10, max_length=500)


class ReviewInput(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=500)


class BonusGrantInput(BaseModel):
    user_email: str = Field(min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    amount: int = Field(ge=1, le=100)
    reason: str = Field(default="Giveaway bonus", min_length=2, max_length=120)


@router.get("/wallet")
async def wallet(identity: Annotated[dict, Depends(current_user)]) -> dict:
    user_id = identity["user"]["id"]
    headers = service_headers()
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(f"{base()}/wallets", headers={**headers, "Prefer": "resolution=ignore-duplicates"}, json={"user_id": user_id})
        wallet_result = await client.get(f"{base()}/wallets", headers=headers, params={"user_id": f"eq.{user_id}", "select": "song_credits,training_credits", "limit": "1"})
        requests = await client.get(f"{base()}/payment_requests", headers=headers, params={"user_id": f"eq.{user_id}", "select": "id,method,product_type,amount_pkr,requested_credits,transaction_reference,status,admin_note,created_at,reviewed_at", "order": "created_at.desc", "limit": "25"})
        ledger = await client.get(f"{base()}/wallet_ledger", headers=headers, params={"user_id": f"eq.{user_id}", "select": "id,credit_type,delta,balance_after,reason,created_at", "order": "created_at.desc", "limit": "50"})
    if wallet_result.status_code != 200 or requests.status_code != 200 or ledger.status_code != 200:
        raise HTTPException(503, "Wallet data unavailable; verify the Phase 6 migration")
    rows = wallet_result.json()
    return {
        "song_credits": rows[0]["song_credits"] if rows else 0,
        "training_credits": rows[0]["training_credits"] if rows else 0,
        "pricing": {
            "song": {"pkr": 50, "usd": settings.song_credit_price_usd, "packs": [{"credits": 1, "pkr": 50}, {"credits": 5, "pkr": 225}, {"credits": 10, "pkr": 400}]},
            "voice_training": {"pkr": settings.training_credit_price_pkr, "usd": settings.training_credit_price_usd, "packs": [{"credits": 1, "pkr": 150}]},
        },
        "payment_accounts": {
            # Stable internal keys preserve existing payment records and DB constraints.
            "easypaisa": {"title": settings.hbl_account_title or "HBL", "number": settings.hbl_account_number},
            "jazzcash": {"title": settings.nayapay_account_title or "NayaPay", "number": settings.nayapay_account_number or settings.jazzcash_account_number},
        },
        "requests": requests.json(), "ledger": ledger.json(),
        "is_admin": bool(settings.admin_email and (identity["user"].get("email") or "").lower() == settings.admin_email.lower()),
    }


@router.post("/wallet/payment-requests", status_code=201)
async def submit_payment(request: PaymentRequestInput, identity: Annotated[dict, Depends(current_user)]) -> dict:
    user_id = identity["user"]["id"]
    await enforce_rate_limit(user_id, "payment_submit", 3, 3600)
    if not request.proof_path.startswith(f"{user_id}/"):
        raise HTTPException(422, "Invalid payment proof path")
    packs = {"song": {50: 1, 225: 5, 400: 10}, "voice_training": {150: 1}}
    requested_credits = packs[request.product_type].get(request.amount_pkr)
    if not requested_credits:
        raise HTTPException(422, "Choose one of the available credit packs")
    headers = service_headers()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    async with httpx.AsyncClient(timeout=15) as client:
        proof = await client.get(
            f"{settings.supabase_url.rstrip('/')}/storage/v1/object/info/payment-proofs/{quote(request.proof_path, safe='/')}",
            headers=headers,
        )
        recent = await client.get(f"{base()}/payment_requests", headers={**headers, "Prefer": "count=exact"}, params={"user_id": f"eq.{user_id}", "created_at": f"gte.{cutoff}", "select": "id", "limit": "4"})
        if proof.status_code != 200:
            raise HTTPException(422, "Upload a valid payment proof first")
        if len(recent.json()) >= 3:
            raise HTTPException(429, "Too many payment requests; try again later")
        payload = {**request.model_dump(), "transaction_reference": request.transaction_reference.strip().upper(), "user_id": user_id, "requested_credits": requested_credits}
        created = await client.post(f"{base()}/payment_requests", headers={**headers, "Prefer": "return=representation"}, json=payload)
    if created.status_code == 409:
        raise HTTPException(409, "This transaction reference was already submitted")
    if created.status_code not in {200, 201}:
        raise HTTPException(503, "Unable to submit payment request")
    return created.json()[0]


@router.get("/admin/payment-requests")
async def admin_payments(identity: Annotated[dict, Depends(current_user)]) -> list[dict]:
    require_admin(identity)
    async with httpx.AsyncClient(timeout=15) as client:
        result = await client.get(f"{base()}/payment_requests", headers=service_headers(), params={"select": "id,user_id,method,product_type,amount_pkr,requested_credits,sender_name,sender_phone,transaction_reference,proof_path,status,admin_note,created_at", "order": "created_at.asc", "limit": "100"})
    if result.status_code != 200:
        raise HTTPException(503, "Unable to load payment requests")
    return result.json()


@router.get("/admin/payment-requests/{payment_id}/proof")
async def admin_proof(payment_id: str, identity: Annotated[dict, Depends(current_user)]) -> dict:
    require_admin(identity)
    async with httpx.AsyncClient(timeout=15) as client:
        row = await client.get(f"{base()}/payment_requests", headers=service_headers(), params={"id": f"eq.{payment_id}", "select": "proof_path", "limit": "1"})
        if row.status_code != 200 or not row.json():
            raise HTTPException(404, "Payment request not found")
        path = row.json()[0]["proof_path"]
        signed = await client.post(f"{settings.supabase_url.rstrip('/')}/storage/v1/object/sign/payment-proofs/{quote(path, safe='/')}", headers=service_headers(), json={"expiresIn": 300})
    if signed.status_code != 200 or not signed.json().get("signedURL"):
        raise HTTPException(503, "Unable to authorize payment proof")
    return {"url": f"{settings.supabase_url.rstrip('/')}/storage/v1{signed.json()['signedURL']}"}


@router.post("/admin/payment-requests/{payment_id}/review")
async def review_payment(payment_id: str, request: ReviewInput, identity: Annotated[dict, Depends(current_user)]) -> dict:
    require_admin(identity)
    if not request.approve and not (request.note or "").strip():
        raise HTTPException(422, "A rejection reason is required")
    async with httpx.AsyncClient(timeout=15) as client:
        result = await client.post(f"{base()}/rpc/review_payment_request", headers=service_headers(), json={"p_payment_id": payment_id, "p_admin_id": identity["user"]["id"], "p_approve": request.approve, "p_note": request.note})
    if result.status_code not in {200, 204}:
        if "already reviewed" in result.text.lower():
            raise HTTPException(409, "Payment request was already reviewed")
        raise HTTPException(503, "Unable to review payment request")
    return {"id": payment_id, "status": "approved" if request.approve else "rejected"}


@router.post("/admin/bonus-credits")
async def grant_bonus_credits(request: BonusGrantInput, identity: Annotated[dict, Depends(current_user)]) -> dict:
    require_admin(identity)
    async with httpx.AsyncClient(timeout=15) as client:
        result = await client.post(
            f"{base()}/rpc/grant_bonus_song_credits",
            headers=service_headers(),
            json={
                "p_admin_id": identity["user"]["id"],
                "p_user_email": request.user_email.strip().lower(),
                "p_amount": request.amount,
                "p_reason": request.reason.strip(),
            },
        )
    if result.status_code not in {200, 204}:
        if "user email not found" in result.text.lower():
            raise HTTPException(404, "No registered user found with this email")
        raise HTTPException(503, "Unable to grant bonus credits")
    return result.json()
