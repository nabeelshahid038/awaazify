"""Server-only generation reservation and authenticated worker dispatch."""

from typing import Annotated
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.me import current_user
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/jobs", tags=["jobs"])


class CreateJobRequest(BaseModel):
    project_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    model_slug: str = Field(default="my-voice-model", pattern=r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


async def owned_job(client: httpx.AsyncClient, job_id: str, user_id: str, fields: str) -> dict:
    result = await client.get(
        f"{settings.supabase_url.rstrip('/')}/rest/v1/generation_jobs",
        headers=service_headers(),
        params={"id": f"eq.{job_id}", "user_id": f"eq.{user_id}", "select": fields, "limit": "1"},
    )
    if result.status_code != 200 or not result.json():
        raise HTTPException(404, "Generation job not found")
    return result.json()[0]


def service_headers() -> dict[str, str]:
    if not settings.supabase_secret_key:
        raise HTTPException(503, "Server database credential is not configured")
    return {
        "apikey": settings.supabase_secret_key,
        "Authorization": f"Bearer {settings.supabase_secret_key}",
        "Content-Type": "application/json",
    }


async def refund_failed_dispatch(client: httpx.AsyncClient, job_id: str, message: str) -> None:
    await client.post(
        f"{settings.supabase_url.rstrip('/')}/rest/v1/rpc/fail_generation_job_and_refund",
        headers=service_headers(),
        json={"p_job_id": job_id, "p_error_code": "dispatch_failed", "p_error_message": message},
    )


@router.post("", status_code=202)
async def create_job(
    request: CreateJobRequest,
    identity: Annotated[dict, Depends(current_user)],
) -> dict:
    if not settings.worker_prepare_url or not settings.worker_shared_secret:
        raise HTTPException(503, "Audio worker is not configured")

    base = settings.supabase_url.rstrip("/")
    user_id = identity["user"]["id"]
    await enforce_rate_limit(user_id, "generation_create", 5, 3600)
    async with httpx.AsyncClient(timeout=60) as client:
        voice_result = await client.get(
            f"{base}/rest/v1/voice_models",
            headers=service_headers(),
            params={
                "slug": f"eq.{request.model_slug}", "is_active": "eq.true",
                "or": f"(visibility.eq.public,owner_user_id.eq.{user_id})",
                "consent_status": "in.(licensed,owner_verified)", "select": "slug", "limit": "1",
            },
        )
        if voice_result.status_code != 200 or not voice_result.json():
            raise HTTPException(403, "This voice model is unavailable for your account")
        project_result = await client.get(
            f"{base}/rest/v1/studio_projects",
            headers=service_headers(),
            params={
                "id": f"eq.{request.project_id}", "user_id": f"eq.{user_id}",
                "select": "id,source_type,storage_path,youtube_url,trim_start_seconds,trim_end_seconds,status",
                "limit": "1",
            },
        )
        if project_result.status_code != 200 or not project_result.json():
            raise HTTPException(404, "Studio project not found")
        project = project_result.json()[0]
        if project["status"] != "ready":
            raise HTTPException(409, "Project already has a generation job")

        reserve = await client.post(
            f"{base}/rest/v1/rpc/reserve_generation_job",
            headers=service_headers(),
            json={"p_user_id": user_id, "p_project_id": request.project_id, "p_model_slug": request.model_slug},
        )
        if reserve.status_code not in {200, 201}:
            detail = reserve.text.lower()
            if "credit" in detail:
                raise HTTPException(402, "No song credit available")
            raise HTTPException(409, "Unable to reserve this generation job")
        job_id = reserve.json()

        try:
            if project["source_type"] == "upload":
                storage_path = project.get("storage_path") or ""
                signed = await client.post(
                    f"{base}/storage/v1/object/sign/source-audio/{quote(storage_path, safe='/')}",
                    headers=service_headers(), json={"expiresIn": 900},
                )
                if signed.status_code != 200 or not signed.json().get("signedURL"):
                    raise RuntimeError("Unable to authorize private source audio")
                source_url = f"{base}/storage/v1{signed.json()['signedURL']}"
            else:
                source_url = project.get("youtube_url") or ""

            dispatched = await client.post(
                settings.worker_prepare_url,
                headers={"Authorization": f"Bearer {settings.worker_shared_secret}"},
                json={
                    "job_id": job_id, "user_id": user_id, "source_type": project["source_type"],
                    "source_url": source_url, "trim_start_seconds": float(project["trim_start_seconds"]),
                    "trim_end_seconds": float(project["trim_end_seconds"]), "model_slug": request.model_slug,
                },
            )
            if dispatched.status_code not in {200, 202}:
                raise RuntimeError("Worker rejected the preparation job")
        except (httpx.RequestError, RuntimeError) as exc:
            await refund_failed_dispatch(client, job_id, str(exc))
            raise HTTPException(503, "Worker dispatch failed; your credit was restored") from None

    return {"job_id": job_id, "status": "queued", "progress": 0}


@router.post("/{job_id}/retry", status_code=202)
async def retry_job(
    job_id: str,
    identity: Annotated[dict, Depends(current_user)],
) -> dict:
    """Atomically reopen a failed job at the earliest reusable stage."""
    if not all((settings.worker_prepare_url, settings.worker_convert_url, settings.worker_shared_secret)):
        raise HTTPException(503, "Audio workers are not configured")
    base = settings.supabase_url.rstrip("/")
    user_id = identity["user"]["id"]
    await enforce_rate_limit(user_id, "generation_retry", 3, 3600)
    async with httpx.AsyncClient(timeout=60) as client:
        job = await owned_job(
            client,
            job_id,
            user_id,
            "id,status,project_id,model_slug,normalized_storage_path",
        )
        if job["status"] != "failed":
            raise HTTPException(409, "Only a failed job can be retried")

        project_result = await client.get(
            f"{base}/rest/v1/studio_projects",
            headers=service_headers(),
            params={
                "id": f"eq.{job['project_id']}", "user_id": f"eq.{user_id}",
                "select": "id,source_type,storage_path,youtube_url,trim_start_seconds,trim_end_seconds",
                "limit": "1",
            },
        )
        if project_result.status_code != 200 or not project_result.json():
            raise HTTPException(404, "Studio project not found")
        project = project_result.json()[0]

        if job.get("normalized_storage_path"):
            reopened = await client.post(
                f"{base}/rest/v1/rpc/retry_failed_conversion",
                headers=service_headers(),
                json={"p_job_id": job_id, "p_user_id": user_id},
            )
            if reopened.status_code not in {200, 201, 204}:
                detail = reopened.text.lower()
                if "credit" in detail:
                    raise HTTPException(402, "No song credit available")
                if "retry limit" in detail:
                    raise HTTPException(409, "This job has reached its retry limit")
                raise HTTPException(409, "This job is no longer ready to retry")
            next_status, next_progress = "prepared", 20
            dispatch_url = settings.worker_convert_url
            dispatch_payload = {
                "job_id": job_id,
                "user_id": user_id,
                "normalized_storage_path": job["normalized_storage_path"],
                "model_slug": job["model_slug"],
                "pitch": 0,
                "index_rate": 0.5,
                "protect": 0.33,
            }
        else:
            reopened = await client.post(
                f"{base}/rest/v1/rpc/retry_failed_preparation",
                headers=service_headers(),
                json={"p_job_id": job_id, "p_user_id": user_id},
            )
            if reopened.status_code not in {200, 201, 204}:
                detail = reopened.text.lower()
                if "credit" in detail:
                    raise HTTPException(402, "No song credit available")
                if "retry limit" in detail:
                    raise HTTPException(409, "This job has reached its retry limit")
                raise HTTPException(409, "This job is no longer ready to retry")
            next_status, next_progress = "queued", 0
            if project["source_type"] == "upload":
                storage_path = project.get("storage_path") or ""
                signed = await client.post(
                    f"{base}/storage/v1/object/sign/source-audio/{quote(storage_path, safe='/')}",
                    headers=service_headers(),
                    json={"expiresIn": 900},
                )
                if signed.status_code != 200 or not signed.json().get("signedURL"):
                    if reopened.status_code in {200, 201, 204}:
                        await refund_failed_dispatch(client, job_id, "Unable to authorize private source audio")
                    raise HTTPException(503, "Source audio is temporarily unavailable; credit restored")
                source_url = f"{base}/storage/v1{signed.json()['signedURL']}"
            else:
                source_url = project.get("youtube_url") or ""
            dispatch_url = settings.worker_prepare_url
            dispatch_payload = {
                "job_id": job_id,
                "user_id": user_id,
                "source_type": project["source_type"],
                "source_url": source_url,
                "trim_start_seconds": float(project["trim_start_seconds"]),
                "trim_end_seconds": float(project["trim_end_seconds"]),
                "model_slug": job["model_slug"],
            }

        try:
            dispatched = await client.post(
                dispatch_url,
                headers={"Authorization": f"Bearer {settings.worker_shared_secret}"},
                json=dispatch_payload,
            )
            if dispatched.status_code not in {200, 202}:
                raise RuntimeError("Worker rejected the retry")
        except (httpx.RequestError, RuntimeError):
            await refund_failed_dispatch(client, job_id, "Retry dispatch failed")
            raise HTTPException(503, "Retry dispatch failed; your credit was restored") from None

    return {"job_id": job_id, "status": next_status, "progress": next_progress, "accepted": True}


@router.post("/{job_id}/convert", status_code=202)
async def continue_conversion(
    job_id: str,
    identity: Annotated[dict, Depends(current_user)],
) -> dict:
    """Resume a Phase 4C job that reached prepared before Phase 4D was deployed."""
    if not settings.worker_convert_url or not settings.worker_shared_secret:
        raise HTTPException(503, "Voice conversion worker is not configured")
    base = settings.supabase_url.rstrip("/")
    user_id = identity["user"]["id"]
    async with httpx.AsyncClient(timeout=60) as client:
        result = await client.get(
            f"{base}/rest/v1/generation_jobs",
            headers=service_headers(),
            params={
                "id": f"eq.{job_id}",
                "user_id": f"eq.{user_id}",
                "select": "id,status,normalized_storage_path,model_slug",
                "limit": "1",
            },
        )
        if result.status_code != 200 or not result.json():
            raise HTTPException(404, "Generation job not found")
        job = result.json()[0]
        if job["status"] not in {"prepared", "failed"} or not job.get("normalized_storage_path"):
            raise HTTPException(409, "This job is not ready for voice conversion")
        if job["status"] == "failed":
            reopened = await client.post(
                f"{base}/rest/v1/rpc/retry_failed_conversion",
                headers=service_headers(),
                json={"p_job_id": job_id, "p_user_id": user_id},
            )
            if reopened.status_code not in {200, 204}:
                if "credit" in reopened.text.lower():
                    raise HTTPException(402, "No song credit available")
                raise HTTPException(409, "Unable to reopen this failed conversion")
        try:
            dispatched = await client.post(
                settings.worker_convert_url,
                headers={"Authorization": f"Bearer {settings.worker_shared_secret}"},
                json={
                    "job_id": job_id,
                    "user_id": user_id,
                    "normalized_storage_path": job["normalized_storage_path"],
                    "model_slug": job["model_slug"],
                    "pitch": 0,
                    "index_rate": 0.5,
                    "protect": 0.33,
                },
            )
        except httpx.RequestError:
            await refund_failed_dispatch(client, job_id, "Voice conversion dispatch failed")
            raise HTTPException(503, "Voice conversion worker is temporarily unavailable") from None
        if dispatched.status_code not in {200, 202}:
            await refund_failed_dispatch(client, job_id, "Voice conversion worker rejected the job")
            raise HTTPException(503, "Voice conversion worker rejected the job")
    return {"job_id": job_id, "status": "prepared", "progress": 20, "accepted": True}


@router.get("")
async def list_jobs(identity: Annotated[dict, Depends(current_user)]) -> list[dict]:
    base = f"{settings.supabase_url.rstrip('/')}/rest/v1/generation_jobs"
    params = {
        "user_id": f"eq.{identity['user']['id']}",
        "select": "id,project_id,status,progress,error_message,created_at,updated_at",
        "order": "created_at.desc", "limit": "20",
    }
    async with httpx.AsyncClient(timeout=12) as client:
        result = await client.get(base, headers=service_headers(), params=params)
    if result.status_code != 200:
        raise HTTPException(503, "Unable to load generation jobs")
    return result.json()


@router.post("/{job_id}/mix", status_code=202)
async def continue_final_mix(
    job_id: str,
    identity: Annotated[dict, Depends(current_user)],
) -> dict:
    if not settings.worker_mix_url or not settings.worker_shared_secret:
        raise HTTPException(503, "Final mixing worker is not configured")
    user_id = identity["user"]["id"]
    async with httpx.AsyncClient(timeout=60) as client:
        job = await owned_job(
            client, job_id, user_id,
            "id,status,instrumental_storage_path,converted_vocals_storage_path",
        )
        if job["status"] != "converted":
            raise HTTPException(409, "This job is not ready for final mixing")
        try:
            dispatched = await client.post(
                settings.worker_mix_url,
                headers={"Authorization": f"Bearer {settings.worker_shared_secret}"},
                json={
                    "job_id": job_id, "user_id": user_id,
                    "instrumental_storage_path": job["instrumental_storage_path"],
                    "converted_vocals_storage_path": job["converted_vocals_storage_path"],
                },
            )
        except httpx.RequestError:
            raise HTTPException(503, "Final mixing worker is temporarily unavailable") from None
        if dispatched.status_code not in {200, 202}:
            raise HTTPException(503, "Final mixing worker rejected the job")
    return {"job_id": job_id, "status": "converted", "progress": 75, "accepted": True}


@router.get("/{job_id}/artifacts")
async def final_artifacts(
    job_id: str,
    identity: Annotated[dict, Depends(current_user)],
) -> dict:
    user_id = identity["user"]["id"]
    base = settings.supabase_url.rstrip("/")
    async with httpx.AsyncClient(timeout=30) as client:
        job = await owned_job(
            client, job_id, user_id,
            "id,status,final_wav_storage_path,final_mp3_storage_path",
        )
        if job["status"] != "completed":
            raise HTTPException(409, "Final song is not ready")
        output = {}
        for label, field in (("wav_url", "final_wav_storage_path"), ("mp3_url", "final_mp3_storage_path")):
            path = job.get(field)
            if not path:
                raise HTTPException(500, "Final artifact is missing")
            signed = await client.post(
                f"{base}/storage/v1/object/sign/job-artifacts/{quote(path, safe='/')}",
                headers=service_headers(), json={"expiresIn": 900},
            )
            if signed.status_code != 200 or not signed.json().get("signedURL"):
                raise HTTPException(503, "Unable to authorize final song")
            output[label] = f"{base}/storage/v1{signed.json()['signedURL']}"
    return output
