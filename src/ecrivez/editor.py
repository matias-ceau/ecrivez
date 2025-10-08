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

    # Best-effort: wait a bit for Neovim to create its socket, otherwise skip
    import time

    for _ in range(20):  # 2 seconds total
        if Path(nvim_socket).exists():
            try:
                nvim = attach("socket", path=nvim_socket)
                break
            except FileNotFoundError:
                pass
        time.sleep(0.1)

    # Start REPL in second pane
    window.panes[1].send_keys("ecrivez repl", enter=True)

    # Keep session alive
    session.attach_session()
    session.attach_session()
