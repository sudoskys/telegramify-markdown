from typing import Union

import mistletoe
from mistletoe.block_token import BlockToken, ThematicBreak
from mistletoe.markdown_renderer import LinkReferenceDefinition
from mistletoe.span_token import SpanToken

from . import customize
from .render import TelegramMarkdownRenderer, escape_markdown

__all__ = [
    "convert",
    "escape_markdown",
    "customize",
    "markdownify"
]


def _update_text(token: Union[SpanToken, BlockToken]):
    """Update the text contents of a span token and its children.
    `InlineCode` tokens are left unchanged."""
    if isinstance(token, ThematicBreak):
        token.line = escape_markdown("————————")
        pass
    elif isinstance(token, LinkReferenceDefinition):
        pass
    else:
        assert hasattr(token, "content"), f"Token {token} has no content attribute"
        token.content = escape_markdown(token.content, unescape_html=customize.unescape_html)


def _update_block(token: BlockToken):
    """Update the text contents of paragraphs and headings within this block,
    and recursively within its children."""
    if hasattr(token, "children"):
        # Dispatch all children
        for child in token.children:
            _update_block(child)
    else:
        _update_text(token)


def markdownify(
        content: str,
        max_line_length: int = None,
        normalize_whitespace=False
) -> str:
    with TelegramMarkdownRenderer(
            max_line_length=max_line_length,
            normalize_whitespace=normalize_whitespace
    ) as renderer:
        document = mistletoe.Document(content)
        _update_block(document)
        result = renderer.render(document)
    return result


def convert(content: str) -> str:
    # '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'
    # simple warp for the markdownify function
    return markdownify(content)
