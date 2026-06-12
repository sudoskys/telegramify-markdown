"""Telegram Bot API 10.1 Rich Message output.

This module is a parallel backend to ``converter.py``. It keeps the existing
``convert() -> (text, entities)`` contract untouched and emits
``InputRichMessage`` payloads for ``sendRichMessage``.
"""

from __future__ import annotations

import dataclasses
import html
from typing import Literal, Optional

import pyromark

from telegramify_markdown.converter import (
    STANDARD_OPTIONS,
    _escape_latex,
    _preprocess_spoilers,
    _validate_telegram_emoji,
)

try:
    RICH_OPTIONS = STANDARD_OPTIONS | pyromark.Options.ENABLE_FOOTNOTES
except AttributeError:  # pragma: no cover - older pyromark compatibility
    RICH_OPTIONS = STANDARD_OPTIONS


RichMode = Literal["html", "markdown"]


@dataclasses.dataclass(slots=True)
class InputRichMessage:
    """Telegram-compatible InputRichMessage payload.

    Exactly one of ``html`` or ``markdown`` is present. Optional Bot API fields
    are omitted from ``to_dict()`` when they are ``None``.
    """

    html: Optional[str] = None
    markdown: Optional[str] = None
    is_rtl: Optional[bool] = None
    skip_entity_detection: Optional[bool] = None

    def __post_init__(self) -> None:
        if (self.html is None) == (self.markdown is None):
            raise ValueError("exactly one of html or markdown must be set")

    def to_dict(self) -> dict:
        """Convert to a dict suitable for Telegram Bot API requests."""
        result: dict = {}
        if self.html is not None:
            result["html"] = self.html
        if self.markdown is not None:
            result["markdown"] = self.markdown
        if self.is_rtl is not None:
            result["is_rtl"] = self.is_rtl
        if self.skip_entity_detection is not None:
            result["skip_entity_detection"] = self.skip_entity_detection
        return result


@dataclasses.dataclass(slots=True)
class _ListScope:
    tag: str


@dataclasses.dataclass(slots=True)
class _ImageCapture:
    url: str
    title: str
    parts: list[str]


class _RichHtmlWalker:
    """Walk pyromark events and emit Telegram Rich HTML."""

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._inline_closers: list[str] = []
        self._list_stack: list[_ListScope] = []

        self._pending_paragraph = False
        self._paragraph_open = False

        self._in_code_block = False
        self._code_block_lang = ""
        self._code_block_parts: list[str] = []

        self._in_table = False
        self._in_table_head = False
        self._in_table_cell = False
        self._table_alignments: tuple = ()
        self._table_rows: list[list[tuple[str, bool]]] = []
        self._current_row: list[tuple[str, bool]] = []
        self._cell_parts: list[str] = []
        self._cell_col = 0

        self._image: _ImageCapture | None = None

    def walk(self, events: tuple) -> str:
        for event in events:
            self._handle_event(event)
        self._close_paragraph()
        return "".join(self._parts)

    def _handle_event(self, event) -> None:
        source_range = None
        if (
            isinstance(event, tuple)
            and len(event) == 2
            and isinstance(event[1], dict)
        ):
            event, source_range = event

        if isinstance(event, str):
            if event == "SoftBreak":
                self._on_soft_break()
            elif event == "HardBreak":
                self._on_hard_break()
            elif event == "Rule":
                self._close_paragraph()
                self._emit("<hr/>")
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
            self._write_inline(f"<tg-math>{self._escape_text(event['InlineMath'])}</tg-math>")
        elif "DisplayMath" in event:
            self._close_paragraph()
            self._emit(f"<tg-math-block>{self._escape_text(event['DisplayMath'])}</tg-math-block>")
        elif "InlineHtml" in event:
            self._on_inline_html(event["InlineHtml"])
        elif "Html" in event:
            self._write_inline(self._escape_text(event["Html"]))
        elif "TaskListMarker" in event:
            self._write_inline("✅ " if event["TaskListMarker"] else "☑ ")
        elif "FootnoteReference" in event:
            ref = str(event["FootnoteReference"])
            href = self._escape_attr(f"#{ref}")
            label = self._escape_text(f"[{ref}]")
            self._write_inline(f'<a href="{href}">{label}</a>')

    def _on_inline_html(self, value: str) -> None:
        tag = value.strip().lower()
        if tag == "<tg-spoiler>":
            self._open_inline("<tg-spoiler>", "</tg-spoiler>")
        elif tag == "</tg-spoiler>":
            self._close_inline()
        else:
            self._write_inline(self._escape_text(value))

    def _on_start(self, tag) -> None:
        if tag == "Strong":
            self._open_inline("<b>", "</b>")
        elif tag == "Emphasis":
            self._open_inline("<i>", "</i>")
        elif tag == "Strikethrough":
            self._open_inline("<s>", "</s>")
        elif tag == "Paragraph":
            self._pending_paragraph = True
        elif tag == "Item":
            self._close_paragraph()
            self._emit("<li>")
        elif tag == "TableHead":
            self._current_row = []
            self._in_table_head = True
        elif tag == "TableRow":
            self._current_row = []
            self._cell_col = 0
        elif tag == "TableCell":
            self._cell_parts = []
            self._in_table_cell = True
        elif tag == "HtmlBlock":
            self._pending_paragraph = True
        elif isinstance(tag, dict):
            if "Heading" in tag:
                self._on_start_heading(tag["Heading"])
            elif "CodeBlock" in tag:
                self._on_start_code_block(tag["CodeBlock"])
            elif "BlockQuote" in tag:
                self._close_paragraph()
                self._emit("<blockquote>")
            elif "Link" in tag:
                self._on_start_link(tag["Link"])
            elif "Image" in tag:
                self._on_start_image(tag["Image"])
            elif "List" in tag:
                self._on_start_list(tag["List"])
            elif "Table" in tag:
                self._on_start_table(tag["Table"])
            elif "FootnoteDefinition" in tag:
                self._close_paragraph()
                name = self._escape_attr(str(tag["FootnoteDefinition"]))
                self._emit(f'<tg-reference name="{name}">')

    def _on_end(self, tag) -> None:
        if tag == "Strong":
            self._close_inline()
        elif tag == "Emphasis":
            self._close_inline()
        elif tag == "Strikethrough":
            self._close_inline()
        elif tag == "Paragraph":
            self._close_paragraph()
        elif tag == "Item":
            self._close_paragraph()
            self._emit("</li>")
        elif tag == "CodeBlock":
            self._on_end_code_block()
        elif tag == "Table":
            self._on_end_table()
        elif tag == "TableCell":
            self._on_end_table_cell()
        elif tag == "TableRow":
            self._on_end_table_row()
        elif tag == "TableHead":
            self._on_end_table_row()
            self._in_table_head = False
        elif tag == "Link":
            self._close_inline()
        elif tag == "Image":
            self._on_end_image()
        elif tag == "FootnoteDefinition":
            self._close_paragraph()
            self._emit("</tg-reference>")
        elif isinstance(tag, dict):
            if "Heading" in tag:
                level = self._heading_level(tag["Heading"])
                self._emit(f"</h{level}>")
            elif "BlockQuote" in tag:
                self._close_paragraph()
                self._emit("</blockquote>")
            elif "List" in tag:
                self._on_end_list()

    def _on_text(self, text: str) -> None:
        if self._in_code_block:
            self._code_block_parts.append(text)
            return
        if self._image is not None:
            self._image.parts.append(text)
            return
        self._write_inline(self._escape_text(text))

    def _on_soft_break(self) -> None:
        if self._in_code_block:
            self._code_block_parts.append("\n")
            return
        if self._image is not None:
            self._image.parts.append(" ")
            return
        self._write_inline("<br/>")

    def _on_hard_break(self) -> None:
        if self._in_code_block:
            self._code_block_parts.append("\n")
            return
        self._write_inline("<br/>")

    def _on_inline_code(self, code: str) -> None:
        if self._image is not None:
            self._image.parts.append(code)
            return
        self._write_inline(f"<code>{self._escape_text(code)}</code>")

    def _on_start_heading(self, heading_data: dict) -> None:
        self._close_paragraph()
        level = self._heading_level(heading_data)
        self._emit(f"<h{level}>")

    def _on_start_code_block(self, kind) -> None:
        self._close_paragraph()
        self._in_code_block = True
        self._code_block_parts = []
        if isinstance(kind, dict) and "Fenced" in kind:
            self._code_block_lang = kind["Fenced"]
        else:
            self._code_block_lang = ""

    def _on_end_code_block(self) -> None:
        self._in_code_block = False
        raw_code = "".join(self._code_block_parts)
        if raw_code.endswith("\n"):
            raw_code = raw_code[:-1]

        lang = self._code_block_lang.split(",")[0].strip() if self._code_block_lang else ""
        escaped_code = self._escape_text(raw_code)
        if lang.lower() == "math":
            self._emit(f"<tg-math-block>{escaped_code}</tg-math-block>")
        elif lang:
            escaped_lang = self._escape_attr(f"language-{lang}")
            self._emit(f'<pre><code class="{escaped_lang}">{escaped_code}</code></pre>')
        else:
            self._emit(f"<pre>{escaped_code}</pre>")

        self._code_block_lang = ""
        self._code_block_parts = []

    def _on_start_link(self, link_data: dict) -> None:
        dest_url = link_data.get("dest_url", "")
        emoji_id = _validate_telegram_emoji(dest_url)
        if emoji_id:
            self._open_inline(
                f'<tg-emoji emoji-id="{self._escape_attr(emoji_id)}">',
                "</tg-emoji>",
            )
            return
        if dest_url:
            self._open_inline(
                f'<a href="{self._escape_attr(dest_url)}">',
                "</a>",
            )
            return
        self._inline_closers.append("")

    def _on_start_image(self, image_data: dict) -> None:
        self._image = _ImageCapture(
            url=image_data.get("dest_url", ""),
            title=image_data.get("title", ""),
            parts=[],
        )

    def _on_end_image(self) -> None:
        if self._image is None:
            return

        image = self._image
        self._image = None
        alt = "".join(image.parts)
        emoji_id = _validate_telegram_emoji(image.url)
        if emoji_id:
            self._write_inline(
                f'<tg-emoji emoji-id="{self._escape_attr(emoji_id)}">'
                f"{self._escape_text(alt)}"
                "</tg-emoji>"
            )
            return

        if image.url.startswith(("http://", "https://")):
            attrs = [
                f'src="{self._escape_attr(image.url)}"',
                f'alt="{self._escape_attr(alt)}"',
            ]
            if image.title:
                attrs.append(f'title="{self._escape_attr(image.title)}"')
            self._write_inline(f"<img {' '.join(attrs)}/>")
            return

        if image.url:
            href = self._escape_attr(image.url)
            text = self._escape_text(alt or image.url)
            self._write_inline(f'<a href="{href}">{text}</a>')
        else:
            self._write_inline(self._escape_text(alt))

    def _on_start_list(self, start_number: int | None) -> None:
        self._close_paragraph()
        if start_number is None:
            self._emit("<ul>")
            self._list_stack.append(_ListScope("ul"))
        else:
            self._emit(f'<ol start="{int(start_number)}">')
            self._list_stack.append(_ListScope("ol"))

    def _on_end_list(self) -> None:
        self._close_paragraph()
        if not self._list_stack:
            return
        scope = self._list_stack.pop()
        self._emit(f"</{scope.tag}>")

    def _on_start_table(self, alignments) -> None:
        self._close_paragraph()
        self._in_table = True
        self._table_alignments = alignments if isinstance(alignments, tuple) else ()
        self._table_rows = []
        self._emit("")

    def _on_end_table_cell(self) -> None:
        content = "".join(self._cell_parts)
        self._current_row.append((content, self._in_table_head))
        self._cell_col += 1
        self._cell_parts = []
        self._in_table_cell = False

    def _on_end_table_row(self) -> None:
        if self._current_row:
            self._table_rows.append(self._current_row)
        self._current_row = []
        self._cell_col = 0

    def _on_end_table(self) -> None:
        self._in_table = False
        rows: list[str] = []
        for row in self._table_rows:
            cells: list[str] = []
            for cell_index, (content, is_header) in enumerate(row):
                tag = "th" if is_header else "td"
                align = self._table_alignment(cell_index)
                attr = f' align="{align}"' if align else ""
                cells.append(f"<{tag}{attr}>{content}</{tag}>")
            rows.append(f"<tr>{''.join(cells)}</tr>")
        self._emit(f"<table>{''.join(rows)}</table>")
        self._table_rows = []
        self._table_alignments = ()

    def _open_inline(self, open_tag: str, close_tag: str) -> None:
        self._write_inline(open_tag)
        self._inline_closers.append(close_tag)

    def _close_inline(self) -> None:
        if not self._inline_closers:
            return
        closer = self._inline_closers.pop()
        if closer:
            self._write_inline(closer)

    def _write_inline(self, value: str) -> None:
        self._open_paragraph_if_pending()
        self._emit(value)

    def _emit(self, value: str) -> None:
        if self._in_table_cell:
            self._cell_parts.append(value)
        else:
            self._parts.append(value)

    def _open_paragraph_if_pending(self) -> None:
        if self._pending_paragraph and not self._paragraph_open and not self._in_table_cell:
            self._parts.append("<p>")
            self._paragraph_open = True
        self._pending_paragraph = False

    def _close_paragraph(self) -> None:
        self._pending_paragraph = False
        if self._paragraph_open:
            self._parts.append("</p>")
            self._paragraph_open = False

    def _table_alignment(self, index: int) -> str:
        if index >= len(self._table_alignments):
            return ""
        value = str(self._table_alignments[index]).lower()
        if value in {"left", "center", "right"}:
            return value
        return ""

    @staticmethod
    def _heading_level(heading_data) -> int:
        if isinstance(heading_data, dict):
            level = heading_data.get("level", "H1")
        else:
            level = heading_data
        text = str(level)
        if text.startswith("H") and text[1:].isdigit():
            return max(1, min(6, int(text[1:])))
        return 1

    @staticmethod
    def _escape_text(value: str) -> str:
        return html.escape(value, quote=False)

    @staticmethod
    def _escape_attr(value: str) -> str:
        return html.escape(value, quote=True)


def richify(
    markdown: str,
    *,
    mode: RichMode = "html",
    is_rtl: bool | None = None,
    skip_entity_detection: bool | None = None,
    latex_escape: bool = False,
) -> InputRichMessage:
    """Convert Markdown to a Telegram Bot API 10.1 InputRichMessage.

    ``mode="html"`` parses Markdown and emits Telegram Rich HTML. ``mode="markdown"``
    passes the input through as Telegram Rich Markdown, which is useful when
    callers deliberately rely on Telegram-specific Rich Markdown constructs.
    """
    if mode == "markdown":
        return InputRichMessage(
            markdown=markdown,
            is_rtl=is_rtl,
            skip_entity_detection=skip_entity_detection,
        )
    if mode != "html":
        raise ValueError("mode must be 'html' or 'markdown'")

    preprocessed = markdown
    if latex_escape:
        preprocessed = _escape_latex(preprocessed)
    preprocessed = _preprocess_spoilers(preprocessed)

    events = pyromark.events_with_range(preprocessed, options=RICH_OPTIONS)
    html_text = _RichHtmlWalker().walk(events)
    return InputRichMessage(
        html=html_text,
        is_rtl=is_rtl,
        skip_entity_detection=skip_entity_detection,
    )
