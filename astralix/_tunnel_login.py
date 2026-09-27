# © LowSense, 2026 · astralix Userbot · GNU AGPLv3
# https://github.com/lowsense-dev/astralix
"""Publish the loopback login page through an ephemeral Cloudflare tunnel."""
import asyncio
import contextlib
import re
import shutil

from ._web_login import WebLogin, TTL


TUNNEL_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


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
        cloudflared = shutil.which("cloudflared")
        if not cloudflared:
            raise ConnectionError(
                "Install cloudflared or choose local web login / --no-web"
            )
        local_link = await super().start(port)
        self.process = await asyncio.create_subprocess_exec(
            cloudflared, "tunnel", "--no-autoupdate", "--url", self.origin,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            while True:
                line = await asyncio.wait_for(self.process.stdout.readline(), timeout=30)
                if not line:
                    raise ConnectionError("cloudflared exited before creating a tunnel")
                match = TUNNEL_URL.search(line.decode(errors="replace"))
                if match:
                    self.external_origin = match.group(0)
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
                raise ConnectionError("cloudflared tunnel stopped")
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
