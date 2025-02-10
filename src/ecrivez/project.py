from pathlib import Path
import subprocess
import os
import yaml
import click
from typing import Optional


def usage():
    """Print usage information"""
    click.echo("Usage: ecrivez init [name] [path]")
    exit(1)


def init_project(model: str = "gpt-4o", name: str = "", path: Optional[Path] = None):
    """Initialize a new Ecrivez project which needs a name, a model and a path.
    It can also be initialized in the current directory"""
    if name != "":
        path = Path(name)
        if not path.exists():
            Path(path).mkdir(parents=True, exist_ok=True)
    elif path == ".":
        path = Path(".")
        name = path.name
    else:
        raise click.UsageError("Project name or path is required")

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


def open_project(input_string):
    """Open an existing Ecrivez project"""
    path = Path(input_string)
    if path.exists():
        os.chdir(path)
    else:
        click.echo("Project does not exist")
        return
    # Check if git repository
    if not Path(".git").exists():
        click.echo("Not a git repository")
        return
    # Check if .ecrivez directory exists
    if not Path(".ecrivez").exists():
        click.echo("No Ecrivez configuration found. Run 'ecrivez init' first.")
        return
    else:
        with open(".ecrivez/config.yaml") as f:
            config = yaml.safe_load(f)
        return config


def modify_config(model, editor):
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


def greet(name: Optional[str] = None) -> None:
    if name is not None:
        print(f"Hello, {name}!")
    else:
        print("Hello, World!")
