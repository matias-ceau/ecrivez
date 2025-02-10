from pathlib import Path

import libtmux
import yaml
from pynvim import attach

__all__ = ["start_editor"]


def start_editor(file: str | None) -> None:
    """Start the editor with an optional file"""
    cfg = Path(".ecrivez/config.yaml")
    assert cfg.exists()
    with open(cfg, "r") as f:
        config = yaml.safe_load(f)
    server = libtmux.Server()
    session = server.new_session(f"ecrivez-{config['name']}")

    # Split window horizontally
    window = session.attached_window
    window.split_window(vertical=True)

    # Launch nvim in the first pane
    nvim_socket = f"/tmp/nvim-ecrivez-{config['name']}.sock"
    file = file if file else config["name"]
    window.attached_pane.send_keys(f"nvim --listen {nvim_socket} {file}")

    # Connect to nvim instance
    nvim = attach("socket", path=nvim_socket)

    # Start REPL in second pane
    # Note: REPL implementation details would go here
    # Keep session alive
    session.attach_session()
    session.attach_session()
