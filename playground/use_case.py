import telegramify_markdown
from telegramify_markdown.customize import markdown_symbol

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol
md = """
---
key: value
---

\(c!ode\)
\# Heading Level 1 `c!ode`
# Heading Level 1 `c!ode`
## Heading Level 2
### Heading Level 3
**Bold text**
*Italic text*
~~Strikethrough text~~
> Blockquote text
`Inline code`
\\/\\111`sad`
```

Code block

```
"""
converted = telegramify_markdown.convert(md)
print(converted)
