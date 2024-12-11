import dataclasses
import re
from abc import ABCMeta
from copy import deepcopy
from enum import StrEnum
from typing import Union, List

import mistletoe
from mistletoe.block_token import BlockToken, ThematicBreak  # noqa
from mistletoe.markdown_renderer import LinkReferenceDefinition, BlankLine
from mistletoe.span_token import SpanToken  # noqa

from . import customize
from .latex_escape.const import LATEX_SYMBOLS, NOT_MAP, LATEX_STYLES
from .latex_escape.helper import LatexToUnicodeHelper
from .render import TelegramMarkdownRenderer, escape_markdown

__all__ = [
    "escape_markdown",
    "customize",
    "markdownify",
    "telegramify",
    "ContentTypes",
]

latex_escape_helper = LatexToUnicodeHelper()


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
    """
    Update the text contents of a span token and its children.
    `InlineCode` tokens are left unchanged.
    """
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
    """
    Update the text contents of paragraphs and headings within this block,
    and recursively within its children.
    """
    if hasattr(token, "children") and token.children:
        # Dispatch all children
        for child in token.children:
            _update_block(child)
    else:
        _update_text(token)


class ContentTypes(StrEnum):
    TEXT = "text"
    FILE = "file"
    PHOTO = "photo"


class RenderedContent(object, metaclass=ABCMeta):
    """
    The rendered content.

    - content: str
    - content_type: ContentTypes
    """
    content_type: ContentTypes


@dataclasses.dataclass
class Text(RenderedContent):
    content: str
    content_type: ContentTypes = ContentTypes.TEXT


@dataclasses.dataclass
class File(RenderedContent):
    file_name: str
    file_data: bytes
    caption: str
    content_type: ContentTypes = ContentTypes.FILE


@dataclasses.dataclass
class Photo(RenderedContent):
    file_name: str
    file_data: bytes
    caption: bytes
    content_type: ContentTypes = ContentTypes.PHOTO


def telegramify(
        content: str,
        max_line_length: int = None,
        normalize_whitespace=False,
        latex_escape=None,
        max_word_count: int = 4090
) -> List[Union[Text, File, Photo]]:
    """
    Convert markdown content to Telegram Markdown format.
    :param content: The markdown content to convert.
    :param max_line_length: The maximum length of a line.
    :param normalize_whitespace: Whether to normalize whitespace.
    :param latex_escape: Whether to make LaTeX content readable in Telegram.
    :param max_word_count: The maximum number of words in a single message.
    :return: The Telegram markdown formatted content. **Need Send in MarkdownV2 Mode.**
    """
    _rendered: List[Union[Text, File, Photo]] = []
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
        # 解离 Token
        tokens = document.children

        # 对内容进行分块渲染
        def is_over_max_word_count(doc_t: List[BlockToken]):
            doc = mistletoe.Document(lines=[])
            doc.children = doc_t
            return len(renderer.render(doc)) > max_word_count

        def render_block(doc_t: List[BlockToken]):
            doc = mistletoe.Document(lines=[])
            doc.children = doc_t
            return renderer.render(doc)

        _stack = []
        _packed = []
        # 步进推送
        for token in tokens:
            # 计算如果推送当前 Token 是否会超过最大字数限制
            if is_over_max_word_count(_stack + [token]):
                _packed.append(_stack)
                _stack = [token]
            else:
                _stack.append(token)
        for pack in _packed:
            _rendered.append(Text(render_block(pack)))
    return _rendered


def markdownify(
        content: str,
        max_line_length: int = None,
        normalize_whitespace=False,
        latex_escape=None,
) -> str:
    """
    Convert markdown str to Telegram Markdown format.
    :param content: The markdown content to convert.
    :param max_line_length: The maximum length of a line.
    :param normalize_whitespace: Whether to normalize whitespace.
    :param latex_escape: Whether to make LaTeX content readable in Telegram.
    :return: The Telegram markdown formatted content. **Need Send in MarkdownV2 Mode.**
    """
    _rendered = []
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
