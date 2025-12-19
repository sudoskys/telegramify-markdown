import re
from typing import Union, List, Tuple, Any

import mistletoe
from mistletoe.block_token import BlockToken, ThematicBreak  # noqa
from mistletoe.markdown_renderer import LinkReferenceDefinition, BlankLine
from mistletoe.span_token import SpanToken

from telegramify_markdown.word_count import count_markdown  # noqa

from . import customize
from .interpreters import (
    BaseInterpreter, TextInterpreter, FileInterpreter, MermaidInterpreter,
    InterpreterChain, create_default_chain
)
from .latex_escape.const import LATEX_SYMBOLS, NOT_MAP, LATEX_STYLES
from .latex_escape.helper import LatexToUnicodeHelper
from .render import TelegramMarkdownRenderer, escape_markdown, TelegramMarkdownFormatter
from .type import Text, File, Photo, ContentTypes

__all__ = [
    "escape_markdown",
    "customize",
    "markdownify",
    "telegramify",
    "BaseInterpreter",
    "TextInterpreter",
    "FileInterpreter",
    "MermaidInterpreter",
    "InterpreterChain",
    "create_default_chain",
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
            token.content = escape_markdown(token.content, unescape_html=customize.get_runtime_config().unescape_html)


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

    :param interpreters_use: The interpreters to use. Can be a list of interpreters or an InterpreterChain.
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
        # Use the default interpreter chain
        interpreter_chain = create_default_chain()
    elif isinstance(interpreters_use, InterpreterChain):
        # If the interpreter chain is already created, use it directly
        interpreter_chain = interpreters_use
    elif isinstance(interpreters_use, list):
        # If the interpreter list is already created, create a new interpreter chain
        interpreter_chain = InterpreterChain(interpreters_use)
    else:
        raise ValueError(
            "interpreters_use must be a list of interpreters or an InterpreterChain."
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
        # Only update the first document, because we need to check the content of the second document
        _update_block(document)
        # Disconnect the Token
        tokens = list(document.children)
        tokens2 = list(document2.children)
        if len(tokens) != len(tokens2):
            raise ValueError("Token length mismatch")

        # Split the content into blocks
        def is_over_max_word_count(doc_t: List[Tuple[Any, Any]]):
            doc = mistletoe.Document(lines=[])
            doc.children = [___token for ___token, ___token2 in doc_t]
            return count_markdown(renderer.render(doc)) > max_word_count

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

        # Step by step push
        for _token, _token2 in zip(tokens, tokens2):
            # Calculate if pushing the current token will exceed the maximum word count limit
            if is_over_max_word_count(_stack + [(_token, _token2)]):
                _packed.append(_stack)
                _stack = [(_token, _token2)]
            else:
                _stack.append((_token, _token2))
        if _stack:
            _packed.append(_stack)
        _task = [("base", cell) for cell in _packed]

        # Use the responsibility chain to process the task
        for _per_task in _task:
            # First, split the task
            split_tasks = []
            current_tasks = [_per_task]

            # Let each interpreter have a chance to split the task
            for interpreter in interpreter_chain.interpreters:
                new_tasks = []
                for task in current_tasks:
                    new_tasks.extend(await interpreter.split(task))
                current_tasks = new_tasks

            split_tasks = current_tasks

            # Process the split tasks
            for task in split_tasks:
                result = await interpreter_chain.process(
                    task=task,
                    render_lines_func=render_lines,
                    render_block_func=render_block,
                    max_word_count=max_word_count
                )
                _rendered.extend(result)

    return _rendered


def standardize(
        content: str,
        *,
        max_line_length: int = None,
        normalize_whitespace=False,
        latex_escape: bool = True,
) -> str:
    """
    Convert Unstandardized Telegram MarkdownV2 Syntax to Standardized Telegram MarkdownV2 Syntax.
    Used for replace the Telegram MarkdownV2 Syntax Builder.

     **Showcase** https://github.com/sudoskys/telegramify-markdown/blob/main/playground/standardize_case.py

    :param content: The markdown content to convert.
    :param max_line_length: The maximum length of a line.
    :param normalize_whitespace: Whether to normalize whitespace.
    :param latex_escape: Whether to make LaTeX content readable in Telegram.
    :return: The Telegram markdown formatted content. **Need Send in MarkdownV2 Mode.**
    """
    with TelegramMarkdownFormatter(
            max_line_length=max_line_length,
            normalize_whitespace=normalize_whitespace
    ) as renderer:
        if latex_escape:
            content = escape_latex(content)
        document = mistletoe.Document(content)
        _update_block(document)
        result = renderer.render(document)
    return result


def markdownify(
        content: str,
        *,
        max_line_length: int = None,
        normalize_whitespace=False,
        latex_escape: bool = True,
) -> str:
    """
    Convert Standardized Markdown to Standardized Telegram MarkdownV2 Syntax.

     **Showcase** https://github.com/sudoskys/telegramify-markdown/blob/main/playground/markdownify_case.py

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
        if latex_escape:
            content = escape_latex(content)
        document = mistletoe.Document(content)
        _update_block(document)
        result = renderer.render(document)
    return result
