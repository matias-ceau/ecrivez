import os
import sys
import yaml
import pytest

from ecrivez.chat import _load_config, ProjectConfig

def write_config(path, data):
    cfg_dir = path / ".ecrivez"
    cfg_dir.mkdir(exist_ok=True)
    cfg_file = cfg_dir / "config.yaml"
    cfg_file.write_text(yaml.dump(data))
    return cfg_file


def test_load_config_valid(tmp_path, monkeypatch):
    # Setup a valid config
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    valid = {"name": "demo", "model": "gpt-4o", "provider": "echo"}
    write_config(project_dir, valid)
    # Change cwd
    monkeypatch.chdir(project_dir)
    cfg = _load_config()
    assert cfg["name"] == "demo"
    assert cfg["model"] == "gpt-4o"
    assert cfg["provider"] == "echo"
    # openai_api_key should default to None
    assert cfg.get("openai_api_key") is None


def test_load_config_extra_key(tmp_path, monkeypatch, capsys):
    # Setup config with an extra invalid field
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    invalid = {"name": "demo", "model": "gpt-4o", "provider": "echo", "foo": "bar"}
    write_config(project_dir, invalid)
    monkeypatch.chdir(project_dir)
    with pytest.raises(SystemExit) as exc:
        _load_config()
    # Ensure exit code is 1
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "Config validation error" in captured.err

