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

import logging

from .. import loader, translations, utils
from ..inline.types import BotInlineCall

logger = logging.getLogger(__name__)


@loader.tds
class Quickstart(loader.Module):
    """Notifies user about userbot installation"""

    strings = {"name": "Quickstart"}

    async def client_ready(self):
        self.text = lambda: self.strings["base"].format(
            utils.get_platform_emoji()
            if self.client.astralix_me.premium is True
            else "astralix"
        )

        try:
            content_channel = await self.db.ensure_content_channel()
            if not content_channel:
                raise RuntimeError("Failed to get or create content channel")
            forum_entity = content_channel
            if not getattr(content_channel, "forum", False):
                from astralixtl.tl.functions.channels import ToggleForumRequest
                await self.client(ToggleForumRequest(channel=content_channel, enabled=True))
            self.db.set("astralix.forums", "forum_id", int(content_channel.id))

            required_topics = [
                (
                    "Assets",
                    "🌆 Your astralix assets will be stored here",
                    5877307202888273539,
                ),
                (
                    "Backups",
                    "💾 Your astralix backups will be stored here",
                    5877307202888273539,
                ),
            ]

            for topic_title, topic_desc, emoji_id in required_topics:
                try:
                    await utils.asset_forum_topic(
                        client=self.client,
                        db=self.db,
                        peer=forum_entity.id if forum_entity else content_channel.id,
                        title=topic_title,
                        description=topic_desc,
                        icon_emoji_id=emoji_id,
                    )
                    logger.debug(f"Created or verified topic '{topic_title}'")
                except Exception:
                    logger.exception(f"Failed to create/verify topic '{topic_title}'")

            await utils.invite_inline_bot(self.client, content_channel)

        except Exception:
            logger.exception(
                "Can't find and/or create content channel\n"
                "This may cause several consequences, such as:\n"
                "- Non working inline-logs, backups, assets features\n"
                "- This error will occur every restart\n\n"
                "You can try solving this by leaving some channels/groups"
            )

        self.mark = lambda: [
        ] + utils.chunks(
            [
                {
                    "text": self.strings.get("language", lang),
                    "data": f"astralix/lang/{lang}",
                }
                for lang in translations.SUPPORTED_LANGUAGES
            ],
            3,
        )

        if self.get("no_msg"):
            return

        await self.inline.bot.send_message(
            self._client.tg_id,
            self.text(),
            reply_markup=self.inline.generate_markup(self.mark()),
            disable_web_page_preview=True,
        )

        self.set("no_msg", True)

    @loader.callback_handler()
    async def lang(self, call: BotInlineCall):
        if not call.data.startswith("astralix/lang/"):
            return

        lang = call.data.split("/")[2]

        self._db.set(translations.__name__, "lang", lang)
        await self.allmodules.reload_translations()

        await self.inline.bot(call.answer(self.strings["language_saved"]))
        await call.edit(text=self.text(), reply_markup=self.mark())
