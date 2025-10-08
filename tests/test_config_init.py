from pathlib import Path
import yaml

from ecrivez.project import init_project


def test_init_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_project(model="gpt-4o", name="demo")

    cfg = tmp_path / "demo" / ".ecrivez" / "config.yaml"
    assert cfg.is_file()

    data = yaml.safe_load(cfg.read_text())
    assert data["provider"] == "openai"
    assert Path("demo/demo.py").exists()