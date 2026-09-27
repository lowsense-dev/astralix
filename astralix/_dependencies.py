# ©️ LowSense, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/lowsense-dev/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""Build uv commands for the interpreter actually running astralix."""

import importlib.util
from contextlib import contextmanager
from contextvars import ContextVar
import os
import shutil
import sys
from pathlib import Path


_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_INSTALL_ROOT_VALUE = os.environ.get("ASTRALIX_DATA_ROOT")
_INSTALL_ROOT = (
    Path(_INSTALL_ROOT_VALUE).expanduser() if _INSTALL_ROOT_VALUE else None
)
PROJECT_ROOT = (
    _INSTALL_ROOT.resolve()
    if _INSTALL_ROOT is not None and (_INSTALL_ROOT / ".git").exists()
    else _PACKAGE_ROOT
)
_installation_allowed = ContextVar("dependency_installation_allowed", default=True)


@contextmanager
def dependency_installation(allowed: bool):
    """Carry startup's no-install policy through nested async library loads."""
    token = _installation_allowed.set(allowed)
    try:
        yield
    finally:
        _installation_allowed.reset(token)


def _uv_command() -> list[str]:
    if not _installation_allowed.get():
        raise RuntimeError("Dependency installation is disabled during startup")
    candidates = (
        Path(sys.executable).parent / "uv",
        Path.home() / ".local" / "bin" / "uv",
    )
    uv = shutil.which("uv") or next(
        (str(path) for path in candidates if shutil.which(str(path))), None
    )
    if uv:
        command = [uv]
    elif importlib.util.find_spec("uv") is not None:
        command = [sys.executable, "-m", "uv"]
    else:
        raise RuntimeError("uv is not installed. Install uv and run bash install.sh.")

    return command


def sync_command(python: str | Path | None = None) -> list[str]:
    """Sync the project lockfile, preserving packages installed by user modules."""
    return [
        *_uv_command(), "sync", "--locked", "--inexact",
        "--project", str(PROJECT_ROOT), "--python", str(python or sys.executable),
    ]


def install_command(*requirements: str, upgrade: bool = True) -> list[str]:
    """Install explicit module requirements into the running environment."""
    command = [*_uv_command(), "pip", "install", "--python", sys.executable]
    if upgrade:
        command.append("--upgrade")
    return [*command, *requirements]
