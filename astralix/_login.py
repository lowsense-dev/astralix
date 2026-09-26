# ©️ radiocycle, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/radiocycle/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""Lifecycle and actor checks for temporary inline login sessions."""
import asyncio
from functools import wraps


def login_step(*, starts=False):
    """Bind sensitive login callbacks to their actor and serialize each session."""
    def decorate(func):
        @wraps(func)
        async def guarded(self, call, data, *args, **kwargs):
            user = args[0] if starts else args[2]
            if getattr(getattr(call, "from_user", None), "id", None) != user.id:
                await call.answer("This login belongs to another user.", show_alert=True)
                return
            if starts:
                if not hasattr(self, "_login_start_locks"):
                    self._login_start_locks = {}
                lock = self._login_start_locks.setdefault(user.id, asyncio.Lock())
                async with lock:
                    try:
                        return await func(self, call, data, *args, **kwargs)
                    except BaseException:
                        for client, state in list(getattr(self, "_login_sessions", {}).items()):
                            if state[0] == user.id:
                                await self._close_login(client)
                        raise
            client = args[0]
            state = getattr(self, "_login_sessions", {}).get(client)
            if not state or state[0] != user.id:
                await call.answer("Login expired. Start again.", show_alert=True)
                return
            async with state[1]:
                if client not in self._login_sessions:
                    return
                try:
                    return await func(self, call, data, *args, **kwargs)
                except BaseException:
                    await self._close_login(client)
                    raise
        return guarded
    return decorate


class LoginSessions:
    async def _close_login(self, client):
        state = getattr(self, "_login_sessions", {}).pop(client, None)
        if state:
            state[2].cancel()
        await client.disconnect()

    async def _expire_login(self, client):
        state = getattr(self, "_login_sessions", {}).get(client)
        if state:
            async with state[1]:
                await self._close_login(client)

    async def on_unload(self):
        for client in list(getattr(self, "_login_sessions", {})):
            await self._close_login(client)

