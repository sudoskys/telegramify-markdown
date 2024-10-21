import re
from typing import Union

import mistletoe
from mistletoe.block_token import BlockToken, ThematicBreak  # noqa
from mistletoe.markdown_renderer import LinkReferenceDefinition, BlankLine
from mistletoe.span_token import SpanToken  # noqa

from . import customize
from .latex_escape.const import LATEX_SYMBOLS, NOT_MAP, LATEX_STYLES
from .latex_escape.helper import LatexToUnicodeHelper
from .render import TelegramMarkdownRenderer, escape_markdown

latex_escape_helper = LatexToUnicodeHelper()

__all__ = [
    "convert",
    "escape_markdown",
    "customize",
    "markdownify"
]


def escape_latex(text):
    # Patterns to match block and inline math
    math_p = re.compile(r'\\\[(.*?)\\\]', re.DOTALL)
    inline_math_p = re.compile(r'\\\((.*?)\\\)', re.DOTALL)

    def contains_latex_symbols(content):
        # Check for common LaTeX symbols
        if len(content) < 5:
            return False
        latex_symbols = (r"\frac",
                         r"\sqrt",
                         r"\begin",
                         ) + tuple(LATEX_SYMBOLS.keys()) + tuple(NOT_MAP.keys()) + tuple(LATEX_STYLES.keys())
        return any(symbol in content for symbol in latex_symbols)

    def latex2unicode(match, is_block):
        # Extract the content of the match
        content = match.group(1)
        if not contains_latex_symbols(content):
            return match.group(0)  # Return the original match if no LaTeX symbols are found
        content = latex_escape_helper.convert(content)
        if is_block:
            return f"```{content.strip()}```"
        else:
            pre_process = content.strip().strip('\n')
            return f"`{pre_process}`"

    lines = text.split("\n\n")
    processed_lines = []
    for line in lines:
        # Process block-level math
        processed_line = math_p.sub(lambda match: latex2unicode(match, is_block=True), line)
        # Process inline math
        processed_line = inline_math_p.sub(lambda match: latex2unicode(match, is_block=False), processed_line)
        processed_lines.append(processed_line)
    return "\n\n".join(processed_lines)


def _update_text(token: Union[SpanToken, BlockToken]):
    """Update the text contents of a span token and its children.
    `InlineCode` tokens are left unchanged."""
    if isinstance(token, ThematicBreak):
        token.line = escape_markdown("————————")
        pass
    elif isinstance(token, LinkReferenceDefinition):
        pass
    elif isinstance(token, BlankLine):
        pass
    else:
        if hasattr(token, "content"):
            token.content = escape_markdown(token.content, unescape_html=customize.unescape_html)


def _update_block(token: BlockToken):
    """Update the text contents of paragraphs and headings within this block,
    and recursively within its children."""
    if hasattr(token, "children") and token.children:
        # Dispatch all children
        for child in token.children:
            _update_block(child)
    else:
        _update_text(token)


def markdownify(
        content: str,
        max_line_length: int = None,
        normalize_whitespace=False,
        latex_escape=None
) -> str:
    """
    Convert markdown content to Telegram markdown format.
    :param content: The markdown content to convert.
    :param max_line_length: The maximum length of a line.
    :param normalize_whitespace: Whether to normalize whitespace.
    :param latex_escape: Whether to make LaTeX content readable in Telegram.
    :return: The Telegram markdown formatted content. **Need Send in MarkdownV2 Mode.**
    """
    with TelegramMarkdownRenderer(
            max_line_length=max_line_length,
            normalize_whitespace=normalize_whitespace
    ) as renderer:
        if latex_escape is None:
            latex_escape = customize.latex_escape
        if latex_escape:
            content = escape_latex(content)
        document = mistletoe.Document(content)
        _update_block(document)
        result = renderer.render(document)
    return result


def convert(content: str) -> str:
    # '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'
    # simple warp for the markdownify function
    return markdownify(content)
