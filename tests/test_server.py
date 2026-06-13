"""Integration tests that send messages to the Telegram Bot API.

These tests verify that the (text, entities) output produced by the library
is accepted by the Telegram servers.  They require TELEGRAM_BOT_TOKEN to be
set in the environment (or in a .env file).

The trick: we send the message to the bot's own chat_id.  Telegram validates
the message content (text + entities) and rejects it with a descriptive
"can't send messages to bots" error only after it passes validation.
If the entities were malformed, we'd get a different error first.
"""

import asyncio
import json
import os
import pathlib
import unittest
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

TESTS_DIR = pathlib.Path(__file__).parent


def _live_required() -> bool:
    """Return True when live Telegram tests must fail instead of skipping."""
    return os.getenv("TELEGRAM_LIVE_REQUIRED") == "1"


def _require_env_or_skip(*names: str) -> None:
    """Require environment variables, or skip unless live tests are mandatory."""
    missing = [name for name in names if not os.getenv(name)]
    if not missing:
        return

    message = f"{', '.join(missing)} not set — skipping server integration tests"
    if _live_required():
        raise AssertionError(f"[AUTH] {message}")
    raise unittest.SkipTest(message)


def _send_text_with_entities(bot, chat_id, text: str, entities_dicts: list[dict]) -> bool:
    """Send a message with entities to Telegram and expect validation success.

    Returns True if the message was validated (i.e. rejected only because the
    target is a bot, not because the entities were invalid).
    """
    try:
        bot.send_message(
            chat_id,
            text,
            entities=entities_dicts or None,
        )
    except Exception as e:
        err = str(e)
        if (
            "send messages to bots" in err
            or "bot can't send messages to bots" in err
            or "bot can't send messages to the bot" in err
        ):
            return True
        # Re-raise unexpected errors (e.g. entity validation failures)
        raise
    return False


def _post_bot_api_json(token: str, method_name: str, payload: dict) -> dict:
    """Call Telegram Bot API with JSON and return the result object."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method_name}",
        data=body,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(
            f"[CONTRACT] Telegram {method_name} rejected request: "
            f"HTTP {exc.code}: {error_body[:500]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise AssertionError(
            f"[NETWORK] Telegram {method_name} is unreachable: {exc.reason}"
        ) from exc

    if not response_body.get("ok"):
        raise AssertionError(
            f"[CONTRACT] Telegram {method_name} returned ok=false: "
            f"{str(response_body)[:500]}"
        )
    return response_body["result"]


def _delete_message_best_effort(token: str, chat_id: str, message_id: int | None) -> None:
    """Delete live-test messages when the bot has permission to do so."""
    if message_id is None:
        return
    try:
        _post_bot_api_json(
            token,
            "deleteMessage",
            {"chat_id": chat_id, "message_id": message_id},
        )
    except AssertionError:
        pass


@unittest.skipUnless(
    os.getenv("TELEGRAM_BOT_TOKEN"),
    "TELEGRAM_BOT_TOKEN not set — skipping server integration tests",
)
class TelegramServerTest(unittest.TestCase):
    """Test that convert() output is accepted by the Telegram Bot API."""

    @classmethod
    def setUpClass(cls):
        from telebot import TeleBot

        token = os.environ["TELEGRAM_BOT_TOKEN"]
        cls.bot = TeleBot(token)
        cls.chat_id = cls.bot.get_me().id

    def test_convert_exp1(self):
        """convert() output for exp1.md passes Telegram entity validation."""
        from telegramify_markdown import convert

        md = (TESTS_DIR / "exp1.md").read_text(encoding="utf-8")
        text, entities = convert(md)
        self.assertTrue(len(text) > 0)
        entities_dicts = [e.to_dict() for e in entities]
        result = _send_text_with_entities(self.bot, self.chat_id, text, entities_dicts)
        self.assertTrue(result, "Expected 'send messages to bots' error from Telegram")

    def test_convert_exp2(self):
        """convert() + split_entities() output for exp2.md passes Telegram entity validation."""
        from telegramify_markdown import convert, split_entities

        md = (TESTS_DIR / "exp2.md").read_text(encoding="utf-8")
        text, entities = convert(md)
        self.assertTrue(len(text) > 0)
        chunks = split_entities(text, entities, 4096)
        self.assertGreater(len(chunks), 0)
        for chunk_text, chunk_entities in chunks:
            entities_dicts = [e.to_dict() for e in chunk_entities]
            result = _send_text_with_entities(self.bot, self.chat_id, chunk_text, entities_dicts)
            self.assertTrue(result, "Expected 'send messages to bots' error from Telegram")


@unittest.skipUnless(
    os.getenv("TELEGRAM_BOT_TOKEN"),
    "TELEGRAM_BOT_TOKEN not set — skipping server integration tests",
)
class TelegramTelegramifyServerTest(unittest.IsolatedAsyncioTestCase):
    """Test that telegramify() output is accepted by the Telegram Bot API."""

    @classmethod
    def setUpClass(cls):
        from telebot import TeleBot

        token = os.environ["TELEGRAM_BOT_TOKEN"]
        cls.bot = TeleBot(token)
        cls.chat_id = cls.bot.get_me().id

    async def test_telegramify_exp1(self):
        """telegramify() output for exp1.md: all Text segments pass validation."""
        from telegramify_markdown import telegramify
        from telegramify_markdown.content import Text

        md = (TESTS_DIR / "exp1.md").read_text(encoding="utf-8")
        results = await telegramify(content=md, max_message_length=4090, latex_escape=True)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

        for item in results:
            if isinstance(item, Text):
                entities_dicts = [e.to_dict() for e in item.entities]
                result = _send_text_with_entities(
                    self.bot, self.chat_id, item.text, entities_dicts
                )
                self.assertTrue(
                    result, "Expected 'send messages to bots' error from Telegram"
                )

    async def test_telegramify_exp2(self):
        """telegramify() output for exp2.md: all Text segments pass validation."""
        from telegramify_markdown import telegramify
        from telegramify_markdown.content import Text

        md = (TESTS_DIR / "exp2.md").read_text(encoding="utf-8")
        results = await telegramify(content=md, max_message_length=4090, latex_escape=True)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

        for item in results:
            if isinstance(item, Text):
                entities_dicts = [e.to_dict() for e in item.entities]
                result = _send_text_with_entities(
                    self.bot, self.chat_id, item.text, entities_dicts
                )
                self.assertTrue(
                    result, "Expected 'send messages to bots' error from Telegram"
                )


def _send_mdv2(bot, chat_id, mdv2_text: str) -> bool:
    """发送 MarkdownV2 格式消息到 Telegram 并期望验证通过。

    和 _send_text_with_entities 类似，通过向 bot 自身发送消息来验证格式正确性。
    """
    try:
        bot.send_message(
            chat_id,
            mdv2_text,
            parse_mode="MarkdownV2",
        )
    except Exception as e:
        err = str(e)
        if (
            "send messages to bots" in err
            or "bot can't send messages to bots" in err
            or "bot can't send messages to the bot" in err
        ):
            return True
        raise
    return False


@unittest.skipUnless(
    os.getenv("TELEGRAM_BOT_TOKEN"),
    "TELEGRAM_BOT_TOKEN not set — skipping server integration tests",
)
class TelegramMarkdownV2ServerTest(unittest.TestCase):
    """测试 entities_to_markdownv2() 的输出能被 Telegram MarkdownV2 解析器接受。"""

    @classmethod
    def setUpClass(cls):
        from telebot import TeleBot

        token = os.environ["TELEGRAM_BOT_TOKEN"]
        cls.bot = TeleBot(token)
        cls.chat_id = cls.bot.get_me().id

    def test_mdv2_exp1(self):
        """convert(exp1.md) → entities_to_markdownv2 的输出通过 Telegram MarkdownV2 验证。"""
        from telegramify_markdown import convert, split_markdownv2

        md = (TESTS_DIR / "exp1.md").read_text(encoding="utf-8")
        text, entities = convert(md)
        for mdv2 in split_markdownv2(text, entities, 4096):
            result = _send_mdv2(self.bot, self.chat_id, mdv2)
            self.assertTrue(result, f"MarkdownV2 rejected by Telegram:\n{mdv2[:200]}")

    def test_mdv2_exp2(self):
        """convert(exp2.md) → entities_to_markdownv2 的输出通过 Telegram MarkdownV2 验证。"""
        from telegramify_markdown import convert, split_markdownv2

        md = (TESTS_DIR / "exp2.md").read_text(encoding="utf-8")
        text, entities = convert(md)
        for mdv2 in split_markdownv2(text, entities, 4096):
            result = _send_mdv2(self.bot, self.chat_id, mdv2)
            self.assertTrue(result, f"MarkdownV2 rejected by Telegram:\n{mdv2[:200]}")

    def test_mdv2_basic_formats(self):
        """基础格式组合的 MarkdownV2 输出通过 Telegram 验证。"""
        from telegramify_markdown import convert, entities_to_markdownv2

        md = "**bold** _italic_ `code` [link](https://example.com)"
        text, entities = convert(md)
        mdv2 = entities_to_markdownv2(text, entities)
        result = _send_mdv2(self.bot, self.chat_id, mdv2)
        self.assertTrue(result, f"MarkdownV2 rejected by Telegram:\n{mdv2}")


class TelegramRichMessageLiveTest(unittest.TestCase):
    """Doctor-style live check for Bot API 10.1 Rich Message compatibility.

    This test proves that richify() output is accepted by the real Telegram
    sendRichMessage endpoint and that Telegram returns a Message.rich_message
    witness. It requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
    """

    def setUp(self):
        _require_env_or_skip("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
        self.token = os.environ["TELEGRAM_BOT_TOKEN"]
        self.chat_id = os.environ["TELEGRAM_CHAT_ID"]
        self.message_id = None

    def tearDown(self):
        _delete_message_best_effort(self.token, self.chat_id, self.message_id)

    def test_richify_html_payload_is_accepted_by_send_rich_message(self):
        """richify() HTML output reaches Telegram and returns rich_message."""
        from telegramify_markdown import richify

        md = """# Rich live check

Text **bold** and *italic* with `code`.

- one
- two

| Metric | Value |
| --- | --- |
| Speed | **42 ms** |

$$E = mc^2$$
"""
        rich_message = richify(md, skip_entity_detection=True)
        result = _post_bot_api_json(
            self.token,
            "sendRichMessage",
            {
                "chat_id": self.chat_id,
                "rich_message": rich_message.to_dict(),
                "disable_notification": True,
            },
        )
        self.message_id = result.get("message_id")

        self.assertIsInstance(result, dict)
        self.assertIn(
            "rich_message",
            result,
            "[CONTRACT] Telegram response did not include Message.rich_message",
        )
        self.assertIn(
            "blocks",
            result["rich_message"],
            "[CONTRACT] Message.rich_message did not include blocks",
        )
        self.assertGreater(
            len(result["rich_message"]["blocks"]),
            0,
            "[CONTRACT] Telegram returned an empty rich message",
        )

    def test_telegramify_rich_chunks_accepted_by_send_rich_message(self):
        """telegramify_rich() 输出的所有 chunk 均被 Telegram 接受。"""
        from telegramify_markdown import telegramify_rich

        # 生成一个触发拆分的长文档（600+ 段落）
        paragraphs = [f"Paragraph {i}: some content here." for i in range(550)]
        md = "\n\n".join(paragraphs)
        items = telegramify_rich(md, skip_entity_detection=True)
        self.assertGreater(len(items), 1, "Expected multiple chunks for 550 paragraphs")

        message_ids = []
        try:
            for item in items:
                result = _post_bot_api_json(
                    self.token,
                    "sendRichMessage",
                    {
                        "chat_id": self.chat_id,
                        "rich_message": item.to_dict(),
                        "disable_notification": True,
                    },
                )
                mid = result.get("message_id")
                if mid:
                    message_ids.append(mid)
                self.assertIn(
                    "rich_message",
                    result,
                    "[CONTRACT] Telegram response missing rich_message",
                )
        finally:
            for mid in message_ids:
                _delete_message_best_effort(self.token, self.chat_id, mid)


@unittest.skipUnless(
    os.getenv("TELEGRAM_LIVE_REQUIRED") == "1" and os.getenv("TELEGRAM_CHAT_ID"),
    "TELEGRAM_LIVE_REQUIRED=1 and TELEGRAM_CHAT_ID required for draft streaming tests",
)
class TelegramStreamDraftLiveTest(unittest.IsolatedAsyncioTestCase):
    """Live test for DraftStream: sends draft updates then a final rich message.

    Proves that:
    1. sendRichMessageDraft is accepted by the real Telegram API
    2. DraftStream correctly throttles and accumulates content
    3. Final sendRichMessage delivers the complete message

    Requires private chat (draft API is private-chat only).
    """

    def setUp(self):
        self.token = os.environ["TELEGRAM_BOT_TOKEN"]
        self.chat_id = os.environ["TELEGRAM_CHAT_ID"]
        self.message_id = None

    def tearDown(self):
        _delete_message_best_effort(self.token, self.chat_id, self.message_id)

    async def test_draft_stream_rich_mode(self):
        """DraftStream(mode='rich') sends drafts and finalizes with sendRichMessage."""
        from telegramify_markdown.stream.draft import (
            DraftStream,
            RichDraftPayload,
            RichFinalPayload,
        )

        draft_count = 0
        draft_errors = []

        async def send_draft(payload: RichDraftPayload) -> None:
            nonlocal draft_count
            draft_count += 1
            api_payload = {
                "chat_id": self.chat_id,
                "draft_id": payload.draft_id,
                "rich_message": payload.rich_message.to_dict(),
            }
            try:
                _post_bot_api_json(self.token, "sendRichMessageDraft", api_payload)
            except AssertionError as e:
                draft_errors.append(str(e))
                raise

        async def send_final(payload: RichFinalPayload) -> None:
            api_payload = {
                "chat_id": self.chat_id,
                "rich_message": payload.rich_message.to_dict(),
                "disable_notification": True,
            }
            result = _post_bot_api_json(self.token, "sendRichMessage", api_payload)
            self.message_id = result.get("message_id")

        md = "# Stream Test\n\nHello **world**, this is a `streaming` draft.\n\n- Item 1\n- Item 2\n"

        async with DraftStream(
            send_draft=send_draft,
            send_final=send_final,
            mode="rich",
            interval=0.3,
            thinking_delay=0.3,
            keepalive_timeout=25.0,
        ) as stream:
            # 模拟逐 token 输入
            for ch in md:
                stream.feed(ch)
                await asyncio.sleep(0.02)

        # Verify results
        self.assertGreater(draft_count, 0, "Expected at least one draft to be sent")
        self.assertIsNotNone(self.message_id, "Final message should have been sent")
        self.assertEqual(len(draft_errors), 0, f"Draft errors: {draft_errors}")

    async def test_draft_stream_entity_mode(self):
        """DraftStream(mode='entity') sends drafts via sendMessageDraft."""
        from telegramify_markdown.stream.draft import (
            DraftStream,
            EntityDraftPayload,
            EntityFinalPayload,
        )

        draft_count = 0

        async def send_draft(payload: EntityDraftPayload) -> None:
            nonlocal draft_count
            draft_count += 1
            api_payload = {
                "chat_id": self.chat_id,
                "draft_id": payload.draft_id,
                "text": payload.text,
                "entities": [e.to_dict() if hasattr(e, "to_dict") else e for e in payload.entities],
            }
            _post_bot_api_json(self.token, "sendMessageDraft", api_payload)

        async def send_final(payload: EntityFinalPayload) -> None:
            api_payload = {
                "chat_id": self.chat_id,
                "text": payload.text,
                "entities": [e.to_dict() if hasattr(e, "to_dict") else e for e in payload.entities],
                "disable_notification": True,
            }
            result = _post_bot_api_json(self.token, "sendMessage", api_payload)
            self.message_id = result.get("message_id")

        md = "Hello **bold** and `code` test.\n"

        async with DraftStream(
            send_draft=send_draft,
            send_final=send_final,
            mode="entity",
            interval=0.3,
            thinking_delay=None,
            keepalive_timeout=25.0,
        ) as stream:
            for ch in md:
                stream.feed(ch)
                await asyncio.sleep(0.02)

        self.assertGreater(draft_count, 0)
        self.assertIsNotNone(self.message_id)


if __name__ == "__main__":
    unittest.main()
