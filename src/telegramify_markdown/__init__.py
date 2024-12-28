import re
from typing import Union, List, Tuple, Any

import mistletoe
from mistletoe.block_token import BlockToken, ThematicBreak  # noqa
from mistletoe.markdown_renderer import LinkReferenceDefinition, BlankLine
from mistletoe.span_token import SpanToken  # noqa

from . import customize
from .interpreters import Text, File, Photo, BaseInterpreter, MermaidInterpreter
from .latex_escape.const import LATEX_SYMBOLS, NOT_MAP, LATEX_STYLES
from .latex_escape.helper import LatexToUnicodeHelper
from loguru import logger
from .mermaid import render_mermaid
from .mime import get_filename
from .render import TelegramMarkdownRenderer, escape_markdown
from .type import Text, File, Photo, ContentTypes

__all__ = [
    "escape_markdown",
    "customize",
    "markdownify",
    "telegramify",
    "BaseInterpreter",
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


async def telegramify(
        content: str,
        *,
        max_line_length: int = None,
        normalize_whitespace=False,
        latex_escape: bool = True,
        interpreters_use=None,
        max_word_count: int = 4090,
) -> List[Union[Text, File, Photo]]:
    """
    Convert markdown content to Telegram Markdown format.

    **Showcase** https://github.com/sudoskys/telegramify-markdown/blob/main/playground/telegramify_case.py

    :param interpreters_use: The interpreters to use.
    :param content: The markdown content to convert.
    :param max_line_length: The maximum length of a line.
    :param normalize_whitespace: Whether to normalize whitespace.
    :param latex_escape: Whether to make LaTeX content readable in Telegram.
    :param max_word_count: The maximum number of words in a single message.
    :return: The Telegram markdown formatted content. **Need Send in MarkdownV2 Mode.**
    :raises ValueError: If the token length mismatch.
    :raises Exception: Some other exceptions.
    """
    if interpreters_use is None:
        interpreters_use = [BaseInterpreter(), MermaidInterpreter()]
    if not interpreters_use:
        raise ValueError(
            "No interpreters provided, at least `telegramify_markdown.interpreters.BaseInterpreter` is required."
        )
    _rendered: List[Union[Text, File, Photo]] = []
    with TelegramMarkdownRenderer(
            max_line_length=max_line_length,
            normalize_whitespace=normalize_whitespace
    ) as renderer:
        if latex_escape:
            content = escape_latex(content)
        document = mistletoe.Document(content)
        document2 = mistletoe.Document(content)
        # 只更新第一个文档，因为我们要倒查第二个文档的内容
        _update_block(document)
        # 解离 Token
        tokens = list(document.children)
        tokens2 = list(document2.children)
        if len(tokens) != len(tokens2):
            raise ValueError("Token length mismatch")

        # 对内容进行分块渲染
        def is_over_max_word_count(doc_t: List[Tuple[Any, Any]]):
            doc = mistletoe.Document(lines=[])
            doc.children = [___token for ___token, ___token2 in doc_t]
            return len(renderer.render(doc)) > max_word_count

        def render_block(doc_t: List[Any]):
            doc = mistletoe.Document(lines=[])
            doc.children = doc_t.copy()
            return renderer.render(doc)

        def render_lines(lines: str):
            doc = mistletoe.Document(lines=lines)
            _update_block(doc)
            return renderer.render(doc)

        _stack = []
        _packed = []

        # 步进推送
        for _token, _token2 in zip(tokens, tokens2):
            # 计算如果推送当前 Token 是否会超过最大字数限制
            if is_over_max_word_count(_stack + [(_token, _token2)]):
                _packed.append(_stack)
                _stack = [(_token, _token2)]
            else:
                _stack.append((_token, _token2))
        if _stack:
            _packed.append(_stack)
        _task = [("base", cell) for cell in _packed]
        # [(base, [(token1,token2),(token1,token2)]), (base, [(token1,token2),(token1,token2)])]
        interpreters_map = {interpreter.name: interpreter for interpreter in interpreters_use}
        if len(interpreters_map.keys()) != len(interpreters_use):
            raise ValueError(f"Interpreter name conflict: {interpreters_use}")
        run_interpreters = interpreters_map.values()
        for interpreter in run_interpreters:
            _task = await interpreter.merge(_task)
        for interpreter in run_interpreters:
            _new_task = []
            for _per_task in _task:
                _new_task.extend(
                    await interpreter.split(_per_task)
                )
            _task = _new_task

        for _per_task in _task:
            task_type, token_pairs = _per_task
            if task_type not in interpreters_map:
                raise ValueError(f"Cannot find interpreter for task type: {task_type}")
            interpreter = interpreters_map[task_type]
            _rendered.extend(
                await interpreter.render_task(
                    task=_per_task,
                    render_lines_func=render_lines,
                    render_block_func=render_block,
                    max_word_count=max_word_count
                ))
    return _rendered


def markdownify(
        content: str,
        *,
        max_line_length: int = None,
        normalize_whitespace=False,
        latex_escape: bool = True,
) -> str:
    """
    Convert markdown str to Telegram Markdown format.

     **Showcase** https://github.com/sudoskys/telegramify-markdown/blob/main/playground/markdownify_case.py

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
        if latex_escape:
            content = escape_latex(content)
        document = mistletoe.Document(content)
        _update_block(document)
        result = renderer.render(document)
    return result
