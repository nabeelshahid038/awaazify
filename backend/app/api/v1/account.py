"""Self-service deletion controls for songs and accounts."""
from typing import Annotated
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.jobs import service_headers
from app.api.v1.me import current_user
from app.core.config import settings

router = APIRouter(tags=["account"])


async def delete_object(client: httpx.AsyncClient, bucket: str, path: str | None) -> None:
    if not path:
        return
    await client.delete(
        f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{quote(path, safe='/')}",
        headers=service_headers(),
    )


@router.delete("/library/songs/{job_id}")
async def delete_song(job_id: str, identity: Annotated[dict, Depends(current_user)]) -> dict:
    base = settings.supabase_url.rstrip("/")
    user_id = identity["user"]["id"]
    async with httpx.AsyncClient(timeout=25) as client:
        result = await client.get(
            f"{base}/rest/v1/generation_jobs",
            headers=service_headers(),
            params={
                "id": f"eq.{job_id}", "user_id": f"eq.{user_id}",
                "status": "in.(completed,failed)",
                "select": "id,project_id,vocals_storage_path,instrumental_storage_path,converted_vocals_storage_path,normalized_storage_path,final_wav_storage_path,final_mp3_storage_path,studio_projects(storage_path)",
            },
        )
        if result.status_code != 200 or not result.json():
            raise HTTPException(404, "Song not found or still processing")
        row = result.json()[0]
        project = row.get("studio_projects") or {}
        await delete_object(client, "source-audio", project.get("storage_path"))
        for field in ("vocals_storage_path", "instrumental_storage_path", "converted_vocals_storage_path", "normalized_storage_path", "final_wav_storage_path", "final_mp3_storage_path"):
            await delete_object(client, "job-artifacts", row.get(field))
        rpc = await client.post(
            f"{base}/rest/v1/rpc/delete_own_song",
            headers={**service_headers(), "Authorization": f"Bearer {identity['token']}"},
            json={"p_user_id": user_id, "p_job_id": job_id},
        )
    if rpc.status_code >= 300:
        raise HTTPException(409, "Song files were removed but its record could not be deleted")
    return {"deleted": True, "job_id": job_id}


