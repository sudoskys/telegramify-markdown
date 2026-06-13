"""Telegram Bot API 10.1 Rich Message output.

This module is a parallel backend to ``converter.py``. It keeps the existing
``convert() -> (text, entities)`` contract untouched and emits
``InputRichMessage`` payloads for ``sendRichMessage``.

@see docs/adr/001-rich-message-pipeline-composition.md
"""

from __future__ import annotations

import dataclasses
import html
import logging
import re
from html.parser import HTMLParser
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

logger = logging.getLogger(__name__)

RichMode = Literal["html", "markdown"]

# Telegram Rich Message 硬限制
RICH_BYTE_LIMIT = 32768
RICH_BLOCK_LIMIT = 500


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
class RichBlock:
    """单个顶层 block 的 HTML 片段及其元信息（内部类型，不导出）。"""

    html: str
    byte_len: int  # len(html.encode('utf-8'))
    block_count: int  # 顶层 block = 1


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

        # block 追踪: 顶层 block 深度
        self._block_depth = 0
        self._blocks: list[RichBlock] = []
        self._block_mode = False  # walk_blocks 模式

    def walk(self, events: tuple) -> str:
        """返回完整 HTML 字符串（向后兼容）。"""
        for event in events:
            self._handle_event(event)
        self._close_paragraph()
        return "".join(self._parts)

    def walk_blocks(self, events: tuple) -> list[RichBlock]:
        """返回按顶层 block 边界切分的 RichBlock 列表。"""
        self._block_mode = True
        for event in events:
            self._handle_event(event)
        self._close_paragraph()
        self._flush_block()
        return self._blocks

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
                self._enter_block()
                self._emit("<hr/>")
                self._leave_block()
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
            self._enter_block()
            self._emit(f"<tg-math-block>{self._escape_text(event['DisplayMath'])}</tg-math-block>")
            self._leave_block()
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
            self._enter_block()
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
            self._enter_block()
            self._pending_paragraph = True
        elif isinstance(tag, dict):
            if "Heading" in tag:
                self._enter_block()
                self._on_start_heading(tag["Heading"])
            elif "CodeBlock" in tag:
                self._enter_block()
                self._on_start_code_block(tag["CodeBlock"])
            elif "BlockQuote" in tag:
                self._enter_block()
                self._close_paragraph()
                self._emit("<blockquote>")
            elif "Link" in tag:
                self._on_start_link(tag["Link"])
            elif "Image" in tag:
                self._on_start_image(tag["Image"])
            elif "List" in tag:
                self._enter_block()
                self._on_start_list(tag["List"])
            elif "Table" in tag:
                self._enter_block()
                self._on_start_table(tag["Table"])
            elif "FootnoteDefinition" in tag:
                self._enter_block()
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
            self._leave_block()
        elif tag == "Item":
            self._close_paragraph()
            self._emit("</li>")
        elif tag == "CodeBlock":
            self._on_end_code_block()
            self._leave_block()
        elif tag == "Table":
            self._on_end_table()
            self._leave_block()
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
            self._leave_block()
        elif isinstance(tag, dict):
            if "Heading" in tag:
                level = self._heading_level(tag["Heading"])
                self._emit(f"</h{level}>")
                self._leave_block()
            elif "BlockQuote" in tag:
                self._close_paragraph()
                self._emit("</blockquote>")
                self._leave_block()
            elif "List" in tag:
                self._on_end_list()
                self._leave_block()

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

    def _enter_block(self) -> None:
        """进入一个 block-level 容器。仅在 _block_mode 下追踪深度。"""
        self._block_depth += 1

    def _leave_block(self) -> None:
        """离开一个 block-level 容器。深度归零时 flush 当前 block。"""
        self._block_depth -= 1
        if self._block_mode and self._block_depth == 0:
            self._flush_block()

    def _flush_block(self) -> None:
        """将当前 _parts 缓冲区 flush 为一个 RichBlock。"""
        if not self._parts:
            return
        block_html = "".join(self._parts)
        self._parts = []
        self._blocks.append(
            RichBlock(
                html=block_html,
                byte_len=len(block_html.encode("utf-8")),
                block_count=1,
            )
        )

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


def _walk_blocks_from_markdown(
    markdown: str,
    *,
    latex_escape: bool = False,
) -> list[RichBlock]:
    """预处理 + 解析 + walk，返回 RichBlock 列表。"""
    preprocessed = markdown
    if latex_escape:
        preprocessed = _escape_latex(preprocessed)
    preprocessed = _preprocess_spoilers(preprocessed)
    events = pyromark.events_with_range(preprocessed, options=RICH_OPTIONS)
    return _RichHtmlWalker().walk_blocks(events)


def split_rich(
    rich_message: InputRichMessage,
    *,
    byte_limit: int = RICH_BYTE_LIMIT,
    block_limit: int = RICH_BLOCK_LIMIT,
) -> list[InputRichMessage]:
    """将 InputRichMessage 拆分为多个 chunk，每个 chunk 符合 Telegram 限制。

    对于 ``html`` 模式：重新通过 walker 获取 block 列表，按 byte 和 block 预算分箱。
    对于 ``markdown`` 模式：按段落（双换行）拆分，尊重字节限制。
    输入在限制内时直接返回 ``[rich_message]``。

    @see docs/adr/001-rich-message-pipeline-composition.md
    """
    if rich_message.html is not None:
        return _split_html(rich_message, byte_limit=byte_limit, block_limit=block_limit)
    else:
        return _split_markdown(rich_message, byte_limit=byte_limit, block_limit=block_limit)


def _split_html(
    rich_message: InputRichMessage,
    *,
    byte_limit: int,
    block_limit: int,
) -> list[InputRichMessage]:
    """拆分 html 模式的 InputRichMessage。"""
    html_content = rich_message.html
    assert html_content is not None

    # 快速路径: 不需要拆分
    byte_len = len(html_content.encode("utf-8"))
    if byte_len <= byte_limit:
        # 还需要检查 block 数，但无法精确得知 block 数不做 re-walk
        # 对于单 payload 直接返回（richify 的输出最多 ~500 block 时才到这里）
        # 实际 re-walk 以确保 block 数正确
        pass

    # 用简化的 walker 从 HTML 重构 block 列表不可行（会违反 single-parse-boundary）
    # 但 split_rich 接受的是已构建的 InputRichMessage，无法回溯到 markdown 源
    # 因此对于 split_rich(已构建 payload) 的情况，用标签启发式拆分
    blocks = _heuristic_html_blocks(html_content)

    return _bin_blocks(
        blocks,
        byte_limit=byte_limit,
        block_limit=block_limit,
        is_rtl=rich_message.is_rtl,
        skip_entity_detection=rich_message.skip_entity_detection,
        mode="html",
    )


def _heuristic_html_blocks(html_content: str) -> list[RichBlock]:
    """从已渲染的 Rich HTML 中启发式提取顶层 block。

    walker 输出的 HTML 结构是严格的顶层 block 序列（无换行分隔），
    每个顶层 block 以 <tag 开头且在同一层级闭合。
    """
    import re

    # 顶层 block-level 标签
    _BLOCK_TAGS = frozenset([
        "p", "h1", "h2", "h3", "h4", "h5", "h6",
        "pre", "blockquote", "ul", "ol", "table",
        "hr", "tg-math-block", "img", "tg-reference", "details",
    ])

    blocks: list[RichBlock] = []
    pos = 0
    length = len(html_content)

    while pos < length:
        # 找到下一个 < 标签
        if html_content[pos] != "<":
            # 不应该出现，但容错: 收集到下一个 <
            next_tag = html_content.find("<", pos)
            if next_tag == -1:
                # 剩余文本作为一个 block
                fragment = html_content[pos:]
                blocks.append(RichBlock(
                    html=fragment,
                    byte_len=len(fragment.encode("utf-8")),
                    block_count=1,
                ))
                break
            pos = next_tag
            continue

        # 解析标签名
        m = re.match(r"<([a-zA-Z][a-zA-Z0-9-]*)", html_content[pos:])
        if not m:
            # 不可解析，取到下一个 <
            next_tag = html_content.find("<", pos + 1)
            if next_tag == -1:
                next_tag = length
            fragment = html_content[pos:next_tag]
            blocks.append(RichBlock(
                html=fragment,
                byte_len=len(fragment.encode("utf-8")),
                block_count=1,
            ))
            pos = next_tag
            continue

        tag_name = m.group(1).lower()

        if tag_name not in _BLOCK_TAGS:
            # 不认识的顶层标签，尝试找到闭合
            end = _find_tag_end(html_content, pos, tag_name)
            fragment = html_content[pos:end]
            blocks.append(RichBlock(
                html=fragment,
                byte_len=len(fragment.encode("utf-8")),
                block_count=1,
            ))
            pos = end
            continue

        # 自闭合标签
        if tag_name in ("hr", "img"):
            # 找到 /> 或 >
            close = html_content.find(">", pos)
            if close == -1:
                close = length - 1
            end = close + 1
            fragment = html_content[pos:end]
            blocks.append(RichBlock(
                html=fragment,
                byte_len=len(fragment.encode("utf-8")),
                block_count=1,
            ))
            pos = end
            continue

        # 带闭合标签的 block
        end = _find_tag_end(html_content, pos, tag_name)
        fragment = html_content[pos:end]
        blocks.append(RichBlock(
            html=fragment,
            byte_len=len(fragment.encode("utf-8")),
            block_count=1,
        ))
        pos = end

    return blocks


def _find_tag_end(html_content: str, start: int, tag_name: str) -> int:
    """找到从 start 开始的标签对应闭合位置（包含闭合标签）。

    简单实现：计数同名标签的嵌套深度。
    """
    import re
    pos = start
    depth = 0
    length = len(html_content)
    pattern = re.compile(rf"<(/?)({re.escape(tag_name)})(?:\s|>|/>)")

    while pos < length:
        m = pattern.search(html_content, pos)
        if m is None:
            return length

        is_close = m.group(1) == "/"
        if is_close:
            depth -= 1
            if depth == 0:
                # 找到匹配的 > 位置
                end = html_content.find(">", m.end() - 1)
                return (end + 1) if end != -1 else length
        else:
            depth += 1

        pos = m.end()

    return length


def _split_markdown(
    rich_message: InputRichMessage,
    *,
    byte_limit: int,
    block_limit: int,
) -> list[InputRichMessage]:
    """拆分 markdown 模式的 InputRichMessage（按双换行段落）。"""
    md_content = rich_message.markdown
    assert md_content is not None

    if not md_content.strip():
        return []

    if len(md_content.encode("utf-8")) <= byte_limit:
        return [rich_message]

    paragraphs = md_content.split("\n\n")
    chunks: list[InputRichMessage] = []
    current_parts: list[str] = []
    current_bytes = 0

    for para in paragraphs:
        para_bytes = len(para.encode("utf-8"))
        # 段落分隔符的字节数
        sep_bytes = 2 if current_parts else 0

        if para_bytes > byte_limit:
            if current_parts:
                chunks.append(InputRichMessage(
                    markdown="\n\n".join(current_parts),
                    is_rtl=rich_message.is_rtl,
                    skip_entity_detection=rich_message.skip_entity_detection,
                ))
                current_parts = []
                current_bytes = 0

            for part in _split_text_by_utf8_bytes(para, byte_limit):
                chunks.append(InputRichMessage(
                    markdown=part,
                    is_rtl=rich_message.is_rtl,
                    skip_entity_detection=rich_message.skip_entity_detection,
                ))
            continue

        if current_bytes + sep_bytes + para_bytes > byte_limit and current_parts:
            # flush 当前 chunk
            chunks.append(InputRichMessage(
                markdown="\n\n".join(current_parts),
                is_rtl=rich_message.is_rtl,
                skip_entity_detection=rich_message.skip_entity_detection,
            ))
            current_parts = []
            current_bytes = 0

        current_parts.append(para)
        current_bytes += (sep_bytes + para_bytes) if current_bytes > 0 else para_bytes

    if current_parts:
        chunks.append(InputRichMessage(
            markdown="\n\n".join(current_parts),
            is_rtl=rich_message.is_rtl,
            skip_entity_detection=rich_message.skip_entity_detection,
        ))

    return chunks if chunks else [rich_message]


def _bin_blocks(
    blocks: list[RichBlock],
    *,
    byte_limit: int,
    block_limit: int,
    is_rtl: bool | None,
    skip_entity_detection: bool | None,
    mode: str,
) -> list[InputRichMessage]:
    """将 RichBlock 列表分箱为多个 InputRichMessage。"""
    if not blocks:
        return []

    # 快速路径
    total_bytes = sum(b.byte_len for b in blocks)
    total_blocks = sum(b.block_count for b in blocks)
    if total_bytes <= byte_limit and total_blocks <= block_limit:
        joined = "".join(b.html for b in blocks)
        if mode == "html":
            return [InputRichMessage(html=joined, is_rtl=is_rtl, skip_entity_detection=skip_entity_detection)]
        else:
            return [InputRichMessage(markdown=joined, is_rtl=is_rtl, skip_entity_detection=skip_entity_detection)]

    chunks: list[InputRichMessage] = []
    current_blocks: list[RichBlock] = []
    current_bytes = 0
    current_block_count = 0

    for block in blocks:
        # 超大 atomic block: 独立发出并警告
        if block.byte_len > byte_limit:
            # 先 flush 已有内容
            if current_blocks:
                _flush_chunk(chunks, current_blocks, mode, is_rtl, skip_entity_detection)
                current_blocks = []
                current_bytes = 0
                current_block_count = 0

            split_blocks = _split_oversized_block(block, byte_limit)
            if split_blocks:
                for split_block in split_blocks:
                    _flush_chunk(chunks, [split_block], mode, is_rtl, skip_entity_detection)
            else:
                logger.warning(
                    "单个 block 超过字节限制 (%d > %d)，独立发出。Telegram 可能拒绝。",
                    block.byte_len,
                    byte_limit,
                )
                _flush_chunk(chunks, [block], mode, is_rtl, skip_entity_detection)
            continue

        # 检查是否会超出预算
        if (
            current_bytes + block.byte_len > byte_limit
            or current_block_count + block.block_count > block_limit
        ):
            _flush_chunk(chunks, current_blocks, mode, is_rtl, skip_entity_detection)
            current_blocks = []
            current_bytes = 0
            current_block_count = 0

        current_blocks.append(block)
        current_bytes += block.byte_len
        current_block_count += block.block_count

    if current_blocks:
        _flush_chunk(chunks, current_blocks, mode, is_rtl, skip_entity_detection)

    return chunks


def _flush_chunk(
    chunks: list[InputRichMessage],
    blocks: list[RichBlock],
    mode: str,
    is_rtl: bool | None,
    skip_entity_detection: bool | None,
) -> None:
    """将一组 block 合并为一个 InputRichMessage 并追加到 chunks。"""
    joined = "".join(b.html for b in blocks)
    if mode == "html":
        chunks.append(InputRichMessage(html=joined, is_rtl=is_rtl, skip_entity_detection=skip_entity_detection))
    else:
        chunks.append(InputRichMessage(markdown=joined, is_rtl=is_rtl, skip_entity_detection=skip_entity_detection))


def _split_oversized_block(block: RichBlock, byte_limit: int) -> list[RichBlock]:
    """Split oversized paragraph/pre blocks while preserving valid Rich HTML."""
    html_text = block.html

    paragraph = _extract_wrapped_text(html_text, "p")
    if paragraph is not None:
        budget = byte_limit - len("<p></p>".encode("utf-8"))
        return [
            _make_block(f"<p>{_escape_text(part)}</p>")
            for part in _split_text_by_escaped_utf8_bytes(
                _html_fragment_to_text(paragraph),
                budget,
            )
            if part
        ]

    pre = _extract_pre_text(html_text)
    if pre is not None:
        open_tag, content, close_tag = pre
        budget = byte_limit - len((open_tag + close_tag).encode("utf-8"))
        return [
            _make_block(open_tag + _escape_text(part) + close_tag)
            for part in _split_text_by_escaped_utf8_bytes(
                html.unescape(content),
                budget,
            )
            if part
        ]

    return []


def _make_block(html_text: str) -> RichBlock:
    return RichBlock(
        html=html_text,
        byte_len=len(html_text.encode("utf-8")),
        block_count=1,
    )


def _extract_wrapped_text(html_text: str, tag: str) -> str | None:
    open_tag = f"<{tag}>"
    close_tag = f"</{tag}>"
    if html_text.startswith(open_tag) and html_text.endswith(close_tag):
        return html_text[len(open_tag):-len(close_tag)]
    return None


def _extract_pre_text(html_text: str) -> tuple[str, str, str] | None:
    match = re.fullmatch(r"(<pre(?:><code class=\"[^\"]+\">|>))(.*)(</code></pre>|</pre>)", html_text, re.DOTALL)
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3)


def _split_text_by_utf8_bytes(text: str, byte_limit: int) -> list[str]:
    """Split text into chunks whose UTF-8 encoded byte length fits byte_limit."""
    if byte_limit <= 0:
        raise ValueError("byte_limit must leave room for wrapper tags")

    chunks: list[str] = []
    current: list[str] = []
    current_bytes = 0
    for ch in text:
        ch_bytes = len(ch.encode("utf-8"))
        if current and current_bytes + ch_bytes > byte_limit:
            chunks.append("".join(current))
            current = []
            current_bytes = 0
        current.append(ch)
        current_bytes += ch_bytes
    if current:
        chunks.append("".join(current))
    return chunks


def _split_text_by_escaped_utf8_bytes(text: str, byte_limit: int) -> list[str]:
    """Split raw text by the byte length it will have after HTML escaping."""
    if byte_limit <= 0:
        raise ValueError("byte_limit must leave room for wrapper tags")

    chunks: list[str] = []
    current: list[str] = []
    current_bytes = 0
    for ch in text:
        escaped_bytes = len(_escape_text(ch).encode("utf-8"))
        if current and current_bytes + escaped_bytes > byte_limit:
            chunks.append("".join(current))
            current = []
            current_bytes = 0
        current.append(ch)
        current_bytes += escaped_bytes
    if current:
        chunks.append("".join(current))
    return chunks


class _TextExtractor(HTMLParser):
    """Extract visible text from a trusted Rich HTML fragment."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _html_fragment_to_text(fragment: str) -> str:
    parser = _TextExtractor()
    parser.feed(fragment)
    parser.close()
    return "".join(parser.parts)


def _escape_text(value: str) -> str:
    return html.escape(value, quote=False)


def telegramify_rich(
    markdown: str,
    *,
    mode: RichMode = "html",
    is_rtl: bool | None = None,
    skip_entity_detection: bool | None = None,
    latex_escape: bool = False,
) -> list:
    """将 Markdown 转换为可发送的 RichMessage 列表。

    组合流程: richify() → split_rich() → 包装为 RichMessage。
    同步函数，不涉及网络请求。

    @see docs/adr/001-rich-message-pipeline-composition.md
    """
    from telegramify_markdown.content import ContentTrace, RichMessage

    if mode == "html":
        # 直接使用 walk_blocks 获取精确的 block 列表
        blocks = _walk_blocks_from_markdown(markdown, latex_escape=latex_escape)
        chunks = _bin_blocks(
            blocks,
            byte_limit=RICH_BYTE_LIMIT,
            block_limit=RICH_BLOCK_LIMIT,
            is_rtl=is_rtl,
            skip_entity_detection=skip_entity_detection,
            mode="html",
        )
        if not chunks:
            chunks = []
    else:
        # markdown 模式: 先构建再拆分
        payload = richify(
            markdown,
            mode=mode,
            is_rtl=is_rtl,
            skip_entity_detection=skip_entity_detection,
            latex_escape=latex_escape,
        )
        chunks = split_rich(payload)

    return [
        RichMessage(
            rich_message=chunk,
            content_trace=ContentTrace(source_type="rich"),
        )
        for chunk in chunks
    ]
