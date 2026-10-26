"""Authenticated profile endpoint. Supabase validates the bearer token; DB reads use user RLS."""
from fastapi import APIRouter, Depends, Header, HTTPException
import httpx
from app.core.config import settings

router = APIRouter(tags=["account"])

async def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise HTTPException(503, "Authentication is not configured")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "Authentication required")
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            result = await client.get(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
                headers={"apikey": settings.supabase_publishable_key,
                         "Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError:
            raise HTTPException(503, "Identity service temporarily unavailable") from None
    if result.status_code != 200:
        raise HTTPException(401, "Invalid or expired session")
    user = result.json()
    if not user.get("id"):
        raise HTTPException(401, "Invalid session")
    return {"user": user, "token": token}

@router.get("/me")
async def get_me(identity: dict = Depends(current_user)) -> dict:
    user = identity["user"]
    headers = {"apikey": settings.supabase_publishable_key,
               "Authorization": f"Bearer {identity['token']}"}
    base = f"{settings.supabase_url.rstrip('/')}/rest/v1"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            p = await client.get(f"{base}/profiles", headers=headers,
                                 params={"id": f"eq.{user['id']}", "select": "id,display_name,avatar_url,created_at"})
            t = await client.get(f"{base}/trial_entitlements", headers=headers,
                                 params={"user_id": f"eq.{user['id']}", "select": "free_song_credits"})
            w = await client.get(f"{base}/wallets", headers=headers,
                                 params={"user_id": f"eq.{user['id']}", "select": "song_credits,bonus_song_credits"})
        except httpx.RequestError:
            raise HTTPException(503, "Database temporarily unavailable") from None
    if p.status_code != 200 or t.status_code != 200 or w.status_code != 200:
        raise HTTPException(503, "Account data unavailable; check migrations and RLS")
    profiles, trials, wallets = p.json(), t.json(), w.json()
    if not profiles or not trials:
        raise HTTPException(409, "Account setup incomplete; contact support")
    return {"id": user["id"], "email": user.get("email"),
            "display_name": profiles[0].get("display_name") or user.get("email", "User").split("@")[0],
            "avatar_url": profiles[0].get("avatar_url"),
            "created_at": profiles[0]["created_at"],
            "free_song_credits": trials[0]["free_song_credits"],
            "bonus_song_credits": wallets[0]["bonus_song_credits"] if wallets else 0,
            "song_credits": wallets[0]["song_credits"] if wallets else 0,
            "is_admin": bool(settings.admin_email and (user.get("email") or "").lower() == settings.admin_email.lower())}
