import asyncio
import os
import pathlib
from time import sleep

from dotenv import load_dotenv
from telebot import TeleBot

import telegramify_markdown
from telegramify_markdown.config import get_runtime_config
from telegramify_markdown.content import ContentType

load_dotenv()
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", None)
chat_id = os.getenv("TELEGRAM_CHAT_ID", None)
bot = TeleBot(telegram_bot_token)

# Customizing global rendering options
get_runtime_config().markdown_symbol.heading_level_1 = "📌"
get_runtime_config().markdown_symbol.link = "🔗"
md = pathlib.Path(__file__).parent.joinpath("t_longtext.md").read_text(encoding="utf-8")


async def send_message():
    boxs = await telegramify_markdown.telegramify(
        content=md,
        latex_escape=True,
        max_message_length=4090,
    )
    for item in boxs:
        print(f"Sending one item: {item.content_type.value}")
        sleep(0.2)
        try:
            if item.content_type == ContentType.TEXT:
                bot.send_message(
                    chat_id,
                    item.text,
                    entities=[e.to_dict() for e in item.entities],
                )
            elif item.content_type == ContentType.PHOTO:
                bot.send_photo(
                    chat_id,
                    (item.file_name, item.file_data),
                    caption=item.caption_text or None,
                    caption_entities=[e.to_dict() for e in item.caption_entities] or None,
                )
            elif item.content_type == ContentType.FILE:
                bot.send_document(
                    chat_id,
                    (item.file_name, item.file_data),
                    caption=item.caption_text or None,
                    caption_entities=[e.to_dict() for e in item.caption_entities] or None,
                )
        except Exception as e:
            print(f"Error: {item}")
            raise e


if __name__ == "__main__":
    asyncio.run(send_message())
