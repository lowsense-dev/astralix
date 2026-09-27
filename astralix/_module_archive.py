# ©️ LowSense, 2026
# This file is a part of astralix Userbot
# https://github.com/lowsense-dev/astralix · GNU AGPLv3
"""Portable module sources, without account databases or Telegram sessions."""
import hashlib
import io
import json
import zipfile

LIMIT = 32 * 1024 * 1024
MAX_MODULES = 200


def encode(modules):
    if len(modules) > MAX_MODULES:
        raise ValueError("Too many modules in one archive")
    stream = io.BytesIO()
    manifest = {"format": "astralix-modules", "version": 1, "modules": []}
    total = 0
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, details in sorted(modules.items()):
            if not name.isidentifier():
                raise ValueError("Invalid module class name")
            item = {"name": name, "origin": details.get("origin", "<file>")}
            source = details.get("source")
            if source is not None:
                data = source.encode("utf-8")
                total += len(data)
                if total > LIMIT:
                    raise ValueError("Module sources exceed the archive size limit")
                item.update(file=f"modules/{name}.py", sha256=hashlib.sha256(data).hexdigest())
                archive.writestr(item["file"], data)
            manifest["modules"].append(item)
        metadata = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
        if total + len(metadata) > LIMIT:
            raise ValueError("Module archive exceeds the unpacked size limit")
        archive.writestr("manifest.json", metadata)
    if stream.tell() > LIMIT:
        raise ValueError("Module archive exceeds the compressed size limit")
    stream.seek(0)
    stream.name = "astralix-modules.zip"
    return stream


def decode(data):
    if len(data) > LIMIT:
        raise ValueError("Archive is too large")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_MODULES + 1 or sum(item.file_size for item in entries) > LIMIT:
            raise ValueError("Archive exceeds the unpacked size limit")
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)) or "manifest.json" not in names:
            raise ValueError("Invalid archive entries")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != "astralix-modules" or manifest.get("version") != 1:
            raise ValueError("Unsupported archive format")
        modules = manifest.get("modules")
        if not isinstance(modules, list) or len(modules) > MAX_MODULES:
            raise ValueError("Invalid module list")
        result, allowed = {}, {"manifest.json"}
        for item in modules:
            name = item.get("name")
            if not isinstance(name, str) or not name.isidentifier() or name in result:
                raise ValueError("Invalid or duplicate module class name")
            source = None
            if "file" in item:
                filename = f"modules/{name}.py"
                if item["file"] != filename:
                    raise ValueError("Invalid module source path")
                allowed.add(filename)
                payload = archive.read(filename)
                if hashlib.sha256(payload).hexdigest() != item.get("sha256"):
                    raise ValueError("Module source checksum mismatch")
                source = payload.decode("utf-8")
            result[name] = source
        if set(names) != allowed:
            raise ValueError("Unexpected files in module archive")
        return result
