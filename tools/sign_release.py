# © LowSense, 2026 · astralix Userbot · GNU AGPLv3
"""Sign a reviewed commit locally. Private signing keys never belong on Forgejo.

Usage: python tools/sign_release.py --key /private/release.pem --channel dev
       --commit <full SHA> --sequence <increasing integer> --output /tmp/dev.json
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives import serialization
from astralix._release_trust import canonical


def build(commit, channel, sequence):
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', commit + '^{commit}'], text=True).strip()
    files = {}
    tree = subprocess.check_output(['git', 'ls-tree', '-r', '-z', commit])
    for record in tree.split(b'\0'):
        if not record:
            continue
        metadata, name = record.split(b'\t', 1)
        mode, kind, oid = metadata.split()
        if kind != b'blob' or mode not in (b'100644', b'100755'):
            raise ValueError('Release contains symlinks or submodules')
        data = subprocess.check_output(['git', 'cat-file', 'blob', oid.decode()])
        files[name.decode()] = {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    now = int(time.time())
    return {'schema': 1, 'channel': channel, 'commit': commit, 'sequence': sequence,
            'issued': now, 'expires': now + 30 * 86400, 'files': files}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key', type=Path, required=True)
    parser.add_argument('--channel', choices=['main', 'dev'], required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--sequence', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    key = serialization.load_pem_private_key(args.key.read_bytes(), password=None)
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    payload = build(args.commit, args.channel, args.sequence)
    envelope = {'signed': payload, 'keyid': hashlib.sha256(public).hexdigest(),
                'signature': base64.b64encode(key.sign(canonical(payload))).decode()}
    args.output.write_bytes(canonical(envelope) + b'\n')
