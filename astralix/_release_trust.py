# © LowSense, 2026 · astralix Userbot · GNU AGPLv3
"""Verify release authorization before invoking build tools or candidate Python."""
import base64
import json
import re
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def verify_manifest(raw, channel, target, trusted=None, seen=None, now=None):
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('Release manifest is too large')
    envelope = json.loads(raw)
    payload = envelope['signed']
    keys = trusted if trusted is not None else json.loads(Path(__file__).with_name('release-keys.json').read_text())
    key = keys.get(envelope['keyid'])
    if not key:
        raise ValueError('Release signer is not trusted')
    Ed25519PublicKey.from_public_bytes(base64.b64decode(key, validate=True)).verify(
        base64.b64decode(envelope['signature'], validate=True), canonical(payload),
    )
    now = int(time.time()) if now is None else now
    if payload['schema'] != 1 or payload['channel'] != channel or payload['commit'] != target:
        raise ValueError('Manifest does not authorize this release')
    if not isinstance(target, str) or not re.fullmatch(r'[a-f0-9]{40}', target):
        raise ValueError('Invalid release commit')
    if not payload['issued'] <= now + 300 or not now < payload['expires'] <= payload['issued'] + 31 * 86400:
        raise ValueError('Release metadata expired or has an invalid date')
    if type(payload['sequence']) is not int or payload['sequence'] < 1:
        raise ValueError('Invalid release sequence')
    if seen and (payload['sequence'] < seen['sequence'] or (
        payload['sequence'] == seen['sequence'] and payload['commit'] != seen['commit']
    )):
        raise ValueError('Refusing replayed or conflicting release metadata')
    return payload
