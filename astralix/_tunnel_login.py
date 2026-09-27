# © LowSense, 2026 · astralix Userbot · GNU AGPLv3
# https://github.com/lowsense-dev/astralix
"""Publish the loopback login page through a temporary localhost.run SSH tunnel."""
import asyncio
import contextlib
import re
import shutil
from urllib.parse import urlsplit

from ._web_login import WebLogin, TTL


TUNNEL_URL = re.compile(r"https://[^\s<>\"']+")
TUNNEL_HOST_SUFFIXES = (".lhr.life", ".localhost.run")


def _public_tunnel_origin(output):
    clean_output = re.sub(r"\x1b\[[0-9;]*m", "", output)
    for candidate in TUNNEL_URL.findall(clean_output):
        try:
            parsed = urlsplit(candidate.rstrip(".,;:)"))
            port = parsed.port
        except ValueError:
            continue
        hostname = (parsed.hostname or "").lower()
        if (
            parsed.scheme == "https"
            and port is None
            and parsed.username is None
            and parsed.password is None
            and any(hostname.endswith(suffix) for suffix in TUNNEL_HOST_SUFFIXES)
        ):
            return f"https://{hostname}"
    return None


class TunnelLogin(WebLogin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.encrypted_transport = True
        self.process = None
        self.output_task = None

    async def _drain_output(self):
        if not self.process or not self.process.stdout:
            return
        while await self.process.stdout.readline():
            pass

    async def start(self, port=None):
        ssh = shutil.which("ssh")
        if not ssh:
            raise ConnectionError(
                "Install an OpenSSH client or choose local web login / --no-web"
            )

        local_link = await super().start(port)
        self.process = await asyncio.create_subprocess_exec(
            ssh,
            "-T",
            "-o", "BatchMode=yes",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=60",
            "-o", "ServerAliveCountMax=3",
            "-o", "StrictHostKeyChecking=accept-new",
            "-R", f"80:127.0.0.1:{self.port}",
            "nokey@localhost.run",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            while True:
                line = await asyncio.wait_for(self.process.stdout.readline(), timeout=45)
                if not line:
                    raise ConnectionError(
                        "localhost.run SSH tunnel exited before returning its URL"
                    )
                output = line.decode(errors="replace")
                if "tunneled with tls termination" not in output.lower():
                    continue
                self.external_origin = _public_tunnel_origin(output)
                if self.external_origin:
                    self.output_task = asyncio.create_task(self._drain_output())
                    break
        except BaseException:
            await self.stop_server()
            raise
        return local_link.replace(self.origin, self.external_origin, 1)

    async def wait_completed(self):
        finished = asyncio.create_task(self.done.wait())
        process_done = asyncio.create_task(self.process.wait())
        try:
            done, _ = await asyncio.wait(
                (finished, process_done), timeout=TTL,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                raise asyncio.TimeoutError()
            if self.process.returncode is not None and not self.done.is_set():
                raise ConnectionError("localhost.run SSH tunnel stopped")
        finally:
            finished.cancel()
            process_done.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await finished
            with contextlib.suppress(asyncio.CancelledError):
                await process_done

    async def stop_server(self):
        if self.output_task:
            self.output_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.output_task
            self.output_task = None
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
        self.process = None
        await super().stop_server()
