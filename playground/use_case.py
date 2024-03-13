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
