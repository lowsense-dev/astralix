# ©️ radiocycle, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/radiocycle/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import io
import unittest
from unittest.mock import patch
import zipfile
from astralix._backup import module_plan


def archive(entries):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('db_mods.json','{}')
        for name,content in entries:z.writestr(name,content)
    return data.getvalue()


class BackupTests(unittest.TestCase):
    def test_regular_module_backup(self):
        self.assertEqual(module_plan(archive([('test.py','x=1')])),({}, {'test.py':b'x=1'}))

    def test_traversal_and_collisions_rejected(self):
        for entries in [[('../test.py','x')],[('a/test.py','x'),('b/test.py','y')]]:
            with self.assertRaises(ValueError):module_plan(archive(entries))

    def test_expansion_rejected_before_read(self):
        data=archive([('large.py','a'*1000)])
        with patch('astralix._backup.MAX_ARCHIVE_SIZE',500):
            with self.assertRaises(ValueError):module_plan(data)
