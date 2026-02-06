import asyncio
import os
import pathlib
from time import sleep

from dotenv import load_dotenv
from telebot import TeleBot

import telegramify_markdown
from telegramify_markdown.config import get_runtime_config
from telegramify_markdown.content import ContentType

markdown_symbol = get_runtime_config().markdown_symbol

load_dotenv()
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", None)
chat_id = os.getenv("TELEGRAM_CHAT_ID", None)
bot = TeleBot(telegram_bot_token)

markdown_symbol.heading_level_1 = "📌"
markdown_symbol.link = "🔗"
md = pathlib.Path(__file__).parent.parent.joinpath('playground').joinpath("t_longtext.md").read_text(encoding="utf-8")


async def main():
    boxs = await telegramify_markdown.telegramify(md)
    for item in boxs:
        print("Sent one item")
        sleep(0.2)
        if item.content_type == ContentType.TEXT:
            print("TEXT")
            print(item.text)
        elif item.content_type == ContentType.PHOTO:
            print("PHOTO")
            print(item.caption_text)
        elif item.content_type == ContentType.FILE:
            print("FILE")
            print(item.file_name)


if __name__ == "__main__":
    asyncio.run(main())
