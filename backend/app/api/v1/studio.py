"""Phase 3 studio endpoints: safe YouTube metadata and owned project drafts."""
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.api.v1.me import current_user
from app.core.config import settings

router = APIRouter(prefix="/studio", tags=["studio"])


def youtube_video_id(value: str) -> str | None:
    """Return a canonical YouTube video id from supported public URL forms."""
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower().removeprefix("www.")
    video_id: str | None = None
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif parsed.path.startswith(("/shorts/", "/embed/", "/live/")):
            parts = parsed.path.strip("/").split("/")
            video_id = parts[1] if len(parts) > 1 else None
    if video_id and len(video_id) == 11 and all(c.isalnum() or c in "-_" for c in video_id):
        return video_id
    return None


class YoutubeRequest(BaseModel):
    url: str = Field(min_length=10, max_length=500)


class ProjectRequest(BaseModel):
    source_type: str
    title: str = Field(min_length=1, max_length=160)
    rights_confirmed: bool
    trim_start_seconds: float = Field(ge=0, le=360)
    trim_end_seconds: float = Field(gt=0, le=360)
    youtube_url: str | None = Field(default=None, max_length=500)
    youtube_video_id: str | None = Field(default=None, min_length=11, max_length=11)
    youtube_title: str | None = Field(default=None, max_length=300)
    youtube_thumbnail_url: str | None = Field(default=None, max_length=1000)
    storage_path: str | None = Field(default=None, max_length=1000)
    original_filename: str | None = Field(default=None, max_length=255)
    mime_type: str | None = Field(default=None, max_length=100)
    size_bytes: int | None = Field(default=None, ge=1, le=104_857_600)
    source_duration_seconds: float | None = Field(default=None, gt=0, le=360)

    @model_validator(mode="after")
    def validate_source(self):
        if not self.rights_confirmed:
            raise ValueError("You must confirm that you have permission to use this audio")
        if self.trim_end_seconds <= self.trim_start_seconds:
            raise ValueError("Trim end must be after trim start")
        if self.trim_end_seconds - self.trim_start_seconds > 360:
            raise ValueError("Selected audio cannot exceed six minutes")
        if self.source_type == "youtube":
            if not self.youtube_url or youtube_video_id(self.youtube_url) != self.youtube_video_id:
                raise ValueError("Valid YouTube metadata is required")
        elif self.source_type == "upload":
            if not self.storage_path or not self.original_filename or not self.mime_type:
                raise ValueError("Uploaded audio details are required")
        else:
            raise ValueError("Unsupported source type")
        return self


def user_headers(token: str) -> dict[str, str]:
    return {
        "apikey": settings.supabase_publishable_key,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


@router.post("/youtube/metadata")
async def youtube_metadata(request: YoutubeRequest, _identity: dict = Depends(current_user)) -> dict:
    video_id = youtube_video_id(request.url)
    if not video_id:
        raise HTTPException(422, "Enter a valid YouTube video URL")
    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            result = await client.get(
                "https://www.youtube.com/oembed",
                params={"url": canonical_url, "format": "json"},
            )
    except httpx.RequestError:
        raise HTTPException(503, "YouTube metadata service is temporarily unavailable") from None
    if result.status_code != 200:
        raise HTTPException(404, "This YouTube video is unavailable or private")
    data = result.json()
    return {
        "video_id": video_id,
        "canonical_url": canonical_url,
        "title": data.get("title") or "YouTube audio",
        "author_name": data.get("author_name"),
        "thumbnail_url": data.get("thumbnail_url"),
    }


@router.post("/projects", status_code=201)
async def create_project(request: ProjectRequest, identity: dict = Depends(current_user)) -> dict:
    payload = request.model_dump()
    payload["user_id"] = identity["user"]["id"]
    base = f"{settings.supabase_url.rstrip('/')}/rest/v1/studio_projects"
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            result = await client.post(
                base,
                headers={**user_headers(identity["token"]), "Prefer": "return=representation"},
                json=payload,
            )
    except httpx.RequestError:
        raise HTTPException(503, "Database temporarily unavailable") from None
    if result.status_code not in {200, 201}:
        raise HTTPException(503, "Unable to save studio project; verify the Phase 3 migration")
    rows = result.json()
    if not rows:
        raise HTTPException(503, "Project was not returned after saving")
    return rows[0]


@router.get("/projects")
async def list_projects(identity: dict = Depends(current_user)) -> list[dict]:
    base = f"{settings.supabase_url.rstrip('/')}/rest/v1/studio_projects"
    params = {
        "select": "id,title,source_type,status,trim_start_seconds,trim_end_seconds,created_at",
        "order": "created_at.desc",
        "limit": "20",
    }
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            result = await client.get(base, headers=user_headers(identity["token"]), params=params)
    except httpx.RequestError:
        raise HTTPException(503, "Database temporarily unavailable") from None
    if result.status_code != 200:
        raise HTTPException(503, "Unable to load studio projects")
    return result.json()
