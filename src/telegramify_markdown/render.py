import html
import re
from itertools import chain, tee
from typing import Iterable
from telegramify_markdown import markdown

from mistletoe import span_token, block_token
from mistletoe.markdown_renderer import (
    MarkdownRenderer,
    LinkReferenceDefinition,
    Fragment,
)
from .customize import get_runtime_config


class Spoiler(span_token.SpanToken):
    """
    Spoiler token. ("||some text||")
    This is an inline token. Its children are inline (span) tokens.
    """

    pattern = re.compile(r"(?<!\\)(?:\\\\)*\|\|(.+?)\|\|", re.DOTALL)


class TelegramStrikethrough(span_token.SpanToken):
    """
    Telegram Strikethrough token. ("~some text~")
    This is an inline token. Its children are inline (span) tokens.
    """

    pattern = re.compile(r"(?<!\\)(?:\\\\)*~(.+?)~", re.DOTALL)


class TaskListItem(block_token.BlockToken):
    """
    Custom block token for task list items in Markdown.
    Matches task list items like '- [ ]' and '- [x]'.

    Attributes:
        checked (bool): whether the task is checked.
        content (str): the description of the task list item.
    """

    repr_attributes = block_token.BlockToken.repr_attributes + ("checked", "content")
    pattern = re.compile(r"^( *)(- \[([ xX])\] )(.*)")

    def __init__(self, match):
        self.indentation, self.marker, self.checked_char, self.content = match
        self.checked = self.checked_char.lower() == "x"
        super().__init__(lines=self.content, tokenize_func=span_token.tokenize_inner)

    @classmethod
    def start(cls, line):
        stripped = line.lstrip()
        if not stripped.startswith("- [ ]") and not stripped.startswith("- [x]"):
            return False
        return bool(cls.pattern.match(line))

    @classmethod
    def read(cls, lines):
        line = next(lines)
        match = cls.pattern.match(line)
        if match:
            return match.groups()
        raise ValueError("TaskListItem did not match expected format.")


def escape_markdown(content: str, unescape_html: bool = True) -> str:
    """
    Escapes Markdown characters in a string of Markdown with optional HTML unescaping.

    :param content: The string of Markdown to escape.
    :type content: str
    :param unescape_html: Whether to unescape HTML entities before escaping, defaults to True.
    :type unescape_html: bool, optional
    :return: The escaped string.
    :rtype: str
    """
    if not content:
        return ""
    # Unescape HTML entities if specified
    if unescape_html:
        content = html.unescape(content)
    # First pass to escape all markdown special characters
    escaped_content = re.sub(r"([_*\[\]()~`>\#\+\-=|{}\.!\\])", r"\\\1", content)
    # Second pass to remove double escaping
    final_content = re.sub(
        r"\\\\([_*\[\]()~`>\#\+\-=|{}\.!\\])", r"\\\1", escaped_content
    )
    return final_content


def validate_telegram_emoji(url: str) -> bool:
    """
    Validate if the URL is a telegram emoji.
    tg://emoji?id=5368324170671202286
    id must be 19 digits.
    :param url: The URL to validate.
    :type url: str
    :return: Whether the URL is a telegram emoji.
    :rtype: bool
    """
    wait_validate = str(url)
    if not wait_validate.startswith("tg://emoji?id="):
        return False
    emoji_id = wait_validate.removeprefix("tg://emoji?id=")
    if not emoji_id.isdigit():
        return False
    if not len(emoji_id) == 19:
        return False
    return True


class TelegramMarkdownRenderer(MarkdownRenderer):
    def __init__(self, *extras, **kwargs):
        super().__init__(
            *chain(
                (
                    Spoiler,
                    TaskListItem
                ),
                extras,
            )
        )
        self.render_map["Spoiler"] = self.render_spoiler
        self.render_map["TaskListItem"] = self.render_task_list_item

    def render_quote(
        self, token: block_token.Quote, max_line_length: int
    ) -> Iterable[str]:
        def add_expanded_suffix(iterable: Iterable[str]) -> Iterable[str]:
            iterator = iter(iterable)
            try:
                previous_item = next(iterator)
            except StopIteration:
                return iter([])
            for current_item in iterator:
                yield previous_item
                previous_item = current_item
            yield f"{previous_item}||"

        max_child_line_length = max_line_length - 2 if max_line_length else None
        lines = self.blocks_to_lines(
            token.children, max_line_length=max_child_line_length
        )
        lines, counter = tee(lines)
        total_characters = sum(len(s) for s in counter)
        # NOTE: Remove the space after the > , but it is not standard markdown
        append_expanded_cite = get_runtime_config().cite_expandable and total_characters > 200
        if append_expanded_cite:
            first_line_prefix = "**>"
            lines = add_expanded_suffix(lines)
        else:
            first_line_prefix = ">"
        yield from self.prefix_lines(
            lines or [""],
            first_line_prefix=first_line_prefix,
            following_line_prefix=">",
        )

    def render_heading(
        self, token: block_token.Heading, max_line_length: int
    ) -> Iterable[str]:
        # note: no word wrapping, because atx headings always fit on a single line.
        line = ""
        if token.level == 1:
            line += get_runtime_config().markdown_symbol.head_level_1
        elif token.level == 2:
            line += get_runtime_config().markdown_symbol.head_level_2
        elif token.level == 3:
            line += get_runtime_config().markdown_symbol.head_level_3
        elif token.level == 4:
            line += get_runtime_config().markdown_symbol.head_level_4
        text = next(
            self.span_to_lines(token.children, max_line_length=max_line_length), ""
        )
        if text:
            line += " " + text
        if token.closing_sequence:
            line += " " + token.closing_sequence
        return [markdown.bold(line)]

    def render_fenced_code_block(
        self, token: block_token.BlockCode, max_line_length: int
    ) -> Iterable[str]:
        indentation = " " * token.indentation
        yield indentation + token.delimiter + token.info_string
        yield from self.prefix_lines(token.content[:-1].split("\n"), indentation)
        yield indentation + token.delimiter

    def render_inline_code(self, token: span_token.InlineCode) -> Iterable[Fragment]:
        if len(token.delimiter) == 3:
            return self.embed_span(
                Fragment(token.delimiter + token.padding + "\n"),
                token.children,
                Fragment(token.padding + token.delimiter),
            )
        return self.embed_span(
            Fragment(token.delimiter + token.padding),
            token.children,
            Fragment(token.padding + token.delimiter),
        )

    def render_block_code(
        self, token: block_token.BlockCode, max_line_length: int
    ) -> Iterable[str]:
        return [markdown.code(token.content)]

    def render_setext_heading(
        self, token: block_token.SetextHeading, max_line_length: int
    ) -> Iterable[str]:
        yield from self.span_to_lines(token.children, max_line_length=max_line_length)
        yield markdown.escape("───────────────────")

    def render_emphasis(self, token: span_token.Emphasis) -> Iterable[Fragment]:
        return self.embed_span(Fragment("_"), token.children)

    def render_strong(self, token: span_token.Strong) -> Iterable[Fragment]:
        return self.embed_span(Fragment("*"), token.children)

    def render_strikethrough(
        self, token: span_token.Strikethrough
    ) -> Iterable[Fragment]:
        return self.embed_span(Fragment("~"), token.children)

    def render_spoiler(self, token: Spoiler) -> Iterable[Fragment]:
        return self.embed_span(Fragment("||"), token.children)

    def render_task_list_item(
        self, token: TaskListItem, max_line_length: int
    ) -> Iterable[str]:
        symbol = (
            get_runtime_config().markdown_symbol.task_completed
            if token.checked
            else get_runtime_config().markdown_symbol.task_uncompleted
        )
        if self.normalize_whitespace:
            indentation = 0
        else:
            indentation = len(token.indentation)
        lines = self.span_to_lines(token.children, max_line_length=max_line_length)
        space = " " * indentation
        return self.prefix_lines(lines or [""], f"{space}{symbol} ")

    def render_list_item(
        self, token: block_token.ListItem, max_line_length: int
    ) -> Iterable[str]:
        token_origin = str(token.leader).strip()
        if token_origin.endswith("."):
            if not token.leader.endswith(" "):
                token.leader += " "
            token.leader = markdown.escape(token.leader)
        else:
            token.leader = markdown.escape("⦁")
        return super().render_list_item(token, max_line_length)

    def render_link_reference_definition(
        self, token: LinkReferenceDefinition
    ) -> Iterable[Fragment]:
        yield from (
            Fragment(
                get_runtime_config().markdown_symbol.link
                + markdown.link(
                    body=token.title if token.title else token.label,
                    href=token.dest,
                )
            ),
        )

    def render_image(self, token: span_token.Image) -> Iterable[Fragment]:
        # tg://emoji?id=5368324170671202286 is a special case
        if not validate_telegram_emoji(token.src):
            yield Fragment(get_runtime_config().markdown_symbol.image)
        yield from self.render_link_or_image(token, token.src)

    def render_link(self, token: span_token.Link) -> Iterable[Fragment]:
        return self.render_link_or_image(token, token.target)

    def render_link_or_image(
        self, token: span_token.SpanToken, target: str
    ) -> Iterable[Fragment]:
        title = next(
            self.span_to_lines(token.children, max_line_length=self.max_line_length), ""
        )
        if token.dest_type == "uri" or token.dest_type == "angle_uri":
            # "[" description "](" dest_part [" " title] ")"
            # "[" description "](" dest_part [" " title] ")"
            if validate_telegram_emoji(target):
                yield Fragment(f"![{title}]({target})")
            else:
                yield Fragment(markdown.link(href=target, body=title))
        elif token.dest_type == "full":
            # "[" description "][" label "]"
            yield from (
                Fragment(markdown.escape("[")),
                Fragment(markdown.escape(token.label), wordwrap=True),
                Fragment(markdown.escape("]")),
            )
        elif token.dest_type == "collapsed":
            # "[" description "][]"
            yield (Fragment(markdown.escape("[]")),)
        else:
            # "[" description "]"
            pass

    def render_auto_link(self, token: span_token.AutoLink) -> Iterable[Fragment]:
        yield Fragment(
            markdown.escape("<") + token.children[0].content + markdown.escape(">")
        )

    def render_escape_sequence(
        self, token: span_token.EscapeSequence
    ) -> Iterable[Fragment]:
        # because the escape_markdown already happened in the parser, we can skip it here.
        yield Fragment("" + token.children[0].content)

    def render_table(
        self, token: block_token.Table, max_line_length: int
    ) -> Iterable[str]:
        # note: column widths are not preserved; they are automatically adjusted to fit the contents.
        fs = super().render_table(token, max_line_length)
        return [markdown.code(markdown.escape("\n".join(fs)))]


class TelegramMarkdownFormatter(TelegramMarkdownRenderer):
    def __init__(self, *extras, **kwargs):
        super().__init__(
            *chain(
                (
                    Spoiler,
                    TelegramStrikethrough,
                    TaskListItem,
                ),
                extras,
            )
        )
        self.render_map["Spoiler"] = self.render_spoiler
        self.render_map["TelegramStrikethrough"] = self.render_telegram_strikethrough
        self.render_map["TaskListItem"] = self.render_task_list_item

    def render_telegram_strikethrough(
        self, token: TelegramStrikethrough
    ) -> Iterable[Fragment]:
        return self.embed_span(Fragment("~"), token.children)

    def render_emphasis(self, token: span_token.Emphasis) -> Iterable[Fragment]:
        return self.embed_span(Fragment(token.delimiter), token.children)

    def render_strong(self, token: span_token.Strong) -> Iterable[Fragment]:
        if token.delimiter == "_":
            return self.embed_span(Fragment(token.delimiter * 2), token.children)
        return self.embed_span(Fragment(token.delimiter), token.children)
