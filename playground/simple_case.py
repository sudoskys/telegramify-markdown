import telegramify_markdown
from telegramify_markdown.customize import get_runtime_config

markdown_symbol = get_runtime_config().markdown_symbol

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
test_md = r"""
**bold text**
||spoiler||
"""
math = r"""
\[
\begin{aligned}
\text{Let } f(x) &= \frac{1}{x} \\
\text{Then } f'(x) &= -\frac{1}{x^2} \\
\text{And } f''(x) &= \frac{2}{x^3}
\end{aligned}
\]

$ f(x) = \frac{1}{x} $
"""

emoji = r"""
[inline URL](http://www.example.com/)
[inline mention of a user](tg://user?id=123456789)
![👍](tg://emoji?id=5368324170671202286)
![👍](tg://emoji?id=53683241706712http-hack)
[👍](tg://emoji?id=53683241706712http-hack)
[](tg://emoji?id=5368324170671202286)
"""

converted = telegramify_markdown.markdownify(emoji)
print(converted)
