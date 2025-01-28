import click
import subprocess
import yaml
import os
from pathlib import Path
import libtmux
from pynvim import attach


@click.group()
def cli():
    """Ecrivez CLI tool for managing coding sessions with LLMs"""
    pass


@cli.command()
@click.option("--model", default="gpt-4o", help="Default LLM model to use")
@click.option("--name", default="", help="Filename and project name")
def init(model, name):
    """Initialize a new Ecrivez project"""
    if name != "":
        path = Path(name)
        if not path.exists():
            subprocess.run(["mkdir", path])
    else:
        path = Path(".")
        name = path.name
    os.chdir(path)
    # Initialize git repository
    if not Path(".git").exists():
        subprocess.run(["git", "init"], check=True)

    # Create .ecrivez directory
    ecrivez_dir = Path(".ecrivez")
    ecrivez_dir.mkdir(exist_ok=False)

    # Create and write config file
    config = {"name": name, "model": model}

    with open(ecrivez_dir / "config.yaml", "w") as f:
        yaml.dump(config, f)

    click.echo(f"Initialized {name} project")


@cli.command()
@click.option("--model", help="LLM model to use")
@click.option("--editor", help="Editor to use")
def set(model, editor):
    """Modify Ecrivez configuration"""
    config_path = Path(".ecrivez/config.yaml")

    if not config_path.exists():
        click.echo("No Ecrivez configuration found. Run 'ecrivez init' first.")
        return

    with open(config_path) as f:
        config = yaml.safe_load(f)

    if model:
        config["model"] = model
    if editor:
        config["editor"] = editor

    with open(config_path, "w") as f:
        yaml.dump(config, f)

    click.echo("Updated configuration")


@cli.command()
@click.option("--file", default=None, help="Filename to open")
def chat(file):
    """Start a chat session with file editing capabilities"""
    # Create tmux session
    cfg = Path(".ecrivez/config.yaml")
    assert cfg.exists()
    with open(cfg, "r") as f:
        config = yaml.safe_load(f)
    server = libtmux.Server()
    session = server.new_session(f"ecrivez-{config['name']}")

    # Split window horizontally
    window = session.attached_window
    pane_repl = window.split_window(vertical=True)

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
