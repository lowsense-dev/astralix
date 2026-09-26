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

# ©️ radiocycle, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/radiocycle/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import base64
import contextlib
import contextvars
import functools
import html
import inspect
import logging
import os
import random
import re
import sys
import tempfile
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit

_secrets = set()
_secret_names = re.compile(
    r"(?:token|password|passwd|secret|api_?hash|api_?key|auth_?key|"
    r"string_?session|session_?string|private_?key|basic_auth|redis_uri|"
    r"redis_url|database_url|db_uri|credentials)", re.I
)


def register_secret(value):
    if isinstance(value, dict):
        for item in value.values():
            register_secret(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            register_secret(item)
    elif isinstance(value, str) and len(value) >= 4:
        _secrets.update((value, html.escape(value), quote(value, safe="")))
        if ":" in value:
            _secrets.add(base64.b64encode(value.encode()).decode())


def register_secrets(data):
    if isinstance(data, dict):
        for key, value in data.items():
            if _secret_names.search(str(key)):
                register_secret(value)
            elif isinstance(value, (dict, list, tuple)):
                register_secrets(value)
    elif isinstance(data, (list, tuple)):
        for value in data:
            register_secrets(value)


def redact(text):
    text = str(text)
    for secret in sorted(_secrets.copy(), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    text = re.sub(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        "[REDACTED PRIVATE KEY]", text, flags=re.S,
    )
    text = re.sub(r"\b\d{5,16}:[A-Za-z0-9_-]{30,}\b", "[REDACTED]", text)
    text = re.sub(r"\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{16,}\b", "[REDACTED]", text)
    text = re.sub(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9+/_.=-]+", r"\1 [REDACTED]", text)
    text = re.sub(r"(\w+://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", text)
    text = re.sub(
        r"(?i)([\"']?(?:[\w.-]*(?:token|password|passwd|secret|api_key|api_hash|"
        r"auth_key|session_string|basic_auth))[\"']?\s*[:=]\s*)"
        r"(?:\"[^\"]*\"|'[^']*'|[^\s&,;<>]+)",
        r"\1[REDACTED]", text,
    )
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        return redact(super().format(record))


class PrivateRotatingFileHandler(RotatingFileHandler):
    def _open(self):
        stream = super()._open()
        if hasattr(os, "fchmod"):
            os.fchmod(stream.fileno(), 0o600)
        else:
            os.chmod(self.baseFilename, 0o600)
        return stream


def private_write(path, data):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Refusing to write private data through a symlink")
    if isinstance(data, str):
        data = data.encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


register_secrets(dict(os.environ))


def validate_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or any(ord(char) < 33 or char == "\\" for char in url)
    ):
        raise ValueError("Code downloads require an HTTPS URL without credentials")
    parsed.port
    return parsed


def auth_for_url(url, auth, trusted_url):
    target = validate_url(url)
    if not auth or not trusted_url:
        return None
    trusted = validate_url(trusted_url)
    if (target.hostname, target.port or 443) != (trusted.hostname, trusted.port or 443):
        return None
    path = unquote(target.path)
    root = unquote(trusted.path).rstrip("/") + "/"
    if (
        ".." in path.split("/") or "%" in path or "\\" in path
        or not path.startswith(root)
    ):
        return None
    return tuple(auth.split(":", 1))


def fetch_text(url, *, auth=None, trusted_url=None, max_size=5 * 1024 * 1024):
    import requests

    with requests.Session() as session:
        session.trust_env = False
        for _ in range(6):
            validate_url(url)
            session.cookies.clear()
            with session.get(
                url,
                auth=auth_for_url(url, auth, trusted_url),
                allow_redirects=False,
                timeout=(10, 30),
                stream=True,
            ) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers["Location"])
                    continue
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > max_size:
                        raise ValueError("Downloaded content exceeds the size limit")
                return content.decode("utf-8-sig")
    raise requests.TooManyRedirects("Too many redirects while downloading code")


client_id_ctx: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "astralix_client_id",
    default=None,
)


def get_client_id() -> int | None:
    """Get id of the client, which owns the current execution context"""
    return client_id_ctx.get()


def set_client_id(client_id: int | None):
    """Bind the current execution context and its future tasks to the client"""
    if isinstance(client_id, int):
        client_id_ctx.set(client_id)


def resolve_client_id(instance, path: str) -> int | None:
    """Read client id from the attribute chain of `instance`"""
    value = instance
    for attr in path.split("."):
        value = getattr(value, attr, None)
        if value is None:
            return None

    return value if isinstance(value, int) else None


@contextlib.contextmanager
def client_id_override(client_id: int | None):
    """Bind the block to the client, detaching it from the outer one if `None`"""
    token = client_id_ctx.set(client_id)
    try:
        yield
    finally:
        try:
            client_id_ctx.reset(token)
        except ValueError:
            pass


@contextlib.contextmanager
def client_id_scope(client_id: int | None):
    """Bind the block to the client, keeping the outer one if there is no id"""
    if not isinstance(client_id, int):
        yield
        return

    with client_id_override(client_id):
        yield


def tag_client_id(path: str) -> Callable:
    """Bind the decorated method to the client, read from `self.<path>`"""

    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(self, *args, **kwargs):
                with client_id_scope(resolve_client_id(self, path)):
                    return await func(self, *args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            with client_id_scope(resolve_client_id(self, path)):
                return func(self, *args, **kwargs)

        return wrapper

    return decorator

_background_tasks: set[asyncio.Task] = set()


def _track_task(task: asyncio.Task) -> asyncio.Task:
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


def install_task_tracking():
    loop_cls = asyncio.base_events.BaseEventLoop
    if getattr(loop_cls.create_task, "_astralix_tracked", False):
        return

    original_create_task = loop_cls.create_task

    def create_task(self, coro, **kwargs):
        return _track_task(original_create_task(self, coro, **kwargs))

    create_task._astralix_tracked = True
    loop_cls.create_task = create_task

async def fw_protect():
    await asyncio.sleep(random.randint(1000, 2000) / 1000)


def restart():
    """Replace this process in place, preserving interpreter, cwd and CLI options."""
    if "--sandbox" in sys.argv[1:]:
        raise SystemExit(0)

    env = os.environ.copy()
    env.pop("ASTRALIX_DO_NOT_RESTART", None)
    env.pop("ASTRALIX_DO_NOT_RESTART2", None)
    # Keep the checkout importable even when started outside its directory.
    root = str(Path(__file__).resolve().parent.parent)
    paths = env.get("PYTHONPATH", "").split(os.pathsep)
    env["PYTHONPATH"] = os.pathsep.join([root, *(p for p in paths if p and p != root)])
    print("🔄 Restarting...", flush=True)
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            stream.flush()
    # An exec failure raises while the current application is still connected.
    os.execve(sys.executable, [sys.executable, "-m", "astralix", *sys.argv[1:]], env)


def print_banner(banner: str):
    from ._branding import LOGIN_STAGES, login_banner
    import shutil

    color = sys.stdout.isatty() and "--no-tty" not in sys.argv and "NO_COLOR" not in os.environ
    if banner in LOGIN_STAGES:
        print(login_banner(banner, color=color, width=shutil.get_terminal_size((80, 24)).columns))
    else:
        print((Path(__file__).resolve().parent.parent / "assets" / banner).read_text())
