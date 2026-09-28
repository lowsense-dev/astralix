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

import ast
import contextlib
import difflib
import functools
import getpass
import logging
import re
import typing
from math import ceil

import astralixtl
from astralixtl.extensions import html
from astralixtl.tl.types import Message, User
from astralixtl.utils import get_display_name

from .. import loader, main, translations, utils, version
from ..inline.types import InlineCall
from ..types import AstralixReplyMarkup

logger = logging.getLogger(__name__)

# Everywhere in this module, we use the following naming convention:
# `obj_type` of non-core module = False
# `obj_type` of core module = True
# `obj_type` of library = "library"


ROW_SIZE = 3
NUM_ROWS = 5


class _InlineFormDraft:
    inline_message_id = None

    def __init__(self):
        self.text: str | None = None
        self.reply_markup: AstralixReplyMarkup | None = None
        self.kwargs: dict[str, typing.Any] = {}

    async def edit(
        self,
        text: str | None = None,
        reply_markup: AstralixReplyMarkup | None = None,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        if text is None:
            text = kwargs.pop("text", None)

        if reply_markup is None and args:
            reply_markup = args[0]

        self.text = text
        self.reply_markup = reply_markup
        self.kwargs = kwargs


ALL_INVOKES = [
    "flush_entity_cache",
    "flush_fulluser_cache",
    "flush_fullchannel_cache",
    "flush_perms_cache",
    "flush_loader_cache",
    "flush_cache",
    "reload_core",
    "inspect_cache",
    "inspect_modules",
]


@loader.tds
class CoreMod(loader.Module):
    """Control core userbot settings"""

    strings = {"name": "Settings"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "allow_nonstandart_prefixes",
                False,
                "Allow non-standard prefixes like premium emojis or multi-symbol prefixes",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "alias_emoji",
                "<tg-emoji emoji-id=4974259868996207180>▪️</tg-emoji>",
                "just emoji in .aliases",
            ),
            loader.ConfigValue(
                "cfg_emoji",
                "✨",
                "Change emoji when opening config",
                validator=loader.validators.String(),
            ),
        )


    async def blacklistcommon(self, message: Message):
        args = utils.get_args(message)

        if len(args) > 2:
            await utils.answer(message, self.strings["too_many_args"])
            return

        chatid = None
        module = None

        if args:
            try:
                chatid = int(args[0])
            except ValueError:
                module = args[0]

        if len(args) == 2:
            module = args[1]

        if chatid is None:
            chatid = utils.get_chat_id(message)

        module = self.allmodules.get_classname(module)
        return f"{str(chatid)}.{module}" if module else chatid

    @loader.command()
    async def blacklist(self, message: Message):
        chatid = await self.blacklistcommon(message)
        chatid_str = str(chatid)

        if chatid_str.startswith("-100"):
            chatid = chatid_str[4:]

        self._db.set(
            main.__name__,
            "blacklist_chats",
            self._db.get(main.__name__, "blacklist_chats", []) + [chatid],
        )

        await utils.answer(message, self.strings["blacklisted"].format(chatid))

    @loader.command()
    async def unblacklist(self, message: Message):
        chatid = await self.blacklistcommon(message)
        chatid_str = str(chatid)

        if chatid_str.startswith("-100"):
            chatid = chatid_str[4:]

        self._db.set(
            main.__name__,
            "blacklist_chats",
            list(set(self._db.get(main.__name__, "blacklist_chats", [])) - {chatid}),
        )

        await utils.answer(message, self.strings["unblacklisted"].format(chatid))

    async def getuser(self, message: Message):
        try:
            return int(utils.get_args(message)[0])
        except (ValueError, IndexError):
            if reply := await message.get_reply_message():
                return reply.sender_id

            return message.to_id.user_id if message.is_private else False

    @loader.command()
    async def blacklistuser(self, message: Message):
        if not (user := await self.getuser(message)):
            await utils.answer(message, self.strings["who_to_blacklist"])
            return

        self._db.set(
            main.__name__,
            "blacklist_users",
            self._db.get(main.__name__, "blacklist_users", []) + [user],
        )

        await utils.answer(message, self.strings["user_blacklisted"].format(user))

    @loader.command()
    async def unblacklistuser(self, message: Message):
        if not (user := await self.getuser(message)):
            await utils.answer(message, self.strings["who_to_unblacklist"])
            return

        self._db.set(
            main.__name__,
            "blacklist_users",
            list(set(self._db.get(main.__name__, "blacklist_users", [])) - {user}),
        )

        await utils.answer(
            message,
            self.strings["user_unblacklisted"].format(user),
        )

    @loader.command()
    async def setprefix(self, message: Message):
        """<prefix ...> [@owner] or --user <ID> <prefix ...> — Set personal prefixes."""
        args = utils.get_args(message)
        if not isinstance(args, list):
            return await utils.answer(message, self.strings["what_prefix"])
        target = getattr(message, "sender_id", None) or self.tg_id
        if "--user" in args:
            index = args.index("--user")
            if index + 1 >= len(args):
                return await utils.answer(message, self.strings["what_prefix"])
            target = args[index + 1]
            del args[index:index + 2]
        elif len(args) > 1 and (
            (args[-1].startswith("@") and len(args[-1]) > 1)
            or (args[-1].isdigit() and len(args[-1]) >= 5)
        ):
            target = args.pop()
        if not args:
            return await utils.answer(message, self.strings["what_prefix"])
        if any(
            not p or p == "s" or any(c.isspace() for c in p)
            or (len(p) != 1 and not self.config.get("allow_nonstandart_prefixes"))
            for p in args
        ):
            return await utils.answer(message, self.strings["prefix_incorrect"])
        prefixes = utils.normalize_prefixes(args)
        target = int(target) if str(target).isdigit() else target
        try:
            entity = await self.client.get_entity(target)
        except Exception:
            return await utils.answer(message, self.strings["invalid_id_or_username"])
        if not isinstance(entity, User):
            return await utils.answer(message, self.strings["not_a_user"].format(target))
        oldprefixes = utils.user_prefixes(
            self._db, main.__name__, entity.id, self.tg_id
        )
        if entity.id != self.tg_id:
            security = self._client.dispatcher.security
            allowed = set(security.owner)
            allowed.update(u for g in security._sgroups.values() for u in g.users)
            allowed.update(rule["target"] for rule in security._tsec_user)
            if entity.id not in allowed:
                return await utils.answer(message, self.strings["id_not_found_scgroup"])
            personal = dict(self._db.get(main.__name__, "command_prefixes", {}))
            personal[str(entity.id)] = prefixes[0] if len(prefixes) == 1 else prefixes
            self._db.set(main.__name__, "command_prefixes", personal)
        else:
            self._db.set(main.__name__, "command_prefix", prefixes[0])
            self._db.set(main.__name__, "command_prefix_aliases", prefixes[1:])
        await utils.answer(
            message,
            self.strings[
                "prefix_set" if entity.id == self.tg_id else "entity_prefix_set"
            ].format(
                "<tg-emoji emoji-id=5197474765387864959>👍</tg-emoji>",
                entity_name=utils.escape_html(entity.first_name),
                entity_id=entity.id,
                newprefix=utils.escape_html(utils.format_prefixes(prefixes)),
                oldprefix=utils.escape_html(" ".join(oldprefixes)),
            ),
        )

    @loader.command()
    async def aliases(self, message: Message):
        await utils.answer(
            message,
            self.strings["aliases"]
            + "<blockquote expandable>"
            + "\n".join(
                [
                    (self.config["alias_emoji"] + f" <code>{i}</code> &lt;- {y}")
                    for i, y in self.allmodules.aliases.items()
                ]
            )
            + "</blockquote>",
        )

    @loader.command()
    async def addalias(self, message: Message):

        args_raw = utils.get_args_raw(message)
        if not args_raw:
            await utils.answer(message, self.strings["alias_args"])
            return

        import keyword

        def parse_alias_line(line: str) -> tuple[list[str], str] | None:
            line = line.strip()
            if not line:
                return None

            if "&&" in line:
                parts = line.split("&&", 1)
                alias_part, command_part = parts[0].strip(), parts[1].strip()
                aliases = [a.strip().lower() for a in alias_part.split(",") if a.strip()]
                return aliases, command_part
            elif "," in line:
                parts = [part.strip() for part in line.split(",")]
                if parts:
                    last = parts[-1].split(maxsplit=1)
                    if len(last) >= 2:
                        aliases = [part.lower() for part in parts[:-1] if part]
                        aliases.append(last[0].lower())
                        return aliases, last[1]
            else:
                args = line.split(maxsplit=1)
                if len(args) >= 2:
                    return [args[0].lower()], args[1]
            return None

        alias_lines = []
        lines = args_raw.splitlines()

        for line_idx, line in enumerate(lines):
            is_new_alias = False
            parsed_aliases = None
            parsed_cmd = None
            parsed_rest = None

            stripped_line = line.strip()
            if stripped_line:
                parsed = parse_alias_line(line)
                if parsed:
                    aliases, command = parsed
                    command_parts = command.split(maxsplit=1)
                    cmd = command_parts[0]
                    rest = command_parts[1] if len(command_parts) > 1 else None

                    first_word = stripped_line.split()[0] if stripped_line else ""
                    is_valid_candidate = (
                        not line.startswith(" ")
                        and not line.startswith("\t")
                        and not keyword.iskeyword(first_word)
                        and all(c.isalnum() or c in "_-" for c in first_word)
                    )

                    if is_valid_candidate and cmd in self.allmodules.commands:
                        is_new_alias = True
                        parsed_aliases = aliases
                        parsed_cmd = cmd
                        parsed_rest = rest

            if line_idx == 0:
                parsed = parse_alias_line(line)
                if not parsed:
                    await utils.answer(message, self.strings["alias_args"])
                    return
                aliases, command = parsed
                command_parts = command.split(maxsplit=1)
                cmd = command_parts[0]
                rest = command_parts[1] if len(command_parts) > 1 else None

                if cmd not in self.allmodules.commands:
                    await utils.answer(
                        message,
                        self.strings["no_command"].format(utils.escape_html(cmd)),
                    )
                    return

                alias_lines.append((aliases, cmd, rest))
            else:
                if is_new_alias:
                    alias_lines.append((parsed_aliases, parsed_cmd, parsed_rest))
                else:
                    if alias_lines:
                        aliases, cmd, rest = alias_lines[-1]
                        if rest is None:
                            new_rest = line
                        else:
                            new_rest = rest + "\n" + line
                        alias_lines[-1] = (aliases, cmd, new_rest)

        if not alias_lines:
            await utils.answer(message, self.strings["alias_args"])
            return

        added_lines = []
        skipped_lines = []
        planned_aliases = {}
        stored_aliases = {**self.get("aliases", {})}

        for aliases, cmd, rest in alias_lines:
            target = f"{cmd} {rest}" if rest else cmd
            added_aliases = []

            for alias in aliases:
                if alias in self.allmodules.aliases:
                    skipped_lines.append(
                        self.strings["alias_exists"].format(
                            alias=utils.escape_html(alias),
                            command=utils.escape_html(self.allmodules.aliases[alias]),
                        )
                    )
                    continue

                if alias in planned_aliases:
                    skipped_lines.append(
                        self.strings["alias_exists"].format(
                            alias=utils.escape_html(alias),
                            command=utils.escape_html(planned_aliases[alias]),
                        )
                    )
                    continue

                if not self.allmodules.add_alias(alias, cmd, rest):
                    await utils.answer(
                        message,
                        self.strings["no_command"].format(utils.escape_html(cmd)),
                    )
                    return

                stored_aliases[alias] = target
                planned_aliases[alias] = target
                added_aliases.append(alias)

            if added_aliases:
                added_lines.append((added_aliases, target))

        if added_lines:
            self.set("aliases", stored_aliases)

        if len(added_lines) == 1 and len(added_lines[0][0]) == 1 and not skipped_lines:
            await utils.answer(
                message,
                self.strings["alias_created"].format(
                    utils.escape_html(added_lines[0][0][0])
                ),
            )
            return

        added_count = sum(len(aliases) for aliases, _ in added_lines)
        response = []

        if added_lines:
            response.append(
                self.strings["aliases_created"].format(
                    count=added_count,
                    aliases="\n".join(
                        self.strings["aliases_created_line"].format(
                            aliases=utils.escape_html(", ".join(aliases)),
                            command=utils.escape_html(target),
                        )
                        for aliases, target in added_lines
                    ),
                )
            )

        response.extend(skipped_lines)

        await utils.answer(message, "\n\n".join(response))

    @loader.command()
    async def delalias(self, message: Message):
        args_raw = utils.get_args_raw(message)

        if not args_raw:
            await utils.answer(message, self.strings["delalias_args"])
            return

        if args_raw.strip() in {"-c", "--clear"}:
            self.allmodules.aliases.clear()
            self.set("aliases", {})
            await utils.answer(message, self.strings["aliases_cleared"])
            return

        aliases = []
        seen_aliases = set()
        for line in args_raw.splitlines():
            for alias in line.split(","):
                alias = alias.lower().strip()
                if alias and alias not in seen_aliases:
                    aliases.append(alias)
                    seen_aliases.add(alias)

        if not aliases:
            await utils.answer(message, self.strings["delalias_args"])
            return

        current = self.get("aliases", {})
        removed_aliases = []
        missed_aliases = []

        for alias in aliases:
            if not self.allmodules.remove_alias(alias):
                missed_aliases.append(alias)
                continue

            current.pop(alias, None)
            removed_aliases.append(alias)

        if removed_aliases:
            self.set("aliases", current)

        if len(removed_aliases) == 1 and not missed_aliases:
            await utils.answer(
                message,
                self.strings["alias_removed"].format(
                    utils.escape_html(removed_aliases[0])
                ),
            )
            return

        response = []
        if removed_aliases:
            response.append(
                self.strings["aliases_removed"].format(
                    count=len(removed_aliases),
                    aliases=utils.escape_html(", ".join(removed_aliases)),
                )
            )

        response.extend(
            self.strings["no_alias"].format(utils.escape_html(alias))
            for alias in missed_aliases
        )

        await utils.answer(
            message,
            "\n\n".join(response),
        )

    @loader.command()
    async def cleardb(self, message: Message):
        await self.inline.form(
            self.strings["confirm_cleardb"],
            message,
            reply_markup=[
                {
                    "text": self.strings["cleardb_confirm"],
                    "callback": self._inline__cleardb,
                },
                {
                    "text": self.strings["cancel"],
                    "action": "close",
                },
            ],
        )

    async def _inline__cleardb(self, call: InlineCall):
        self._db.clear()
        self._db.save()
        await utils.answer(call, self.strings["db_cleared"])

    @loader.command()
    async def togglecmdcmd(self, message: Message):
        """Toggle disable specific command of a module: togglecmd <module> <command> or togglecmd <command>"""
        args = utils.get_args(message)
        if not args:
            await utils.answer(message, self.strings["wrong_usage_tcc"])

        if args and len(args) >= 2:
            mod_arg, cmd = args[0], args[1]
            mod_inst = self.allmodules.lookup(mod_arg)
            if not mod_inst:
                await utils.answer(message, self.strings["mod404"].format(mod_arg))

        module_key = mod_inst.__class__.__name__

        disabled_commands = self._db.get(main.__name__, "disabled_commands", {})
        current = [x for x in disabled_commands.get(module_key, [])]

        if cmd.lower() not in [c.lower() for c in mod_inst.astralix_commands.keys()]:
            await utils.answer(message, self.strings["cmd404"])

        if any(c.lower() == cmd.lower() for c in current):
            current = [c for c in current if c.lower() != cmd.lower()]
            if current:
                disabled_commands[module_key] = current
            else:
                disabled_commands.pop(module_key, None)

            self._db.set(main.__name__, "disabled_commands", disabled_commands)
            try:
                self.allmodules.register_commands(mod_inst)
            except Exception:
                pass

            await utils.answer(
                message, self.strings["cmd_enabled"].format(cmd, module_key)
            )
        else:
            current.append(cmd)
            disabled_commands[module_key] = current
            self._db.set(main.__name__, "disabled_commands", disabled_commands)

            try:
                self.allmodules.commands.pop(cmd.lower(), None)
            except Exception:
                pass

            for alias, target in list(self.allmodules.aliases.items()):
                if target.split()[0].lower() == cmd.lower():
                    self.allmodules.aliases.pop(alias, None)

            await utils.answer(
                message, self.strings["cmd_disabled"].format(cmd, module_key)
            )

    @loader.command()
    async def togglemod(self, message: Message):
        """Toggle disable entire module: togglemod <module>"""
        args = utils.get_args(message)
        if not args:
            await utils.answer(message, self.strings["wrong_usage_tmc"])

        mod_arg = args[0]
        mod_inst = self.allmodules.lookup(mod_arg)
        if not mod_inst:
            await utils.answer(message, self.strings["mod404"].format(mod_arg))

        module_key = mod_inst.__class__.__name__
        disabled = self._db.get(main.__name__, "disabled_modules", [])

        if module_key in disabled:
            disabled = [m for m in disabled if m != module_key]
            self._db.set(main.__name__, "disabled_modules", disabled)
            try:
                self.allmodules.register_commands(mod_inst)
                self.allmodules.register_watchers(mod_inst)
                self.allmodules.register_raw_handlers(mod_inst)
                self.allmodules.register_inline_stuff(mod_inst)
            except Exception:
                pass
            await utils.answer(message, self.strings["mod_enabled"].format(module_key))
        else:
            disabled += [module_key]
            self._db.set(main.__name__, "disabled_modules", disabled)
            try:
                self.allmodules.unregister_commands(mod_inst, "disable")
                self.allmodules.unregister_watchers(mod_inst, "disable")
                self.allmodules.unregister_raw_handlers(mod_inst, "disable")
                self.allmodules.unregister_inline_stuff(mod_inst, "disable")
            except Exception:
                pass
            await utils.answer(message, self.strings["mod_disabled"].format(module_key))

    @loader.command()
    async def clearmodule(self, message: Message):
        """Clear all DB entries for module: clearmodule <module>"""
        args = utils.get_args(message)
        if not args:
            return await utils.answer(message, self.strings["wrong_usage_cmc"])

        mod_arg = args[0]
        mod_inst = self.allmodules.lookup(mod_arg)
        if mod_inst:
            module_key = mod_inst.__class__.__name__
        else:
            module_key = mod_arg

        if module_key in self._db:
            try:
                del self._db[module_key]
                self._db.save()
            except Exception:
                pass

        disabled_commands = self._db.get(main.__name__, "disabled_commands", {})
        disabled_commands.pop(module_key, None)
        self._db.set(main.__name__, "disabled_commands", disabled_commands)

        disabled_modules = self._db.get(main.__name__, "disabled_modules", [])
        if module_key in disabled_modules:
            disabled_modules = [m for m in disabled_modules if m != module_key]
            self._db.set(main.__name__, "disabled_modules", disabled_modules)

        await utils.answer(message, self.strings["cmc_done"].format(mod_arg))

    async def installationcmd(self, message: Message):
        """| Installation guide for Linux"""
        await utils.answer(message, self.strings["linux_install"])

    def get_watchers(self) -> tuple:
        return [
            str(watcher.__self__.__class__.strings["name"])
            for watcher in self.allmodules.watchers
            if watcher.__self__.__class__.strings is not None
        ], self._db.get(main.__name__, "disabled_watchers", {})

    @loader.command()
    async def watchers(self, message: Message):
        watchers, disabled_watchers = self.get_watchers()
        watchers = [
            f"♻️ {watcher}"
            for watcher in watchers
            if watcher not in list(disabled_watchers.keys())
        ]
        watchers += [f"💢 {k} {v}" for k, v in disabled_watchers.items()]
        await utils.answer(
            message, self.strings["watchers"].format("\n".join(watchers))
        )

    @loader.command()
    async def watcherbl(self, message: Message):
        if not (args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings["args"])
            return

        watchers, disabled_watchers = self.get_watchers()

        if args.lower() not in map(lambda x: x.lower(), watchers):
            await utils.answer(message, self.strings["mod404"].format(args))
            return

        args = next((x for x in watchers if x.lower() == args.lower()), args)

        current_bl = [
            v for k, v in disabled_watchers.items() if k.lower() == args.lower()
        ]
        current_bl = current_bl[0] if current_bl else []

        chat = utils.get_chat_id(message)
        if chat not in current_bl:
            if args in disabled_watchers:
                for k in disabled_watchers:
                    if k.lower() == args.lower():
                        disabled_watchers[k].append(chat)
                        break
            else:
                disabled_watchers[args] = [chat]

            await utils.answer(
                message,
                self.strings["disabled"].format(args) + " <b>in current chat</b>",
            )
        else:
            for k in disabled_watchers.copy():
                if k.lower() == args.lower():
                    disabled_watchers[k].remove(chat)
                    if not disabled_watchers[k]:
                        del disabled_watchers[k]
                    break

            await utils.answer(
                message,
                self.strings["enabled"].format(args) + " <b>in current chat</b>",
            )

        self._db.set(main.__name__, "disabled_watchers", disabled_watchers)

    @loader.command()
    async def watchercmd(self, message: Message):
        if not (args := utils.get_args_raw(message)):
            return await utils.answer(message, self.strings["args"])

        chats, pm, out, incoming = False, False, False, False

        if "-c" in args:
            args = args.replace("-c", "").replace("  ", " ").strip()
            chats = True

        if "-p" in args:
            args = args.replace("-p", "").replace("  ", " ").strip()
            pm = True

        if "-o" in args:
            args = args.replace("-o", "").replace("  ", " ").strip()
            out = True

        if "-i" in args:
            args = args.replace("-i", "").replace("  ", " ").strip()
            incoming = True

        if chats and pm:
            pm = False
        if out and incoming:
            incoming = False

        watchers, disabled_watchers = self.get_watchers()

        if args.lower() not in [watcher.lower() for watcher in watchers]:
            return await utils.answer(message, self.strings["mod404"].format(args))

        args = [watcher for watcher in watchers if watcher.lower() == args.lower()][0]

        if chats or pm or out or incoming:
            disabled_watchers[args] = [
                *(["only_chats"] if chats else []),
                *(["only_pm"] if pm else []),
                *(["out"] if out else []),
                *(["in"] if incoming else []),
            ]
            self._db.set(main.__name__, "disabled_watchers", disabled_watchers)
            await utils.answer(
                message,
                self.strings["enabled"].format(args)
                + f" (<code>{disabled_watchers[args]}</code>)",
            )
            return

        if args in disabled_watchers and "*" in disabled_watchers[args]:
            await utils.answer(message, self.strings["enabled"].format(args))
            del disabled_watchers[args]
            self._db.set(main.__name__, "disabled_watchers", disabled_watchers)
            return

        disabled_watchers[args] = ["*"]
        self._db.set(main.__name__, "disabled_watchers", disabled_watchers)
        await utils.answer(message, self.strings["disabled"].format(args))

    @loader.command()
    async def nonickuser(self, message: Message):
        if not (reply := await message.get_reply_message()):
            await utils.answer(message, self.strings["reply_required"])
            return

        u = reply.sender_id
        if not isinstance(u, int):
            u = u.user_id

        nn = self._db.get(main.__name__, "nonickusers", [])
        if u not in nn:
            nn += [u]
            nn = list(set(nn))  # skipcq: PTC-W0018
            await utils.answer(message, self.strings["user_nn"].format("on"))
        else:
            nn = list(set(nn) - {u})
            await utils.answer(message, self.strings["user_nn"].format("off"))

        self._db.set(main.__name__, "nonickusers", nn)

    @loader.command()
    async def nonickchat(self, message: Message):
        if message.is_private:
            await utils.answer(message, self.strings["private_not_allowed"])
            return

        chat = utils.get_chat_id(message)

        nn = self._db.get(main.__name__, "nonickchats", [])
        if chat not in nn:
            nn += [chat]
            nn = list(set(nn))  # skipcq: PTC-W0018
            await utils.answer(
                message,
                self.strings["cmd_nn"].format(
                    utils.escape_html((await message.get_chat()).title),
                    "on",
                ),
            )
        else:
            nn = list(set(nn) - {chat})
            await utils.answer(
                message,
                self.strings["cmd_nn"].format(
                    utils.escape_html((await message.get_chat()).title),
                    "off",
                ),
            )

        self._db.set(main.__name__, "nonickchats", nn)

    @loader.command()
    async def nonickcmdcmd(self, message: Message):
        if not (args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings["no_cmd"])
            return

        if args not in self.allmodules.commands:
            await utils.answer(message, self.strings["cmd404"])
            return

        nn = self._db.get(main.__name__, "nonickcmds", [])
        if args not in nn:
            nn += [args]
            nn = list(set(nn))
            await utils.answer(
                message,
                self.strings["cmd_nn"].format(
                    utils.escape_html(self.get_prefix() + args),
                    "on",
                ),
            )
        else:
            nn = list(set(nn) - {args})
            await utils.answer(
                message,
                self.strings["cmd_nn"].format(
                    utils.escape_html(self.get_prefix() + args),
                    "off",
                ),
            )

        self._db.set(main.__name__, "nonickcmds", nn)

    @loader.command()
    async def nonickcmds(self, message: Message):
        if not self._db.get(main.__name__, "nonickcmds", []):
            await utils.answer(message, self.strings["nothing"])
            return

        await utils.answer(
            message,
            self.strings["cmd_nn_list"].format(
                "\n".join(
                    [
                        f"▫️ <code>{utils.escape_html(self.get_prefix() + cmd)}</code>"
                        for cmd in self._db.get(main.__name__, "nonickcmds", [])
                    ]
                )
            ),
        )

    @loader.command()
    async def nonickusers(self, message: Message):
        users = []
        for user_id in self._db.get(main.__name__, "nonickusers", []).copy():
            try:
                user = await self._client.get_entity(user_id)
            except Exception:
                self._db.set(
                    main.__name__,
                    "nonickusers",
                    list(
                        set(self._db.get(main.__name__, "nonickusers", [])) - {user_id}
                    ),
                )

                logger.warning("User %s removed from nonickusers list", user_id)
                continue

            users += [
                '▫️ <b><a href="tg://user?id={}">{}</a></b>'.format(
                    user_id,
                    utils.escape_html(get_display_name(user)),
                )
            ]

        if not users:
            await utils.answer(message, self.strings["nothing"])
            return

        await utils.answer(
            message,
            self.strings["user_nn_list"].format("\n".join(users)),
        )

    @loader.command()
    async def nonickchats(self, message: Message):
        chats = []
        for chat in self._db.get(main.__name__, "nonickchats", []):
            try:
                chat_entity = await self._client.get_entity(int(chat))
            except Exception:
                self._db.set(
                    main.__name__,
                    "nonickchats",
                    list(set(self._db.get(main.__name__, "nonickchats", [])) - {chat}),
                )

                logger.warning("Chat %s removed from nonickchats list", chat)
                continue

            chats += [
                '▫️ <b><a href="{}">{}</a></b>'.format(
                    utils.get_entity_url(chat_entity),
                    utils.escape_html(get_display_name(chat_entity)),
                )
            ]

        if not chats:
            await utils.answer(message, self.strings["nothing"])
            return

        await utils.answer(
            message,
            self.strings["user_nn_list"].format("\n".join(chats)),
        )

    async def inline__setting(self, call: InlineCall, key: str, state: bool = False):

        self.db.set(main.__name__, key, state)

        if key == "no_nickname" and state and self.get_prefix() == ".":
            await call.answer(
                self.strings["nonick_warning"],
                show_alert=True,
            )
        else:
            await call.answer("Configuration value saved!")

        await call.edit(
            self.strings["inline_settings"],
            reply_markup=self._get_settings_markup(),
        )

    async def inline__update(
        self,
        call: InlineCall,
        confirm_required: bool = False,
    ):
        if confirm_required:
            await call.edit(
                self.strings["confirm_update"],
                reply_markup=[
                    {
                        "text": "🪂 Update",
                        "callback": self.inline__update,
                        "style": "primary",
                    },
                    {
                        "text": "🚫 Cancel",
                        "action": "close",
                        "style": "danger",
                    },
                ],
            )
            return

        await call.answer("You userbot is being updated...", show_alert=True)
        await call.delete()
        await self.invoke("update", "-f", peer="me")

    async def inline__restart(
        self,
        call: InlineCall,
        confirm_required: bool = False,
    ):
        if confirm_required:
            await call.edit(
                self.strings["confirm_restart"],
                reply_markup=[
                    {
                        "text": "🔄 Restart",
                        "callback": self.inline__restart,
                        "style": "primary",
                    },
                    {"text": "🚫 Cancel", "action": "close", "style": "danger"},
                ],
            )
            return

        await call.answer("You userbot is being restarted...", show_alert=True)
        await call.delete()
        await self.invoke("restart", "-f", peer="me")

    def _get_settings_markup(self) -> list:
        return [
            [
                (
                    {
                        "text": "✅ NoNick",
                        "callback": self.inline__setting,
                        "args": (
                            "no_nickname",
                            False,
                        ),
                    }
                    if self._db.get(main.__name__, "no_nickname", False)
                    else {
                        "text": "🚫 NoNick",
                        "callback": self.inline__setting,
                        "args": (
                            "no_nickname",
                            True,
                        ),
                    }
                ),
                (
                    {
                        "text": "✅ Grep",
                        "callback": self.inline__setting,
                        "args": (
                            "grep",
                            False,
                        ),
                    }
                    if self._db.get(main.__name__, "grep", False)
                    else {
                        "text": "🚫 Grep",
                        "callback": self.inline__setting,
                        "args": (
                            "grep",
                            True,
                        ),
                    }
                ),
                (
                    {
                        "text": "✅ InlineLogs",
                        "callback": self.inline__setting,
                        "args": (
                            "inlinelogs",
                            False,
                        ),
                    }
                    if self._db.get(main.__name__, "inlinelogs", True)
                    else {
                        "text": "🚫 InlineLogs",
                        "callback": self.inline__setting,
                        "args": (
                            "inlinelogs",
                            True,
                        ),
                    }
                ),
            ],
            [
                (
                    {
                        "text": self.strings["suggest_subscribe"],
                        "callback": self.inline__setting,
                        "args": (
                            "suggest_subscribe",
                            False,
                        ),
                    }
                    if self._db.get(main.__name__, "suggest_subscribe", True)
                    else {
                        "text": self.strings["do_not_suggest_subscribe"],
                        "callback": self.inline__setting,
                        "args": (
                            "suggest_subscribe",
                            True,
                        ),
                    }
                ),
            ],
            [
                {
                    "text": self.strings["btn_restart"],
                    "callback": self.inline__restart,
                    "style": "primary",
                    "args": (True,),
                },
                {
                    "text": self.strings["btn_update"],
                    "callback": self.inline__update,
                    "style": "primary",
                    "args": (True,),
                },
            ],
            [
                {
                    "text": self.strings["close_menu"],
                    "action": "close",
                    "style": "danger",
                }
            ],
        ]

    @loader.command()
    async def settings(self, message: Message):
        await self.inline.form(
            self.strings["inline_settings"],
            message=message,
            reply_markup=self._get_settings_markup(),
        )

    def _get_all_IDM(self, module: str):
        return {
            getattr(getattr(self.lookup(module), name), "name", name): getattr(
                self.lookup(module), name
            )
            for name in dir(self.lookup(module))
            if getattr(getattr(self.lookup(module), name), "is_debug_method", False)
        }

    @staticmethod
    def prep_value(value: typing.Any) -> typing.Any:
        if isinstance(value, str):
            return f"<b><code>{utils.escape_html(value.strip())}</code></b>"

        if isinstance(value, list) and value:
            return (
                "<b><code>[</code></b>\n    "
                + "\n    ".join(
                    [
                        f"<b><code>{utils.escape_html(str(item))}</code></b>"
                        for item in value
                    ]
                )
                + "\n<b><code>]</code></b>"
            )

        return f"<b><code>{utils.escape_html(value)}</code></b>"

    def hide_value(self, value: typing.Any) -> str:
        if isinstance(value, list) and value:
            return self.prep_value(["*" * len(str(i)) for i in value])

        return self.prep_value("*" * len(str(value)))

    def _get_value(self, mod: str, option: str) -> str:
        return (
            self.prep_value(self.lookup(mod).config[option])
            if (
                not self.lookup(mod).config._config[option].validator
                or self.lookup(mod).config._config[option].validator.internal_id
                != "Hidden"
            )
            else self.hide_value(self.lookup(mod).config[option])
        )

    def _get_inline_value(self, mod: str, option: str, limit: int = 2500) -> str:
        value = self._get_value(mod, option)
        if len(value) <= limit:
            return value

        plain = utils.remove_html(value)
        suffix = "\n... <i>значение обрезано для inline-сообщения</i>"
        plain_limit = max(0, limit - len(suffix) - len("<b><code></code></b>"))
        return f"<b><code>{utils.escape_html(plain[:plain_limit])}</code></b>{suffix}"

    @staticmethod
    def _paginate_text_markup(
        text: str,
        page: int,
        callback: typing.Any,
    ) -> tuple[str, list[list[dict[str, typing.Any]]]]:
        parsed_text, parsed_entities = html.parse(text)
        pages = list(
            utils.smart_split(parsed_text, typing.cast(typing.Any, parsed_entities))
        )

        if len(pages) <= 1:
            return text, []

        page = min(max(page, 0), len(pages) - 1)

        row = []
        if page > 0:
            row.append({"text": "◀️", "callback": callback, "args": (page - 1,)})

        row.append(
            {"text": f"{page + 1}/{len(pages)}", "callback": callback, "args": (page,)}
        )

        if page < len(pages) - 1:
            row.append({"text": "▶️", "callback": callback, "args": (page + 1,)})

        return pages[page], [row]

    @staticmethod
    def _put_pagination_before_nav(
        reply_markup: list[list[dict[str, typing.Any]]],
        pagination: list[list[dict[str, typing.Any]]],
    ) -> list[list[dict[str, typing.Any]]]:
        if not pagination:
            return reply_markup

        return reply_markup[:-1] + pagination + reply_markup[-1:]

    def _guess_back_to_page(
        self,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ) -> dict:
        kwargs = {"obj_type": obj_type}
        cat = self.lookup(mod).config.get_category(option)
        if cat is not None:
            kwargs["category"] = cat.name
        return kwargs

    @staticmethod
    def _config_categories(instance: typing.Any) -> dict[str, list[str]]:
        return {
            category: options
            for category, options in instance.config.grouped_options().items()
            if category is not None
        }

    @staticmethod
    def _get_category_doc(instance: typing.Any, category: str) -> str:
        cat_obj = getattr(instance.config, "_categories", {}).get(category)
        return cat_obj.getdoc() if cat_obj else ""

    async def inline__set_config(
        self,
        call: InlineCall,
        query: str,
        mod: str,
        option: str,
        inline_message_id: str | None = None,
        obj_type: bool | str = False,
    ):
        try:
            self.lookup(mod).config[option] = query
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        await call.edit(
            self.strings[
                "option_saved" if isinstance(obj_type, bool) else "option_saved_lib"
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                self._get_inline_value(mod, option),
            ),
            reply_markup=[
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, option, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
            inline_message_id=inline_message_id or call.inline_message_id,
        )

    async def inline__reset_default(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ):
        mod_instance = self.lookup(mod)
        mod_instance.config[option] = mod_instance.config.getdef(option)

        await call.edit(
            self.strings[
                "option_reset" if isinstance(obj_type, bool) else "option_reset_lib"
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                self._get_inline_value(mod, option),
            ),
            reply_markup=[
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, option, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
        )

    async def inline__set_bool(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        value: bool,
        obj_type: bool | str = False,
    ):
        try:
            self.lookup(mod).config[option] = value
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        validator = self.lookup(mod).config._config[option].validator
        doc = utils.escape_html(
            next(
                (
                    validator.doc[lang]
                    for original_lang in self._db.get(
                        translations.__name__, "lang", "en"
                    ).split(" ")
                    for lang in translations.iter_language_codes(original_lang)
                    if lang in validator.doc
                ),
                validator.doc["en"],
            )
        )

        await call.edit(
            self.strings[
                (
                    "configuring_option"
                    if isinstance(obj_type, bool)
                    else "configuring_option_lib"
                )
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                utils.escape_html(self.lookup(mod).config.getdoc(option)),
                self.prep_value(self.lookup(mod).config.getdef(option)),
                (
                    self.prep_value(self.lookup(mod).config[option])
                    if not validator or validator.internal_id != "Hidden"
                    else self.hide_value(self.lookup(mod).config[option])
                ),
                (
                    self.strings["typehint"].format(
                        doc,
                        eng_art="n" if doc.lower().startswith(tuple("euioay")) else "",
                    )
                    if doc
                    else ""
                ),
            ),
            reply_markup=self._generate_bool_markup(mod, option, obj_type),
        )

        await call.answer("✅")

    def _generate_bool_markup(
        self,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ) -> list:
        return [
            [
                *(
                    [
                        {
                            "text": f"❌ {self.strings['set']} `False`",
                            "callback": self.inline__set_bool,
                            "args": (mod, option, False),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                    if self.lookup(mod).config[option]
                    else [
                        {
                            "text": f"✅ {self.strings['set']} `True`",
                            "callback": self.inline__set_bool,
                            "args": (mod, option, True),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                )
            ],
            [
                *(
                    [
                        {
                            "text": self.strings["set_default_btn"],
                            "callback": self.inline__reset_default,
                            "args": (mod, option),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else []
                )
            ],
            [
                {
                    "text": self.strings["back_btn"],
                    "callback": self.inline__configure,
                    "args": (mod,),
                    "style": "primary",
                    "kwargs": self._guess_back_to_page(mod, option, obj_type),
                },
                {
                    "text": self.strings["close_btn"],
                    "action": "close",
                    "style": "danger",
                },
            ],
        ]

    async def inline__add_item(
        self,
        call: InlineCall,
        query: str,
        mod: str,
        option: str,
        inline_message_id: str | None = None,
        obj_type: bool | str = False,
    ):
        try:
            with contextlib.suppress(Exception):
                query = ast.literal_eval(query)

            if isinstance(query, (set, tuple)):
                query = list(query)

            if not isinstance(query, list):
                query = [query]

            self.lookup(mod).config[option] = self.lookup(mod).config[option] + query
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        await call.edit(
            self.strings[
                "option_saved" if isinstance(obj_type, bool) else "option_saved_lib"
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                self._get_inline_value(mod, option),
            ),
            reply_markup=[
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, option, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
            inline_message_id=inline_message_id or call.inline_message_id,
        )

    async def inline__remove_item(
        self,
        call: InlineCall,
        query: str,
        mod: str,
        option: str,
        inline_message_id: str | None = None,
        obj_type: bool | str = False,
    ):
        try:
            with contextlib.suppress(Exception):
                query = ast.literal_eval(query)

            if isinstance(query, (set, tuple)):
                query = list(query)

            if not isinstance(query, list):
                query = [query]

            query = list(map(str, query))

            old_config_len = len(self.lookup(mod).config[option])

            self.lookup(mod).config[option] = [
                i for i in self.lookup(mod).config[option] if str(i) not in query
            ]

            if old_config_len == len(self.lookup(mod).config[option]):
                raise loader.validators.ValidationError(
                    f"Nothing from passed value ({self.prep_value(query)}) is not in"
                    " target list"
                )
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        await call.edit(
            self.strings[
                "option_saved" if isinstance(obj_type, bool) else "option_saved_lib"
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                self._get_inline_value(mod, option),
            ),
            reply_markup=[
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, option, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
            inline_message_id=inline_message_id or call.inline_message_id,
        )

    def _generate_series_markup(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ) -> list:
        return [
            [
                {
                    "text": self.strings["enter_value_btn"],
                    "input": self.strings["enter_value_desc"],
                    "handler": self.inline__set_config,
                    "args": (mod, option, call.inline_message_id),
                    "kwargs": {"obj_type": obj_type},
                }
            ],
            [
                *(
                    [
                        {
                            "text": self.strings["remove_item_btn"],
                            "input": self.strings["remove_item_desc"],
                            "handler": self.inline__remove_item,
                            "args": (mod, option, call.inline_message_id),
                            "kwargs": {"obj_type": obj_type},
                        },
                        {
                            "text": self.strings["add_item_btn"],
                            "input": self.strings["add_item_desc"],
                            "handler": self.inline__add_item,
                            "args": (mod, option, call.inline_message_id),
                            "kwargs": {"obj_type": obj_type},
                        },
                    ]
                    if self.lookup(mod).config[option]
                    else []
                ),
            ],
            [
                *(
                    [
                        {
                            "text": self.strings["set_default_btn"],
                            "callback": self.inline__reset_default,
                            "args": (mod, option),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else []
                )
            ],
            [
                {
                    "text": self.strings["back_btn"],
                    "callback": self.inline__configure,
                    "args": (mod,),
                    "style": "primary",
                    "kwargs": self._guess_back_to_page(mod, option, obj_type),
                },
                {
                    "text": self.strings["close_btn"],
                    "action": "close",
                    "style": "danger",
                },
            ],
        ]

    async def _choice_set_value(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        value: bool,
        obj_type: bool | str = False,
    ):
        try:
            self.lookup(mod).config[option] = value
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        await call.edit(
            self.strings[
                "option_saved" if isinstance(obj_type, bool) else "option_saved_lib"
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                self._get_inline_value(mod, option),
            ),
            reply_markup=[
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, option, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
        )

        await call.answer("✅")

    async def _multi_choice_set_value(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        value: bool,
        obj_type: bool | str = False,
    ):
        try:
            if value in self.lookup(mod).config._config[option].value:
                self.lookup(mod).config._config[option].value.remove(value)
            else:
                self.lookup(mod).config._config[option].value += [value]

            self.lookup(mod).config.reload()
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        await self.inline__configure_option(
            call, mod=mod, config_opt=option, force_hidden=False, obj_type=obj_type
        )
        await call.answer("✅")

    def _generate_choice_markup(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ) -> list:
        possible_values = list(
            self.lookup(mod)
            .config._config[option]
            .validator.validate.keywords["possible_values"]
        )
        return [
            [
                {
                    "text": self.strings["enter_value_btn"],
                    "input": self.strings["enter_value_desc"],
                    "handler": self.inline__set_config,
                    "args": (mod, option, call.inline_message_id),
                    "kwargs": {"obj_type": obj_type},
                }
            ],
            *utils.chunks(
                [
                    {
                        "text": (
                            f"{'☑️' if self.lookup(mod).config[option] == value else '🔘'} "
                            f"{value if len(str(value)) < 20 else str(value)[:20]}"
                        ),
                        "callback": self._choice_set_value,
                        "args": (mod, option, value, obj_type),
                    }
                    for value in possible_values
                ],
                2,
            )[
                : (
                    6
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else 7
                )
            ],
            [
                *(
                    [
                        {
                            "text": self.strings["set_default_btn"],
                            "callback": self.inline__reset_default,
                            "args": (mod, option),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else []
                )
            ],
            [
                {
                    "text": self.strings["back_btn"],
                    "callback": self.inline__configure,
                    "args": (mod,),
                    "style": "primary",
                    "kwargs": self._guess_back_to_page(mod, option, obj_type),
                },
                {
                    "text": self.strings["close_btn"],
                    "action": "close",
                    "style": "danger",
                },
            ],
        ]

    def _generate_multi_choice_markup(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ) -> list:
        possible_values = list(
            self.lookup(mod)
            .config._config[option]
            .validator.validate.keywords["possible_values"]
        )
        return [
            [
                {
                    "text": self.strings["enter_value_btn"],
                    "input": self.strings["enter_value_desc"],
                    "handler": self.inline__set_config,
                    "args": (mod, option, call.inline_message_id),
                    "kwargs": {"obj_type": obj_type},
                }
            ],
            *utils.chunks(
                [
                    {
                        "text": (
                            f"{'☑️' if value in self.lookup(mod).config[option] else '◻️'} "
                            f"{value if len(str(value)) < 20 else str(value)[:20]}"
                        ),
                        "callback": self._multi_choice_set_value,
                        "args": (mod, option, value, obj_type),
                    }
                    for value in possible_values
                ],
                2,
            )[
                : (
                    6
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else 7
                )
            ],
            [
                *(
                    [
                        {
                            "text": self.strings["set_default_btn"],
                            "callback": self.inline__reset_default,
                            "args": (mod, option),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else []
                )
            ],
            [
                {
                    "text": self.strings["back_btn"],
                    "callback": self.inline__configure,
                    "args": (mod,),
                    "style": "primary",
                    "kwargs": self._guess_back_to_page(mod, option, obj_type),
                },
                {
                    "text": self.strings["close_btn"],
                    "action": "close",
                    "style": "danger",
                },
            ],
        ]

    async def inline__configure_option(
        self,
        call: InlineCall,
        page: int = 0,
        mod: str = "",
        config_opt: str = "",
        force_hidden: bool = False,
        obj_type: bool | str = False,
    ):
        module = self.lookup(mod)
        args = [
            utils.escape_html(config_opt),
            utils.escape_html(mod),
            utils.escape_non_html(module.config.getdoc(config_opt)),
            self.prep_value(module.config.getdef(config_opt)),
            (
                self.prep_value(module.config[config_opt])
                if not module.config._config[config_opt].validator
                or module.config._config[config_opt].validator.internal_id != "Hidden"
                or force_hidden
                else self.hide_value(module.config[config_opt])
            ),
        ]

        if (
            module.config._config[config_opt].validator
            and module.config._config[config_opt].validator.internal_id == "Hidden"
        ):
            additonal_button_row = (
                [
                    [
                        {
                            "text": self.strings["hide_value"],
                            "callback": self.inline__configure_option,
                            "kwargs": {
                                "obj_type": obj_type,
                                "mod": mod,
                                "config_opt": config_opt,
                                "force_hidden": False,
                            },
                        }
                    ]
                ]
                if force_hidden
                else [
                    [
                        {
                            "text": self.strings["show_hidden"],
                            "callback": self.inline__configure_option,
                            "kwargs": {
                                "obj_type": obj_type,
                                "mod": mod,
                                "config_opt": config_opt,
                                "force_hidden": True,
                            },
                        }
                    ]
                ]
            )
        else:
            additonal_button_row = []

        try:
            validator = module.config._config[config_opt].validator
            doc = utils.escape_html(
                next(
                    (
                        validator.doc[lang]
                        for original_lang in self._db.get(
                            translations.__name__, "lang", "en"
                        ).split(" ")
                        for lang in translations.iter_language_codes(original_lang)
                        if lang in validator.doc
                    ),
                    validator.doc["en"],
                )
            )
        except Exception:
            doc = None
            validator = None
            args += [""]
        else:
            args += [
                self.strings["typehint"].format(
                    doc,
                    eng_art="n" if doc.lower().startswith(tuple("euioay")) else "",
                )
            ]
            text = self.strings[
                (
                    "configuring_option"
                    if isinstance(obj_type, bool)
                    else "configuring_option_lib"
                )
            ].format(*args)
            text, pagination = self._paginate_text_markup(
                text,
                page,
                functools.partial(
                    self.inline__configure_option,
                    mod=mod,
                    config_opt=config_opt,
                    force_hidden=force_hidden,
                    obj_type=obj_type,
                ),
            )
            match validator.internal_id:
                case "Boolean":
                    await call.edit(
                        text,
                        reply_markup=additonal_button_row
                        + self._put_pagination_before_nav(
                            self._generate_bool_markup(mod, config_opt, obj_type),
                            pagination,
                        ),
                    )
                    return
                case "Series":
                    await call.edit(
                        text,
                        reply_markup=additonal_button_row
                        + self._put_pagination_before_nav(
                            self._generate_series_markup(
                                call, mod, config_opt, obj_type
                            ),
                            pagination,
                        ),
                    )
                    return
                case "Choice":
                    await call.edit(
                        text,
                        reply_markup=additonal_button_row
                        + self._put_pagination_before_nav(
                            self._generate_choice_markup(
                                call, mod, config_opt, obj_type
                            ),
                            pagination,
                        ),
                    )
                    return
                case "MultiChoice":
                    await call.edit(
                        text,
                        reply_markup=additonal_button_row
                        + self._put_pagination_before_nav(
                            self._generate_multi_choice_markup(
                                call, mod, config_opt, obj_type
                            ),
                            pagination,
                        ),
                    )
                    return

        text = self.strings[
            (
                "configuring_option"
                if isinstance(obj_type, bool)
                else "configuring_option_lib"
            )
        ].format(*args)

        text, pagination = self._paginate_text_markup(
            text,
            page,
            functools.partial(
                self.inline__configure_option,
                mod=mod,
                config_opt=config_opt,
                force_hidden=force_hidden,
                obj_type=obj_type,
            ),
        )

        await call.edit(
            text,
            reply_markup=additonal_button_row
            + [
                [
                    {
                        "text": self.strings["enter_value_btn"],
                        "input": self.strings["enter_value_desc"],
                        "handler": self.inline__set_config,
                        "args": (mod, config_opt, call.inline_message_id),
                        "kwargs": {"obj_type": obj_type},
                    }
                ],
                [
                    {
                        "text": self.strings["set_default_btn"],
                        "callback": self.inline__reset_default,
                        "args": (mod, config_opt),
                        "kwargs": {"obj_type": obj_type},
                    }
                ],
                *pagination,
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, config_opt, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ],
            ],
        )

    async def inline__configure_page(
        self,
        call: InlineCall,
        page: int = 0,
        mod: str = "",
        obj_type: bool | str = False,
        folder: str | None = None,
        category: str | None = None,
    ):
        await self.inline__configure(
            call,
            mod,
            page=page,
            obj_type=obj_type,
            folder=folder,
            category=category,
        )

    async def inline__configure(
        self,
        call: InlineCall,
        mod: str,
        page: int = 0,
        obj_type: bool | str = False,
        folder: str | None = None,
        category: str | None = None,
    ):

        module = self.lookup(mod)
        grouped = module.config.grouped_options()

        def fmt_value(option: str) -> str:
            value = self._get_inline_value(mod, option)
            if len(value) >= 200:
                value = list(utils.smart_split(*html.parse(value), 200))[0] + "..."
            return value

        close_btn = {
            "text": self.strings["close_btn"],
            "action": "close",
            "style": "danger",
        }

        if category is not None:
            params = list(grouped.get(category, []))
            option_lines = [
                f"<tg-emoji emoji-id=5253713110111365241>▫️</tg-emoji> <code>{utils.escape_html(p)}</code>: {fmt_value(p)}"
                for p in params
            ]
            options_text = "\n".join(option_lines) if option_lines else "No options"

            cat_doc = self._get_category_doc(module, category)

            cat_text = self.strings[
                (
                    "configuring_category"
                    if isinstance(obj_type, bool)
                    else "configuring_category_lib"
                )
            ].format(
                utils.escape_html(mod),
                utils.escape_html(category),
                utils.escape_html(cat_doc),
                options_text,
            )
            cat_text, pagination = self._paginate_text_markup(
                cat_text,
                page,
                functools.partial(
                    self.inline__configure_page,
                    mod=mod,
                    obj_type=obj_type,
                    category=category,
                ),
            )

            return await call.edit(
                cat_text,
                reply_markup=list(
                    utils.chunks(
                        [
                            {
                                "text": opt,
                                "callback": self.inline__configure_option,
                                "kwargs": {
                                    "obj_type": obj_type,
                                    "mod": mod,
                                    "config_opt": opt,
                                },
                            }
                            for opt in params
                        ],
                        2,
                    )
                )
                + pagination
                + [
                    [
                        {
                            "text": self.strings["back_btn"],
                            "callback": self.inline__configure,
                            "args": (mod,),
                            "style": "primary",
                            "kwargs": {"obj_type": obj_type},
                        },
                        close_btn,
                    ]
                ],
            )

        elif folder is not None:
            params = list(module.config)
            option_lines = [
                f"<tg-emoji emoji-id=5253713110111365241>▫️</tg-emoji> <code>{utils.escape_html(p)}</code>: {fmt_value(p)}"
                for p in params
            ]
            text = "\n".join(option_lines) if option_lines else "No options"
            text = self.strings[
                ("configuring_mod" if isinstance(obj_type, bool) else "configuring_lib")
            ].format(utils.escape_html(mod), text)
            text, pagination = self._paginate_text_markup(
                text,
                page,
                functools.partial(
                    self.inline__configure_page,
                    mod=mod,
                    obj_type=obj_type,
                    folder=folder,
                ),
            )

            return await call.edit(
                text,
                reply_markup=list(
                    utils.chunks(
                        [
                            {
                                "text": opt,
                                "callback": self.inline__configure_option,
                                "kwargs": {
                                    "obj_type": obj_type,
                                    "mod": mod,
                                    "config_opt": opt,
                                },
                            }
                            for opt in params
                        ],
                        2,
                    )
                )
                + pagination
                + [
                    [
                        {
                            "text": self.strings["back_btn"],
                            "callback": self.inline__global_config,
                            "style": "primary",
                            "kwargs": {"obj_type": obj_type},
                        },
                        close_btn,
                    ]
                ],
            )

        sections = []
        btns = []
        for section_name, section_params in grouped.items():
            if section_name is None:
                visible = [
                    p
                    for p in section_params
                    if not getattr(module.config._config.get(p), "folder", None)
                ]
                if not visible:
                    continue
                sections.append(
                    "\n".join(
                        "<tg-emoji emoji-id=5253713110111365241>▫️</tg-emoji> <code>{}</code>: {}".format(
                            utils.escape_html(p), fmt_value(p)
                        )
                        for p in visible
                    )
                )
                btns += [
                    {
                        "text": opt,
                        "callback": self.inline__configure_option,
                        "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": opt},
                    }
                    for opt in visible
                ]
            else:
                cat_lines = [
                    "∟ <tg-emoji emoji-id=5253713110111365241>▫️</tg-emoji> <code>{}</code>: {}".format(
                        utils.escape_html(p), fmt_value(p)
                    )
                    for p in section_params
                ]
                cat_text = [
                    self.strings["category_header"].format(
                        utils.escape_html(section_name)
                    ),
                    "<blockquote expandable>" + "\n".join(cat_lines),
                    "</blockquote>",
                ]
                sections.append("\n".join(cat_text))
                btns.append(
                    {
                        "text": f"📂 {section_name}",
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "kwargs": {"obj_type": obj_type, "category": section_name},
                    }
                )

        text = "\n".join(sections).lstrip("\n") if sections else "No options"
        text = self.strings[
            "configuring_mod" if isinstance(obj_type, bool) else "configuring_lib"
        ].format(utils.escape_html(mod), text)
        text, pagination = self._paginate_text_markup(
            text,
            page,
            functools.partial(self.inline__configure_page, mod=mod, obj_type=obj_type),
        )

        await call.edit(
            text,
            reply_markup=list(utils.chunks(btns, 2))
            + pagination
            + [
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__global_config,
                        "style": "primary",
                        "kwargs": {"obj_type": obj_type},
                    },
                    close_btn,
                ]
            ],
        )

    def _fuzzy_lookup_configurable(self, query: str) -> tuple[str | None, bool]:
        query_lower = query.lower()
        best_score = -1.0
        best_name: str | None = None

        for mod in self.allmodules.modules:
            if not hasattr(mod, "config") or not mod.config:
                continue
            try:
                mod_name = (
                    mod.strings("name")
                    if callable(mod.strings)
                    else mod.__class__.__name__
                )
            except Exception:
                mod_name = mod.__class__.__name__

            cls_name = mod.__class__.__name__
            names = {mod_name, cls_name}
            if cls_name.endswith("Mod"):
                names.add(cls_name[:-3])

            for name in names:
                if name.lower() == query_lower:
                    return mod_name, True
                score = difflib.SequenceMatcher(None, query_lower, name.lower()).ratio()
                if score > best_score:
                    best_score = score
                    best_name = mod_name

        for lib in self.allmodules.libraries:
            if not hasattr(lib, "config") or not lib.config:
                continue
            lib_name = getattr(lib, "name", lib.__class__.__name__)
            if lib_name.lower() == query_lower:
                return lib_name, True
            score = difflib.SequenceMatcher(None, query_lower, lib_name.lower()).ratio()
            if score > best_score:
                best_score = score
                best_name = lib_name

        return best_name, False

    def _get_all_folders(self) -> dict:
        folders = {}
        for mod in self.allmodules.modules:
            if not hasattr(mod, "config") or not mod.config:
                continue
            mod_name = (
                mod.strings("name") if callable(mod.strings) else mod.__class__.__name__
            )
            module_folders = set()
            for param in mod.config:
                config_value = mod.config._config.get(param)
                if (
                    config_value
                    and hasattr(config_value, "folder")
                    and config_value.folder
                ):
                    module_folders.add(config_value.folder)

            for folder_name in module_folders:
                if folder_name not in folders:
                    folders[folder_name] = {}
                folders[folder_name][mod_name] = [p for p in mod.config]
        try:
            preset_folders = self.db.get("presets", "folders")
        except Exception:
            preset_folders = {}

        if preset_folders:
            for folder_name, mod_list in preset_folders.items():
                if folder_name not in folders:
                    folders[folder_name] = {}
                for raw_mod in mod_list:
                    for mod in self.allmodules.modules:
                        try:
                            if mod.__class__.__name__.lower() == raw_mod.lower():
                                mod_name = (
                                    mod.strings("name")
                                    if callable(mod.strings)
                                    else mod.__class__.__name__
                                )
                                if mod_name not in folders[folder_name]:
                                    folders[folder_name][mod_name] = [
                                        p for p in mod.config
                                    ]
                                break
                        except Exception:
                            continue

        return folders

    async def inline__choose_category(self, call: Message | InlineCall):
        all_folders = self._get_all_folders()

        folder_btns = [
            {
                "text": f"📁 {folder_name}",
                "callback": self.inline__global_folder,
                "kwargs": {"folder": folder_name},
            }
            for folder_name in sorted(all_folders.keys())
        ]

        await utils.answer(
            call,
            self.strings["choose_core"],
            reply_markup=[
                [
                    {
                        "text": self.strings["builtin"],
                        "callback": self.inline__global_config,
                        "kwargs": {"obj_type": True},
                    },
                    {
                        "text": self.strings["external"],
                        "callback": self.inline__global_config,
                    },
                ],
                *(
                    [
                        [
                            {
                                "text": self.strings["libraries"],
                                "callback": self.inline__global_config,
                                "kwargs": {"obj_type": "library"},
                            }
                        ]
                    ]
                    if self.allmodules.libraries
                    and any(hasattr(lib, "config") for lib in self.allmodules.libraries)
                    else []
                ),
                *list(utils.chunks(folder_btns, 2)),
                [
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    }
                ],
            ],
        )

    async def _send_initial_config_form(
        self,
        message: Message,
        handler: typing.Callable[..., typing.Awaitable[typing.Any]],
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        draft = _InlineFormDraft()
        await handler(draft, *args, **kwargs)

        if draft.text is None:
            return

        form_kwargs = dict(draft.kwargs)
        form_kwargs.pop("inline_message_id", None)

        await self.inline.form(
            draft.text,
            message=message,
            reply_markup=draft.reply_markup,
            silent=True,
            **form_kwargs,
        )

    async def inline__global_folder(
        self,
        call: InlineCall,
        folder: str,
    ):
        all_folders = self._get_all_folders()
        folder_options = all_folders.get(folder, {})

        btns = [
            {
                "text": f"{mod_name}",
                "callback": self.inline__configure,
                "kwargs": {"obj_type": False, "mod": mod_name, "folder": folder},
            }
            for mod_name in sorted(folder_options.keys())
        ]

        text_parts = []
        for mod_name, params in folder_options.items():
            try:
                raw_parts = []
                for param in params:
                    try:
                        raw_value = str(self.lookup(mod_name).config[param])
                        if len(raw_value) > 100:
                            raw_value = raw_value[:100] + "..."
                        raw_parts.append(
                            f"<code>{utils.escape_html(param)}</code>: <code>{utils.escape_html(raw_value)}</code>"
                        )
                    except Exception:
                        raw_parts.append(f"<code>{utils.escape_html(param)}</code>")
                text_parts.append(
                    f"<tg-emoji emoji-id=5253713110111365241>▫️</tg-emoji> <b>{utils.escape_html(mod_name)}</b>"
                )
            except Exception:
                text_parts.append(
                    f"<tg-emoji emoji-id=5253713110111365241>▫️</tg-emoji> <b>{utils.escape_html(mod_name)}</b>"
                )

        await call.edit(
            self.strings["configuring_folder"].format(
                utils.escape_html(folder),
                "\n".join(text_parts) if text_parts else "No options",
            ),
            reply_markup=list(utils.chunks(btns, 1))
            + [
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__choose_category,
                        "style": "primary",
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
        )

    async def inline__global_config(
        self,
        call: InlineCall,
        page: int = 0,
        obj_type: bool | str = False,
    ):
        if isinstance(obj_type, bool):
            to_config = [
                mod.strings("name")
                for mod in self.allmodules.modules
                if hasattr(mod, "config")
                and callable(mod.strings)
                and (mod.__origin__.startswith("<core") or not obj_type)
                and (not mod.__origin__.startswith("<core") or obj_type)
            ]
        else:
            to_config = [
                lib.name for lib in self.allmodules.libraries if hasattr(lib, "config")
            ]

        to_config.sort()

        kb = []
        for mod_row in utils.chunks(
            to_config[page * NUM_ROWS * ROW_SIZE : (page + 1) * NUM_ROWS * ROW_SIZE],
            3,
        ):
            row = [
                {
                    "text": btn,
                    "callback": self.inline__configure,
                    "args": (btn,),
                    "kwargs": {"obj_type": obj_type},
                }
                for btn in mod_row
            ]
            kb += [row]

        if len(to_config) > NUM_ROWS * ROW_SIZE:
            kb += self.inline.build_pagination(
                callback=functools.partial(
                    self.inline__global_config, obj_type=obj_type
                ),
                total_pages=ceil(len(to_config) / (NUM_ROWS * ROW_SIZE)),
                current_page=page + 1,
            )

        kb += [
            [
                {
                    "text": self.strings["back_btn"],
                    "callback": self.inline__choose_category,
                    "style": "primary",
                },
                {
                    "text": self.strings["close_btn"],
                    "action": "close",
                    "style": "danger",
                },
            ]
        ]

        await call.edit(
            self.strings[
                "configure" if isinstance(obj_type, bool) else "configure_lib"
            ],
            reply_markup=kb,
        )

    @staticmethod
    def _get_config_obj_type(instance: typing.Any) -> bool | str:
        if isinstance(instance, loader.Library):
            return "library"

        return instance.__origin__.startswith("<core")

    def _resolve_configurable(
        self,
        query: str,
    ) -> tuple[str | None, typing.Any, bool | str | None]:
        if (instance := self.lookup(query)) and hasattr(instance, "config"):
            return query, instance, self._get_config_obj_type(instance)

        fuzzy_name, _ = self._fuzzy_lookup_configurable(query)
        if fuzzy_name and (instance := self.lookup(fuzzy_name)):
            if hasattr(instance, "config") and instance.config:
                return fuzzy_name, instance, self._get_config_obj_type(instance)

        return None, None, None

    @staticmethod
    def _category_option(
        instance: typing.Any,
        category: str,
        option: str,
    ) -> str | None:
        if option in CoreMod._config_categories(instance).get(category, []):
            return option

        return None

    def _parse_config_update(
        self,
        instance: typing.Any,
        raw: str,
        reply_text: str | None = None,
        first_part: bool = False,
    ) -> tuple[str, str] | None:
        if first_part:
            split = raw.split(maxsplit=3)
            if len(split) >= 4:
                _, category, option, value = split
                if config_opt := self._category_option(instance, category, option):
                    return config_opt, value

            split = raw.split(maxsplit=2)
            if len(split) >= 3 and split[1] in instance.config:
                return split[1], split[2]

            if len(split) == 2 and reply_text and split[1] in instance.config:
                return split[1], reply_text

            return None

        split = raw.split(maxsplit=2)
        if len(split) >= 3:
            category, option, value = split
            if config_opt := self._category_option(instance, category, option):
                return config_opt, value

        split = raw.split(maxsplit=1)
        if len(split) >= 2:
            return split[0], split[1]

        return None

    async def _apply_config_updates(
        self,
        message: Message,
        mod: str,
        instance: typing.Any,
        first_update: tuple[str, str],
        parts: list[str],
    ) -> None:
        updates = []

        for option, value in [first_update]:
            if option not in instance.config:
                await utils.answer(message, self.strings["no_option"])
                return

            try:
                instance.config[option] = value
            except loader.validators.ValidationError as e:
                await utils.answer(
                    message, self.strings["validation_error"].format(e.args[0])
                )
                return

            updates.append((option, self._get_value(mod, option)))

        for part in parts:
            update = self._parse_config_update(instance, part)
            if update is None:
                await utils.answer(message, self.strings["cfg_args"])
                return

            option, value = update
            if option not in instance.config:
                await utils.answer(message, self.strings["no_option"])
                return

            try:
                instance.config[option] = value
            except loader.validators.ValidationError as e:
                await utils.answer(
                    message, self.strings["validation_error"].format(e.args[0])
                )
                return

            updates.append((option, self._get_value(mod, option)))

        lines = []
        for option, value in updates:
            lines.append(
                self.strings[
                    (
                        "option_saved"
                        if isinstance(instance, loader.Module)
                        else "option_saved_lib"
                    )
                ].format(utils.escape_html(option), utils.escape_html(mod), value)
            )

        await utils.answer(message, "\n".join(lines))

    async def _reset_config_option(self, message: Message, raw: str):
        text = re.sub(r"(?:^|\s)(?:-r|--reset)(?=\s|$)", " ", raw, count=1).strip()
        parts = [
            part.strip()
            for chunk in text.split("&&")
            for part in chunk.splitlines()
            if part.strip()
        ]
        if not parts:
            await utils.answer(message, self.strings["cfg_args"])
            return

        lines = []
        for part in parts:
            args = part.split()

            mod_name, instance, _ = self._resolve_configurable(args[0])
            if not mod_name or not instance:
                await utils.answer(message, self.strings["no_mod"])
                return

            if len(args) == 2 and args[1] in instance.config:
                option = args[1]
            elif len(args) == 3 and (
                config_opt := self._category_option(instance, args[1], args[2])
            ):
                option = config_opt
            else:
                await utils.answer(message, self.strings["no_option"])
                return

            instance.config[option] = instance.config.getdef(option)
            lines.append(
                self.strings[
                    "option_reset"
                    if isinstance(instance, loader.Module)
                    else "option_reset_lib"
                ].format(
                    utils.escape_html(option),
                    utils.escape_html(mod_name),
                    self._get_value(mod_name, option),
                )
            )

        await utils.answer(message, "\n".join(lines))

    async def _configcmd_impl(self, message: Message):
        raw = utils.get_args_raw(message).strip()
        args_s = raw.split()

        if not args_s:
            await self.inline__choose_category(message)
            return

        if any(arg in {"-r", "--reset"} for arg in args_s):
            await self._reset_config_option(message, raw)
            return

        mod_name, instance, obj_type = self._resolve_configurable(args_s[0])
        if not mod_name or not instance or obj_type is None:
            await self.inline__choose_category(message)
            return

        parts = [part.strip() for part in raw.split("&&") if part.strip()]
        reply = await message.get_reply_message()
        reply_text = reply.raw_text if reply and reply.raw_text else None
        first_update = self._parse_config_update(
            instance,
            parts[0],
            reply_text=reply_text,
            first_part=True,
        )

        if first_update is not None:
            await self._apply_config_updates(
                message,
                mod_name,
                instance,
                first_update,
                parts[1:],
            )
            return

        if len(args_s) == 1:
            await self._send_initial_config_form(
                message,
                self.inline__configure,
                mod_name,
                obj_type=obj_type,
            )
            return

        if args_s[1] in instance.config.keys():
            await self._send_initial_config_form(
                message,
                self.inline__configure_option,
                mod=mod_name,
                config_opt=args_s[1],
                obj_type=obj_type,
            )
            return

        if args_s[1] in self._config_categories(instance):
            if len(args_s) >= 3 and (
                config_opt := self._category_option(instance, args_s[1], args_s[2])
            ):
                await self._send_initial_config_form(
                    message,
                    self.inline__configure_option,
                    mod=mod_name,
                    config_opt=config_opt,
                    obj_type=obj_type,
                )
                return

            await self._send_initial_config_form(
                message,
                self.inline__configure,
                mod_name,
                obj_type=obj_type,
                category=args_s[1],
            )
            return

        await self.inline__choose_category(message)

    @loader.command(alias="cfg")
    async def configcmd(self, message: Message):
        await self._configcmd_impl(message)
