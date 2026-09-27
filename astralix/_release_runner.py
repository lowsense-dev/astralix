# ©️ LowSense, 2026
# This file is a part of astralix Userbot
# https://github.com/lowsense-dev/astralix · GNU AGPLv3
"""Dependency-free release supervisor, also copied outside release directories."""

import contextlib
import atexit
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time

PROTOCOL = 1
DATA_SCHEMA = 1
RESTART = 75


def atomic_json(path, value):
    atomic_bytes(path, json.dumps(value, ensure_ascii=False, indent=2).encode())


def atomic_bytes(path, value):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".state-")
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(value)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def locked(path, *, blocking=False):
    # flock is released by the kernel on process death, unlike a PID file.
    import fcntl
    with Path(path).open("a") as file:
        try:
            fcntl.flock(file, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            raise RuntimeError("Another update or supervisor is already running") from None
        yield


def event(state, status, release, **extra):
    state.setdefault("history", []).append({
        "time": int(time.time()), "status": status,
        "release": release["id"], "commit": release["commit"],
        "channel": release["channel"], **extra,
    })
    state["history"] = state["history"][-100:]


def bootstrap():
    if os.environ.get("ASTRALIX_SUPERVISED") == "1":
        return
    root = Path(os.environ.get("ASTRALIX_INSTALL_ROOT", Path(__file__).resolve().parent.parent))
    directory = root / ".astralix-releases"
    if (directory / "state.json").is_file():
        os.execv(sys.executable, [sys.executable, str(directory / "runner.py"), str(root), *sys.argv[1:]])


def mark_ready(account, modules):
    directory = os.environ.get("ASTRALIX_HEALTH_DIR")
    token = os.environ.get("ASTRALIX_HEALTH_TOKEN")
    if directory and token:
        atomic_json(Path(directory) / f"{int(account)}.json", {
            "token": token, "core": sorted(modules),
        })


def snapshot_configs(directory, data_root, identifier):
    dest = directory / "snapshots" / identifier
    dest.mkdir(parents=True, mode=0o700, exist_ok=False)
    for path in data_root.glob("config*.json"):
        if path.is_file() and not path.is_symlink():
            shutil.copyfile(path, dest / path.name)
            (dest / path.name).chmod(0o600)
    return str(dest)


def restore_configs(snapshot, data_root):
    # Deliberately exclude Telegram sessions and module code.
    contents = {path.name: json.loads(path.read_text()) for path in Path(snapshot).glob("config*.json")}
    for name, value in contents.items():
        atomic_json(data_root / name, value)


def supervise(root, arguments):
    root = Path(root).resolve()
    directory = root / ".astralix-releases"
    state_path = directory / "state.json"
    with locked(directory / "run.lock"):
        stopping = False
        child = None

        def reap_child():
            # Do not leave a second account process behind if supervision raises.
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()

        atexit.register(reap_child)

        def stop(signum, frame):
            nonlocal stopping
            stopping = True
            if child is not None and child.poll() is None:
                child.send_signal(signum)

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)

        while not stopping:
            state = json.loads(state_path.read_text())
            pending = state.get("pending")
            if pending and pending.get("started"):
                # A power loss or killed supervisor during probation is a failure,
                # not permission to retry the candidate indefinitely.
                with locked(directory / "update.lock", blocking=True):
                    if pending.get("restore") and pending.get("snapshot"):
                        restore_configs(pending["snapshot"], Path(state["data_root"]))
                    event(state, "interrupted", pending["target"])
                    state["pending"] = None
                    atomic_json(state_path, state)
                pending = None
            release = pending["target"] if pending else state["active"]
            if pending:
                with locked(directory / "update.lock", blocking=True):
                    pending["snapshot"] = snapshot_configs(
                        directory, Path(state["data_root"]), secrets.token_hex(12),
                    )
                    pending["started"] = int(time.time())
                    atomic_json(state_path, state)
                    if pending.get("restore"):
                        try:
                            restore_configs(pending["restore"], Path(state["data_root"]))
                        except Exception:
                            restore_configs(pending["snapshot"], Path(state["data_root"]))
                            event(state, "failed", release, reason="configuration restore failed")
                            state["pending"] = None
                            atomic_json(state_path, state)
                            continue

            health = directory / "health"
            health.mkdir(mode=0o700, exist_ok=True)
            token = secrets.token_hex(32)
            environment = {**os.environ,
                "ASTRALIX_SUPERVISED": "1", "ASTRALIX_INSTALL_ROOT": str(root),
                "ASTRALIX_HEALTH_DIR": str(health), "ASTRALIX_HEALTH_TOKEN": token,
                "ASTRALIX_DATA_ROOT": state["data_root"],
                "VIRTUAL_ENV": str(Path(release["python"]).parent.parent),
                "PYTHONPATH": release["path"],
                "PATH": str(Path(release["python"]).parent) + os.pathsep + os.environ.get("PATH", ""),
            }
            child_args = []
            skip = False
            for argument in arguments:
                if skip:
                    skip = False
                elif argument == "--data-root":
                    skip = True
                elif not argument.startswith("--data-root="):
                    child_args.append(argument)
            try:
                child = subprocess.Popen(
                    [release["python"], "-m", "astralix", *child_args, "--data-root", state["data_root"]],
                    cwd=release["path"], env=environment,
                )
            except OSError as error:
                if not pending:
                    raise
                with locked(directory / "update.lock", blocking=True):
                    if pending.get("restore"):
                        restore_configs(pending["snapshot"], Path(state["data_root"]))
                    event(state, "failed", release, reason=str(error))
                    state["pending"] = None
                    event(state, "automatic_rollback", state["active"])
                    atomic_json(state_path, state)
                continue
            deadline = time.monotonic() + (pending["timeout"] if pending else 0)
            failure = None
            healthy_since = None
            while child.poll() is None and not stopping:
                if pending:
                    healthy = True
                    for account in pending["accounts"]:
                        try:
                            ready = json.loads((health / f"{account}.json").read_text())
                            healthy &= ready["token"] == token and set(pending["core"]) <= set(ready["core"])
                        except (OSError, ValueError, KeyError):
                            healthy = False
                    if healthy and pending["accounts"]:
                        healthy_since = healthy_since or time.monotonic()
                    else:
                        healthy_since = None
                    if healthy_since and time.monotonic() - healthy_since >= 5:
                        with locked(directory / "update.lock", blocking=True):
                            state["previous"] = {**state["active"], "snapshot": pending["snapshot"]}
                            state["active"] = release
                            state["pending"] = None
                            event(state, "healthy", release)
                            atomic_json(state_path, state)
                        pending = None
                    elif time.monotonic() >= deadline:
                        failure = "startup timeout"
                        break
                time.sleep(0.25)

            if stopping:
                with contextlib.suppress(subprocess.TimeoutExpired):
                    child.wait(timeout=15)
                if child.poll() is None:
                    child.kill()
                    child.wait()
                return 0
            if failure or (pending and child.poll() != RESTART):
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
                with locked(directory / "update.lock", blocking=True):
                    if pending.get("restore"):
                        restore_configs(pending["snapshot"], Path(state["data_root"]))
                    event(state, "failed", release, reason=failure or f"exit {child.returncode}")
                    state["pending"] = None
                    event(state, "automatic_rollback", state["active"])
                    atomic_json(state_path, state)
                print("astralix: candidate failed; starting previous release", flush=True)
                continue
            if child.returncode == RESTART:
                # Normal restarts and explicitly requested release switches.
                continue
            return child.returncode or 0
    return 0


if __name__ == "__main__":
    raise SystemExit(supervise(sys.argv[1], sys.argv[2:]))
