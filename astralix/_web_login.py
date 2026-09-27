# ©️ LowSense, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/lowsense-dev/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""Temporary, loopback-only first-login server."""
import asyncio
import base64
from collections import deque
import hashlib
from pathlib import Path
import re
import secrets
import time

from aiohttp import web
from astralixtl.errors import (
    ApiIdInvalidError, FloodWaitError, PasswordHashInvalidError,
    PhoneCodeExpiredError, PhoneCodeInvalidError, PhoneNumberInvalidError,
    SessionPasswordNeededError,
)

from .qr import QRCode

ASSETS = Path(__file__).with_name("web")
TTL = 900


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class WebLogin:
    def __init__(
        self,
        client_factory,
        credentials=None,
        register_secret=lambda value: None,
        save_credentials=lambda credentials: None,
    ):
        self.client_factory = client_factory
        self.credentials = credentials
        self.register_secret = register_secret
        self.save_credentials = save_credentials
        self.client = None
        self.qr_login = self.qr_code = None
        self.stage = "phone" if credentials else "api"
        self.phone = None
        self.phone_code_hash = None
        self.done = asyncio.Event()
        self.lock = asyncio.Lock()
        self.origin = ""
        self.runner = None
        self.expires = time.monotonic() + TTL
        self.key = secrets.token_urlsafe(32)
        self.key_hash = digest(self.key)
        self.session_hash = None
        self.csrf = secrets.token_urlsafe(32)
        self.attempts = deque(maxlen=10)
        self.phone_attempts = deque(maxlen=3)
        self.rpc_attempts = deque(maxlen=10)
        self.blocked_until = 0
        self.app = web.Application(client_max_size=4096, middlewares=[self.guard])
        for path in ("/", "/app.css", "/app.js", "/tunnel.js"):
            self.app.router.add_get(path, self.asset)
        self.app.router.add_post("/api/unlock", self.unlock)
        self.app.router.add_get("/api/state", self.state)
        self.app.router.add_post("/api/step", self.step)

    @property
    def cookie_name(self):
        return "astralix_login_" + self.origin.rsplit(":", 1)[-1]

    async def start(self, port=8765):
        self.runner = web.AppRunner(self.app, access_log=None, shutdown_timeout=5)
        await self.runner.setup()
        try:
            await web.TCPSite(self.runner, "127.0.0.1", port).start()
            self.port = self.runner.addresses[0][1]
            self.origin = f"http://127.0.0.1:{self.port}"
        except BaseException:
            await self.close()
            raise
        link = f"{self.origin}/#key={self.key}"
        self.register_secret(self.key)
        self.key = None
        return link

    async def close(self):
        self.key = self.key_hash = self.session_hash = None
        self.qr_login = self.qr_code = None
        await self.stop_server()
        if self.client:
            await self.client.disconnect()
            self.client = None

    async def stop_server(self):
        if self.runner:
            await self.runner.cleanup()
            self.runner = None

    @web.middleware
    async def guard(self, request, handler):
        try:
            # Bind to one exact origin; ignore all proxy/forwarded headers.
            if request.host != self.origin.removeprefix("http://"):
                raise web.HTTPForbidden()
            if request.headers.get("Origin", self.origin) != self.origin:
                raise web.HTTPForbidden()
            if request.headers.get("Sec-Fetch-Site") in {"cross-site", "same-site"}:
                raise web.HTTPForbidden()
            if request.method not in {"GET", "HEAD"}:
                if request.headers.get("Origin") != self.origin:
                    raise web.HTTPForbidden()
                if request.content_type != "application/json":
                    raise web.HTTPUnsupportedMediaType()
            if request.path.startswith("/api/"):
                if time.monotonic() >= self.expires:
                    raise web.HTTPGone()
                if request.path != "/api/unlock":
                    token = request.cookies.get(self.cookie_name, "")
                    if not self.session_hash or not secrets.compare_digest(digest(token), self.session_hash):
                        raise web.HTTPUnauthorized()
                    if request.method not in {"GET", "HEAD"}:
                        if not secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), self.csrf):
                            raise web.HTTPForbidden()
            response = await handler(request)
        except web.HTTPException as exc:
            response = web.json_response({"error": exc.reason}, status=exc.status)
        except Exception:
            # Never log request bodies, RPC exceptions or credentials.
            response = web.json_response({"error": "internal"}, status=500)
        response.headers.update({
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; object-src 'none'",
            "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin",
        })
        return response

    async def asset(self, request):
        name, mime = {"/": ("index.html", "text/html"), "/app.css": ("app.css", "text/css"), "/app.js": ("app.js", "application/javascript"), "/tunnel.js": ("tunnel.js", "application/javascript")}[request.path]
        return web.Response(body=(ASSETS / name).read_bytes(), content_type=mime)

    async def body(self, request):
        try:
            data = await request.json()
        except (ValueError, UnicodeError):
            raise web.HTTPBadRequest() from None
        if not isinstance(data, dict) or any(not isinstance(v, str) or len(v) > 1024 for v in data.values()):
            raise web.HTTPBadRequest()
        return data

    def throttle(self, bucket, interval):
        now = time.monotonic()
        if len(bucket) == bucket.maxlen and now - bucket[0] < interval:
            raise web.HTTPTooManyRequests()
        bucket.append(now)

    async def unlock(self, request):
        self.throttle(self.attempts, 60)
        data = await self.body(request)
        if set(data) != {"key"}:
            raise web.HTTPBadRequest()
        if not self.key_hash or not secrets.compare_digest(digest(data["key"]), self.key_hash):
            raise web.HTTPUnauthorized()
        # Atomically consume the bootstrap key before any await.
        self.key_hash = None
        token = secrets.token_urlsafe(32)
        self.session_hash = digest(token)
        response = web.json_response({"ok": True})
        # HTTP cookie is intentionally limited to a loopback-only SSH endpoint.
        response.set_cookie(self.cookie_name, token, httponly=True, samesite="Strict", path="/", max_age=TTL)
        return response

    async def state(self, request):
        data = self.state_data()
        data["csrf"] = self.csrf
        return web.json_response(data)

    def state_data(self):
        data = {"stage": self.stage}
        if self.stage == "qr":
            data["qr"] = self.qr_code
        return data

    async def step(self, request):
        data = await self.body(request)
        return await self.submit(data)

    async def submit(self, data):
        if not isinstance(data, dict) or any(
            not isinstance(v, str) or len(v) > 1024 for v in data.values()
        ):
            raise web.HTTPBadRequest()
        async with self.lock:
            if time.monotonic() >= self.expires:
                raise web.HTTPGone()
            if time.monotonic() < self.blocked_until:
                return web.json_response({"error": "flood", "retry_after": max(1, int(self.blocked_until - time.monotonic()))}, status=429)
            expected = {"api": {"api_id", "api_hash"}, "phone": {"phone"}, "qr": {"qr"}, "code": {"code"}, "password": {"password"}}
            if self.stage not in expected or not (
                set(data) == expected[self.stage]
                or self.stage == "phone" and set(data) == {"qr"}
            ):
                raise web.HTTPConflict()
            for value in data.values():
                self.register_secret(value)
            try:
                await asyncio.wait_for(self.advance(data), timeout=45)
            except SessionPasswordNeededError:
                self.qr_login = self.qr_code = None
                self.stage = "password"
            except PhoneCodeInvalidError:
                return web.json_response({"error": "code"}, status=400)
            except PasswordHashInvalidError:
                return web.json_response({"error": "password"}, status=400)
            except PhoneCodeExpiredError:
                self.stage = "phone"
                return web.json_response({"error": "expired", "stage": self.stage}, status=400)
            except PhoneNumberInvalidError:
                return web.json_response({"error": "phone"}, status=400)
            except ApiIdInvalidError:
                if self.client:
                    await self.client.disconnect()
                    self.client = None
                self.credentials = None
                self.qr_login = self.qr_code = None
                self.save_credentials(None)
                self.stage = "api"
                return web.json_response({"error": "api", "stage": self.stage}, status=400)
            except FloodWaitError as exc:
                self.blocked_until = time.monotonic() + exc.seconds
                return web.json_response({"error": "flood", "retry_after": exc.seconds}, status=429)
            except (TimeoutError, ConnectionError, OSError):
                return web.json_response({"error": "network"}, status=503)
            return web.json_response(self.state_data())

    async def advance(self, data):
        if self.stage == "api":
            if not re.fullmatch(r"[0-9]{1,10}", data["api_id"]) or not 0 < int(data["api_id"]) < 2**31 or not re.fullmatch(r"[a-fA-F0-9]{32}", data["api_hash"]):
                raise web.HTTPBadRequest()
            self.credentials = (int(data["api_id"]), data["api_hash"])
            self.save_credentials(self.credentials)
            self.stage = "phone"
        elif self.stage == "phone":
            if data.get("qr") == "start":
                self.throttle(self.phone_attempts, 300)
                await self.connect_client()
                self.qr_login = await self.client.qr_login()
                self.set_qr_code()
                self.stage = "qr"
                return
            if not re.fullmatch(r"\+[0-9]{7,15}", data["phone"]):
                raise web.HTTPBadRequest()
            self.throttle(self.phone_attempts, 300)
            await self.connect_client()
            sent = await self.client.send_code_request(data["phone"])
            self.phone = data["phone"]
            self.phone_code_hash = sent.phone_code_hash
            self.stage = "code"
        elif self.stage == "qr":
            if data["qr"] != "poll":
                raise web.HTTPBadRequest()
            try:
                await self.qr_login.wait(10)
            except asyncio.TimeoutError:
                await self.qr_login.recreate()
                self.set_qr_code()
                return
            await self.finish_login()
        else:
            self.throttle(self.rpc_attempts, 60)
            if self.stage == "code":
                if not re.fullmatch(r"[0-9]{5,8}", data["code"]):
                    raise web.HTTPBadRequest()
                await self.client.sign_in(self.phone, code=data["code"], phone_code_hash=self.phone_code_hash)
            else:
                if not data["password"]:
                    raise web.HTTPBadRequest()
                await self.client.sign_in(password=data["password"])
            await self.finish_login()

    async def connect_client(self):
        if self.client is None:
            self.client = self.client_factory(*self.credentials)
        await self.client.connect()

    def set_qr_code(self):
        url = self.qr_login.url
        self.register_secret(url)
        qr = QRCode()
        qr.add_data(url)
        matrix = qr.get_matrix()
        packed = bytearray((len(matrix) ** 2 + 7) // 8)
        for offset, dark in enumerate(value for row in matrix for value in row):
            if dark:
                packed[offset // 8] |= 1 << (7 - offset % 8)
        self.qr_code = {"size": len(matrix), "data": base64.b64encode(packed).decode()}

    async def finish_login(self):
        if not await self.client.get_me():
            raise RuntimeError("Login did not authorize the client")
        self.phone = self.phone_code_hash = self.qr_login = self.qr_code = None
        self.stage = "done"
        self.done.set()
