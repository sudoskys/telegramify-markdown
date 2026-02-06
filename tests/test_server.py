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


if __name__ == "__main__":
    unittest.main()
