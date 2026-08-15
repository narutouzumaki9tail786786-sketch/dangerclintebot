import unittest
import sys
import asyncio
import io
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot import (
    build_auto_reaction_plan,
    campaign_scope_for_state,
    extract_allowed_reaction_choices,
    extract_allowed_reaction_emojis,
    DEFAULT_AUTO_REACTIONS,
    get_message_with_peer_retry,
    increment_post_view_with_peer_retry,
    leave_all_joined_channels,
    parse_admin_account_limit,
    resolve_auto_reaction_choice,
    resolve_manual_reaction_choice,
    resolve_leave_chat_target,
    safe_extract_session_files,
    send_reaction_value,
    UnsupportedReactionError,
)


class AutoReactionPlanTests(unittest.TestCase):
    def test_spreads_accounts_across_different_reactions(self):
        plan = build_auto_reaction_plan(100, seed=42)
        counts = Counter(plan)

        self.assertEqual(len(plan), 100)
        self.assertTrue(set(plan).issubset(set(DEFAULT_AUTO_REACTIONS)))
        self.assertGreaterEqual(len(counts), 4)
        self.assertLess(max(counts.values()), 100)
        self.assertGreater(max(counts.values()), min(counts.values()))

    def test_small_campaign_still_assigns_every_account(self):
        plan = build_auto_reaction_plan(3, reactions=["👍", "🔥", "❤️"], seed=1)

        self.assertEqual(len(plan), 3)
        self.assertEqual(len(set(plan)), 3)

    def test_admin_account_limit_parser(self):
        self.assertEqual(parse_admin_account_limit("123456 50"), (123456, 50))
        self.assertEqual(parse_admin_account_limit("123456,0"), (123456, 0))

    def test_campaign_scope_separates_admin_all_adv_and_user(self):
        self.assertEqual(campaign_scope_for_state({"admin_all": True}), "all")
        self.assertEqual(campaign_scope_for_state({"adv_campaign": True}), "grant")
        self.assertEqual(campaign_scope_for_state({}), "user")

    def test_zip_session_extracts_only_session_basenames(self):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as zf:
            zf.writestr("../evil.session", b"bad")
            zf.writestr("nested/917990832761.session", b"ok")
            zf.writestr("notes.txt", b"skip")

        with tempfile.TemporaryDirectory() as tmp:
            paths = safe_extract_session_files(payload.getvalue(), tmp)

            self.assertEqual([p.name for p in paths], ["evil.session", "917990832761.session"])
            self.assertTrue(all(Path(p).parent == Path(tmp) for p in paths))

    def test_extracts_only_allowed_chat_reactions(self):
        class Reaction:
            def __init__(self, emoji):
                self.emoji = emoji

        class Available:
            all_are_enabled = False
            reactions = [Reaction("👍"), Reaction("🔥"), Reaction(None)]

        class Chat:
            available_reactions = Available()

        self.assertEqual(extract_allowed_reaction_emojis(Chat()), ["👍", "🔥"])

    def test_extracts_custom_reaction_ids_for_restricted_channels(self):
        class Reaction:
            def __init__(self, custom_emoji_id):
                self.custom_emoji_id = custom_emoji_id
                self.emoji = None

        class Available:
            all_are_enabled = False
            reactions = [Reaction(5190745930319554349), Reaction(5190566778643702939)]

        class Chat:
            available_reactions = Available()

        self.assertEqual(
            extract_allowed_reaction_choices(Chat()),
            [5190745930319554349, 5190566778643702939],
        )

    def test_auto_reaction_can_choose_custom_reaction_id(self):
        choice = resolve_auto_reaction_choice(
            "session-a",
            planned_reaction="❤️",
            allowed_reactions=[5190745930319554349, 5190566778643702939],
        )

        self.assertIsInstance(choice, int)
        self.assertIn(choice, [5190745930319554349, 5190566778643702939])

    def test_custom_reaction_id_uses_raw_reaction_custom_emoji(self):
        class FakeClient:
            def __init__(self):
                self.invoked = None
                self.high_level_called = False

            async def resolve_peer(self, chat_id):
                return f"peer:{chat_id}"

            async def invoke(self, request):
                self.invoked = request

            async def send_reaction(self, *args, **kwargs):
                self.high_level_called = True

        client = FakeClient()
        asyncio.run(send_reaction_value(client, -1001, 33, 5190745930319554349))

        self.assertFalse(client.high_level_called)
        self.assertEqual(client.invoked.reaction[0].document_id, 5190745930319554349)

    def test_manual_reaction_is_not_replaced_when_channel_restricts_reactions(self):
        with self.assertRaises(UnsupportedReactionError):
            resolve_manual_reaction_choice("❤️", ["👍", "🔥"], reactions_restricted=True)

    def test_manual_reaction_is_allowed_when_channel_does_not_report_restrictions(self):
        self.assertEqual(
            resolve_manual_reaction_choice("❤️", [], reactions_restricted=False),
            "❤️",
        )

    def test_manual_heart_matches_allowed_heart_without_variation_selector(self):
        self.assertEqual(
            resolve_manual_reaction_choice("\u2764\ufe0f", ["\u2764", "🔥", "👀"], reactions_restricted=True),
            "\u2764",
        )

    def test_custom_only_reaction_policy_fails_before_random_fallback(self):
        with self.assertRaises(UnsupportedReactionError):
            resolve_manual_reaction_choice("❤️", [], reactions_restricted=True)

    def test_get_message_retry_reuses_same_chat_id_after_dialog_cache_warm(self):
        class FakeClient:
            def __init__(self):
                self.calls = 0

            async def get_messages(self, chat_id, msg_id):
                self.calls += 1
                if self.calls == 1:
                    raise ValueError(f"Peer id invalid: {chat_id}")
                return {"chat_id": chat_id, "msg_id": msg_id}

            async def get_chat(self, chat_id):
                raise ValueError(f"Peer id invalid: {chat_id}")

            async def get_dialogs(self):
                yield SimpleNamespace(chat=SimpleNamespace(id=-1003586753317))

        result, resolved_chat_id = asyncio.run(
            get_message_with_peer_retry(FakeClient(), -1003586753317, 1368)
        )

        self.assertEqual(result["msg_id"], 1368)
        self.assertEqual(resolved_chat_id, -1003586753317)

    def test_view_retry_retries_same_chat_id_after_cache_warm(self):
        class FakeClient:
            def __init__(self):
                self.resolve_calls = 0
                self.invoked = []

            async def resolve_peer(self, chat_id):
                self.resolve_calls += 1
                if self.resolve_calls == 1:
                    raise ValueError(f"Peer id invalid: {chat_id}")
                return f"peer:{chat_id}"

            async def invoke(self, request):
                self.invoked.append(request)

            async def get_chat(self, chat_id):
                raise ValueError(f"Peer id invalid: {chat_id}")

            async def get_dialogs(self):
                yield SimpleNamespace(chat=SimpleNamespace(id=-1003586753317))

        resolved_chat_id = asyncio.run(
            increment_post_view_with_peer_retry(FakeClient(), -1003586753317, 1368)
        )

        self.assertEqual(resolved_chat_id, -1003586753317)

    def test_leave_target_resolves_invite_link_to_chat_id(self):
        class FakeClient:
            async def get_chat(self, chat_id):
                self.chat_id = chat_id
                return SimpleNamespace(id=-1001397413809)

        client = FakeClient()
        resolved = asyncio.run(
            resolve_leave_chat_target(client, "https://t.me/+NhiZOAEmJZwyMzU1")
        )

        self.assertEqual(client.chat_id, "https://t.me/+NhiZOAEmJZwyMzU1")
        self.assertEqual(resolved, -1001397413809)

    def test_leave_target_preview_uses_matching_dialog_title(self):
        class FakeClient:
            async def get_chat(self, chat_id):
                return SimpleNamespace(title="Private Channel")

            async def get_dialogs(self):
                yield SimpleNamespace(chat=SimpleNamespace(id=-100111, title="Other", type="ChatType.CHANNEL"))
                yield SimpleNamespace(chat=SimpleNamespace(id=-100222, title="Private Channel", type="ChatType.CHANNEL"))

        resolved = asyncio.run(
            resolve_leave_chat_target(FakeClient(), "https://t.me/+NhiZOAEmJZwyMzU1")
        )

        self.assertEqual(resolved, -100222)

    def test_leave_target_preview_without_dialog_gives_clear_error(self):
        class FakeClient:
            async def get_chat(self, chat_id):
                return SimpleNamespace(title="Private Channel")

            async def get_dialogs(self):
                if False:
                    yield None

        with self.assertRaisesRegex(RuntimeError, "not joined"):
            asyncio.run(resolve_leave_chat_target(FakeClient(), "https://t.me/+NhiZOAEmJZwyMzU1"))

    def test_leave_all_joined_channels_skips_private_chats(self):
        class FakeClient:
            def __init__(self):
                self.left = []

            async def get_dialogs(self):
                yield SimpleNamespace(chat=SimpleNamespace(id=-1001, type="ChatType.CHANNEL"))
                yield SimpleNamespace(chat=SimpleNamespace(id=-1002, type="ChatType.SUPERGROUP"))
                yield SimpleNamespace(chat=SimpleNamespace(id=12345, type="ChatType.PRIVATE"))

            async def leave_chat(self, chat_id):
                self.left.append(chat_id)

        client = FakeClient()
        left = asyncio.run(leave_all_joined_channels(client))

        self.assertEqual(left, 2)
        self.assertEqual(client.left, [-1001, -1002])


if __name__ == "__main__":
    unittest.main()
