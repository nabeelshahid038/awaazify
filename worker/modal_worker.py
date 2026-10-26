"""Awaazify worker: preparation, stem separation, and RVC voice conversion."""
import base64
import hmac
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse

import modal
from fastapi import Header, HTTPException
from pydantic import BaseModel, Field

app = modal.App("awaazify-v1-worker")
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "fastapi>=0.115,<1",
    "pydantic>=2.9,<3",
    "torch==2.5.1",
    "faiss-cpu==1.9.0.post1",
)
media_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "curl", "unzip", "ca-certificates", "git")
    .run_commands(
        "curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh",
        "deno --version",
        "git clone --single-branch --branch 2.0.2 --depth 1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil-pot",
        "cd /opt/bgutil-pot/server && deno install --allow-scripts=npm:canvas --frozen",
    )
    .pip_install(
        "fastapi>=0.115,<1",
        "pydantic>=2.9,<3",
        "httpx>=0.27,<1",
        "yt-dlp[default]>=2026.1",
        "bgutil-ytdlp-pot-provider==2.0.2",
    )
)
rvc_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04", add_python="3.12"
    )
    .apt_install("ffmpeg", "git", "build-essential", "libsndfile1")
    .run_commands(
        "git clone --branch 3.6.5 --depth 1 https://github.com/IAHispano/Applio.git /opt/applio",
        "python -m pip install --upgrade pip",
        "python -m pip install -r /opt/applio/requirements.txt",
        "python -m pip install 'demucs==4.0.1' 'torchcodec>=0.8,<1' 'httpx>=0.27,<1' 'pydantic>=2.9,<3' 'fastapi>=0.115,<1'",
        "cd /opt/applio && python core.py prerequisites",
        "mkdir -p /root/.cache/torch/hub/checkpoints && python -c \"import urllib.request; urllib.request.urlretrieve('https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/955717e8-8726e21a.th', '/root/.cache/torch/hub/checkpoints/955717e8-8726e21a.th')\"",
        "python -c \"import demucs.separate, torchcodec\"",
    )
)
api_image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "fastapi>=0.115,<1", "pydantic>=2.9,<3"
)
secret = modal.Secret.from_name("awaazify-v1-production")
model_volume = modal.Volume.from_name("awaazify-rvc-models", create_if_missing=False)
MODEL_ROOT = Path("/models-volume")
MODEL_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


# Keep deployment-critical helpers in this file. Modal deploys this worker as a
# self-contained entrypoint, so importing an adjacent local module can make the
# remote container fail even though local tests pass.
def artifact_paths(user_id: str, job_id: str) -> dict[str, str]:
    root = f"{user_id}/{job_id}"
    return {
        "normalized": f"{root}/normalized.wav",
        "vocals": f"{root}/vocals.wav",
        "instrumental": f"{root}/instrumental.wav",
        "converted": f"{root}/converted-vocals.wav",
        "final_wav": f"{root}/final-mix.wav",
        "final_mp3": f"{root}/final-mix.mp3",
    }


def build_rvc_command(
    input_path: Path,
    output_path: Path,
    checkpoint_path: Path,
    index_path: Path,
    pitch: int,
    index_rate: float,
    protect: float,
) -> list[str]:
    return [
        "python", "/opt/applio/core.py", "infer",
        "--input-path", str(input_path),
        "--output-path", str(output_path),
        "--pth-path", str(checkpoint_path),
        "--index-path", str(index_path),
        "--pitch", str(pitch),
        "--f0-method", "rmvpe",
        "--index-rate", str(index_rate),
        "--volume-envelope", "0.75",
        "--protect", str(protect),
        "--embedder-model", "contentvec",
        "--export-format", "WAV",
        "--split-audio",
    ]


class ModelContractError(ValueError):
    """Raised when a voice model violates the runtime contract."""


def resolve_model_files(volume_root: Path, model_slug: str) -> tuple[Path, Path]:
    slug = model_slug.strip().lower()
    if not MODEL_SLUG.fullmatch(slug):
        raise ModelContractError("Invalid model slug")

    model_dir = volume_root / "models" / slug
    if not model_dir.is_dir():
        raise ModelContractError(f"Model directory not found: models/{slug}")

    checkpoints = sorted(model_dir.glob("*.pth"))
    indexes = sorted(model_dir.glob("*.index"))
    if len(checkpoints) != 1:
        raise ModelContractError(f"Expected exactly one .pth file; found {len(checkpoints)}")
    if len(indexes) != 1:
        raise ModelContractError(f"Expected exactly one .index file; found {len(indexes)}")
    return checkpoints[0], indexes[0]


def summarize_checkpoint(checkpoint: Any) -> dict[str, Any]:
    if not isinstance(checkpoint, dict):
        raise ModelContractError("Checkpoint root must be a dictionary")

    weights = checkpoint.get("weight")
    if weights is None:
        weights = checkpoint.get("model")
    if not isinstance(weights, dict) or not weights:
        raise ModelContractError("Checkpoint does not contain a non-empty weight/model dictionary")

    config = checkpoint.get("config")
    if config is not None and not isinstance(config, (list, tuple)):
        raise ModelContractError("Checkpoint config has an unexpected format")

    sample_rate = checkpoint.get("sr")
    if sample_rate is None and config:
        sample_rate = config[-1]

    return {
        "version": str(checkpoint.get("version") or "unknown"),
        "sample_rate": str(sample_rate or "unknown"),
        "f0": checkpoint.get("f0"),
        "weight_tensors": len(weights),
    }


class ProbeRequest(BaseModel):
    job_id: str = Field(min_length=36, max_length=36)


class ModelProbeRequest(BaseModel):
    model_slug: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


class PrepareAudioRequest(BaseModel):
    job_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    user_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    source_type: str = Field(pattern=r"^(upload|youtube)$")
    source_url: str = Field(min_length=10, max_length=4000)
    trim_start_seconds: float = Field(ge=0, le=360)
    trim_end_seconds: float = Field(gt=0, le=360)
    model_slug: str = Field(default="my-voice-model", pattern=r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


class ConvertVoiceRequest(BaseModel):
    job_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    user_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    normalized_storage_path: str = Field(min_length=10, max_length=1000)
    model_slug: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
    pitch: int = Field(default=0, ge=-24, le=24)
    index_rate: float = Field(default=0.5, ge=0, le=1)
    protect: float = Field(default=0.33, ge=0, le=0.5)


class MixFinalRequest(BaseModel):
    job_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    user_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    instrumental_storage_path: str = Field(min_length=10, max_length=1000)
    converted_vocals_storage_path: str = Field(min_length=10, max_length=1000)


def authorize(value: str | None) -> None:
    expected = os.environ.get("WORKER_SHARED_SECRET", "")
    supplied = (value or "").removeprefix("Bearer ").strip()
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(401, "Invalid worker credential")


def supabase_headers(content_type: str = "application/json") -> dict[str, str]:
    key = os.environ["SUPABASE_SECRET_KEY"]
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": content_type}


def validate_source_url(source_type: str, source_url: str) -> None:
    parsed = urlparse(source_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        raise ValueError("Source URL must use HTTPS")
    if source_type == "youtube":
        if host not in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}:
            raise ValueError("Unsupported YouTube host")
    else:
        expected = (urlparse(os.environ["SUPABASE_URL"]).hostname or "").lower()
        if host != expected:
            raise ValueError("Private source host does not match Supabase")


def update_job(job_id: str, user_id: str, status: str, progress: int, message: str, **fields: Any) -> None:
    import httpx

    base = os.environ["SUPABASE_URL"].rstrip("/")
    payload = {"status": status, "progress": progress, "updated_at": datetime.now(timezone.utc).isoformat(), **fields}
    with httpx.Client(timeout=20) as client:
        result = client.patch(
            f"{base}/rest/v1/generation_jobs",
            params={"id": f"eq.{job_id}", "user_id": f"eq.{user_id}"},
            headers=supabase_headers(), json=payload,
        )
        result.raise_for_status()
        event = client.post(
            f"{base}/rest/v1/job_events", headers=supabase_headers(),
            json={"job_id": job_id, "user_id": user_id, "stage": status, "progress": progress, "message": message[:500]},
        )
        event.raise_for_status()


def fail_and_refund(job_id: str, code: str, message: str) -> None:
    import httpx

    base = os.environ["SUPABASE_URL"].rstrip("/")
    with httpx.Client(timeout=20) as client:
        client.post(
            f"{base}/rest/v1/rpc/fail_generation_job_and_refund", headers=supabase_headers(),
            json={"p_job_id": job_id, "p_error_code": code[:80], "p_error_message": message[:500]},
        ).raise_for_status()


def claim_prepared_job(request: ConvertVoiceRequest) -> bool:
    """Atomically let only one GPU task advance a prepared job."""
    import httpx

    base = os.environ["SUPABASE_URL"].rstrip("/")
    with httpx.Client(timeout=20) as client:
        result = client.patch(
            f"{base}/rest/v1/generation_jobs",
            params={
                "id": f"eq.{request.job_id}",
                "user_id": f"eq.{request.user_id}",
                "status": "eq.prepared",
                "normalized_storage_path": f"eq.{request.normalized_storage_path}",
                "model_slug": f"eq.{request.model_slug}",
                "select": "id",
            },
            headers={**supabase_headers(), "Prefer": "return=representation"},
            json={
                "status": "separating",
                "progress": 25,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        result.raise_for_status()
        rows = result.json()
        if not rows:
            return False
        client.post(
            f"{base}/rest/v1/job_events",
            headers=supabase_headers(),
            json={
                "job_id": request.job_id,
                "user_id": request.user_id,
                "stage": "separating",
                "progress": 25,
                "message": "GPU worker claimed the prepared audio",
            },
        ).raise_for_status()
        return True


def download_artifact(storage_path: str, destination: Path) -> None:
    import httpx

    base = os.environ["SUPABASE_URL"].rstrip("/")
    with httpx.stream(
        "GET",
        f"{base}/storage/v1/object/authenticated/job-artifacts/{storage_path}",
        headers=supabase_headers("application/octet-stream"),
        timeout=180,
    ) as response:
        response.raise_for_status()
        total = 0
        with destination.open("wb") as output:
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > 1_000_000_000:
                    raise ValueError("Prepared artifact exceeds the worker limit")
                output.write(chunk)


def upload_artifact(storage_path: str, source: Path, content_type: str = "audio/wav") -> None:
    import httpx

    if not source.is_file() or source.stat().st_size < 44:
        raise ValueError(f"Missing or empty output artifact: {source.name}")
    base = os.environ["SUPABASE_URL"].rstrip("/")
    with source.open("rb") as audio:
        result = httpx.post(
            f"{base}/storage/v1/object/job-artifacts/{storage_path}",
            headers={**supabase_headers(content_type), "x-upsert": "false"},
            content=audio.read(),
            timeout=300,
        )
    result.raise_for_status()


def download_youtube_audio(source_url: str, temp_dir: Path) -> Path:
    """Download one YouTube source using PO-token support and safe fallbacks."""
    output_template = str(temp_dir / "source.%(ext)s")
    cookie_args: list[str] = []
    encoded_cookies = os.getenv("YOUTUBE_COOKIES_B64", "").strip()
    if encoded_cookies:
        try:
            cookie_data = base64.b64decode(encoded_cookies, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("The secure YouTube cookie secret is invalid") from exc
        cookie_header = cookie_data.lstrip(b"\xef\xbb\xbf")
        if not cookie_header.startswith((b"# Netscape HTTP Cookie File", b"# HTTP Cookie File")):
            raise ValueError("The YouTube cookie file must use Netscape cookies.txt format")
        cookie_path = temp_dir / "youtube-cookies.txt"
        cookie_path.write_bytes(cookie_data)
        cookie_path.chmod(0o600)
        cookie_args = ["--cookies", str(cookie_path)]

    base = [
        "yt-dlp",
        "--no-playlist",
        "--max-filesize", "110M",
        "--js-runtimes", "deno",
        "--retries", "3",
        "--fragment-retries", "3",
        "--retry-sleep", "exp=1:5",
        "--extractor-args", "youtubepot-bgutilscript:server_home=/opt/bgutil-pot/server",
        *cookie_args,
    ]
    output = [
        "-f", "bestaudio/best",
        "-o", output_template,
    ]
    attempts = [
        [*base, "--extractor-args", "youtube:player_client=mweb,web_safari", *output],
        [*base, *output],
        [*base, "--extractor-args", "youtube:player_client=web_safari", *output],
    ]
    diagnostics: list[str] = []
    for number, command in enumerate(attempts, start=1):
        for old_source in temp_dir.glob("source.*"):
            old_source.unlink(missing_ok=True)
        try:
            subprocess.run(
                [*command, source_url],
                check=True,
                timeout=300,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            stderr = getattr(exc, "stderr", "") or getattr(exc, "stdout", "") or str(exc)
            diagnostics.append(f"attempt {number}: {stderr[-8000:]}")
            continue
        matches = list(temp_dir.glob("source.*"))
        if len(matches) == 1 and matches[0].stat().st_size > 0:
            return matches[0]
        diagnostics.append(f"attempt {number}: downloader produced {len(matches)} source files")

    print("yt-dlp attempts failed:\n" + "\n".join(diagnostics), flush=True)
    raise ValueError("YouTube could not be downloaded. Please retry or use an audio upload.")


@app.function(image=media_image, secrets=[secret], timeout=900)
def prepare_audio(payload: dict[str, Any]) -> None:
    """Download an authorized source, enforce duration, normalize it, and store it privately."""
    import httpx

    request = PrepareAudioRequest.model_validate(payload)
    duration = request.trim_end_seconds - request.trim_start_seconds
    if duration <= 0 or duration > 360:
        fail_and_refund(request.job_id, "invalid_trim", "Selected range must be between 0 and 360 seconds")
        return

    try:
        validate_source_url(request.source_type, request.source_url)
        update_job(request.job_id, request.user_id, "preparing", 5, "Retrieving authorized source audio")
        with tempfile.TemporaryDirectory(prefix="awaazify-") as temp:
            temp_dir = Path(temp)
            if request.source_type == "upload":
                source = temp_dir / "source"
                with httpx.stream("GET", request.source_url, timeout=120, follow_redirects=False) as response:
                    response.raise_for_status()
                    total = 0
                    with source.open("wb") as output:
                        for chunk in response.iter_bytes():
                            total += len(chunk)
                            if total > 110 * 1024 * 1024:
                                raise ValueError("Source exceeds the upload limit")
                            output.write(chunk)
            else:
                source = download_youtube_audio(request.source_url, temp_dir)

            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(source)],
                check=True, timeout=30, capture_output=True, text=True,
            )
            source_duration = float(probe.stdout.strip())
            if source_duration <= 0 or request.trim_end_seconds > source_duration + 1:
                raise ValueError("Selected range exceeds the real source duration")

            normalized = temp_dir / "normalized.wav"
            subprocess.run(
                ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-ss", str(request.trim_start_seconds),
                 "-i", str(source), "-t", str(duration), "-vn", "-ac", "2", "-ar", "44100",
                 "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "pcm_s16le", str(normalized)],
                check=True, timeout=420, capture_output=True, text=True,
            )
            if not normalized.exists() or normalized.stat().st_size < 44:
                raise ValueError("FFmpeg did not produce normalized audio")

            artifact_path = f"{request.user_id}/{request.job_id}/normalized.wav"
            base = os.environ["SUPABASE_URL"].rstrip("/")
            with normalized.open("rb") as audio:
                uploaded = httpx.post(
                    f"{base}/storage/v1/object/job-artifacts/{artifact_path}",
                    headers={**supabase_headers("audio/wav"), "x-upsert": "false"},
                    content=audio.read(), timeout=180,
                )
            uploaded.raise_for_status()
            update_job(
                request.job_id, request.user_id, "prepared", 20, "Audio normalized and stored privately",
                normalized_storage_path=artifact_path,
            )
            convert_voice.spawn(
                ConvertVoiceRequest(
                    job_id=request.job_id,
                    user_id=request.user_id,
                    normalized_storage_path=artifact_path,
                    model_slug=request.model_slug,
                ).model_dump()
            )
    except Exception as exc:
        public_error = str(exc) if isinstance(exc, ValueError) else f"Audio preparation failed: {type(exc).__name__}"
        fail_and_refund(request.job_id, type(exc).__name__, public_error)
        raise


@app.function(
    image=rvc_image,
    secrets=[secret],
    volumes={str(MODEL_ROOT): model_volume},
    gpu="T4",
    cpu=4,
    memory=16384,
    timeout=1800,
    # The complete GPU pipeline runs in one invocation. A short warm window
    # avoids paying for two idle minutes after every low-traffic request.
    scaledown_window=15,
    max_containers=1,
)
def convert_voice(payload: dict[str, Any]) -> None:
    """Separate stems, convert the isolated vocal with RVC, and persist private artifacts."""
    request = ConvertVoiceRequest.model_validate(payload)
    paths = artifact_paths(request.user_id, request.job_id)
    if request.normalized_storage_path != paths["normalized"]:
        fail_and_refund(request.job_id, "invalid_artifact_path", "Prepared artifact path is invalid")
        return
    if not claim_prepared_job(request):
        return

    try:
        checkpoint_path, index_path = resolve_model_files(MODEL_ROOT, request.model_slug)
        with tempfile.TemporaryDirectory(prefix="awaazify-rvc-") as temp:
            temp_dir = Path(temp)
            normalized = temp_dir / "normalized.wav"
            download_artifact(request.normalized_storage_path, normalized)

            separation_root = temp_dir / "separated"
            subprocess.run(
                [
                    "python", "-m", "demucs.separate", "--two-stems=vocals",
                    "-n", "htdemucs", "--device", "cuda", "--shifts", "1",
                    "--overlap", "0.25", "--out", str(separation_root), str(normalized),
                ],
                check=True,
                timeout=900,
            )
            stem_dir = separation_root / "htdemucs" / normalized.stem
            vocals = stem_dir / "vocals.wav"
            instrumental = stem_dir / "no_vocals.wav"
            if not vocals.is_file() or not instrumental.is_file():
                raise ValueError("Stem separation did not produce the expected files")

            vocals_path = paths["vocals"]
            instrumental_path = paths["instrumental"]
            upload_artifact(vocals_path, vocals)
            upload_artifact(instrumental_path, instrumental)
            update_job(
                request.job_id,
                request.user_id,
                "converting",
                50,
                "Vocals isolated; RVC conversion started",
                vocals_storage_path=vocals_path,
                instrumental_storage_path=instrumental_path,
            )

            converted = temp_dir / "converted-vocals.wav"
            subprocess.run(
                build_rvc_command(
                    vocals, converted, checkpoint_path, index_path,
                    request.pitch, request.index_rate, request.protect,
                ),
                cwd="/opt/applio",
                check=True,
                timeout=900,
            )
            converted_path = paths["converted"]
            upload_artifact(converted_path, converted)
            update_job(
                request.job_id,
                request.user_id,
                "converted",
                75,
                "RVC voice conversion completed and stored privately",
                converted_vocals_storage_path=converted_path,
                conversion_settings={
                    "engine": "applio",
                    "engine_release": "3.6.5",
                    "separator": "htdemucs",
                    "f0_method": "rmvpe",
                    "embedder": "contentvec",
                    "pitch": request.pitch,
                    "index_rate": request.index_rate,
                    "protect": request.protect,
                },
            )
            mix_final.spawn(
                MixFinalRequest(
                    job_id=request.job_id,
                    user_id=request.user_id,
                    instrumental_storage_path=instrumental_path,
                    converted_vocals_storage_path=converted_path,
                ).model_dump()
            )
    except Exception as exc:
        fail_and_refund(request.job_id, type(exc).__name__, f"Voice conversion failed: {type(exc).__name__}")
        raise


def claim_converted_job(request: MixFinalRequest) -> bool:
    import httpx

    base = os.environ["SUPABASE_URL"].rstrip("/")
    with httpx.Client(timeout=20) as client:
        result = client.patch(
            f"{base}/rest/v1/generation_jobs",
            params={
                "id": f"eq.{request.job_id}", "user_id": f"eq.{request.user_id}",
                "status": "eq.converted", "select": "id",
            },
            headers={**supabase_headers(), "Prefer": "return=representation"},
            json={"status": "mixing", "progress": 85, "updated_at": datetime.now(timezone.utc).isoformat()},
        )
        result.raise_for_status()
        return bool(result.json())


@app.function(image=media_image, secrets=[secret], timeout=900, cpu=2, memory=4096)
def mix_final(payload: dict[str, Any]) -> None:
    """Mix converted vocals with accompaniment and persist WAV plus MP3."""
    request = MixFinalRequest.model_validate(payload)
    paths = artifact_paths(request.user_id, request.job_id)
    if (
        request.instrumental_storage_path != paths["instrumental"]
        or request.converted_vocals_storage_path != paths["converted"]
    ):
        fail_and_refund(request.job_id, "invalid_mix_path", "Final mix artifact path is invalid")
        return
    if not claim_converted_job(request):
        return
    try:
        with tempfile.TemporaryDirectory(prefix="awaazify-mix-") as temp:
            temp_dir = Path(temp)
            instrumental = temp_dir / "instrumental.wav"
            converted = temp_dir / "converted-vocals.wav"
            final_wav = temp_dir / "final-mix.wav"
            final_mp3 = temp_dir / "final-mix.mp3"
            download_artifact(request.instrumental_storage_path, instrumental)
            download_artifact(request.converted_vocals_storage_path, converted)
            subprocess.run(
                [
                    "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                    "-i", str(instrumental), "-i", str(converted),
                    "-filter_complex",
                    "[0:a]volume=1.0[a0];[1:a]volume=1.0[a1];"
                    "[a0][a1]amix=inputs=2:duration=longest:dropout_transition=0,"
                    "alimiter=limit=0.95,loudnorm=I=-14:TP=-1:LRA=11[out]",
                    "-map", "[out]", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le",
                    str(final_wav),
                ],
                check=True, timeout=600,
            )
            subprocess.run(
                [
                    "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                    "-i", str(final_wav), "-c:a", "libmp3lame", "-b:a", "192k", str(final_mp3),
                ],
                check=True, timeout=300,
            )
            upload_artifact(paths["final_wav"], final_wav)
            upload_artifact(paths["final_mp3"], final_mp3, "audio/mpeg")
            update_job(
                request.job_id, request.user_id, "completed", 100,
                "Final WAV and MP3 completed and stored privately",
                final_wav_storage_path=paths["final_wav"],
                final_mp3_storage_path=paths["final_mp3"],
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
    except Exception as exc:
        fail_and_refund(request.job_id, type(exc).__name__, f"Final mix failed: {type(exc).__name__}")
        raise


@app.function(image=api_image, secrets=[secret], timeout=60)
@modal.fastapi_endpoint(method="POST")
def dispatch_mix_final(
    payload: MixFinalRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    authorize(authorization)
    call = mix_final.spawn(payload.model_dump())
    return {"accepted": True, "job_id": payload.job_id, "worker_call_id": call.object_id}


@app.function(image=api_image, secrets=[secret], timeout=60)
@modal.fastapi_endpoint(method="POST")
def dispatch_convert_voice(
    payload: ConvertVoiceRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    authorize(authorization)
    call = convert_voice.spawn(payload.model_dump())
    return {"accepted": True, "job_id": payload.job_id, "worker_call_id": call.object_id}


@app.function(image=api_image, secrets=[secret], timeout=60)
@modal.fastapi_endpoint(method="POST")
def dispatch_prepare_audio(
    payload: PrepareAudioRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    authorize(authorization)
    call = prepare_audio.spawn(payload.model_dump())
    return {"accepted": True, "job_id": payload.job_id, "worker_call_id": call.object_id}


@app.function(image=image, secrets=[secret], timeout=60)
@modal.fastapi_endpoint(method="POST")
def secure_probe(payload: ProbeRequest, authorization: Annotated[str | None, Header()] = None):
    authorize(authorization)
    return {"ok": True, "job_id": payload.job_id, "worker": "awaazify-v1-worker", "gpu_used": False}


@app.function(
    image=image,
    secrets=[secret],
    volumes={str(MODEL_ROOT): model_volume},
    gpu="T4",
    timeout=300,
    scaledown_window=60,
)
@modal.fastapi_endpoint(method="POST")
def probe_voice_model(
    payload: ModelProbeRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    """Safely inspect one trusted, owner-uploaded Applio/RVC model pair."""
    authorize(authorization)

    try:
        import faiss
        import torch

        checkpoint_path, index_path = resolve_model_files(MODEL_ROOT, payload.model_slug)
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        metadata = summarize_checkpoint(checkpoint)
        vector_index = faiss.read_index(str(index_path))
    except ModelContractError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422, f"Model compatibility check failed: {type(exc).__name__}") from exc

    return {
        "ok": True,
        "model_slug": payload.model_slug,
        "checkpoint_file": checkpoint_path.name,
        "index_file": index_path.name,
        "checkpoint_size_bytes": checkpoint_path.stat().st_size,
        "index_size_bytes": index_path.stat().st_size,
        "index_vectors": int(vector_index.ntotal),
        "index_dimensions": int(vector_index.d),
        "cuda_available": bool(torch.cuda.is_available()),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        **metadata,
    }
