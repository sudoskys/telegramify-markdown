import os
import pathlib
from time import sleep

from dotenv import load_dotenv
from telebot import TeleBot

import telegramify_markdown
from telegramify_markdown import ContentTypes
from telegramify_markdown.customize import markdown_symbol

load_dotenv()
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", None)
chat_id = os.getenv("TELEGRAM_CHAT_ID", None)
bot = TeleBot(telegram_bot_token)

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol
md = pathlib.Path(__file__).parent.joinpath("t_longtext.md").read_text(encoding="utf-8")
boxs = telegramify_markdown.telegramify(md)
for item in boxs:
    print("Sent one item")
    sleep(0.2)
    if item.content_type == ContentTypes.TEXT:
        print("TEXT")
        bot.send_message(
            chat_id,
            item.content,
            parse_mode="MarkdownV2"
        )
    elif item.content_type == ContentTypes.PHOTO:
        print("PHOTO")
        bot.send_photo(
            chat_id,
            (item.file_name, item.file_data),
            caption=item.caption
        )
    elif item.content_type == ContentTypes.FILE:
        print("FILE")
        bot.send_document(
            chat_id,
            (item.file_name, item.file_data),
            caption=item.caption,
        )
