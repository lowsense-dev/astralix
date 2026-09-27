# © LowSense, 2026 · astralix Userbot · GNU AGPLv3
import base64
import hashlib
import json
import os
import signal
import time
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import AsyncMock
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
from astralix._release_trust import canonical, verify_manifest
from astralix._release_integrity import verify_files
from astralix._release_runner import atomic_json, snapshot_configs, restore_configs
from astralix._module_inventory import record, validate_requirements, declared, requirements_for_sources


class ReleaseSecurity(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        public = self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.trusted = {'test': base64.b64encode(public).decode()}
        self.payload = {'schema': 1, 'channel': 'dev', 'commit': 'a' * 40,
                        'sequence': 2, 'issued': 1000, 'expires': 2000, 'files': {}}

    def envelope(self):
        return canonical({'signed': self.payload, 'keyid': 'test',
                          'signature': base64.b64encode(self.key.sign(canonical(self.payload))).decode()})

    def verify(self, raw=None, **kw):
        return verify_manifest(raw or self.envelope(), 'dev', 'a' * 40,
                               trusted=self.trusted, now=1500, **kw)

    def test_signature_channel_expiry_and_replay(self):
        self.verify()
        envelope = json.loads(self.envelope())
        envelope['signed']['sequence'] = 500
        with self.assertRaises(InvalidSignature):
            self.verify(canonical(envelope))
        with self.assertRaises(ValueError):
            self.verify(seen={'sequence': 3, 'commit': 'a' * 40})
        with self.assertRaises(ValueError):
            self.verify(seen={'sequence': 2, 'commit': 'b' * 40})
        self.payload['channel'] = 'main'
        with self.assertRaises(ValueError):
            self.verify()
        self.payload['channel'] = 'dev'
        self.payload['expires'] = 1400
        with self.assertRaises(ValueError):
            self.verify()

    def test_tree_tampering_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'astralix').mkdir()
            path = root / 'astralix/main.py'
            path.write_bytes(b'pass\n')
            files = {'astralix/main.py': {'size': 5, 'sha256': hashlib.sha256(b'pass\n').hexdigest()}}
            verify_files(root, files)
            path.write_bytes(b'exit\n')
            with self.assertRaises(ValueError):
                verify_files(root, files)
            path.unlink()
            path.symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):
                verify_files(root, files)
            with self.assertRaises(ValueError):
                verify_files(root, {'../outside': {}})

    def test_atomic_write_keeps_old_state_on_failed_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            atomic_json(path, {'active': 'old'})
            with patch('astralix._release_runner.os.replace', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    atomic_json(path, {'active': 'new'})
            self.assertEqual(json.loads(path.read_text()), {'active': 'old'})
            self.assertEqual(len(list(path.parent.iterdir())), 1)

    def test_snapshot_excludes_sessions_and_restore_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            atomic_json(root / 'config.json', {'value': 'before'})
            (root / 'account.session').write_bytes(b'private')
            snapshot = snapshot_configs(root, root, 'test')
            self.assertEqual([p.name for p in Path(snapshot).iterdir()], ['config.json'])
            atomic_json(root / 'config.json', {'value': 'after'})
            self.assertEqual(json.loads((root / 'config.json').read_text())['value'], 'after')
            restore_configs(snapshot, root)
            self.assertEqual(json.loads((root / 'config.json').read_text())['value'], 'before')

    def test_module_provenance_and_installer_injection(self):
        before = record(None, 'pass', 'https://example.org/module.py', '1')
        same = record(before, 'pass', before['origin'], '1')
        self.assertEqual(len(same['history']), 1)
        changed = record(same, 'pass\n', same['origin'], '2')
        self.assertEqual(len(changed['history']), 2)
        self.assertNotEqual(changed['sha256'], before['sha256'])
        for invalid in ['--index-url', 'git+https://example.org/a', '/tmp/x.whl', 'a\n--trusted-host=x']:
            with self.assertRaises(ValueError):
                validate_requirements([invalid])
        self.assertEqual(validate_requirements(['requests>=2.0', 'x[y]==1.2']), ['requests>=2.0', 'x[y]==1.2'])

    def test_module_requirements_keep_optional_dependencies(self):
        self.assertEqual(declared('#requires: requests\n# scope:requires moviepy>=2'), ['requests', 'moviepy>=2'])
        lock = '''[[package]]
name = "astralix"
dependencies = [{name = "requests"}]
[package.optional-dependencies]
media = [{name = "moviepy"}]
[[package]]
name = "requests"
[[package]]
name = "moviepy"
'''
        with patch('astralix._module_inventory.metadata.packages_distributions', return_value={'requests': ['requests'], 'moviepy': ['moviepy']}), \
             patch('astralix._module_inventory.metadata.version', return_value='2.0'):
            self.assertEqual(requirements_for_sources(['import requests\nimport moviepy'], lock), ['moviepy==2.0'])

    @unittest.skipUnless(sys.platform == 'linux', 'Linux parent-death protection')
    def test_killed_supervisor_does_not_leave_an_orphan(self):
        supervisor = Path(__file__).resolve().parents[1] / 'astralix/_release_runner.py'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = root / '.astralix-releases'
            control.mkdir()
            package = root / 'astralix'
            package.mkdir()
            (package / '__init__.py').touch()
            (package / '__main__.py').write_text('import os,time\nfrom pathlib import Path\nPath("child.pid").write_text(str(os.getpid()))\ntime.sleep(60)\n')
            release = {'id': 'old', 'path': directory, 'python': sys.executable, 'commit': 'a', 'channel': 'dev'}
            atomic_json(control / 'state.json', {'active': release, 'pending': None, 'data_root': directory})
            parent = subprocess.Popen([sys.executable, str(supervisor), directory], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            child_pid = None
            try:
                for _ in range(100):
                    if (root / 'child.pid').exists():
                        child_pid = int((root / 'child.pid').read_text())
                        break
                    time.sleep(.05)
                self.assertIsNotNone(child_pid)
                parent.kill()
                parent.wait(timeout=5)
                for _ in range(100):
                    status = Path(f'/proc/{child_pid}/stat')
                    if not status.exists() or status.read_text().split()[2] == 'Z':
                        break
                    time.sleep(.02)
                else:
                    self.fail('Orphaned userbot survived supervisor SIGKILL')
            finally:
                if parent.poll() is None:
                    parent.kill()
                    parent.wait()
                if child_pid:
                    try:
                        os.kill(child_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                parent.stderr.close()

    def test_supervisor_rolls_back_failed_or_interrupted_candidate(self):
        supervisor = Path(__file__).resolve().parents[1] / 'astralix/_release_runner.py'
        for interrupted in (False, True):
            with self.subTest(interrupted=interrupted), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                control = root / '.astralix-releases'
                control.mkdir()
                for name, code in [('old', 'from pathlib import Path\nPath("running").touch()'),
                                   ('new', 'raise SystemExit(1)')]:
                    package = root / name / 'astralix'
                    package.mkdir(parents=True)
                    (package / '__init__.py').touch()
                    (package / '__main__.py').write_text(code)
                def release(name):
                    return {'id': name, 'path': str(root / name), 'python': sys.executable,
                            'commit': name, 'channel': 'dev'}
                pending = {'target': release('new'), 'timeout': 1, 'accounts': ['1'], 'core': []}
                if interrupted:
                    pending['started'] = 1
                atomic_json(control / 'state.json', {'active': release('old'), 'pending': pending,
                                                    'previous': None, 'data_root': directory, 'history': []})
                result = subprocess.run([sys.executable, str(supervisor), directory], capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertTrue((root / 'old/running').exists())
                state = json.loads((control / 'state.json').read_text())
                self.assertIsNone(state['pending'])
                self.assertEqual(state['active']['id'], 'old')

    def test_diagnostics_does_not_export_account_data(self):
        from astralix._diagnostics import report
        state = {'active': {'commit': 'a' * 40, 'channel': 'dev', 'path': '/home/private'},
                 'api_hash': 'sensitive', 'session': 'sensitive',
                 'history': [{'reason': 'sensitive', 'status': 'failed'}]}
        raw = json.dumps(report(state, []))
        self.assertNotIn('sensitive', raw)
        self.assertNotIn('/home/private', raw)


class UpdateInteraction(unittest.IsolatedAsyncioTestCase):
    async def invoke(self, arguments='', latest=False, inline=False):
        with tempfile.TemporaryDirectory() as data, patch.object(sys, 'argv', ['astralix', '--data-root', data]):
            from astralix import main
            from astralix.modules import updater
        from ruamel.yaml import YAML
        language = YAML(typ='safe').load((Path(__file__).resolve().parents[1] / 'astralix/langpacks/en.yml').read_text())
        strings = next(value for value in language.values() if isinstance(value, dict) and 'release_check' in value)
        fake = SimpleNamespace(_git_available=True, _channel=lambda: 'dev',
                               config={'GIT_ORIGIN_URL': 'https://git.astralix.cc'}, strings=strings,
                               inline=SimpleNamespace(init_complete=inline, form=AsyncMock(return_value=True)),
                               inline_update=AsyncMock(), _show_error=AsyncMock())
        report = {'current': 'a' * 40, 'target': ('a' if latest else 'b') * 40,
                  'channel': 'dev', 'branch': 'dev', 'dirty': '', 'changes': 'fix', 'dependencies': ''}
        with patch.object(updater.utils, 'get_args_raw', return_value=arguments), \
             patch.object(updater.utils, 'answer', new_callable=AsyncMock) as answer, \
             patch.object(updater.Updates, 'check', return_value=report):
            await updater.UpdaterMod.update(fake, object())
        return fake, answer

    async def test_latest_does_not_prepare(self):
        fake, answer = await self.invoke(latest=True)
        fake.inline_update.assert_not_awaited()
        fake._show_error.assert_not_awaited()
        self.assertEqual(answer.call_args.args[1], fake.strings['release_current'])

    async def test_no_inline_requires_explicit_force(self):
        fake, answer = await self.invoke()
        fake.inline_update.assert_not_awaited()
        fake._show_error.assert_not_awaited()
        self.assertIn('update -f', answer.call_args.args[1])

    async def test_confirmation_pins_commit(self):
        fake, _ = await self.invoke(inline=True)
        fake.inline_update.assert_not_awaited()
        self.assertEqual(fake.inline.form.call_args.kwargs['reply_markup'][0]['args'], (False, 'dev', 'b' * 40))

    async def test_force_does_not_skip_release_check(self):
        fake, _ = await self.invoke('-f')
        fake.inline_update.assert_awaited_once()
        self.assertEqual(fake.inline_update.call_args.kwargs['expected'], 'b' * 40)

    async def test_removed_arguments_are_rejected(self):
        fake, _ = await self.invoke('--check')
        fake.inline_update.assert_not_awaited()
        fake._show_error.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
