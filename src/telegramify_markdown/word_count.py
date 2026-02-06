"""Telegram message length counting utilities.

In the entity-based approach, the text sent to Telegram is plain text
(no MarkdownV2 syntax). URLs live in entity fields, not in the text.
So counting is simply the UTF-16 length of the text.
"""

from telegramify_markdown.entity import utf16_len


def count_text(text: str) -> int:
    """Count the effective length of text for Telegram in UTF-16 code units.

    Since there is no MarkdownV2 syntax in the text (URLs are in entities),
    this is simply the UTF-16 length.
    """
    return utf16_len(text)
