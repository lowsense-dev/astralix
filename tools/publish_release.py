# © LowSense, 2026 · astralix Userbot · GNU AGPLv3
"""Publish signed metadata for an explicitly reviewed commit, without force pushes.

Run on the signing machine, after CI succeeds:
python tools/publish_release.py --channel dev --commit <full SHA>
The private key is read locally, never uploaded or supplied to Git.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from sign_release import build, canonical
from astralix._release_trust import verify_manifest
from cryptography.hazmat.primitives import serialization


def git(*args, cwd=None):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()


def publish(channel, commit, key_path, remote):
    if not key_path.is_file() or key_path.stat().st_mode & 0o077:
        raise ValueError('Signing key must exist and be accessible only to its owner')
    commit = git('rev-parse', '--verify', '--end-of-options', commit + '^{commit}')
    git('fetch', remote, channel)
    if git('rev-parse', 'FETCH_HEAD') != commit:
        raise ValueError('Publish the exact remote branch tip after reviewing CI')
    payload = build(commit, channel, int(time.time()))
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    keyid = hashlib.sha256(public).hexdigest()
    trusted = json.loads((Path(__file__).resolve().parents[1] / 'astralix/release-keys.json').read_text())
    if trusted.get(keyid) != base64.b64encode(public).decode():
        raise ValueError('Signing key does not match the published trust root')
    with tempfile.TemporaryDirectory(prefix='astralix-publish-') as directory:
        url = git('remote', 'get-url', remote)
        git('init', '--quiet', directory)
        git('config', 'user.name', 'LowSense release signing', cwd=directory)
        git('config', 'user.email', 'release@astralix.cc', cwd=directory)
        git('remote', 'add', 'origin', url, cwd=directory)
        if git('ls-remote', '--heads', 'origin', 'release-metadata', cwd=directory):
            git('fetch', 'origin', 'release-metadata', cwd=directory)
            git('checkout', '-b', 'release-metadata', 'FETCH_HEAD', cwd=directory)
        else:
            git('checkout', '--orphan', 'release-metadata', cwd=directory)
        path = Path(directory) / f'{channel}.json'
        if path.exists():
            raw = path.read_text()
            previous = json.loads(raw)['signed']
            verify_manifest(raw, channel, previous['commit'], trusted=trusted, now=previous['issued'])
            payload['sequence'] = max(payload['sequence'], previous['sequence'] + 1)
        envelope = {'signed': payload, 'keyid': keyid,
                    'signature': base64.b64encode(key.sign(canonical(payload))).decode()}
        path.write_bytes(canonical(envelope) + b'\n')
        git('add', path.name, cwd=directory)
        git('commit', '-m', f'Authorize {channel} release {commit[:12]}', cwd=directory)
        git('push', 'origin', 'release-metadata', cwd=directory)
    print(f'Published signed {channel} release {commit[:12]}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--channel', choices=['dev', 'main'], required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--remote', default='origin')
    parser.add_argument('--key', type=Path, default=Path.home() / '.local/share/astralix-signing/release.pem')
    args = parser.parse_args()
    publish(args.channel, args.commit, args.key, args.remote)
