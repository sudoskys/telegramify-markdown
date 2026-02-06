import os

from dotenv import load_dotenv
from telebot import TeleBot

import telegramify_markdown
from telegramify_markdown.config import get_runtime_config

markdown_symbol = get_runtime_config().markdown_symbol
markdown_symbol.heading_level_1 = "📌"
markdown_symbol.link = "🔗"

md = r"""
# Title
**bold text**
*italic text*
~~strikethrough~~
||spoiler||
*bold _italic bold ~~italic bold strikethrough ||italic bold strikethrough spoiler||~~ __underline italic bold___ bold*
[inline URL](http://www.example.com/)
[inline mention of a user](tg://user?id=123456789)
![👍](tg://emoji?id=5368324170671202286)
`inline fixed-width code`
```
pre-formatted fixed-width code block
```
```python
pre-formatted fixed-width code block written in the Python programming language
```

> Block quotation started
> Block quotation continued
> Block quotation continued
> Block quotation continued
> The last line of the block quotation

> The expandable block quotation started right after the previous block quotation
> It is separated from the previous block quotation by an empty bold entity
> Expandable block quotation continued
> Hidden by default part of the expandable block quotation started
> Expandable block quotation continued
> The last line of the expandable block quotation with the expandability mark
"""

# Convert to (text, entities)
text, entities = telegramify_markdown.convert(md)
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
