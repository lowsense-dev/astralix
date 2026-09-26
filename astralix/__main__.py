# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/ZetGoHack/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ LowSense, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/lowsense-dev/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""Entry point. Checks for user and starts main script"""



import getpass
import os
import re
import shutil
import sys
from pathlib import Path


if "--no-git" in sys.argv:
    os.environ["ASTRALIX_NO_GIT"] = "1"


def get_data_root():
    for index, arg in enumerate(sys.argv):
        if arg == "--data-root" and index + 1 < len(sys.argv):
            return Path(sys.argv[index + 1]).expanduser()

        if arg.startswith("--data-root="):
            return Path(arg.split("=", maxsplit=1)[1]).expanduser()

    return Path(
        "/data"
        if "DOCKER" in os.environ
        else os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    )


def wipe_data():
    if not {"-w", "--wipe"} & set(sys.argv):
        return

    print(
        "Are you sure you want to completely delete all session files, "
        "their databases and modules? This action is irreversible [y/N]"
    )
    if input("> ").strip().lower() not in {"yes", "y"}:
        print("Cancelled")
        sys.exit(0)

    data_root = get_data_root()
    patterns = (
        "config.json",
        "config-*.json",
        "*.session",
        "*.session-journal",
        "api_token.txt",
    )
    dirs = ("loaded_modules", "sessions")
    removed = 0

    for pattern in patterns:
        for path in data_root.glob(pattern):
            if not path.is_file():
                continue

            path.unlink()
            removed += 1

    for dirname in dirs:
        path = data_root / dirname
        if not path.is_dir():
            continue

        shutil.rmtree(path)
        removed += 1

    print(f"Removed files: {removed}")
    sys.exit(0)


wipe_data()


if (
    getpass.getuser() == "root"
    and "--root" not in " ".join(sys.argv)
    and not {"-h", "--help"} & set(sys.argv)
    and all(trigger not in os.environ for trigger in {"DOCKER", "NO_SUDO"})
):
    print("\U0001f6ab" * 15)
    print("You attempted to run astralix on behalf of root user")
    print("Please, create a new user and restart script")
    print("If this action was intentional, pass --root argument instead")
    print("\U0001f6ab" * 15)
    print()
    print("Type force_insecure to ignore this warning")
    print("Type no_sudo if your system has no sudo (Debian vibes)")
    inp = input("> ").lower()
    if inp == "no_sudo":
        os.environ["NO_SUDO"] = "1"
        print("Added NO_SUDO in your environment variables")
        os.execv(sys.executable, [sys.executable, *sys.argv])
    elif inp != "force_insecure":
        sys.exit(1)

if sys.version_info < (3, 10, 0):
    print("\U0001f6ab Error: you must use at least Python version 3.10.0")
elif __package__ != "astralix":
    print(
        "\U0001f6ab Error: you cannot run this as a script; you must execute as a package"
    )
else:
    try:
        import astralixtl
        import cryptography  # Required by the encrypted login transport.
        ver_ = tuple(
            int(match.group()) if (match := re.match(r"\d+", part)) else 0
            for part in astralixtl.__version__.split(".")
        )
        if ver_ < (1, 0, 0):
            raise ImportError("astralix-tl 1.0.0 or newer is required")
        from . import log
        log.init()
        from . import main
    except ImportError as e:
        print(
            f"Missing or incompatible dependency: {e}\n"
            "Install dependencies explicitly before starting astralix:\n"
            "  uv sync --locked --inexact\n"
            "  .venv/bin/python -m astralix"
        )
        sys.exit(1)

    if "ASTRALIX_DO_NOT_RESTART" in os.environ:
        del os.environ["ASTRALIX_DO_NOT_RESTART"]
    if "ASTRALIX_DO_NOT_RESTART2" in os.environ:
        del os.environ["ASTRALIX_DO_NOT_RESTART2"]

    main.astralix.main()
