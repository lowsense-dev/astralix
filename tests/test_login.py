# ©️ radiocycle, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/radiocycle/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from astralix._login import LoginSessions, login_step


class LoginTests(unittest.IsolatedAsyncioTestCase):
    async def test_other_actor_cannot_submit_credentials(self):
        handler = AsyncMock()
        guarded = login_step(starts=True)(handler)
        call = SimpleNamespace(from_user=SimpleNamespace(id=2), answer=AsyncMock())
        await guarded(SimpleNamespace(), call, 'secret', SimpleNamespace(id=1))
        handler.assert_not_awaited()
        call.answer.assert_awaited_once()

    async def test_expired_session_cannot_sign_in(self):
        handler = AsyncMock()
        guarded = login_step()(handler)
        call = SimpleNamespace(from_user=SimpleNamespace(id=1), answer=AsyncMock())
        await guarded(SimpleNamespace(_login_sessions={}), call, '12345', object(), 'phone', SimpleNamespace(id=1))
        handler.assert_not_awaited()

    async def test_concurrent_completion_consumes_session_once(self):
        client = object()
        state = SimpleNamespace(_login_sessions={client: (1, asyncio.Lock(), Mock())})
        calls = []
        @login_step()
        async def complete(self, call, data, client, phone, user):
            await asyncio.sleep(0)
            self._login_sessions.pop(client)
            calls.append(client)
        call = SimpleNamespace(from_user=SimpleNamespace(id=1), answer=AsyncMock())
        await asyncio.gather(*(complete(state, call, '12345', client, 'phone', SimpleNamespace(id=1)) for _ in range(2)))
        self.assertEqual(calls, [client])

    async def test_cleanup_disconnects_and_cancels_expiry(self):
        client = Mock(disconnect=AsyncMock())
        timer = Mock()
        module = LoginSessions()
        module._login_sessions = {client: (1, asyncio.Lock(), timer)}
        await module._expire_login(client)
        self.assertEqual(module._login_sessions, {})
        client.disconnect.assert_awaited_once()
        timer.cancel.assert_called_once()
