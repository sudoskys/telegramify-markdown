import textwrap

import telegramify_markdown

# Use textwrap.dedent to remove the leading whitespace from the text.
md = textwrap.dedent(r"""
# Title

**Latex Math**
Function Change:
    \(\Delta y = f(x_2) - f(x_1)\) can represent the change in the value of a function.
Average Rate of Change:
    \(\frac{\Delta y}{\Delta x} = \frac{f(x_2) - f(x_1)}{x_2 - x_1}\) is used to denote the average rate of change of a function over the interval \([x_1, x_2]\).

- Slope:222
    \[
    F = G\frac{{m_1m_2}}{{r^2}}
    \]

\[
  F = G\frac{{m_1m_2}}{{r^2}}


- Inline: \(F = G\frac{{m_1m_2}}{{r^4}}\)

\(A = X × \left( (P)/100 \right) × (V)/365\)

\(\text{R} = \frac{\text{EXAMPLE}}{\text{Any}}\)

""")

# export Markdown to Telegram MarkdownV2 style.
converted = telegramify_markdown.markdownify(
    md,
    max_line_length=None,  # If you want to change the max line length for links, images, set it to the desired value.
    normalize_whitespace=False,
    latex_escape=False,
)
print(converted)
# export Markdown to Telegram MarkdownV2 style.
from dotenv import load_dotenv
import os
from telebot import TeleBot
load_dotenv()
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", None)
chat_id = os.getenv("TELEGRAM_CHAT_ID", None)
bot = TeleBot(telegram_bot_token)
bot.send_message(
    chat_id,
    converted,
    parse_mode="MarkdownV2"  # IMPORTANT: Need Send in MarkdownV2 Mode.
)