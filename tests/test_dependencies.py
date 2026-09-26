# ©️ radiocycle, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/radiocycle/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import ast
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from astralix._dependencies import dependency_installation, install_command

ROOT=Path(__file__).resolve().parent.parent


class DependencyTests(unittest.IsolatedAsyncioTestCase):
    def test_explicit_interpreter_and_argument_boundaries(self):
        with patch('astralix._dependencies.shutil.which',return_value='/usr/bin/uv'):
            cmd=install_command('some-package>=1','package ; echo injected')
        self.assertEqual(cmd[:5],['/usr/bin/uv','pip','install','--python',sys.executable])
        self.assertIn('package ; echo injected',cmd)
        self.assertNotIn('--user',cmd)

    async def test_startup_policy_propagates_and_resets(self):
        async def nested():
            with self.assertRaises(RuntimeError):install_command('missing')
        with dependency_installation(False):await asyncio.create_task(nested())
        with patch('astralix._dependencies.shutil.which',return_value='/usr/bin/uv'):
            self.assertEqual(install_command('valid')[0],'/usr/bin/uv')

    def test_startup_has_no_installer_or_restart(self):
        tree=ast.parse((ROOT/'astralix/__main__.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                name=ast.unparse(node.func)
                self.assertNotIn(name,('deps','restart','subprocess.run','install_command'))

    def test_missing_dependency_exits_without_installing(self):
        # -S hides installed packages, making this check independent of the test environment.
        result=subprocess.run([sys.executable,'-S','-m','astralix','--help'],cwd=ROOT,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,1)
        self.assertIn('Install dependencies explicitly',result.stdout)
        self.assertNotIn('Attempting dependencies installation',result.stdout)


if __name__=='__main__':unittest.main()
