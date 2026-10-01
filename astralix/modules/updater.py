# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/ZetGoHack/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ LowSense, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/lowsense-dev/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

from .._branding import LOGO_PATH, REPO_URL
import asyncio
import contextlib
import errno
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
import typing
from urllib.parse import urlsplit

import git
from git import Repo
from astralixtl.tl.functions.messages import (
    GetDialogFiltersRequest,
    UpdateDialogFilterRequest,
)
from astralixtl.tl.types import (
    DialogFilter,
    InputBotInlineMessageID,
    InputBotInlineMessageID64,
    Message,
    TextWithEntities,
)

from .. import loader, utils, version
from .._dependencies import PROJECT_ROOT, sync_command
from .._internal import restart
from ..inline.types import BotInlineCall, InlineCall

logger = logging.getLogger(__name__)
NO_GIT = os.environ.get("ASTRALIX_NO_GIT") == "1"

os.environ["GIT_TERMINAL_PROMPT"] = "0"
os.environ["GIT_ASKPASS"] = "echo"


@loader.tds
class UpdaterMod(loader.Module):
    """Update astralix from its Git repository and notify about new commits."""

    strings = {"name": "Updater"}
    _GIT_FETCH_INTERVAL = 300
    _EMFILE_FETCH_BACKOFF = 900

    def __init__(self):
        self._git_available = not NO_GIT
        self._notified = None
        self._last_emfile_warning = 0.0
        self._last_git_fetch = 0.0
        self._git_fetch_backoff_until = 0.0
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "GIT_ORIGIN_URL",
                REPO_URL,
                lambda: self.strings["origin_cfg_doc"],
                validator=loader.validators.Link(),
            ),
            loader.ConfigValue(
                "disable_notifications",
                doc=lambda: self.strings["_cfg_doc_disable_notifications"],
                validator=loader.validators.Boolean(),
            ),
        )


    @staticmethod
    def _is_emfile_error(error: BaseException) -> bool:
        current: BaseException | None = error
        while current is not None:
            if isinstance(current, OSError) and current.errno in (errno.EMFILE, errno.EAGAIN):
                return True

            current = current.__cause__ or current.__context__

        return False

    def _log_git_poll_error(self, error: Exception):
        if self._is_emfile_error(error):
            now = time.monotonic()
            self._git_fetch_backoff_until = max(
                self._git_fetch_backoff_until,
                now + self._EMFILE_FETCH_BACKOFF,
            )
            if now - self._last_emfile_warning >= 300:
                logger.warning(
                    "Failed to build changelog: too many open files; "
                    "pausing remote fetch attempts"
                )
                self._last_emfile_warning = now
        else:
            logger.exception("Failed to build changelog")

    def _format_changelog(self, commits: list[typing.Any]) -> str:
        entries = []
        for commit in commits[:10]:
            message = commit.message
            if isinstance(message, bytes):
                message = message.decode(errors="replace")

            title = message.splitlines()[0] if message.splitlines() else commit.hexsha
            entries.append(
                f"<b>{commit.hexsha[:7]}</b>:" f" <i>{utils.escape_html(title)}</i>"
            )

        res = "\n".join(entries)

        if len(commits) > 10:
            res += self.strings["more"].format(len(commits) - 10)

        return res

    def _get_update_state(self) -> tuple[str, str, str | typing.Literal[False]]:
        with git.Repo(PROJECT_ROOT) as repo:
            origin = repo.remote("origin")
            if origin.url != self.config["GIT_ORIGIN_URL"]:
                origin.set_url(self.config["GIT_ORIGIN_URL"])
            channel = repo.active_branch.name
            now = time.monotonic()
            if now >= self._git_fetch_backoff_until:
                if now - self._last_git_fetch >= self._GIT_FETCH_INTERVAL:
                    logger.debug("Fetching changelog from %s", origin.url)
                    with contextlib.suppress(Exception):
                        repo.git.fetch(
                            "--quiet", "origin",
                            f"+refs/heads/{channel}:refs/remotes/origin/{channel}",
                            kill_after_timeout=60,
                        )
                    self._last_git_fetch = now
            else:
                logger.debug(
                    "Skipping changelog fetch for %.0f more seconds after EMFILE",
                    self._git_fetch_backoff_until - now,
                )

            current = repo.head.commit.hexsha
            reference = f"origin/{channel}"
            try:
                repo.commit(reference)
            except (git.BadName, git.BadObject, ValueError):
                logger.debug("No remote tracking branch is available for %s", channel)
                return current, current, False
            latest = next(
                repo.iter_commits(reference, max_count=1)
            ).hexsha
            commits = [*repo.iter_commits(f"HEAD..{reference}")]

            return (
                current,
                latest,
                self._format_changelog(commits) if commits else False,
            )

    def get_changelog(self) -> str | typing.Literal[False]:
        if not self._git_available:
            return False
        try:
            return self._get_update_state()[2]
        except Exception as e:
            self._log_git_poll_error(e)
            return False

    def get_latest(self) -> str:
        if not self._git_available:
            return ""
        try:
            with git.Repo(PROJECT_ROOT) as repo:
                return next(repo.iter_commits(
                    f"origin/{repo.active_branch.name}", max_count=1
                )).hexsha
        except Exception:
            return ""

    @loader.loop(interval=60, autostart=True)
    async def poller(self):
        if not self._git_available:
            return
        try:
            current, self._pending, changelog = await utils.run_sync(self._get_update_state)
        except Exception as e:
            self._log_git_poll_error(e)
            return

        if self.config["disable_notifications"] or not changelog:
            return

        if (
            self.get("ignore_permanent", False)
            and self.get("ignore_permanent") == self._pending
        ):
            await asyncio.sleep(60)
            return

        if self._pending not in {current, self._notified}:
            m = await self.inline.bot.send_photo(
                self.tg_id,
                str(LOGO_PATH),
                caption=self.strings["update_required"].format(
                    current[:6],
                    '<a href="https://github.com/lowsense-dev/astralix/compare/{}...{}">{}</a>'.format(
                        current[:12],
                        self._pending[:12],
                        self._pending[:6],
                    ),
                    changelog,
                ),
                reply_markup=self._markup(),
            )

            self._notified = self._pending
            self.set("ignore_permanent", False)

            await self._delete_all_upd_messages()

            self.set("upd_msg", m.message_id)


    async def _delete_all_upd_messages(self):
        for client in self.allclients:
            with contextlib.suppress(Exception):
                await client.loader.inline.bot.delete_message(
                    client.tg_id,
                    client.loader.db.get("Updater", "upd_msg"),
                )

    @loader.callback_handler()
    async def update_call(self, call: InlineCall):
        """Process update buttons clicks"""
        if not self._git_available:
            await call.answer("Git disabled via --no-git.", show_alert=True)
            return
        if call.data not in {"astralix/update", "astralix/ignore_upd"}:
            return

        if call.data == "astralix/ignore_upd":
            self.set("ignore_permanent", self.get_latest())
            await self.inline.bot(call.answer(self.strings["latest_disabled"]))
            return

        await self._delete_all_upd_messages()

        with contextlib.suppress(Exception):
            await call.delete()

        await self.invoke("update", "-f", peer=self.inline.bot_username)

    @loader.command()
    async def changelog(self, message: Message):
        """Shows the changelog of the last major update"""
        with open("CHANGELOG.md", encoding="utf-8") as f:
            changelog = f.read().split("##")[1].strip()
        if (await self._client.get_me()).premium:
            changelog.replace(
                "🌑 astralix",
                "<tg-emoji emoji-id=5192765204898783881>🌘</tg-emoji><tg-emoji emoji-id=5195311729663286630>🌘</tg-emoji><tg-emoji emoji-id=5195045669324201904>🌘</tg-emoji>",
            )

        await utils.answer(message, self.strings["changelog"].format(changelog))

    @staticmethod
    def _serialize_inline_message_id(
        inline_message_id: str | InputBotInlineMessageID | InputBotInlineMessageID64,
    ) -> str:
        if isinstance(
            inline_message_id,
            (InputBotInlineMessageID, InputBotInlineMessageID64),
        ):
            return typing.cast(str, inline_message_id.to_json())

        return inline_message_id

    @staticmethod
    def _deserialize_inline_message_id(
        inline_message_id: str,
    ) -> str | InputBotInlineMessageID | InputBotInlineMessageID64:
        try:
            data = json.loads(inline_message_id)
        except (TypeError, ValueError):
            return inline_message_id

        if not isinstance(data, dict):
            return inline_message_id

        if data.get("_") == "InputBotInlineMessageID":
            return InputBotInlineMessageID(
                dc_id=data["dc_id"],
                id=data["id"],
                access_hash=data["access_hash"],
            )

        if data.get("_") == "InputBotInlineMessageID64":
            return InputBotInlineMessageID64(
                dc_id=data["dc_id"],
                owner_id=data["owner_id"],
                id=data["id"],
                access_hash=data["access_hash"],
            )

        return inline_message_id

    @staticmethod
    def _parse_legacy_update_message_ref(
        message_ref: typing.Any,
    ) -> tuple[int, int] | None:
        if not isinstance(message_ref, str):
            return None

        parts = message_ref.split(":")
        if len(parts) != 2:
            return None

        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return None

    async def process_restart_message(self, msg_obj: InlineCall | Message):
        inline_message_id = getattr(msg_obj, "inline_message_id", None)
        self.set(
            "selfupdatemsg",
            (
                self._serialize_inline_message_id(inline_message_id)
                if inline_message_id is not None
                else f"{utils.get_chat_id(msg_obj)}:{msg_obj.id}"
            ),
        )

    async def restart_common(
        self,
        msg_obj: InlineCall | Message,
        secure_boot: bool = False,
    ):
        if (
            hasattr(msg_obj, "form")
            and isinstance(msg_obj.form, dict)
            and "uid" in msg_obj.form
            and msg_obj.form["uid"] in self.inline._units
            and "message" in self.inline._units[msg_obj.form["uid"]]
        ):
            message = self.inline._units[msg_obj.form["uid"]]["message"]
        else:
            message = msg_obj

        if secure_boot:
            self._db.set(loader.__name__, "secure_boot", True)

        msg_obj = await utils.answer(
            msg_obj,
            self.strings["restarting_caption"].format(
                utils.get_platform_emoji()
                if self._client.astralix_me.premium
                else "astralix"
            ),
        )

        await self.process_restart_message(msg_obj)

        self.db.set("Updater", "modules_count", len(self.allmodules.modules))

        self.set("restart_ts", time.time())

        restart()

    async def download_common(self, channel: str | None = None, expected: str | None = None):
        channel = channel or version.branch

        def _sync():
            with Repo(PROJECT_ROOT) as repo:
                if repo.is_dirty(untracked_files=False):
                    raise RuntimeError(self.strings["update_dirty"])
                origin = repo.remote("origin")
                if origin.url != self.config["GIT_ORIGIN_URL"]:
                    origin.set_url(self.config["GIT_ORIGIN_URL"])
                logger.debug("Fetching %s from %s", channel, origin.url)
                repo.git.fetch(
                    "origin",
                    f"+refs/heads/{channel}:refs/remotes/origin/{channel}",
                    kill_after_timeout=120,
                )
                target = repo.commit(f"origin/{channel}")
                if expected and target.hexsha != expected:
                    raise RuntimeError(self.strings["update_changed"])
                previous = repo.head.commit
                previous_hash = previous.hexsha
                if repo.active_branch.name != channel:
                    if channel in repo.heads:
                        local_branch = repo.heads[channel]
                        if not repo.is_ancestor(local_branch.commit, target):
                            raise RuntimeError(self.strings["update_diverged"])
                        local_branch.checkout()
                    else:
                        local_branch = repo.create_head(channel, target)
                        local_branch.set_tracking_branch(origin.refs[channel])
                        local_branch.checkout()
                elif previous != target and not repo.is_ancestor(previous, target):
                    raise RuntimeError(self.strings["update_diverged"])
                if repo.head.commit != target:
                    repo.git.merge("--ff-only", target.hexsha)
                changed_files = repo.git.diff("--name-only", previous_hash, target.hexsha).splitlines()
                return bool({"pyproject.toml", "uv.lock", "requirements.txt"} & set(changed_files))

        return await asyncio.wait_for(
            asyncio.to_thread(_sync),
            timeout=120,
        )

    @staticmethod
    def req_common():
        # Now we have downloaded new code, install requirements
        logger.debug("Installing new requirements...")
        environment = PROJECT_ROOT / ".venv"
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not python.is_file():
            python = Path(sys.executable)
        try:
            subprocess.run(
                sync_command(python),
                cwd=PROJECT_ROOT,
                env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(environment)},
                check=True,
                timeout=600,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            logger.exception("Req install failed")
            raise

    @loader.command()
    async def update(self, message: Message):
        if not self._git_available:
            await utils.answer(
                message,
                "<b>Git disabled via --no-git.</b>",
            )
            return
        args = (utils.get_args_raw(message) or "").split()
        force = "-f" in args
        if force:
            args.remove("-f")
        channel = version.branch
        if len(args) == 2 and args[0] == "--channel" and args[1] in {"main", "dev"}:
            channel = args[1]
        elif args:
            await utils.answer(message, self.strings["update_usage"])
            return
        try:
            with git.Repo(PROJECT_ROOT) as repo:
                origin = repo.remote("origin")
                if origin.url != self.config["GIT_ORIGIN_URL"]:
                    origin.set_url(self.config["GIT_ORIGIN_URL"])
                repo.git.fetch(
                    "origin",
                    f"+refs/heads/{channel}:refs/remotes/origin/{channel}",
                    kill_after_timeout=120,
                )
                current = repo.head.commit.hexsha
                upcoming = repo.commit(f"origin/{channel}").hexsha
                current_branch = repo.active_branch.name
                changes = self._format_changelog(
                    list(repo.iter_commits(f"{current}..{upcoming}"))
                ) or self.strings["update_no_changes"]
            if current == upcoming and channel == current_branch:
                await utils.answer(message, self.strings["update_current"])
                return
            if not force:
                if not self.inline.init_complete:
                    await utils.answer(
                        message,
                        self.strings["update_confirm_cli"].format(channel),
                    )
                    return
                form = await self.inline.form(
                    message=message,
                    text=(
                        self.strings["update_confirm"].format(
                            current, current[:8], upcoming, upcoming[:8],
                            channel, changes,
                        )
                    ),
                    reply_markup=[
                        {
                            "text": self.strings["btn_update"],
                            "callback": self.inline_update,
                            "args": (False, channel, upcoming),
                            "style": "primary",
                        },
                        {
                            "text": self.strings["cancel"],
                            "action": "close",
                            "style": "danger",
                        },
                    ],
                )
                if not form:
                    await utils.answer(
                        message,
                        self.strings["update_confirm_cli"].format(channel),
                    )
                return
            await self.inline_update(message, channel=channel, expected=upcoming)
        except Exception as error:
            logger.exception("Update failed")
            await utils.answer(
                message,
                self.strings["update_error"].format(utils.escape_html(str(error))),
            )

    async def inline_update(
        self,
        msg_obj: InlineCall | Message,
        hard: bool = False,
        channel: str | None = None,
        expected: str | None = None,
    ):
        if not self._git_available:
            logger.warning("Git disabled via --no-git; update skipped")
            return
        try:
            if await self.download_common(channel, expected):
                await asyncio.to_thread(self.req_common)
            await self.restart_common(msg_obj)
        except Exception as error:
            logger.exception("Update failed")
            await utils.answer(
                msg_obj,
                self.strings["update_error"].format(utils.escape_html(str(error))),
            )

    @loader.command()
    async def source(self, message: Message):
        await utils.answer(
            message,
            self.strings["source"].format(self.config["GIT_ORIGIN_URL"]),
        )

    async def client_ready(self):
        try:
            configured = urlsplit(self.config["GIT_ORIGIN_URL"])
            if (
                configured.hostname != "github.com"
                and (
                    configured.path.rstrip("/") in {"", "/"}
                    or configured.path.rstrip("/").removesuffix(".git")
                    == "/lowsense-dev/astralix"
                )
            ):
                self.config["GIT_ORIGIN_URL"] = REPO_URL
        except ValueError:
            logger.warning("Invalid update origin URL in updater configuration")

        if not NO_GIT:
            try:
                with git.Repo(PROJECT_ROOT):
                    pass
            except (git.exc.InvalidGitRepositoryError, git.exc.NoSuchPathError):
                self._git_available = False
                logger.info("Git checkout unavailable; restart remains enabled")

        self._markup = lambda: self.inline.generate_markup(
            [
                {
                    "text": self.strings["update"],
                    "data": "astralix/update",
                    "style": "primary",
                },
                {
                    "text": self.strings["ignore"],
                    "data": "astralix/ignore_upd",
                    "style": "danger",
                },
            ]
        )

        if self.get("selfupdatemsg") is not None:
            try:
                await self.update_complete()
            except Exception:
                logger.exception("Failed to complete update!")

        if self.get("do_not_create", False):
            pass
        else:
            try:
                await self._add_folder()
            except Exception:
                logger.exception("Failed to add folder!")

            self.set("do_not_create", True)


    async def _add_folder(self):
        folders = await self._client(GetDialogFiltersRequest())

        try:
            folder_id = (
                max(
                    (folder for folder in folders.filters if hasattr(folder, "id")),
                    key=lambda x: x.id,
                ).id
                + 1
            )
        except ValueError:
            folder_id = 2

        folders = await self._client(GetDialogFiltersRequest())
        filters = getattr(folders, "filters", folders)
        astralix_f = False

        if filters:

            for folder in filters:
                title = getattr(folder, "title", None)

                if title:
                    raw_title = getattr(title, "text", title)

                    if str(raw_title).strip() == "astralix":
                        astralix_f = True

        if astralix_f is True:
            return
        else:
            try:
                await self._client(
                    UpdateDialogFilterRequest(
                        folder_id,
                        DialogFilter(
                            folder_id,
                            title=TextWithEntities(text="astralix", entities=[]),
                            pinned_peers=(
                                [
                                    await self._client.get_input_entity(
                                        self._client.loader.inline.bot_id
                                    )
                                ]
                                if self._client.loader.inline.init_complete
                                else []
                            ),
                            include_peers=[
                                await self._client.get_input_entity(dialog.entity)
                                async for dialog in self._client.iter_dialogs(
                                    None,
                                    ignore_migrated=True,
                                )
                                if "astralix" in dialog.name
                                or "astralix" in dialog.name
                                and dialog.is_channel
                                or (
                                    self._client.loader.inline.init_complete
                                    and dialog.entity.id
                                    == self._client.loader.inline.bot_id
                                )
                                or dialog.entity.id
                                in [
                                    2445389036,
                                    2341345589,
                                    2410964167,
                                ]  # official astralix chats
                            ],
                            emoticon="🐱",
                            exclude_peers=[],
                            contacts=False,
                            non_contacts=False,
                            groups=False,
                            broadcasts=False,
                            bots=False,
                            exclude_muted=False,
                            exclude_read=False,
                            exclude_archived=False,
                        ),
                    )
                )
            except Exception:
                logger.critical(
                    "Can't create astralix folder. Possible reasons are:\n"
                    "- User reached the limit of folders in Telegram\n"
                    "- User got floodwait\n"
                    "Ignoring error and adding folder addition to ignore list\n",
                    exc_info=True,
                )

    async def update_complete(self):
        logger.debug("Restart successful; modules are still loading. Edit message")
        start = self.get("restart_ts")
        try:
            took = round(time.time() - start)
        except Exception:
            took = "n/a"

        msg = self.strings["success"].format(utils.ascii_face(), took)
        ms = self.get("selfupdatemsg")

        if legacy_message_ref := self._parse_legacy_update_message_ref(ms):
            chat_id, message_id = legacy_message_ref
            await self._client.edit_message(chat_id, message_id, msg)
            return

        await self.inline.bot.edit_message_text(
            inline_message_id=self._deserialize_inline_message_id(str(ms)),
            text=self.inline.sanitise_text(msg),
        )

    async def full_restart_complete(self, secure_boot: bool = False):
        start = self.get("restart_ts")

        try:
            took = round(time.time() - start)
        except Exception:
            took = "n/a"

        self.set("restart_ts", None)
        ms = self.get("selfupdatemsg")

        modules_count = self.db.get("Updater", "modules_count")
        try:
            modules_count = int(modules_count)
        except Exception:
            modules_count = len(self.allmodules.modules)

        if modules_count <= len(self.allmodules.modules):
            msg = self.strings[
                "secure_boot_complete" if secure_boot else "full_success"
            ].format(utils.ascii_face(), took)
        else:
            fails = modules_count - len(self.allmodules.modules)
            msg = self.strings[
                "secure_boot_fail" if secure_boot else "full_fail"
            ].format(utils.ascii_face(), took, fails)

        if ms is None:
            return

        self.set("selfupdatemsg", None)

        if legacy_message_ref := self._parse_legacy_update_message_ref(ms):
            chat_id, message_id = legacy_message_ref
            await self._client.edit_message(chat_id, message_id, msg)
            await asyncio.sleep(60)
            await self._client.delete_messages(chat_id, message_id)
            return

        await self.inline.bot.edit_message_text(
            inline_message_id=self._deserialize_inline_message_id(str(ms)),
            text=self.inline.sanitise_text(msg),
        )

    @loader.command()
    async def rollback(self, message: Message):
        if not (args := utils.get_args_raw(message)).isdigit():
            await utils.answer(message, self.strings["invalid_args"])
            return
        if int(args) > 10:
            await utils.answer(message, self.strings["rollback_too_far"])
            return
        await self.inline.form(
            message=message,
            text=self.strings["rollback_confirm"].format(num=args),
            reply_markup=[
                [
                    {
                        "text": "✅",
                        "callback": self.rollback_confirm,
                        "args": [args],
                        "style": "success",
                    }
                ],
                [
                    {
                        "text": "❌",
                        "action": "close",
                        "style": "danger",
                    }
                ],
            ],
        )

    async def rollback_confirm(self, call: InlineCall, number: int):
        number = int(number)
        if not 1 <= number <= 10:
            raise ValueError("Rollback count must be between 1 and 10")
        await utils.answer(call, self.strings["rollback_process"].format(num=number))
        utils.ensure_child_watcher()
        process = await asyncio.create_subprocess_exec(
            "git", "reset", "--hard", f"HEAD~{number}",
            cwd=PROJECT_ROOT,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, error = await process.communicate()
        if process.returncode:
            raise RuntimeError("Git rollback failed: " + error.decode(errors="replace"))
        await self.restart_common(call)

    async def ubstop_func(self, call: Message | InlineCall):
        await utils.answer(
            call,
            self.strings["ub_stop"].format(
                emoji=(
                    utils.get_platform_emoji()
                    if self._client.astralix_me.premium
                    else "astralix"
                ),
            ),
        )

        exit()

    @loader.command()
    async def ubstop(self, message: Message):
        """| stops your userbot"""

        args = utils.get_args(message)
        if "-f" in args or "--force" in args:
            await self.ubstop_func(message)
            return

        await self.inline.form(
            message=message,
            text=self.strings["stop_ub_confirm"].format(
                utils.get_platform_emoji()
                if self.client.astralix_me.premium
                else "astralix"
            ),
            reply_markup=[
                [
                    {
                        "text": "✅",
                        "callback": self.ubstop_func,
                        "style": "primary",
                    },
                ],
                [{"text": "❌", "action": "close", "style": "primary"}],
            ],
            silent=True,
        )
