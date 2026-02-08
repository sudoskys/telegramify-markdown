"""Core converter: pyromark events → (plain_text, list[MessageEntity])."""

from __future__ import annotations

import dataclasses
import re
from typing import Optional

import pyromark

from .config import RenderConfig, get_runtime_config
from .entity import MessageEntity, utf16_len
from .latex_escape.const import LATEX_SYMBOLS, NOT_MAP, LATEX_STYLES
from .latex_escape.helper import LatexToUnicodeHelper

_latex_helper = LatexToUnicodeHelper()

# pyromark options for Telegram-compatible parsing
STANDARD_OPTIONS = (
    pyromark.Options.ENABLE_TABLES
    | pyromark.Options.ENABLE_STRIKETHROUGH
    | pyromark.Options.ENABLE_TASKLISTS
    | pyromark.Options.ENABLE_MATH
)

# --- Preprocessing -----------------------------------------------------------

_SPOILER_RE = re.compile(r"(?<![\\])\|\|(.+?)\|\|", re.DOTALL)
_CODE_REGION_RE = re.compile(r"(```[\s\S]*?```|`[^`\n]+`)")


def _preprocess_spoilers(text: str) -> str:
    """Replace ||spoiler|| with <tg-spoiler>spoiler</tg-spoiler>.

    Skips content inside code fences and inline code spans.
    """
    parts = _CODE_REGION_RE.split(text)
    result: list[str] = []
    for i, part in enumerate(parts):
        if i % 2 == 0:  # Not inside code
            part = _SPOILER_RE.sub(r"<tg-spoiler>\1</tg-spoiler>", part)
        result.append(part)
    return "".join(result)


def _validate_telegram_emoji(url: str) -> Optional[str]:
    """If url is tg://emoji?id=<19-digit-id>, return the id. Otherwise None."""
    if not url.startswith("tg://emoji?id="):
        return None
    emoji_id = url.removeprefix("tg://emoji?id=")
    if emoji_id.isdigit() and len(emoji_id) == 19:
        return emoji_id
    return None


_LATEX_MATH_P = re.compile(r"\\\[(.*?)\\\]", re.DOTALL)
_LATEX_INLINE_P = re.compile(r"\\\((.*?)\\\)", re.DOTALL)


def _contains_latex_symbols(content: str) -> bool:
    if len(content) < 5:
        return False
    latex_symbols = (
        (r"\frac", r"\sqrt", r"\begin")
        + tuple(LATEX_SYMBOLS.keys())
        + tuple(NOT_MAP.keys())
        + tuple(LATEX_STYLES.keys())
    )
    return any(symbol in content for symbol in latex_symbols)


def _escape_latex(text: str) -> str:
    """Pre-process LaTeX \\[...\\] and \\(...\\) blocks into Unicode."""

    def _convert(match: re.Match, is_block: bool) -> str:
        content = match.group(1)
        if not _contains_latex_symbols(content):
            return match.group(0)
        converted = _latex_helper.convert(content)
        if is_block:
            return f"$${converted.strip()}$$"
        else:
            return f"${converted.strip().strip(chr(10))}$"

    lines = text.split("\n\n")
    processed = []
    for line in lines:
        line = _LATEX_MATH_P.sub(lambda m: _convert(m, is_block=True), line)
        line = _LATEX_INLINE_P.sub(lambda m: _convert(m, is_block=False), line)
        processed.append(line)
    return "\n\n".join(processed)


# --- Segment tracking --------------------------------------------------------


@dataclasses.dataclass(slots=True)
class Segment:
    """A contiguous region of the output text tagged by its source type."""

    kind: str  # "text", "code_block", "mermaid"
    text_start: int  # Python string index (start, inclusive)
    text_end: int  # Python string index (end, exclusive)
    utf16_start: int
    utf16_end: int
    language: str = ""
    raw_code: str = ""


# --- Text buffer & entity scope ---------------------------------------------


class _TextBuffer:
    """Accumulates plain text and tracks the current UTF-16 offset."""

    __slots__ = ("_parts", "_utf16_offset")

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._utf16_offset: int = 0

    def write(self, text: str) -> None:
        self._parts.append(text)
        self._utf16_offset += utf16_len(text)

    @property
    def utf16_offset(self) -> int:
        return self._utf16_offset

    @property
    def py_offset(self) -> int:
        return sum(len(p) for p in self._parts)

    def trailing_newline_count(self) -> int:
        """Count trailing newline characters in the buffer."""
        count = 0
        for part in reversed(self._parts):
            for ch in reversed(part):
                if ch == "\n":
                    count += 1
                else:
                    return count
        return count

    def pop_last(self) -> str:
        """移除并返回最后写入的部分。用于替换刚写入的 bullet 前缀。"""
        if self._parts:
            part = self._parts.pop()
            self._utf16_offset -= utf16_len(part)
            return part
        return ""

    def get_text(self) -> str:
        return "".join(self._parts)


@dataclasses.dataclass(slots=True)
class _EntityScope:
    """An open entity waiting to be closed."""

    entity_type: str
    start_offset: int  # UTF-16 offset at push time
    url: Optional[str] = None
    language: Optional[str] = None
    custom_emoji_id: Optional[str] = None


# --- EventWalker state machine -----------------------------------------------


class EventWalker:
    """Walks pyromark events and produces (text, entities, segments)."""

    def __init__(self, config: RenderConfig) -> None:
        self._buf = _TextBuffer()
        self._entity_stack: list[_EntityScope] = []
        self._entities: list[MessageEntity] = []
        self._segments: list[Segment] = []
        self._config = config

        # Block-level state
        self._block_count: int = 0  # For paragraph spacing
        self._list_stack: list[int | None] = []  # None=unordered, int=next_number
        self._item_started: bool = False
        self._item_indent: str = ""  # 当前 item 的缩进，用于 task list marker 替换

        # Table state
        self._in_table: bool = False
        self._table_alignments: tuple = ()
        self._table_rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._cell_parts: list[str] = []
        self._in_table_cell: bool = False

        # Code block state
        self._in_code_block: bool = False
        self._code_block_lang: str = ""
        self._code_block_parts: list[str] = []

        # Heading state
        self._in_heading: bool = False
        self._heading_entities: list[str] = []

        # Blockquote state
        self._blockquote_scopes: list[_EntityScope] = []

    def walk(self, events: tuple) -> tuple[str, list[MessageEntity], list[Segment]]:
        for event in events:
            self._handle_event(event)
        text = self._buf.get_text()
        # Post-process: upgrade long blockquotes to expandable
        if self._config.cite_expandable:
            for ent in self._entities:
                if ent.type == "blockquote" and ent.length > 200:
                    ent.type = "expandable_blockquote"
        return text, self._entities, self._segments

    # -- Dispatch --------------------------------------------------------------

    def _handle_event(self, event) -> None:
        if isinstance(event, str):
            if event == "SoftBreak":
                self._on_soft_break()
            elif event == "HardBreak":
                self._on_hard_break()
            elif event == "Rule":
                self._on_rule()
            return

        if not isinstance(event, dict):
            return

        if "Start" in event:
            self._on_start(event["Start"])
        elif "End" in event:
            self._on_end(event["End"])
        elif "Text" in event:
            self._on_text(event["Text"])
        elif "Code" in event:
            self._on_inline_code(event["Code"])
        elif "InlineMath" in event:
            self._on_inline_math(event["InlineMath"])
        elif "DisplayMath" in event:
            self._on_display_math(event["DisplayMath"])
        elif "InlineHtml" in event:
            self._on_inline_html(event["InlineHtml"])
        elif "Html" in event:
            pass  # Block HTML ignored
        elif "TaskListMarker" in event:
            self._on_task_list_marker(event["TaskListMarker"])
        elif "FootnoteReference" in event:
            self._on_text(f"[{event['FootnoteReference']}]")

    # -- Start events ----------------------------------------------------------

    def _on_start(self, tag) -> None:
        if tag == "Strong":
            self._push_entity("bold")
        elif tag == "Emphasis":
            self._push_entity("italic")
        elif tag == "Strikethrough":
            self._push_entity("strikethrough")
        elif tag == "Paragraph":
            self._on_start_paragraph()
        elif tag == "Item":
            self._on_start_item()
        elif tag == "TableHead":
            self._current_row = []
        elif tag == "TableRow":
            self._current_row = []
        elif tag == "TableCell":
            self._cell_parts = []
            self._in_table_cell = True
        elif tag == "HtmlBlock":
            pass
        elif isinstance(tag, dict):
            if "Heading" in tag:
                self._on_start_heading(tag["Heading"])
            elif "CodeBlock" in tag:
                self._on_start_code_block(tag["CodeBlock"])
            elif "BlockQuote" in tag:
                self._on_start_blockquote()
            elif "Link" in tag:
                self._on_start_link(tag["Link"])
            elif "Image" in tag:
                self._on_start_image(tag["Image"])
            elif "List" in tag:
                self._on_start_list(tag["List"])
            elif "Table" in tag:
                self._on_start_table(tag["Table"])
            elif "FootnoteDefinition" in tag:
                self._ensure_block_spacing()

    # -- End events ------------------------------------------------------------

    def _on_end(self, tag) -> None:
        if tag == "Strong":
            self._pop_entity("bold")
        elif tag == "Emphasis":
            self._pop_entity("italic")
        elif tag == "Strikethrough":
            self._pop_entity("strikethrough")
        elif tag == "Paragraph":
            self._on_end_paragraph()
        elif tag == "Item":
            self._on_end_item()
        elif tag == "CodeBlock":
            self._on_end_code_block()
        elif tag == "Table":
            self._on_end_table()
        elif tag == "TableCell":
            self._on_end_table_cell()
        elif tag == "TableRow":
            self._on_end_table_row()
        elif tag == "TableHead":
            self._on_end_table_row()  # Header cells are directly inside TableHead
        elif tag == "Link":
            self._pop_entity("text_link")
        elif tag == "Image":
            self._pop_entity_any()
        elif tag == "FootnoteDefinition":
            pass
        elif isinstance(tag, dict):
            if "Heading" in tag:
                self._on_end_heading()
            elif "BlockQuote" in tag:
                self._on_end_blockquote()
            elif "List" in tag:
                self._on_end_list()

    # -- Inline events ---------------------------------------------------------

    def _on_text(self, text: str) -> None:
        if self._in_code_block:
            self._code_block_parts.append(text)
            return
        if self._in_table_cell:
            self._cell_parts.append(text)
            return
        self._buf.write(text)

    def _on_soft_break(self) -> None:
        if self._in_code_block:
            self._code_block_parts.append("\n")
            return
        if self._in_table_cell:
            self._cell_parts.append(" ")
            return
        self._buf.write("\n")

    def _on_hard_break(self) -> None:
        if self._in_code_block:
            self._code_block_parts.append("\n")
            return
        self._buf.write("\n")

    def _on_rule(self) -> None:
        self._ensure_block_spacing()
        self._buf.write("————————")
        self._block_count += 1

    def _on_inline_code(self, code: str) -> None:
        if self._in_table_cell:
            self._cell_parts.append(code)
            return
        start = self._buf.utf16_offset
        self._buf.write(code)
        length = self._buf.utf16_offset - start
        if length > 0:
            self._entities.append(MessageEntity(type="code", offset=start, length=length))

    def _on_inline_math(self, math: str) -> None:
        converted = math
        if _contains_latex_symbols(math):
            converted = _latex_helper.convert(math).strip().strip("\n")
        start = self._buf.utf16_offset
        self._buf.write(converted)
        length = self._buf.utf16_offset - start
        if length > 0:
            self._entities.append(MessageEntity(type="code", offset=start, length=length))

    def _on_display_math(self, math: str) -> None:
        converted = math
        if _contains_latex_symbols(math):
            converted = _latex_helper.convert(math).strip()
        self._ensure_block_spacing()
        start = self._buf.utf16_offset
        self._buf.write(converted)
        length = self._buf.utf16_offset - start
        if length > 0:
            self._entities.append(MessageEntity(type="pre", offset=start, length=length))
        self._block_count += 1

    def _on_inline_html(self, html: str) -> None:
        tag = html.strip().lower()
        if tag == "<tg-spoiler>":
            self._push_entity("spoiler")
        elif tag == "</tg-spoiler>":
            self._pop_entity("spoiler")
        # Other inline HTML is ignored

    def _on_task_list_marker(self, checked: bool) -> None:
        symbol = (
            self._config.markdown_symbol.task_completed
            if checked
            else self._config.markdown_symbol.task_uncompleted
        )
        # 移除 _on_start_item 刚写入的 bullet 前缀（"⦁ " 或 "N. "），替换为 task marker
        self._buf.pop_last()
        self._buf.write(f"{self._item_indent}{symbol} ")

    # -- Heading ---------------------------------------------------------------

    # entity 样式递降：H1-H2 bold+underline, H3-H4 bold, H5-H6 italic
    _HEADING_ENTITIES: dict[str, list[str]] = {
        "H1": ["bold", "underline"],
        "H2": ["bold", "underline"],
        "H3": ["bold"],
        "H4": ["bold"],
        "H5": ["italic"],
        "H6": ["italic"],
    }

    def _on_start_heading(self, heading_data: dict) -> None:
        self._ensure_block_spacing()
        level = heading_data["level"]
        symbol_map = {
            "H1": self._config.markdown_symbol.heading_level_1,
            "H2": self._config.markdown_symbol.heading_level_2,
            "H3": self._config.markdown_symbol.heading_level_3,
            "H4": self._config.markdown_symbol.heading_level_4,
            "H5": self._config.markdown_symbol.heading_level_5,
            "H6": self._config.markdown_symbol.heading_level_6,
        }
        prefix = symbol_map.get(level, "")
        if prefix:
            self._buf.write(prefix + " ")
        self._heading_entities = self._HEADING_ENTITIES.get(level, ["bold"])
        for etype in self._heading_entities:
            self._push_entity(etype)
        self._in_heading = True

    def _on_end_heading(self) -> None:
        for etype in reversed(self._heading_entities):
            self._pop_entity(etype)
        self._heading_entities = []
        self._in_heading = False
        self._block_count += 1

    # -- Paragraph -------------------------------------------------------------

    def _on_start_paragraph(self) -> None:
        if not self._list_stack:
            self._ensure_block_spacing()

    def _on_end_paragraph(self) -> None:
        if not self._list_stack:
            self._block_count += 1
        elif self._buf.trailing_newline_count() == 0:
            # loose list 中段落结束时写入换行，避免多段落粘连
            self._buf.write("\n")

    # -- Code block ------------------------------------------------------------

    def _on_start_code_block(self, kind) -> None:
        self._in_code_block = True
        self._code_block_parts = []
        if isinstance(kind, dict) and "Fenced" in kind:
            self._code_block_lang = kind["Fenced"]
        else:
            self._code_block_lang = ""

    def _on_end_code_block(self) -> None:
        self._in_code_block = False
        raw_code = "".join(self._code_block_parts)
        # Strip single trailing newline (pulldown-cmark adds one)
        if raw_code.endswith("\n"):
            raw_code = raw_code[:-1]

        self._ensure_block_spacing()

        # Record segment
        seg_text_start = self._buf.py_offset
        seg_utf16_start = self._buf.utf16_offset

        start = self._buf.utf16_offset
        self._buf.write(raw_code)
        length = self._buf.utf16_offset - start

        lang = self._code_block_lang.split(",")[0].strip() if self._code_block_lang else ""

        if length > 0:
            self._entities.append(
                MessageEntity(
                    type="pre",
                    offset=start,
                    length=length,
                    language=lang if lang else None,
                )
            )

        seg_kind = "mermaid" if lang.lower() == "mermaid" else "code_block"
        self._segments.append(
            Segment(
                kind=seg_kind,
                text_start=seg_text_start,
                text_end=self._buf.py_offset,
                utf16_start=seg_utf16_start,
                utf16_end=self._buf.utf16_offset,
                language=lang,
                raw_code=raw_code,
            )
        )

        self._block_count += 1
        self._code_block_lang = ""
        self._code_block_parts = []

    # -- Blockquote ------------------------------------------------------------

    def _on_start_blockquote(self) -> None:
        self._ensure_block_spacing()
        scope = _EntityScope("blockquote", self._buf.utf16_offset)
        self._blockquote_scopes.append(scope)

    def _on_end_blockquote(self) -> None:
        if self._blockquote_scopes:
            scope = self._blockquote_scopes.pop()
            length = self._buf.utf16_offset - scope.start_offset
            if length > 0:
                self._entities.append(
                    MessageEntity(
                        type="blockquote",
                        offset=scope.start_offset,
                        length=length,
                    )
                )
        self._block_count += 1

    # -- Links -----------------------------------------------------------------

    def _on_start_link(self, link_data: dict) -> None:
        dest_url = link_data.get("dest_url", "")
        emoji_id = _validate_telegram_emoji(dest_url)
        if emoji_id:
            self._push_entity("custom_emoji", custom_emoji_id=emoji_id)
        elif dest_url:
            self._push_entity("text_link", url=dest_url)
        # Empty URL links are rendered as plain text (no entity)

    # -- Images ----------------------------------------------------------------

    def _on_start_image(self, image_data: dict) -> None:
        dest_url = image_data.get("dest_url", "")
        emoji_id = _validate_telegram_emoji(dest_url)
        if emoji_id:
            self._push_entity("custom_emoji", custom_emoji_id=emoji_id)
        else:
            self._buf.write(self._config.markdown_symbol.image)
            self._push_entity("text_link", url=dest_url)

    # -- Lists -----------------------------------------------------------------

    def _on_start_list(self, start_number: int | None) -> None:
        if not self._list_stack:
            self._ensure_block_spacing()
        self._list_stack.append(start_number)

    def _on_start_item(self) -> None:
        depth = len(self._list_stack)
        indent = "  " * (depth - 1) if depth > 1 else ""
        current_list = self._list_stack[-1] if self._list_stack else None

        # 嵌套列表：父项文本后没有换行时，插入换行确保子项独占一行
        if self._buf.py_offset > 0 and self._buf.trailing_newline_count() == 0:
            self._buf.write("\n")

        self._item_indent = indent
        if current_list is not None:
            # Ordered list
            self._buf.write(f"{indent}{current_list}. ")
            self._list_stack[-1] = current_list + 1
        else:
            # Unordered list
            self._buf.write(f"{indent}⦁ ")
        self._item_started = True

    def _on_end_item(self) -> None:
        if self._buf.trailing_newline_count() == 0:
            self._buf.write("\n")
        self._item_started = False

    def _on_end_list(self) -> None:
        if self._list_stack:
            self._list_stack.pop()
        if not self._list_stack:
            self._block_count += 1

    # -- Tables ----------------------------------------------------------------

    def _on_start_table(self, alignments) -> None:
        self._ensure_block_spacing()
        self._in_table = True
        self._table_alignments = alignments if isinstance(alignments, tuple) else ()
        self._table_rows = []

    def _on_end_table_cell(self) -> None:
        self._current_row.append("".join(self._cell_parts))
        self._cell_parts = []
        self._in_table_cell = False

    def _on_end_table_row(self) -> None:
        self._table_rows.append(self._current_row)
        self._current_row = []

    def _on_end_table(self) -> None:
        self._in_table = False
        table_text = self._format_table(self._table_rows)

        start = self._buf.utf16_offset
        self._buf.write(table_text)
        length = self._buf.utf16_offset - start
        if length > 0:
            self._entities.append(MessageEntity(type="pre", offset=start, length=length))
        self._table_rows = []
        self._block_count += 1

    def _format_table(self, rows: list[list[str]]) -> str:
        if not rows:
            return ""
        # Compute column widths
        num_cols = max(len(row) for row in rows)
        col_widths = [0] * num_cols
        for row in rows:
            for i, cell in enumerate(row):
                if i < num_cols:
                    col_widths[i] = max(col_widths[i], len(cell))

        lines: list[str] = []
        for row_idx, row in enumerate(rows):
            cells: list[str] = []
            for i in range(num_cols):
                cell = row[i] if i < len(row) else ""
                cells.append(cell.ljust(col_widths[i]))
            lines.append(" | ".join(cells))
            # Add separator after header
            if row_idx == 0 and len(rows) > 1:
                sep_cells = ["-" * w for w in col_widths]
                lines.append("-+-".join(sep_cells))

        return "\n".join(lines)

    # -- Entity helpers --------------------------------------------------------

    def _push_entity(self, entity_type: str, **kwargs) -> None:
        scope = _EntityScope(
            entity_type=entity_type,
            start_offset=self._buf.utf16_offset,
            **kwargs,
        )
        self._entity_stack.append(scope)

    def _pop_entity(self, entity_type: str) -> None:
        # Find the matching scope (search from top)
        for i in range(len(self._entity_stack) - 1, -1, -1):
            if self._entity_stack[i].entity_type == entity_type:
                scope = self._entity_stack.pop(i)
                self._finalize_entity(scope)
                return

    def _pop_entity_any(self) -> None:
        if self._entity_stack:
            scope = self._entity_stack.pop()
            self._finalize_entity(scope)

    def _finalize_entity(self, scope: _EntityScope) -> None:
        length = self._buf.utf16_offset - scope.start_offset
        if length <= 0:
            return
        self._entities.append(
            MessageEntity(
                type=scope.entity_type,
                offset=scope.start_offset,
                length=length,
                url=scope.url,
                language=scope.language,
                custom_emoji_id=scope.custom_emoji_id,
            )
        )

    def _ensure_block_spacing(self) -> None:
        """Ensure a blank line (\\n\\n) between blocks, avoiding excess newlines."""
        if self._block_count > 0:
            trailing = self._buf.trailing_newline_count()
            needed = 2 - trailing
            if needed > 0:
                self._buf.write("\n" * needed)


# --- Public API ---------------------------------------------------------------


def convert(
    markdown: str,
    *,
    latex_escape: bool = True,
    config: RenderConfig | None = None,
) -> tuple[str, list[MessageEntity]]:
    """Convert markdown to (plain_text, entities) for Telegram.

    :param markdown: Raw markdown text.
    :param latex_escape: Whether to convert LaTeX to Unicode.
    :param config: Render configuration. Uses global config if None.
    :return: Tuple of (plain_text, list_of_entities).
    """
    if config is None:
        config = get_runtime_config()

    text, entities, _ = convert_with_segments(
        markdown, latex_escape=latex_escape, config=config
    )
    return text, entities


def convert_with_segments(
    markdown: str,
    *,
    latex_escape: bool = True,
    config: RenderConfig | None = None,
) -> tuple[str, list[MessageEntity], list[Segment]]:
    """Convert markdown to (plain_text, entities, segments).

    Like convert(), but also returns segment information for the pipeline.
    """
    if config is None:
        config = get_runtime_config()

    preprocessed = markdown
    if latex_escape:
        preprocessed = _escape_latex(preprocessed)
    preprocessed = _preprocess_spoilers(preprocessed)

    events = pyromark.events(preprocessed, options=STANDARD_OPTIONS)
    walker = EventWalker(config)
    return walker.walk(events)
