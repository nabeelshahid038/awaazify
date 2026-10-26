from pathlib import Path

import pytest

from model_contract import ModelContractError, resolve_model_files, summarize_checkpoint, validate_model_slug


def test_slug_rejects_traversal():
    with pytest.raises(ModelContractError):
        validate_model_slug("../secret")


def test_resolves_exact_pair(tmp_path: Path):
    model_dir = tmp_path / "models" / "my-voice-model"
    model_dir.mkdir(parents=True)
    (model_dir / "voice.pth").write_bytes(b"checkpoint")
    (model_dir / "voice.index").write_bytes(b"index")
    checkpoint, index = resolve_model_files(tmp_path, "my-voice-model")
    assert checkpoint.name == "voice.pth"
    assert index.name == "voice.index"


def test_rejects_ambiguous_checkpoint(tmp_path: Path):
    model_dir = tmp_path / "models" / "my-voice-model"
    model_dir.mkdir(parents=True)
    (model_dir / "one.pth").touch()
    (model_dir / "two.pth").touch()
    (model_dir / "voice.index").touch()
    with pytest.raises(ModelContractError, match="exactly one .pth"):
        resolve_model_files(tmp_path, "my-voice-model")


def test_checkpoint_summary():
    result = summarize_checkpoint(
        {"weight": {"layer.weight": object()}, "config": [1, 2, 40000], "version": "v2", "f0": 1}
    )
    assert result == {"version": "v2", "sample_rate": "40000", "f0": 1, "weight_tensors": 1}
