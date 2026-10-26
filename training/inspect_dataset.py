"""Colab/admin helper: safely inspect an Awaazify voice-training dataset."""
from __future__ import annotations

import argparse
import json
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path

ALLOWED = {".wav", ".mp3", ".flac"}
MAX_FILES = 1000
MAX_UNCOMPRESSED = 2 * 1024 * 1024 * 1024


def safe_extract(source: Path, destination: Path) -> list[Path]:
    files: list[Path] = []
    total = 0
    with zipfile.ZipFile(source) as archive:
        members = archive.infolist()
        if len(members) > MAX_FILES:
            raise ValueError("Archive contains too many files")
        for member in members:
            relative = Path(member.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Archive contains an unsafe path")
            if stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError("Archive symlinks are not allowed")
            total += member.file_size
            if total > MAX_UNCOMPRESSED:
                raise ValueError("Archive expands beyond the safe limit")
            if member.is_dir():
                continue
            target = (destination / relative).resolve()
            if destination.resolve() not in target.parents:
                raise ValueError("Archive path escapes the extraction folder")
            if target.suffix.lower() not in ALLOWED:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as incoming, target.open("wb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
            files.append(target)
    return files


def duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return float(result.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=Path("awaazify-training-audio"))
    args = parser.parse_args()
    source = args.dataset.resolve()
    if not source.is_file():
        raise SystemExit("Dataset file was not found")
    args.output.mkdir(parents=True, exist_ok=True)
    files = safe_extract(source, args.output) if source.suffix.lower() == ".zip" else [source]
    if not files:
        raise SystemExit("No WAV, MP3 or FLAC audio was found")
    rows = []
    for file in files:
        try:
            seconds = duration(file)
            if seconds > 0:
                rows.append({"file": str(file), "seconds": round(seconds, 2), "bytes": file.stat().st_size})
        except (ValueError, subprocess.SubprocessError):
            continue
    total = sum(row["seconds"] for row in rows)
    report = {
        "valid_audio_files": len(rows),
        "total_seconds": round(total, 2),
        "total_minutes": round(total / 60, 2),
        "recommended_minimum_minutes": 10,
        "ready_for_manual_review": len(rows) > 0 and total >= 180,
        "files": rows,
    }
    print(json.dumps(report, indent=2))
    if total < 180:
        raise SystemExit("Dataset has less than 3 minutes of valid audio")


if __name__ == "__main__":
    main()
