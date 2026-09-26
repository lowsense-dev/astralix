# ©️ LowSense, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/lowsense-dev/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""Validate backup archives completely before applying their contents."""
import io
import json
from pathlib import PurePosixPath
import zipfile

MAX_ARCHIVE_SIZE = 100 * 1024 * 1024
MAX_ENTRY_SIZE = 5 * 1024 * 1024
MAX_ENTRIES = 1000


def read_entry(archive, name, limit=MAX_ENTRY_SIZE):
    info = archive.getinfo(name)
    if info.file_size > limit:
        raise ValueError("Backup entry exceeds size limit")
    with archive.open(info) as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Backup entry exceeds size limit")
    return data


def module_plan(data):
    if len(data) > MAX_ARCHIVE_SIZE:
        raise ValueError("Backup archive exceeds size limit")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ENTRIES or sum(i.file_size for i in infos) > MAX_ARCHIVE_SIZE:
            raise ValueError("Expanded backup exceeds limits")
        if len({i.filename for i in infos}) != len(infos):
            raise ValueError("Duplicate backup entries")
        modules = json.loads(read_entry(archive, "db_mods.json"))
        if not isinstance(modules, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and v.startswith("https://")
            for k, v in modules.items()
        ):
            raise ValueError("Invalid module URL mapping")
        files = {}
        for info in infos:
            name = PurePosixPath(info.filename)
            if info.is_dir() or name.suffix != ".py":
                continue
            if name.is_absolute() or ".." in name.parts or "\\" in info.filename:
                raise ValueError("Unsafe module filename")
            if name.name in files:
                raise ValueError("Conflicting module filenames")
            files[name.name] = read_entry(archive, info.filename)
        return modules, files
