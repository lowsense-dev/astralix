# ©️ LowSense, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/lowsense-dev/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""Build uv commands for the interpreter actually running astralix."""

import importlib.util
from contextlib import contextmanager
from contextvars import ContextVar
import shutil
import sys
from pathlib import Path


REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"
_installation_allowed = ContextVar("dependency_installation_allowed", default=True)


@contextmanager
def dependency_installation(allowed: bool):
    """Carry startup's no-install policy through nested async library loads."""
    token = _installation_allowed.set(allowed)
    try:
        yield
    finally:
        _installation_allowed.reset(token)


def install_command(*requirements: str, upgrade: bool = True) -> list[str]:
    """Install into the active environment without depending on shell activation."""
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

    command += ["pip", "install", "--python", sys.executable]
    if upgrade:
        command.append("--upgrade")
    return [*command, *requirements]
