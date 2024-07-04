import telegramify_markdown
from telegramify_markdown import customize

customize.strict_markdown = True

md = """
[Treating Otitis Externa in Dogs | Today's Veterinary Practice](https://todaysveterinarypractice.com/dermatology/treating-otitis-externa-in-dogs/)
"""


def main():
    escaped = telegramify_markdown.markdownify(md, max_line_length=20)
    print(escaped)


main()
