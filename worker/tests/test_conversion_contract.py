from pathlib import Path

from conversion_contract import artifact_paths, build_rvc_command


def test_artifact_paths_are_scoped_to_user_and_job():
    paths = artifact_paths("user-1", "job-1")
    assert paths["normalized"] == "user-1/job-1/normalized.wav"
    assert all(value.startswith("user-1/job-1/") for value in paths.values())


def test_rvc_command_pins_quality_critical_settings():
    command = build_rvc_command(
        Path("in.wav"), Path("out.wav"), Path("voice.pth"), Path("voice.index"), 0, 0.5, 0.33
    )
    assert command[:3] == ["python", "/opt/applio/core.py", "infer"]
    assert command[command.index("--f0-method") + 1] == "rmvpe"
    assert command[command.index("--embedder-model") + 1] == "contentvec"
    assert "--split-audio" in command

