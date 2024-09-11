import os

from dotenv import load_dotenv
from telebot import TeleBot

import telegramify_markdown

telegramify_markdown.customize.strict_markdown = False  # we need send underline text
run_1 = telegramify_markdown.markdownify(
    "Hello, World! HTML: &lt;strong&gt;Hello, World!&lt;/strong&gt;"
)
print(run_1)
md = """
# Title
## Subtitle
### Subsubtitle
#### Subsubsubtitle
'\_', '\*', '\[', '\]', '\(', '\)', '\~', '\`', '\>', '\#', '\+', '\-', '\=', '\|', '\{', '\}', '\.', '\!'
_ , * , [ , ] , ( , ) , ~ , ` , > , # , + , - , = , | , { , } , . , !
We will remove the \ symbol from the original text.
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
- [ ] __Underline__ ~~Strikethrough~~ _italic_ Item
- [x] Completed task list item
- [x] **Bold** ||Spoiler|| `Inline Code` Item

> Quote

> Multiline Quote In Markdown it's not possible to send multiline quote in telegram without using code block or html tag but telegramify_markdown can do it.
```python
print("Hello, World!")
```
This is `inline code`
1. First ordered list item
2. Another item
    - Unordered sub-list.
    - Another item.
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
