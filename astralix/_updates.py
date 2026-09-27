# ©️ LowSense, 2026
# This file is a part of astralix Userbot
# https://github.com/lowsense-dev/astralix · GNU AGPLv3
"""Explicit, staged updates. Never modifies the running checkout or environment."""

import ast
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit

from ._dependencies import PROJECT_ROOT, _uv_command
from ._release_runner import DATA_SCHEMA, PROTOCOL, atomic_bytes, atomic_json, event, locked
from ._release_integrity import verify_files
from ._release_trust import verify_manifest
from ._internal import redact


class Updates:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get("ASTRALIX_INSTALL_ROOT", PROJECT_ROOT)).resolve()
        self.directory = self.root / ".astralix-releases"
        self.directory.mkdir(mode=0o700, exist_ok=True)
        self.state_path = self.directory / "state.json"

    def read(self):
        return json.loads(self.state_path.read_text()) if self.state_path.exists() else None

    def run(self, arguments, cwd, timeout=120, env=None):
        result = subprocess.run(
            list(map(str, arguments)), cwd=cwd, text=True, capture_output=True,
            timeout=timeout, env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})},
        )
        if result.returncode:
            log = self.directory / "operation.log"
            fd = os.open(log, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w") as output:
                output.write(
                    redact(f"$ {shlex.join(map(str, arguments))}\n"
                           f"exit {result.returncode}\n{result.stdout}{result.stderr}\n")
                )
            raise RuntimeError(f"{Path(str(arguments[0])).name} failed; details: {log}")
        return result.stdout.strip()

    def git(self, *args, cwd=None):
        return self.run(["git", *args], cwd or PROJECT_ROOT)

    def _check(self, origin, channel):
        if channel not in ("main", "dev"):
            raise ValueError("Channel must be main or dev")
        url = urlsplit(origin)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Use an HTTPS Git URL without embedded credentials")
        current = self.git("rev-parse", "HEAD")
        branch = self.git("branch", "--show-current")
        dirty = self.git("status", "--porcelain", "--untracked-files=no")
        self.git("fetch", "--no-tags", origin, f"+refs/heads/{channel}:refs/astralix-updates/{channel}")
        tip = self.git("rev-parse", f"refs/astralix-updates/{channel}")
        self.git("fetch", "--no-tags", origin,
                 "+refs/heads/release-metadata:refs/astralix-updates/metadata")
        reference = f"refs/astralix-updates/metadata:{channel}.json"
        if int(self.git("cat-file", "-s", reference)) > 4 * 1024 * 1024:
            raise ValueError("Release metadata is too large")
        raw = self.git("show", reference)
        target = json.loads(raw)["signed"]["commit"]
        seen_path = self.directory / "trusted-releases.json"
        seen = json.loads(seen_path.read_text()) if seen_path.exists() else {}
        manifest = verify_manifest(raw, channel, target, seen=seen.get(channel))
        # A newer unreviewed branch commit is not a published release.
        self.git("merge-base", "--is-ancestor", target, tip)
        seen[channel] = {"sequence": manifest["sequence"], "commit": target}
        atomic_json(seen_path, seen)
        self.git("update-ref", f"refs/astralix-releases/{channel}", target)
        changes = self.git("log", "--format=%h %s", "-12", f"{current}..{target}")
        dependencies = self.git("diff", "--stat", current, target, "--", "pyproject.toml", "uv.lock")
        if dependencies:
            delta = self.git("diff", "--unified=0", current, target, "--", "pyproject.toml", "uv.lock")
            changes_to_packages = [
                line for line in delta.splitlines()
                if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
                and line[1:].lstrip().startswith(('"', 'name =', 'version =', 'requires-python ='))
            ]
            dependencies += "\n" + "\n".join(changes_to_packages)[:1400]
        return {"current": current, "target": target, "channel": channel,
                "branch": branch, "dirty": dirty, "changes": changes,
                "dependencies": dependencies, "manifest": manifest}

    def check(self, origin, channel):
        with locked(self.directory / "update.lock"):
            return self._check(origin, channel)

    def _initial_state(self, data_root):
        return {"active": {
            "id": "initial", "path": str(PROJECT_ROOT), "python": sys.executable,
            "commit": self.git("rev-parse", "HEAD"),
            "channel": self.git("branch", "--show-current"),
        }, "previous": None, "pending": None, "history": [],
            "data_root": str(Path(data_root).resolve())}

    @staticmethod
    def _protocol(path):
        tree = ast.parse(path.read_text())
        values = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id in ("PROTOCOL", "DATA_SCHEMA"):
                    values[node.targets[0].id] = ast.literal_eval(node.value)
        if values != {"PROTOCOL": PROTOCOL, "DATA_SCHEMA": DATA_SCHEMA}:
            raise RuntimeError("Target release has an incompatible update protocol or data schema")

    def prepare(self, origin, channel, data_root, accounts, timeout=180, expected=None,
                module_requirements=(), health_modules=None):
        with locked(self.directory / "update.lock"):
            state = self.read() or self._initial_state(data_root)
            if state.get("pending"):
                raise RuntimeError("A release switch is already pending")
            report = self._check(origin, channel)
            if expected is not None and report["target"] != expected:
                raise RuntimeError("Release changed since confirmation. Run update again.")
            if report["dirty"]:
                raise RuntimeError("The running checkout has local changes; commit or stash them first")
            if report["target"] == report["current"] and report["branch"] == channel:
                return None
            if report["branch"] == channel:
                self.git("merge-base", "--is-ancestor", report["current"], report["target"])
            identifier = f"{int(time.time())}-{report['target'][:12]}-{secrets.token_hex(3)}"
            target = self.directory / "releases" / identifier
            target.parent.mkdir(mode=0o700, exist_ok=True)
            release = {"id": identifier, "path": str(target),
                       "python": str(target / ".venv/bin/python"),
                       "commit": report["target"], "channel": channel,
                       "files": report["manifest"]["files"], "health_protocol": 2}
            try:
                # Independent object store; no worktree or hardlink dependencies.
                self.git("clone", "--no-hardlinks", "--no-checkout", str(PROJECT_ROOT), str(target))
                self.git("remote", "set-url", "origin", origin, cwd=target)
                self.git("checkout", "-B", channel, report["target"], cwd=target)
                verify_files(target, release["files"])
                self._protocol(target / "astralix/_release_runner.py")
                uv = _uv_command()
                self.run([*uv, "venv", "--python", sys.executable, target / ".venv"], target)
                self.run([*uv, "sync", "--locked", "--project", target,
                          "--python", release["python"]], target, timeout=900,
                         env={"UV_PROJECT_ENVIRONMENT": str(target / ".venv")})
                if module_requirements:
                    from ._module_inventory import validate_requirements
                    requirements = target / ".module-requirements.in"
                    constraints = target / ".core-constraints.txt"
                    resolved = target / ".module-requirements.lock"
                    atomic_bytes(requirements, ('\n'.join(validate_requirements(module_requirements)) + '\n').encode())
                    atomic_bytes(constraints, self.run([*uv, "pip", "freeze", "--python", release["python"]], target).encode())
                    self.run([*uv, "pip", "compile", requirements, "--constraint", constraints,
                              "--generate-hashes", "--python", release["python"], "--only-binary", ":all:",
                              "--output-file", resolved], target, timeout=900)
                    self.run([*uv, "pip", "install", "--python", release["python"],
                              "--require-hashes", "--only-binary", ":all:", "-r", resolved], target, timeout=900)
                self.run([*uv, "pip", "check", "--python", release["python"]], target)
                self.run([release["python"], "-m", "compileall", "-q", "astralix"], target)
                self.run([release["python"], "-c", "import astralixtl, cryptography; from astralix import main"], target,
                         env={"ASTRALIX_DATA_ROOT": str(target / ".preflight-data"), "PYTHONPATH": str(target)})
                verify_files(target, release["files"])
                if self.git("rev-parse", "HEAD") != report["current"] or self.git("status", "--porcelain", "--untracked-files=no"):
                    raise RuntimeError("The running checkout changed while the release was being prepared")
                # No root checkout reset, no modification of its environment.
                atomic_bytes(self.directory / "_release_integrity.py", Path(__file__).with_name("_release_integrity.py").read_bytes())
                atomic_bytes(self.directory / "runner.py", Path(__file__).with_name("_release_runner.py").read_bytes())
                state["pending"] = self._pending(release, accounts, timeout)
                state["pending"]["modules"] = health_modules or {}
                event(state, "prepared", release)
                atomic_json(self.state_path, state)
                return release
            except Exception:
                event(state, "prepare_failed", release)
                # Keep a usable launcher even when the very first build fails.
                atomic_bytes(self.directory / "_release_integrity.py", Path(__file__).with_name("_release_integrity.py").read_bytes())
                atomic_bytes(self.directory / "runner.py", Path(__file__).with_name("_release_runner.py").read_bytes())
                atomic_json(self.state_path, state)
                shutil.rmtree(target, ignore_errors=True)
                raise

    @staticmethod
    def _pending(release, accounts, timeout):
        if not accounts or not 30 <= int(timeout) <= 900:
            raise ValueError("Accounts and a startup timeout of 30–900 seconds are required")
        return {"target": release, "accounts": [str(int(account)) for account in accounts],
                "core": ["LoaderMod", "UpdaterMod", "CoreMod"], "timeout": int(timeout)}

    def rollback(self, accounts, restore_data=False, timeout=180):
        with locked(self.directory / "update.lock"):
            state = self.read()
            if not state or not state.get("previous"):
                raise RuntimeError("There is no previous successfully running release")
            if state.get("pending"):
                raise RuntimeError("A release switch is already pending")
            if self.git("status", "--porcelain", "--untracked-files=no"):
                raise RuntimeError("The running checkout has local changes; commit or stash them first")
            release = state["previous"]
            if not Path(release["python"]).is_file():
                raise RuntimeError("Previous release environment is missing")
            self._protocol(Path(release["path"]) / "astralix/_release_runner.py")
            if self.git("rev-parse", "HEAD", cwd=release["path"]) != release["commit"] or self.git("status", "--porcelain", "--untracked-files=no", cwd=release["path"]):
                raise RuntimeError("Previous release was modified; refusing an unsafe rollback")
            state["pending"] = self._pending(release, accounts, timeout)
            if restore_data:
                snapshot = release.get("snapshot")
                if not snapshot or not Path(snapshot).is_dir():
                    raise RuntimeError("Configuration snapshot is missing")
                state["pending"]["restore"] = snapshot
            event(state, "rollback_requested", release, restore_data=restore_data)
            atomic_json(self.state_path, state)
            return release

    def cancel_pending(self):
        with locked(self.directory / "update.lock"):
            state = self.read()
            if state and state.get("pending") and not state["pending"].get("started"):
                event(state, "cancelled", state["pending"]["target"])
                state["pending"] = None
                atomic_json(self.state_path, state)
