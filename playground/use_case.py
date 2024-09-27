import re

import telegramify_markdown
from telegramify_markdown.customize import markdown_symbol

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol
md = """*bold _italic bold ~italic bold strikethrough ||italic bold strikethrough spoiler||~ __underline italic bold___ bold*
~strikethrough~
"""
quote = """>test"""
task = """
- [x] task1?
-- [x] task2?

\\\\( T\\(n\\) \\= 100^\\{10\\} \\\\) 用大 O 记号表示。\\~\\[RULE\\]\n\n观察此函数可知，它是一个常数

>1231

"""
test_md = """
**bold text**
||spoiler||
"""
converted = telegramify_markdown.convert(task)
print(converted)

rule = re.compile(r"(?<!\\)(?:\\\\)*\|\|(.+?)\|\|", re.DOTALL)
pattern = re.compile(r"^- \[([ xX])\] (.*)", re.DOTALL | re.MULTILINE)
print(rule.findall(test_md))
print(pattern.findall(task))
