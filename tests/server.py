import os

from telebot import TeleBot


def server_t(converted):
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", None)
    assert isinstance(telegram_bot_token,
                      str) and telegram_bot_token, "Please set the TELEGRAM_BOT_TOKEN environment variable"
    bot = TeleBot(telegram_bot_token)
    bot_me = bot.get_me()
    try:
        print("Trying to send a message")
        bot.send_message(bot_me.id, converted, parse_mode="MarkdownV2")
    except Exception as e:
        assert "send messages to bots" in str(e)
        print("Test passed")
        return True
    return False
