# © LowSense, 2026 · astralix Userbot · GNU AGPLv3
# https://github.com/lowsense-dev/astralix
"""Persistent shells with separate command and interactive-input pipes."""
import asyncio
import contextlib
import os
import secrets
import shlex
import signal
import sys


class SessionBusy(Exception):
    pass


class ShellSession:
    def __init__(self, shell, cwd):
        self.shell, self.cwd = shell, cwd
        self.process = None
        self._commands = None
        self._lock = asyncio.Lock()

    @property
    def busy(self):
        return self._lock.locked()

    async def start(self):
        if (
            self.process is not None and self.process.returncode is None
            and not self.process.stdin.is_closing()
        ):
            return
        await self.close()
        read_fd, write_fd = os.pipe()
        try:
            args = [f"/dev/fd/{read_fd}"]
            if os.path.basename(os.path.realpath(self.shell)) == "fish":
                # fish's read builtin may use fd 0 even with an fd redirect.
                # A small external reader keeps command input separate from
                # stdin used by sudo and user commands, without buffering ahead.
                reader = "import os,sys; b=bytearray(); c=os.read(0,1)\nwhile c and c!=b'\\0':\n b.extend(c); c=os.read(0,1)\nsys.stdout.buffer.write(b); sys.exit(0 if c else 1)"
                args = ["-c", (
                    "while true; set --local astralix_script ("
                    f"{shlex.quote(sys.executable)} -c {shlex.quote(reader)} <&{read_fd} | string collect); "
                    "or break; eval $astralix_script; end"
                )]
            self.process = await asyncio.create_subprocess_exec(
                self.shell, *args,
                pass_fds=(read_fd,), start_new_session=True,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, cwd=self.cwd,
            )
            self._commands = write_fd
        except BaseException:
            os.close(write_fd)
            raise
        finally:
            os.close(read_fd)

    async def close(self):
        if self._commands is not None:
            os.close(self._commands)
            self._commands = None
        if self.process is not None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(self.process.pid, signal.SIGKILL)
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self.process.wait(), timeout=3)
            self.process = None

    async def run(self, command, editor, delay):
        if self.busy:
            raise SessionBusy()
        async with self._lock:
            starting = asyncio.create_task(self.start())
            try:
                await asyncio.shield(starting)
            except BaseException:
                with contextlib.suppress(Exception):
                    await starting
                await self.close()
                raise
            process = self.process
            try:
                editor.update_process(process)
                await editor.redraw()
            except BaseException:
                await self.close()
                raise
            token = secrets.token_hex(24)
            marker = f"\x1e{token}:".encode()
            fish = os.path.basename(os.path.realpath(self.shell)) == "fish"
            status = "$status" if fish else "$?"
            quoted = "'" + command.replace("\\", "\\\\").replace("'", "\\'") + "'" if fish else shlex.quote(command)
            # eval runs in this shell, preserving cwd, variables and functions.
            # Its stdin remains available to sudo/read, not to the script parser.
            script = (
                f"eval {quoted}\n"
                f"printf '\\036{token}:%s\\037' \"{status}\"\n"
                f"printf '\\036{token}:0\\037' >&2\n"
            ).encode() + (b"\0" if fish else b"")

            def write_command():
                view = memoryview(script)
                while view:
                    view = view[os.write(self._commands, view):]

            readers = []
            try:
                await asyncio.to_thread(write_command)
                readers = [
                    asyncio.create_task(self._read_command(stream, marker, update, delay))
                    for stream, update in (
                        (process.stdout, editor.update_stdout),
                        (process.stderr, editor.update_stderr),
                    )
                ]
                results = await asyncio.gather(*readers)
                if results[0] is None or results[1] is None:
                    await process.wait()
                    return process.returncode
                return results[0]
            except BaseException:
                await self.close()
                raise
            finally:
                for reader in readers:
                    reader.cancel()
                await asyncio.gather(*readers, return_exceptions=True)
                if process.returncode is not None and self.process is process:
                    await self.close()

    @staticmethod
    async def _read_command(stream, marker, update, delay):
        pending, output = bytearray(), bytearray()
        interval = max(float(delay), 0.05)
        loop = asyncio.get_running_loop()
        last_update = loop.time()
        dirty = False
        while True:
            try:
                chunk = await asyncio.wait_for(stream.read(4096), interval)
            except asyncio.TimeoutError:
                chunk = None
            if chunk:
                pending.extend(chunk)
            index = pending.find(marker)
            end = pending.find(b"\x1f", index + len(marker)) if index >= 0 else -1
            finished = end >= 0 or chunk == b""
            keep = 0
            if index < 0 and not finished:
                for size in range(1, min(len(pending), len(marker) - 1) + 1):
                    if pending[-size:] == marker[:size]:
                        keep = size
            count = index if index >= 0 else len(pending) - keep
            if count:
                output.extend(pending[:count])
                del output[:-65536]
                del pending[:count]
                dirty = True
                if index >= 0:
                    end -= count
            if finished or dirty and loop.time() - last_update >= interval:
                await update(output.decode(errors="replace"))
                last_update = loop.time()
                dirty = False
            if finished:
                return int(pending[len(marker):end]) if end >= 0 else None
