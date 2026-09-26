# © LowSense, 2026 · astralix Userbot · GNU AGPLv3
# https://github.com/lowsense-dev/astralix
"""Outbound login-only relay. No local listening socket or arbitrary proxying."""
import asyncio
import base64
import contextlib
import json
import secrets
import time
from urllib.parse import urlencode

import aiohttp
from aiohttp import web
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ._web_login import WebLogin, TTL

ORIGIN = "https://tunnel.astralix.cc"


def derive_key(secret, direction):
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None,
        info=f"astralix-login-v1:{direction}".encode(),
    ).derive(secret)


class TunnelLogin(WebLogin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.http = self.socket = self.reader = None
        self.sid = None
        self.receive_cipher = self.send_cipher = None

    async def start(self, port=None):
        self.http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))
        async with self.http.post(f"{ORIGIN}/v1/create", json={}) as response:
            if response.status != 201:
                raise ConnectionError("Tunnel service could not create a login session")
            details = await response.json()
        self.sid = details["id"]
        secret = secrets.token_bytes(32)
        encoded = base64.urlsafe_b64encode(secret).decode().rstrip("=")
        self.receive_cipher = AESGCM(derive_key(secret, "request"))
        self.send_cipher = AESGCM(derive_key(secret, "response"))
        for value in (encoded, details["owner"], details["ticket"]):
            self.register_secret(value)
        self.socket = await self.http.ws_connect(
            f"{ORIGIN}/v1/connect", heartbeat=25, max_msg_size=16384,
        )
        await self.socket.send_json({"role": "owner", "id": self.sid, "token": details["owner"]})
        hello = await self.socket.receive_json(timeout=15)
        if hello != {"ready": True}:
            raise ConnectionError("Tunnel service rejected the connection")
        self.expires = time.monotonic() + TTL
        self.reader = asyncio.create_task(self._receive())
        # Fragment secrets are not sent in the HTTP request or Referer.
        return f"{ORIGIN}/#" + urlencode({"id": self.sid, "ticket": details["ticket"], "secret": encoded})

    async def wait_completed(self):
        done = asyncio.create_task(self.done.wait())
        try:
            finished, _ = await asyncio.wait(
                (done, self.reader), timeout=TTL, return_when=asyncio.FIRST_COMPLETED,
            )
            if not finished:
                raise asyncio.TimeoutError()
            if self.reader in finished:
                await self.reader
                if not self.done.is_set():
                    raise ConnectionError("Tunnel disconnected; restart to get a new login link")
        finally:
            done.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await done

    async def _receive(self):
        expected = 0
        async for message in self.socket:
            if message.type != aiohttp.WSMsgType.TEXT:
                break
            try:
                frame = json.loads(message.data)
                seq = frame["seq"]
                if type(seq) is not int or seq != expected or seq >= 128:
                    raise ValueError("Invalid sequence")
                nonce = seq.to_bytes(12, "big")
                raw = self.receive_cipher.decrypt(
                    nonce, base64.b64decode(frame["data"], validate=True),
                    f"{self.sid}:request:{seq}".encode(),
                )
                if len(raw) > 4096:
                    raise ValueError("Oversized request")
                request = json.loads(raw)
                expected += 1
            except Exception:
                raise ConnectionError("Tunnel authentication failed") from None
            try:
                if time.monotonic() >= self.expires:
                    raise web.HTTPGone()
                if not isinstance(request, dict):
                    raise web.HTTPBadRequest()
                if request.get("path") == "/api/state" and set(request) == {"path"}:
                    result = {"stage": self.stage, "csrf": ""}
                    status = 200
                elif request.get("path") == "/api/step" and set(request) == {"path", "data"}:
                    response = await self.submit(request["data"])
                    result, status = json.loads(response.body), response.status
                else:
                    raise web.HTTPBadRequest()
            except web.HTTPException as error:
                result, status = {"error": "bad"}, error.status
            except Exception:
                result, status = {"error": "internal"}, 500
            payload = json.dumps({"status": status, "result": result}).encode()
            encrypted = self.send_cipher.encrypt(
                nonce, payload, f"{self.sid}:response:{seq}".encode(),
            )
            await self.socket.send_json({"seq": seq, "data": base64.b64encode(encrypted).decode()})

    async def stop_server(self):
        if self.reader:
            self.reader.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self.reader
            self.reader = None
        if self.socket:
            await self.socket.close()
            self.socket = None
        if self.http:
            await self.http.close()
            self.http = None
        self.receive_cipher = self.send_cipher = None
