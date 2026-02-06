import os
import textwrap

from dotenv import load_dotenv
from telebot import TeleBot

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

# Convert to (text, entities)
text, entities = telegramify_markdown.convert(md, latex_escape=False)
print(text)
print(f"\n--- {len(entities)} entities ---")
for e in entities:
    print(e.to_dict())

# Send to telegram
load_dotenv()
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", None)
chat_id = os.getenv("TELEGRAM_CHAT_ID", None)
bot = TeleBot(telegram_bot_token)
bot.send_message(
    chat_id,
    text,
    entities=[e.to_dict() for e in entities],
)
