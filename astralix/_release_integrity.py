# © LowSense, 2026 · astralix Userbot · GNU AGPLv3
"""Dependency-free file verification, usable by the release supervisor."""
import hashlib
import os
from pathlib import Path, PurePosixPath


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_files(root, files):
    root = Path(root).resolve()
    if not isinstance(files, dict) or not files or len(files) > 20000:
        raise ValueError('Invalid release file inventory')
    for name, entry in files.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name:
            raise ValueError('Unsafe release path')
        path = root / name
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents):
            raise ValueError('Symlinks are not allowed in releases')
        if not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError(f'Missing release file: {name}')
        if path.stat().st_size != entry['size'] or file_hash(path) != entry['sha256']:
            raise ValueError(f'Release checksum mismatch: {name}')
    # Imported Python files must not be shadowed by untracked source files.
    for path in (root / 'astralix').rglob('*.py'):
        if path.relative_to(root).as_posix() not in files:
            raise ValueError('Unexpected Python file in release')


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
