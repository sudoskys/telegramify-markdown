import os

from dotenv import load_dotenv
from telebot import TeleBot

import telegramify_markdown

telegramify_markdown.customize.strict_markdown = False  # we need send underline text
run_1 = telegramify_markdown.markdownify(
    "Hello, World! HTML: &lt;strong&gt;Hello, World!&lt;/strong&gt;",
    unescape_html=True
)
print(run_1)
md = """
'\_', '\*', '\[', '\]', '\(', '\)', '\~', '\`', '\>', '\#', '\+', '\-', '\=', '\|', '\{', '\}', '\.', '\!'
_ , * , [ , ] , ( , ) , ~ , ` , > , # , + , - , = , | , { , } , . , !
**bold text**
*bold text*
_italic text_
__underline__
~no valid strikethrough~
~~strikethrough~~
||spoiler||
*bold _italic bold ~~italic bold strikethrough ||italic bold strikethrough spoiler||~~ __underline italic bold___ bold*
__underline italic bold__
[link](https://www.google.com)
- [ ] Uncompleted task list item
- [x] Completed task list item
> Quote
```python
print("Hello, World!")
```
This is `inline code`
1. First ordered list item
2. Another item
    - Unordered sub-list.
1. Actual numbers don't matter, just that it's a number
"""
converted = telegramify_markdown.convert(md)
print(converted)
load_dotenv()
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", None)
chat_id = os.getenv("TELEGRAM_CHAT_ID", None)
bot = TeleBot(telegram_bot_token)
bot.send_message(
    chat_id,
    converted,
    parse_mode="MarkdownV2"
)
