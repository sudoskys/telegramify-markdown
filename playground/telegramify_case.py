import asyncio
import os
import pathlib
from time import sleep

from dotenv import load_dotenv
from telebot import TeleBot

import telegramify_markdown
from telegramify_markdown.customize import markdown_symbol
from telegramify_markdown.interpreters import BaseInterpreter, MermaidInterpreter
from telegramify_markdown.type import ContentTypes

tips = """
telegramify_markdown.telegramify 

The stability of telegramify_markdown.telegramify is unproven, please keep good log records.

Feel free to check it out, if you have any questions please open an issue
"""

load_dotenv()
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", None)
chat_id = os.getenv("TELEGRAM_CHAT_ID", None)
bot = TeleBot(telegram_bot_token)

# Customizing global rendering options
markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol
md = pathlib.Path(__file__).parent.joinpath("t_longtext.md").read_text(encoding="utf-8")


# Write an async function to send message
async def send_message():
    boxs = await telegramify_markdown.telegramify(
        content=md,
        interpreters_use=[BaseInterpreter(), MermaidInterpreter(session=None)],  # Render mermaid diagram
        latex_escape=True,
        normalize_whitespace=True,
        max_word_count=4090  # The maximum number of words in a single message.
    )
    for item in boxs:
        print("Sent one item")
        sleep(0.2)
        try:
            if item.content_type == ContentTypes.TEXT:
                print("TEXT")
                bot.send_message(
                    chat_id,
                    item.content,
                    parse_mode="MarkdownV2"
                )
            elif item.content_type == ContentTypes.PHOTO:
                print("PHOTO")
                """
                bot.send_sticker(
                    chat_id,
                    (item.file_name, item.file_data),
                )
                """
                bot.send_photo(
                    chat_id,
                    (item.file_name, item.file_data),
                    caption=item.caption,
                    parse_mode="MarkdownV2"
                )
            elif item.content_type == ContentTypes.FILE:
                print("FILE")
                bot.send_document(
                    chat_id,
                    (item.file_name, item.file_data),
                    caption=item.caption,
                    parse_mode="MarkdownV2"
                )
        except Exception as e:
            print(f"Error: {item}")
            raise e


# Sync usage
loop = asyncio.new_event_loop()
result = loop.run_until_complete(
    telegramify_markdown.telegramify(md)
)
print(f"Got {len(result)} items.")

# Async usage
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(send_message())
