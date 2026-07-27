"""telegramify-markdown: Convert Markdown to Telegram plain text + MessageEntity pairs."""

from __future__ import annotations

import warnings
from typing import Union

from telegramify_markdown import config
from telegramify_markdown.config import RenderConfig
from telegramify_markdown.converter import convert as convert
from telegramify_markdown.entity import MessageEntity, split_entities, utf16_len
from telegramify_markdown.content import ContentType, ContentTypes, ContentTrace, File, Photo, RichMessage, Text
from telegramify_markdown.mdv2 import entities_to_markdownv2, split_markdownv2
from telegramify_markdown.rich import InputRichMessage, richify, split_rich, telegramify_rich

__all__ = [
    "convert",
    "telegramify",
    "entities_to_markdownv2",
    "split_markdownv2",
    "markdownify",
    "standardize",
    "richify",
    "split_rich",
    "telegramify_rich",
    "config",
    "RenderConfig",
    "MessageEntity",
    "InputRichMessage",
    "RichMessage",
    "utf16_len",
    "split_entities",
    "Text",
    "File",
    "Photo",
    "ContentType",
    "ContentTypes",
    "ContentTrace",
]


def markdownify(
    content: str,
    *,
    max_line_length: int | None = None,
    normalize_whitespace: bool = False,
    latex_escape: bool = True,
    config: RenderConfig | None = None,
) -> str:
    """Convert Markdown to a Telegram MarkdownV2 string.

    For middleware that only supports ``parse_mode="MarkdownV2"`` without entities.
    Equivalent to ``entities_to_markdownv2(*convert(content))``.

    :param max_line_length: Deprecated (ignored). Kept for 0.x compatibility.
    :param normalize_whitespace: Deprecated (ignored). Kept for 0.x compatibility.
    :param config: Render configuration. Uses the global config if None.
    """
    if max_line_length is not None:
        warnings.warn(
            "max_line_length is deprecated and ignored in 1.x. "
            "Will be removed in 2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
    if normalize_whitespace:
        warnings.warn(
            "normalize_whitespace is deprecated and ignored in 1.x. "
            "Will be removed in 2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
    return entities_to_markdownv2(*convert(content, latex_escape=latex_escape, config=config))


def standardize(
    content: str,
    *,
    max_line_length: int | None = None,
    normalize_whitespace: bool = False,
    latex_escape: bool = True,
    config: RenderConfig | None = None,
) -> str:
    """Alias for :func:`markdownify`, kept for 0.x compatibility."""
    return markdownify(
        content,
        max_line_length=max_line_length,
        normalize_whitespace=normalize_whitespace,
        latex_escape=latex_escape,
        config=config,
    )


async def telegramify(
    content: str,
    *,
    max_message_length: int = 4096,
    max_word_count: int | None = None,
    max_line_length: int | None = None,
    normalize_whitespace: bool = False,
    latex_escape: bool = True,
    render_mermaid: bool = True,
    min_file_lines: int = 1,
    config: RenderConfig | None = None,
) -> list[Union[Text, File, Photo]]:
    """Convert markdown to Telegram-ready content segments.

    :param content: Raw markdown text.
    :param max_message_length: Maximum UTF-16 code units per text message (Telegram limit is 4096).
    :param max_word_count: Deprecated alias for *max_message_length*. Will be removed in 2.0.
    :param max_line_length: Deprecated (ignored). Kept for 0.x compatibility.
    :param normalize_whitespace: Deprecated (ignored). Kept for 0.x compatibility.
    :param latex_escape: Whether to convert LaTeX ``\\(...\\)`` and ``\\[...\\]`` to Unicode.
    :param render_mermaid: Whether to render Mermaid diagrams as images.
        When *False*, mermaid blocks remain inline as ``pre`` entities with
        ``language="mermaid"``.
    :param min_file_lines: Minimum line count for a code block to be extracted
        as a separate file.  Set to ``0`` to disable file extraction entirely
        (all code blocks stay inline as ``pre`` entities).
    :param config: Render configuration. Uses the global config if None.
        Pass ``RenderConfig.isolated()`` to keep concurrent requests from
        sharing symbol settings.
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
    if max_line_length is not None:
        warnings.warn(
            "max_line_length is deprecated and ignored in 1.x. "
            "Will be removed in 2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
    if normalize_whitespace:
        warnings.warn(
            "normalize_whitespace is deprecated and ignored in 1.x. "
            "Will be removed in 2.0.",
            DeprecationWarning,
            stacklevel=2,
        )

    from telegramify_markdown.pipeline import process_markdown

    return await process_markdown(
        content,
        max_message_length=max_message_length,
        latex_escape=latex_escape,
        render_mermaid=render_mermaid,
        min_file_lines=min_file_lines,
        config=config,
    )
