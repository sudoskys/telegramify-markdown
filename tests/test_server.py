"""Integration tests that send messages to the Telegram Bot API.

These tests verify that the (text, entities) output produced by the library
is accepted by the Telegram servers.  They require TELEGRAM_BOT_TOKEN to be
set in the environment (or in a .env file).

The trick: we send the message to the bot's own chat_id.  Telegram validates
the message content (text + entities) and rejects it with a descriptive
"can't send messages to bots" error only after it passes validation.
If the entities were malformed, we'd get a different error first.
"""

import os
import pathlib
import unittest

from dotenv import load_dotenv

load_dotenv()

TESTS_DIR = pathlib.Path(__file__).parent


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
        if "send messages to bots" in err or "bot can't send messages to bots" in err:
            return True
        # Re-raise unexpected errors (e.g. entity validation failures)
        raise
    return False


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
        if "send messages to bots" in err or "bot can't send messages to bots" in err:
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


if __name__ == "__main__":
    unittest.main()
