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
import io
import logging
import os
import time
import typing

import git
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

from .. import loader, main, utils, version
from .._updates import Updates
from .._internal import restart
from ..inline.types import BotInlineCall, InlineCall

logger = logging.getLogger(__name__)
NO_GIT = os.environ.get("ASTRALIX_NO_GIT") == "1"

os.environ["GIT_TERMINAL_PROMPT"] = "0"
os.environ["GIT_ASKPASS"] = "echo"


@loader.tds
class UpdaterMod(loader.Module):
    """Updates itself, tracks latest astralix releases, and notifies you, if update is required"""

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
            loader.ConfigValue(
                "startup_timeout", 180,
                lambda: self.strings["startup_timeout_doc"],
                validator=loader.validators.Integer(minimum=30, maximum=900),
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
        with git.Repo() as repo:
            channel = self._channel()
            now = time.monotonic()
            if now >= self._git_fetch_backoff_until:
                if now - self._last_git_fetch >= self._GIT_FETCH_INTERVAL:
                    Updates().check(self.config["GIT_ORIGIN_URL"], channel)
                    self._last_git_fetch = now
            else:
                logger.debug(
                    "Skipping changelog fetch for %.0f more seconds after EMFILE",
                    self._git_fetch_backoff_until - now,
                )

            current = repo.head.commit.hexsha
            latest = next(
                repo.iter_commits(f"refs/astralix-releases/{channel}", max_count=1)
            ).hexsha
            commits = [*repo.iter_commits(f"HEAD..refs/astralix-releases/{channel}")]

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
            with git.Repo() as repo:
                return next(
                    repo.iter_commits(f"refs/astralix-releases/{self._channel()}", max_count=1)
                ).hexsha
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

        await self.invoke("update", "", peer=self.inline.bot_username)

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

    @loader.command()
    async def restart(self, message: Message):
        args = utils.get_args_raw(message)
        secure_boot = any(trigger in args for trigger in {"--secure-boot", "-sb"})
        try:
            if (
                "-f" in args
                or not self.inline.init_complete
                or not await self.inline.form(
                    message=message,
                    text=self.strings[
                        "secure_boot_confirm" if secure_boot else "restart_confirm"
                    ],
                    reply_markup=[
                        {
                            "text": self.strings["btn_restart"],
                            "callback": self.inline_restart,
                            "args": (secure_boot,),
                            "style": "primary",
                        },
                        {
                            "text": self.strings["cancel"],
                            "action": "close",
                            "style": "danger",
                        },
                    ],
                )
            ):
                raise
        except Exception:
            await self.restart_common(message, secure_boot)

    async def inline_restart(self, call: InlineCall, secure_boot: bool = False):
        await self.restart_common(call, secure_boot=secure_boot)

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

    def _accounts(self):
        return [client.tg_id for client in self.allclients]

    def _channel(self):
        manager = Updates()
        state = manager.read()
        return (
            state["active"]["channel"]
            if state else manager.git("branch", "--show-current")
        )

    async def _show_error(self, message, error):
        logger.exception("Release operation failed")
        await utils.answer(message, self.strings["release_error"].format(
            utils.escape_html(str(error))
        ))

    @loader.command()
    async def update(self, message: Message):
        """Check for updates; --channel main|dev selects a channel, -f skips confirmation."""
        if not self._git_available:
            await utils.answer(message, "<b>Git disabled via --no-git.</b>")
            return
        args = (utils.get_args_raw(message) or "").split()
        force = "-f" in args
        if force:
            args.remove("-f")
        requested_channel = None
        if len(args) == 2 and args[0] == "--channel" and args[1] in {"main", "dev"}:
            requested_channel = args[1]
        elif args:
            await utils.answer(message, self.strings["update_usage"])
            return
        try:
            channel = requested_channel or self._channel()
            if channel not in {"main", "dev"}:
                raise ValueError(self.strings["release_invalid_channel"].format(channel or "detached HEAD"))
            report = await asyncio.to_thread(
                Updates().check, self.config["GIT_ORIGIN_URL"], channel
            )
            text = self.strings["release_check"].format(
                channel, report["current"][:12], report["target"][:12],
                utils.escape_html(report["changes"] or self.strings["release_no_changes"]),
                utils.escape_html(report["dependencies"] or self.strings["release_no_changes"]),
                utils.escape_html(report["dirty"] or self.strings["release_clean"]),
            )
            if report["target"] == report["current"] and channel == report["branch"]:
                await utils.answer(message, self.strings["release_current"])
                return
            if report["dirty"]:
                raise RuntimeError(self.strings["release_dirty"])
            if not force:
                if self.inline.init_complete and await self.inline.form(message=message, text=text + "\n\n" + self.strings["release_confirm"],
                    reply_markup=[
                        {"text": self.strings["btn_update"], "callback": self.inline_update,
                         "args": (False, channel, report["target"]), "style": "primary"},
                        {"text": self.strings["cancel"], "action": "close"},
                    ]):
                    return
                await utils.answer(message, text + "\n\n" + self.strings["release_confirm_cli"].format(channel))
                return
            await self.inline_update(message, channel=channel, expected=report["target"])
        except Exception as error:
            await self._show_error(message, error)

    async def inline_update(self, msg_obj: InlineCall | Message, hard=False, channel=None, expected=None):
        if not self._git_available:
            return
        manager = Updates()
        prepared = False
        try:
            msg_obj = await utils.answer(msg_obj, self.strings["release_preparing"])
            from .._module_inventory import requirements_for_sources
            from .._dependencies import PROJECT_ROOT
            sources = [item["source"] for client in self.allclients
                       for item in client.loader.lookup("LoaderMod")._installed_sources().values()
                       if item.get("source")]
            requirements = await asyncio.to_thread(
                requirements_for_sources, sources, (PROJECT_ROOT / "uv.lock").read_text()
            )
            requirements = sorted(set(requirements).union(*(
                client.loader.lookup('LoaderMod').get('dependency_requests', []) for client in self.allclients
            )))
            health_modules = {str(client.tg_id): sorted(
                mod.__class__.__name__ for mod in client.loader.modules
                if getattr(mod, "__ready__", False)
            ) for client in self.allclients}
            release = await asyncio.to_thread(
                manager.prepare, self.config["GIT_ORIGIN_URL"], channel or self._channel(),
                main.BASE_DIR, self._accounts(), self.config["startup_timeout"],
                expected=expected,
                module_requirements=requirements, health_modules=health_modules,
            )
            if release is None:
                await utils.answer(msg_obj, self.strings["release_current"])
                return
            prepared = True
            await self.restart_common(msg_obj)
        except Exception as error:
            if prepared:
                await asyncio.to_thread(manager.cancel_pending)
            await self._show_error(msg_obj, error)

    @loader.command()
    async def diagnostics(self, message: Message):
        """Send a report without account credentials, sessions or logs to Saved Messages."""
        from .._diagnostics import report
        document = io.BytesIO(json.dumps(report(Updates().read(), self.allmodules.modules), indent=2).encode())
        document.name = 'astralix-diagnostics.json'
        await self._client.send_file('me', document, caption=self.strings['diagnostics_saved'])
        await utils.answer(message, self.strings['diagnostics_saved'])

    @loader.command()
    async def updatehistory(self, message: Message):
        """Show recent release operations and their results."""
        state = Updates().read() or {}
        lines = [
            f"<code>{time.strftime('%Y-%m-%d %H:%M', time.localtime(item['time']))}</code>"
            f" · <code>{utils.escape_html(item['commit'][:12])}</code>"
            f" · {utils.escape_html(item['channel'])} · "
            f"{self.strings['release_status_' + item['status']]}"
            for item in state.get("history", [])[-12:]
        ]
        await utils.answer(message, self.strings["release_history"].format(
            "\n".join(lines) or self.strings["release_no_history"]
        ))

    @loader.command()
    async def source(self, message: Message):
        await utils.answer(
            message,
            self.strings["source"].format("https://git.astralix.cc/"),
        )

    async def client_ready(self):
        if self.config["GIT_ORIGIN_URL"].removesuffix(".git").rstrip("/") in {
            "https://github.com/coddrago/Heroku",
            "https://github.com/ZetGoHack/Heroku",
        }:
            self.config["GIT_ORIGIN_URL"] = REPO_URL

        if not NO_GIT:
            try:
                with git.Repo(os.path.dirname(utils.get_base_dir())):
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
        """Return to the previous working release; --restore-data also restores configs."""
        args = utils.get_args_raw(message).split()
        if any(arg not in {"--restore-data", "-f"} for arg in args):
            await utils.answer(message, self.strings["rollback_usage"])
            return
        restore = "--restore-data" in args
        if "-f" not in args and self.inline.init_complete:
            if await self.inline.form(
                message=message,
                text=self.strings["release_rollback_data" if restore else "release_rollback_confirm"],
                reply_markup=[
                    {"text": self.strings["btn_restart"], "callback": self.rollback_confirm,
                     "args": (restore,), "style": "primary"},
                    {"text": self.strings["cancel"], "action": "close"},
                ],
            ):
                return
        await self.rollback_confirm(message, restore)

    async def rollback_confirm(self, call: InlineCall | Message, restore_data=False):
        manager = Updates()
        prepared = False
        try:
            await asyncio.to_thread(
                manager.rollback, self._accounts(), restore_data, self.config["startup_timeout"]
            )
            prepared = True
            await self.restart_common(call)
        except Exception as error:
            if prepared:
                await asyncio.to_thread(manager.cancel_pending)
            await self._show_error(call, error)

    async def ubstop_func(self, call: Message | InlineCall):
        await utils.answer(
            call,
            self.strings["ub_stop"].format(emoji=utils.get_platform_emoji()),
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
