from typing import Union

import mistletoe
from mistletoe.block_token import BlockToken, ThematicBreak
from mistletoe.markdown_renderer import LinkReferenceDefinition
from mistletoe.span_token import SpanToken

from .render import TelegramMarkdownRenderer, escape_markdown

__all__ = [
    "convert",
    "escape_markdown",
    "customize",
    "markdownify"
]


def markdownify(text: str, unescape_html: bool = True) -> str:
    # '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'
    return escape_markdown(text, unescape_html=unescape_html)


def _update_text(token: Union[SpanToken, BlockToken]):
    """Update the text contents of a span token and its children.
    `InlineCode` tokens are left unchanged."""
    if isinstance(token, ThematicBreak):
        token.line = markdownify("————————")
        pass
    elif isinstance(token, LinkReferenceDefinition):
        pass
    else:
        assert hasattr(token, "content"), f"Token {token} has no content attribute"
        token.content = markdownify(token.content)


def _update_block(token: BlockToken):
    """Update the text contents of paragraphs and headings within this block,
    and recursively within its children."""
    if hasattr(token, "children"):
        # Dispatch all children
        for child in token.children:
            _update_block(child)
    else:
        _update_text(token)


def convert(content: str):
    with TelegramMarkdownRenderer() as renderer:
        document = mistletoe.Document(content)
        _update_block(document)
        result = renderer.render(document)
    return result
