# ©️ radiocycle, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/radiocycle/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

from types import SimpleNamespace
import unittest
from astralix._event_filters import find_failed_tag


def failed(message, tag):
    return find_failed_tag(message, SimpleNamespace(**{tag:True}), mime_type=lambda m:'',get_chat_id=lambda m:1)


class EventFilterTests(unittest.TestCase):
    def test_supergroup_is_not_exempt_from_no_groups(self):
        m=SimpleNamespace(is_group=True,is_channel=True,is_private=False)
        self.assertEqual(failed(m,'no_groups'),'no_groups')
        self.assertIsNone(failed(m,'only_groups'))

    def test_private_message_is_not_a_group(self):
        m=SimpleNamespace(is_group=False,is_channel=False,is_private=True)
        self.assertEqual(failed(m,'only_groups'),'only_groups')
        self.assertIsNone(failed(m,'no_groups'))

    def test_editable_requires_outgoing_nonforwarded_message(self):
        self.assertEqual(failed(SimpleNamespace(out=False),'editable'),'editable')
        self.assertIsNone(failed(SimpleNamespace(out=True),'editable'))
        self.assertEqual(failed(SimpleNamespace(out=True,fwd_from=True),'editable'),'editable')
