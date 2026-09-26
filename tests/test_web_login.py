# ©️ radiocycle, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/radiocycle/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, Mock

from aiohttp import ClientSession, CookieJar
from astralixtl.errors import SessionPasswordNeededError, PasswordHashInvalidError, FloodWaitError
from astralix._web_login import WebLogin


class WebLoginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.telegram = Mock(
            connect=AsyncMock(), disconnect=AsyncMock(),
            send_code_request=AsyncMock(return_value=Mock(phone_code_hash="private-hash")),
            sign_in=AsyncMock(), get_me=AsyncMock(return_value=Mock(id=123)),
        )
        self.factory = Mock(return_value=self.telegram)
        self.login = WebLogin(self.factory)
        self.link = await self.login.start(0)
        self.http = ClientSession(cookie_jar=CookieJar(unsafe=True))
        self.headers = {"Origin": self.login.origin}

    async def asyncTearDown(self):
        await self.http.close()
        await self.login.close()

    async def post(self, path, data, headers=None):
        return await self.http.post(self.login.origin + path, json=data, headers=self.headers if headers is None else headers)

    async def unlock(self):
        response = await self.post("/api/unlock", {"key": self.link.split("#key=")[1]})
        self.assertEqual(response.status, 200)
        state = await self.http.get(self.login.origin + "/api/state")
        self.headers["X-CSRF-Token"] = (await state.json())["csrf"]
        return response

    async def phone_step(self):
        await self.unlock()
        self.assertEqual((await self.post("/api/step", {"api_id": "1234", "api_hash": "a" * 32})).status, 200)
        self.assertEqual((await self.post("/api/step", {"phone": "+79991234567"})).status, 200)

    async def test_api_requires_authentication_and_assets_have_security_headers(self):
        response = await self.http.get(self.login.origin + "/api/state")
        self.assertEqual(response.status, 401)
        response = await self.http.get(self.login.origin + "/")
        self.assertEqual(response.status, 200)
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertNotIn(self.link.split("#key=")[1], await response.text())

    async def test_one_use_link_and_cookie_flags(self):
        response = await self.unlock()
        cookie = response.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        response = await self.post("/api/unlock", {"key": self.link.split("#key=")[1]})
        self.assertEqual(response.status, 401)

    async def test_rebinding_cross_origin_and_missing_origin_rejected(self):
        for headers in ({"Host": "attacker.example"}, {"Origin": "https://evil.example"}, {"Sec-Fetch-Site": "cross-site", "Origin": self.login.origin}, {}):
            response = await self.post("/api/unlock", {"key": "bad"}, headers)
            self.assertEqual(response.status, 403)

    async def test_csrf_and_content_type_required(self):
        await self.unlock()
        response = await self.post("/api/step", {}, {"Origin": self.login.origin})
        self.assertEqual(response.status, 403)
        response = await self.http.post(self.login.origin + "/api/step", data="{}", headers=self.headers)
        self.assertEqual(response.status, 415)
        self.factory.assert_not_called()

    async def test_expired_session_rejected(self):
        await self.unlock()
        self.login.expires = time.monotonic() - 1
        self.assertEqual((await self.http.get(self.login.origin + "/api/state")).status, 410)

    async def test_bad_api_data_and_large_body_rejected(self):
        await self.unlock()
        for data in ({"api_id": "0", "api_hash": "a" * 32}, {"api_id": "123", "api_hash": []}, ["invalid"]):
            self.assertEqual((await self.post("/api/step", data)).status, 400)
        self.assertEqual((await self.post("/api/step", {"api_id": "1", "api_hash": "x" * 5000})).status, 413)
        self.factory.assert_not_called()

    async def test_two_factor_login_and_secret_not_returned(self):
        await self.phone_step()
        self.telegram.sign_in.side_effect = [SessionPasswordNeededError(None), PasswordHashInvalidError(None), None]
        response = await self.post("/api/step", {"code": "12345"})
        self.assertEqual((await response.json())["stage"], "password")
        response = await self.post("/api/step", {"password": "wrong"})
        self.assertEqual(response.status, 400)
        self.assertFalse(self.login.done.is_set())
        response = await self.post("/api/step", {"password": "  actual password  "})
        self.assertEqual((await response.json())["stage"], "done")
        self.telegram.sign_in.assert_awaited_with(password="  actual password  ")
        self.assertTrue(self.login.done.is_set())
        state = await (await self.http.get(self.login.origin + "/api/state")).json()
        self.assertEqual(set(state), {"stage", "csrf"})

    async def test_duplicate_code_submission_cannot_login_twice(self):
        await self.phone_step()
        responses = await asyncio.gather(*(self.post("/api/step", {"code": "12345"}) for _ in range(2)))
        self.assertEqual(sorted(r.status for r in responses), [200, 409])
        self.telegram.sign_in.assert_awaited_once()

    async def test_wrong_step_does_not_call_telegram(self):
        await self.unlock()
        self.assertEqual((await self.post("/api/step", {"password": "secret"})).status, 409)
        self.factory.assert_not_called()

    async def test_floodwait_blocks_further_rpc(self):
        await self.phone_step()
        self.telegram.sign_in.side_effect = FloodWaitError(None, capture=30)
        self.assertEqual((await self.post("/api/step", {"code": "12345"})).status, 429)
        self.assertEqual((await self.post("/api/step", {"code": "12345"})).status, 429)
        self.telegram.sign_in.assert_awaited_once()

    async def test_unlock_bruteforce_throttled(self):
        for _ in range(10):
            self.assertEqual((await self.post("/api/unlock", {"key": "bad"})).status, 401)
        self.assertEqual((await self.post("/api/unlock", {"key": "bad"})).status, 429)

    async def test_close_disconnects_unfinished_login(self):
        await self.phone_step()
        await self.login.close()
        self.telegram.disconnect.assert_awaited_once()
        self.assertIsNone(self.login.session_hash)

    async def test_static_routes_cannot_read_source(self):
        await self.unlock()
        for path in ("/main.py", "/api/config", "/%2e%2e/main.py"):
            self.assertEqual((await self.http.get(self.login.origin + path)).status, 404)
