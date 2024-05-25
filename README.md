# telegramify-markdown

[![PyPI version](https://badge.fury.io/py/telegramify-markdown.svg)](https://badge.fury.io/py/telegramify-markdown)
[![Downloads](https://pepy.tech/badge/telegramify-markdown)](https://pepy.tech/project/telegramify-markdown)

> 🪄 Python Telegram markdown Converter | No more worrying about formatting.

**Raw Markdown -> Telegram MarkdownV2 Style**

Before this repo came along, when you wanted to send and render unknown Markdown content (like GitHub's Readme),
you had to use complex parsing and reconstruction methods.
Today, you can make it easier and customize it to achieve better results!

I used a custom Render to achieve this, using a real environment server to verify the applicability of this tool.

## Installation

```bash
pip install telegramify-markdown
```

or if you use `pdm`:

```shell
pdm add telegramify-markdown
```

## Supported Features

- [x] Headings (1-6)
- [x] Links [text](url)
- [x] Images ![alt]
- [x] Lists (Ordered, Unordered)
- [x] Tables |-|-|
- [x] Horizontal Rule ----
- [x] *Text* **Styles**
- [x] __Underline__
- [x] Code Blocks
- [x] `Inline Code`
- [x] Block Quotes
- [x] ~~Strikethrough~~
- [ ] Task Lists
- [ ] ~Strikethrough~
- [ ] ||Spoiler||
- [ ] Tg Emoji
- [ ] Tg User At

> [!NOTE]
> Since mistletoe doesn't parse TODO and Spoiler, we can't apply it.
~Strikethrough~ is incorrect, even if it comes from official documentation, please use ~~Strikethrough~~ format.

## Use case

````python3
import telegramify_markdown
from telegramify_markdown.customize import markdown_symbol

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol
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
````

output as follows:

![.github/result.png](.github/result.png)
