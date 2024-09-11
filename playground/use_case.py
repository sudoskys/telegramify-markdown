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
- [ ] task
- [x] task
"""
test_md = """
**bold text**
||spoiler||
"""
converted = telegramify_markdown.convert(task)
print(converted)

rule = re.compile(r"(?<!\\)(?:\\\\)*\|\|(.+?)\|\|", re.DOTALL)

print(rule.findall(test_md))
