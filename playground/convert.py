import pathlib
from telegramify_markdown import convert
from telegramify_markdown.customize import markdown_symbol

markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol
md = pathlib.Path(__file__).parent.joinpath("exp1.md").read_text(encoding="utf-8")
converted = convert(md)
print(converted)
