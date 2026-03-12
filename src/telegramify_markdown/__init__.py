"""telegramify-markdown: Convert Markdown to Telegram plain text + MessageEntity pairs."""

from __future__ import annotations

import warnings
from typing import Union

from telegramify_markdown import config
from telegramify_markdown.converter import convert as convert
from telegramify_markdown.entity import MessageEntity, split_entities, utf16_len
from telegramify_markdown.content import ContentType, ContentTypes, ContentTrace, File, Photo, Text
from telegramify_markdown.mdv2 import entities_to_markdownv2

__all__ = [
    "convert",
    "telegramify",
    "entities_to_markdownv2",
    "markdownify",
    "standardize",
    "config",
    "MessageEntity",
    "utf16_len",
    "split_entities",
    "Text",
    "File",
    "Photo",
    "ContentType",
    "ContentTypes",
    "ContentTrace",
]


def markdownify(content: str, *, latex_escape: bool = True) -> str:
    """Convert Markdown to a Telegram MarkdownV2 string.

    For middleware that only supports ``parse_mode="MarkdownV2"`` without entities.
    Equivalent to ``entities_to_markdownv2(*convert(content))``.
    """
    return entities_to_markdownv2(*convert(content, latex_escape=latex_escape))


def standardize(content: str, *, latex_escape: bool = True) -> str:
    """Alias for :func:`markdownify`, kept for 0.x compatibility."""
    return markdownify(content, latex_escape=latex_escape)


async def telegramify(
    content: str,
    *,
    max_message_length: int = 4096,
    max_word_count: int | None = None,
    latex_escape: bool = True,
    render_mermaid: bool = True,
    min_file_lines: int = 1,
) -> list[Union[Text, File, Photo]]:
    """Convert markdown to Telegram-ready content segments.

    :param content: Raw markdown text.
    :param max_message_length: Maximum UTF-16 code units per text message (Telegram limit is 4096).
    :param max_word_count: Deprecated alias for *max_message_length*. Will be removed in 2.0.
    :param latex_escape: Whether to convert LaTeX ``\\(...\\)`` and ``\\[...\\]`` to Unicode.
    :param render_mermaid: Whether to render Mermaid diagrams as images.
    :param min_file_lines: Minimum number of lines in a code block to be sent as a file instead of text. 0 means always send as text, 1 means always send as file.
    :return: Ordered list of Text, File, or Photo objects ready for the Telegram Bot API.
    """
    if max_word_count is not None:
        warnings.warn(
            "max_word_count is deprecated and will be removed in 2.0. "
            "Use max_message_length instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        max_message_length = max_word_count

    from telegramify_markdown.pipeline import process_markdown

    return await process_markdown(
        content,
        max_message_length=max_message_length,
        latex_escape=latex_escape,
        render_mermaid=render_mermaid,
        min_file_lines=min_file_lines,
    )
