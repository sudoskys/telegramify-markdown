import os
import textwrap

from dotenv import load_dotenv
from telebot import TeleBot

import telegramify_markdown

# Customize the markdownify
telegramify_markdown.customize.strict_markdown = False  # we need send underline text
# Test html tags
html_t = telegramify_markdown.markdownify(
    "Hello, World! HTML: &lt;strong&gt;Hello, World!&lt;/strong&gt;",
    latex_escape=True
)
print(html_t)

# Use textwrap.dedent to remove the leading whitespace from the text.
md = textwrap.dedent(r"""
# Title
## Subtitle
### Subsubtitle
#### Subsubsubtitle

\(TEST
\\(TEST
\\\(TEST
\\\\(TEST
\\\\\(TEST

[inline URL](http://www.example.com/)
[inline mention of a user](tg://user?id=123456789)
![👍](tg://emoji?id=5368324170671202286)
![👍](tg://emoji?id=53683241706712http-hack)
[👍](tg://emoji?id=53683241706712http-hack)
[](tg://emoji?id=5368324170671202286)
![👍](tg://emoji?id=53683241706712022865368324170671202286)

**Latex Math**
Function Change:
    \(\Delta y = f(x_2) - f(x_1)\) can represent the change in the value of a function.
Average Rate of Change:
    \(\frac{\Delta y}{\Delta x} = \frac{f(x_2) - f(x_1)}{x_2 - x_1}\) is used to denote the average rate of change of a function over the interval \([x_1, x_2]\).
- Slope:
   \[
   F = G\frac{{m_1m_2}}{{r^2}}
   \]
- Inline: \(F = G\frac{{m_1m_2}}{{r^4}}\)

\(
A = X × \left( (P)/100 \right) × (V)/365
\)

\(
\text{R} = \frac{\text{EXAMPLE}}{\text{Any}}
\)

There \frac{1}{2} not in the latex block.

**Table**

| Tables        | Are           | Cool  |
| ------------- |:-------------:| -----:|
|               | right-aligned | $1600 |
| col 2 is      | centered      |   $12 |
| zebra stripes | are neat      |    $1 |

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
- [x] Completed task list item
> Quote

>Multiline Quote In Markdown it's not possible to send multiline quote in telegram without using code block or html tag but telegramify_markdown can do it. 
---
Text

Text

Text
> If you quote is too long, it will be automatically set in expandable citation. 
> This is the second line of the quote.
> `This is the third line of the quote.`
> This is the fourth line of the quote.
> `This is the fifth line of the quote.`

```python
print("Hello, World!")
```
This is `inline code`
1. First ordered list item
2. Another item
    - Unordered sub-list.
    - Another item.
1. Actual numbers don't matter, just that it's a number
```
print("```")
```
""")

emoji_md = r"""
![👍](tg://emoji?id=5368324170671202286)
"""

# export Markdown to Telegram MarkdownV2 style.
converted = telegramify_markdown.markdownify(
    md,
    max_line_length=None,  # If you want to change the max line length for links, images, set it to the desired value.
    normalize_whitespace=False,
    latex_escape=True
)
print(converted)
# export Markdown to Telegram MarkdownV2 style.
load_dotenv()
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", None)
chat_id = os.getenv("TELEGRAM_CHAT_ID", None)
bot = TeleBot(telegram_bot_token)
bot.send_message(
    chat_id,
    converted,
    parse_mode="MarkdownV2"  # IMPORTANT: Need Send in MarkdownV2 Mode.
)
