"""Pure helpers for deterministic, testable Phase 4D conversion commands."""
from pathlib import Path


def artifact_paths(user_id: str, job_id: str) -> dict[str, str]:
    root = f"{user_id}/{job_id}"
    return {
        "normalized": f"{root}/normalized.wav",
        "vocals": f"{root}/vocals.wav",
        "instrumental": f"{root}/instrumental.wav",
        "converted": f"{root}/converted-vocals.wav",
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

