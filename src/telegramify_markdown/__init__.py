"""telegramify-markdown: Convert Markdown to Telegram plain text + MessageEntity pairs."""

from __future__ import annotations

from typing import Union

from telegramify_markdown import config
from telegramify_markdown.converter import convert as convert
from telegramify_markdown.entity import MessageEntity, split_entities, utf16_len
from telegramify_markdown.content import ContentType, ContentTrace, File, Photo, Text

__all__ = [
    "convert",
    "telegramify",
    "config",
    "MessageEntity",
    "utf16_len",
    "split_entities",
    "Text",
    "File",
    "Photo",
    "ContentType",
    "ContentTrace",
]


async def telegramify(
    content: str,
    *,
    max_message_length: int = 4096,
    latex_escape: bool = True,
) -> list[Union[Text, File, Photo]]:
    """Convert markdown to Telegram-ready content segments.

    This is the primary async API for complete markdown processing,
    including message splitting, code block extraction, and mermaid rendering.
    For lower-level text-only conversion, use ``convert()``.

    :param content: Raw markdown text.
    :param max_message_length: Maximum UTF-16 code units per text message (Telegram limit is 4096).
    :param latex_escape: Whether to convert LaTeX ``\\(...\\)`` and ``\\[...\\]`` to Unicode.
    :return: Ordered list of Text, File, or Photo objects ready for the Telegram Bot API.
    """
    from telegramify_markdown.pipeline import process_markdown

    return await process_markdown(
        content,
        max_message_length=max_message_length,
        latex_escape=latex_escape,
    )
