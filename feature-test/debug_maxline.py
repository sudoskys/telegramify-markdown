import telegramify_markdown

md = """
[Treating Otitis Externa in Dogs | Today's Veterinary Practice](https://todaysveterinarypractice.com/dermatology/treating-otitis-externa-in-dogs/)
"""


def main():
    text, entities = telegramify_markdown.convert(md)
    print(text)
    for e in entities:
        print(e.to_dict())


main()
