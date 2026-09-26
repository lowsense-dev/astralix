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
from unittest.mock import AsyncMock, Mock, patch

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

    def test_tl_dependency_uses_patched_source(self):
        source=Path(loader.IMPORT_PIP_ALIASES['astralixtl'])
        self.assertTrue(source.is_absolute())
        self.assertTrue((source/'pyproject.toml').is_file())

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
