from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


APP_VENDOR = "Kubo Servicios SpA"
APP_NAME = "OpenAPU"


def resource_dir() -> Path:
    """Return the read-only directory containing packaged application assets."""
    bundled = getattr(sys, "_MEIPASS", None)
    return Path(bundled) if bundled else Path(__file__).resolve().parent


def config_path() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_VENDOR / APP_NAME / "config.json"
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / APP_VENDOR / APP_NAME / "config.json"


def default_projects_dir() -> Path:
    return Path.home() / "Documents" / "OpenAPU Proyectos"


def choose_macos_projects_dir() -> Path | None:
    """Ask for the local projects folder on the first packaged macOS launch."""
    if sys.platform != "darwin" or not getattr(sys, "frozen", False):
        return None
    script = (
        'set selectedFolder to choose folder with prompt '
        '"Seleccione o cree la carpeta donde OpenAPU guardará sus proyectos" '
        'default location (path to documents folder)\n'
        'return POSIX path of selectedFolder'
    )
    try:
        completed = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=300,
        )
        selected = completed.stdout.strip()
        return Path(selected).expanduser().resolve() if completed.returncode == 0 and selected else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def read_config() -> dict:
    path = config_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def write_projects_dir(path: str | Path) -> Path:
    target = Path(path).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    config = read_config()
    config.update({"projectsDir": str(target), "version": 1})
    destination = config_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    serialized = json.dumps(config, ensure_ascii=False, indent=2)
    temporary.write_text(serialized, encoding="utf-8")
    try:
        temporary.replace(destination)
    except OSError as exc:
        # Windows EFS may report ERROR_NOT_SAME_DEVICE when replacing an
        # encrypted configuration file even though both paths share a folder.
        if getattr(exc, "winerror", None) != 17:
            raise
        destination.write_text(serialized, encoding="utf-8")
        temporary.unlink(missing_ok=True)
    return target


def data_root(cli_value: str | None = None) -> Path:
    if cli_value:
        target = Path(cli_value).expanduser().resolve()
    elif os.environ.get("OPENAPU_PROJECTS_DIR"):
        target = Path(os.environ["OPENAPU_PROJECTS_DIR"]).expanduser().resolve()
    else:
        configured = read_config().get("projectsDir")
        if configured:
            target = Path(configured).expanduser().resolve()
        elif sys.platform == "darwin" and getattr(sys, "frozen", False):
            selected = choose_macos_projects_dir()
            if selected:
                return write_projects_dir(selected)
            target = default_projects_dir()
        elif getattr(sys, "frozen", False):
            target = default_projects_dir()
        else:
            # The source workspace keeps persistent projects outside the
            # application assets, matching iniciar.ps1 and the official MCP.
            workspace_projects = Path(__file__).resolve().parent.parent / "01. Proyectos"
            target = workspace_projects if workspace_projects.is_dir() else Path(__file__).resolve().parent
    target.mkdir(parents=True, exist_ok=True)
    return target

