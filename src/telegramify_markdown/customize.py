class Symbol(object):
    head_level_1 = "\N{PUSHPIN}"
    # "📌"
    head_level_2 = "\N{PENCIL}"
    # "✏️"
    head_level_3 = "\N{BOOKS}"
    # "📚"
    head_level_4 = "\N{BOOKMARK}"
    # "🔖"
    image = "\N{FRAME WITH PICTURE}"
    # "🖼"
    link = "\N{LINK SYMBOL}"
    # "🔗"
    task_completed = "\N{WHITE HEAVY CHECK MARK}"
    # "✅"
    task_uncompleted = "\N{BALLOT BOX WITH CHECK}"
    # "☑️"


# NOTE: Settings that are not part of global rendering **are not allowed** to be stored here!!
# Prioritize function parameter passing to ensure definability

# Markdown options
markdown_symbol = Symbol()
# Rendering options
cite_expandable = True
strict_markdown = True
unescape_html = False
