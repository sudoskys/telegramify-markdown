# telegramify-markdown

[![PyPI version](https://badge.fury.io/py/telegramify-markdown.svg)](https://badge.fury.io/py/telegramify-markdown)
[![Downloads](https://pepy.tech/badge/telegramify-markdown)](https://pepy.tech/project/telegramify-markdown)

> 🪄 Python Telegram markdown Converter | No more worrying about formatting.

**Raw Markdown -> Telegram MarkdownV2 Style**

Before the advent of this repository, when you needed to send Markdown content in Telegram rendering, you had to use
complex regularization. Today, you can make it easier and customize it to achieve better results!

I used a custom Render to achieve this, using a real environment server to verify the applicability of this tool.

## Installation

```bash
pip install telegramify-markdown
```

or if you use `pdm`:

```shell
pdm add telegramify-markdown
```

## Use case

````python3
import telegramify_markdown
from telegramify_markdown.customize import markdown_symbol

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol
md = """
# 一级标题 `c!ode` # 一级标题 `code`
[Link!AA](https://www.example.com)

[key!]: https://www.google.com "a title!"

[这是!链接2][asd!asd](https://www.example.com)
[rttt]()
![PIC](https://www.example.com/image.jpg)
1. Order!ed
   1. Order!ed sub
- Unord*-.ered
"""
converted = telegramify_markdown.convert(md)
print(converted)
````

output as follows:

```markdown
*📌 一级标题 `c\!ode` \# 一级标题 `code`*
[Link\!AA](https://www\.example\.com)

🔗[a title\!](https://www\.google\.com)

\[这是\!链接2\][asd\!asd](https://www\.example\.com)
[rttt]()
🖼[PIC](https://www\.example\.com/image\.jpg)
1\. Order\!ed
1\. Order\!ed sub
⦁ Unord\*\-\.ered
```

> Note: Telegram Server automatically processes the double of `\` again (even after escaping), which is beyond the
> control of us.