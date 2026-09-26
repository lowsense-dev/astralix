# ©️ radiocycle, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/radiocycle/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

# main constructs the runtime at import; isolate its data and CLI arguments.
_data = tempfile.TemporaryDirectory()
with patch.object(sys, 'argv', ['astralix', '--no-git', '--data-root', _data.name]):
    from astralix import main
    from astralix.translations import BaseTranslator
    from astralix._local_storage import LocalStorage
    from astralix.modules.updater import UpdaterMod
    from astralix import loader


class CoreAuditTests(unittest.IsolatedAsyncioTestCase):
    def test_multilanguage_pack_flattens_to_dictionaries(self):
        result = BaseTranslator()._get_pack_raw('en:\n  help:\n    greeting: Hello\nru:\n  help:\n    greeting: Привет\n', '.yml')
        self.assertEqual(result['ru']['astralix.modules.help.greeting'], 'Привет')
        self.assertEqual(result['en']['astralix.modules.help.greeting'], 'Hello')

    def test_reject_non_mapping_language_pack(self):
        with self.assertRaises(ValueError):BaseTranslator()._get_pack_raw('- item', '.yml')

    def test_cache_limits_encoded_bytes_and_allows_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = LocalStorage.__new__(LocalStorage)
            cache._path = directory
            cache._tracked_total_size = None
            with patch('astralix._local_storage.MAX_FILESIZE', 6), patch('astralix._local_storage.MAX_TOTALSIZE', 6):
                cache.save('repo','module','яяя')
                self.assertEqual(cache._total_size,6)
                cache.save('repo','module','яя')
                self.assertEqual(cache.fetch('repo','module'),'яя')
                self.assertEqual(cache._total_size,4)
                cache.save('repo','huge','яяяя')
                self.assertIsNone(cache.fetch('repo','huge'))

    def test_tl_dependency_uses_project_repository(self):
        source = "git+https://github.com/radiocycle/astralix-tl.git"
        self.assertEqual(loader.IMPORT_PIP_ALIASES['astralixtl'], source)
        requirements = Path(__file__).resolve().parents[1] / 'requirements.txt'
        self.assertIn(source, requirements.read_text().splitlines())

    async def test_failed_rollback_does_not_restart(self):
        module=UpdaterMod()
        module.strings={'rollback_process':'Rollback {num}'}
        module.restart_common=AsyncMock()
        process=Mock(returncode=1, communicate=AsyncMock(return_value=(b'',b'bad revision')))
        with patch('astralix.modules.updater.utils.answer',new=AsyncMock()), patch('astralix.modules.updater.asyncio.create_subprocess_exec',new=AsyncMock(return_value=process)):
            with self.assertRaises(RuntimeError):await module.rollback_confirm(Mock(),1)
        process.communicate.assert_awaited_once()
        module.restart_common.assert_not_awaited()

    async def test_rollback_rejects_invalid_callback_count(self):
        module=UpdaterMod()
        with self.assertRaises(ValueError):await module.rollback_confirm(Mock(),0)

    async def test_restart_survives_no_git_and_archive_checkout(self):
        from astralix.modules import updater
        for no_git in (True, False):
            with patch.object(updater, 'NO_GIT', no_git):
                module = UpdaterMod()
                module.get = Mock(side_effect=lambda key, default=None: {
                    'autoupdate_answered': True, 'do_not_create': True,
                }.get(key, default))
                module.set = Mock()
                module.inline = Mock()
                with patch.object(updater.git, 'Repo', side_effect=updater.git.exc.InvalidGitRepositoryError) as repo:
                    await module.client_ready()
                    if no_git:
                        repo.assert_not_called()
                self.assertFalse(module._git_available)
                module.restart_common = AsyncMock()
                message = Mock()
                with patch.object(updater.utils, 'get_args_raw', return_value='-f'):
                    await module.restart(message)
                module.restart_common.assert_awaited_once_with(message, False)

    async def test_autoupdate_prompt_failure_does_not_unload_updater(self):
        from astralix.modules import updater
        with patch.object(updater, 'NO_GIT', False):
            module = UpdaterMod()
            module.get = Mock(side_effect=lambda key, default=None: {'do_not_create': True}.get(key, default))
            module.set = Mock()
            module.strings = {'autoupdate': 'Enable automatic updates?'}
            module.tg_id = 1
            module.inline = Mock(bot=Mock(send_message=AsyncMock(side_effect=RuntimeError('unavailable'))))
            with patch.object(updater.git, 'Repo', return_value=MagicMock()):
                await module.client_ready()
            module.inline.bot.send_message.assert_awaited_once()

    async def test_local_banner_is_uploaded_without_exposing_file_path_in_rich_html(self):
        from astralix.utils import messages
        message = Mock(client=Mock(send_file=AsyncMock()), reply_to_msg_id=10)
        with patch.object(messages, 'get_chat_id', return_value=123), patch.object(messages, 'answer_with_media_fallback', new=AsyncMock()) as answer:
            await messages.answer_with_banner(message, banner='/tmp/banner.png', rich_message='<h1>astralix</h1>')
        message.client.send_file.assert_awaited_once_with(123, '/tmp/banner.png', reply_to=10, silent=True)
        answer.assert_awaited_once_with(message, rich_message='<h1>astralix</h1>')

    async def test_fresh_start_uses_browser_before_console_api_prompt(self):
        app = main.Astralix.__new__(main.Astralix)
        app.clients = []
        app.sessions = []
        app.arguments = Mock(no_auth=False, no_web=False, qr_login=True)
        app._web_initial_setup = AsyncMock(return_value=True)
        app._get_token = AsyncMock()
        await app._main()
        app._web_initial_setup.assert_awaited_once()
        app._get_token.assert_not_awaited()

    async def test_no_web_uses_interactive_console(self):
        app = main.Astralix.__new__(main.Astralix)
        app.arguments = Mock(no_auth=False, no_web=True, qr_login=False, tty=False)
        app.api_token = Mock(ID=123, HASH='a' * 32)
        app.conn = app.proxy = None
        app._web_initial_setup = AsyncMock()
        app._phone_login = AsyncMock(return_value=True)
        client = Mock(connect=AsyncMock())
        with patch.object(main, 'CustomTelegramClient', return_value=client), patch.object(main, 'print_banner'), patch('builtins.print'), patch('builtins.input', return_value='n') as prompt:
            self.assertTrue(await app._initial_setup())
        prompt.assert_called_once()
        app._phone_login.assert_awaited_once_with(client)
        app._web_initial_setup.assert_not_awaited()

    async def test_web_login_stops_http_before_saving_and_always_cleans_up(self):
        app = main.Astralix.__new__(main.Astralix)
        app.api_token = None
        app.arguments = Mock(web_port=8765)
        app._get_api_token = Mock()
        order = []
        async def save(client):
            order.append('save')
            raise OSError('disk failure')
        app.save_client_session = AsyncMock(side_effect=save)
        done = asyncio.Event()
        done.set()
        async def stop():
            order.append('stop')
        async def close():
            order.append('close')
        login = Mock(
            credentials=(123, 'a' * 32), done=done, port=8765,
            start=AsyncMock(return_value='http://127.0.0.1:8765/'),
            stop_server=AsyncMock(side_effect=stop), close=AsyncMock(side_effect=close),
        )
        with patch('astralix._web_login.WebLogin', return_value=login), patch.object(main, 'save_config_key'), patch.object(main, 'print_banner'), patch('builtins.print'), patch.object(main.asyncio, 'sleep', new=AsyncMock()):
            with self.assertRaises(OSError):
                await app._web_initial_setup()
        self.assertEqual(order, ['stop', 'save', 'close'])
