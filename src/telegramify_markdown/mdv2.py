"""将 (text, list[MessageEntity]) 反向转换为 MarkdownV2 字符串。

用户的中间件 API 不支持 entities 参数时，可用此模块将 convert() 的输出
转为 parse_mode="MarkdownV2" 可直接使用的字符串。

核心算法：扫描线事件排序
1. 构建 UTF-16 offset → Python index 映射
2. 将每个 entity 拆为 open/close 事件，按 Python index 排序
3. 从左到右扫描文本，在事件边界插入 MarkdownV2 标记，分区域转义
4. blockquote 在扫描过程中内联处理（逐行添加 > 前缀），不做后处理
"""

from __future__ import annotations

from telegramify_markdown.entity import MessageEntity

# MarkdownV2 普通文本需要转义的 20 个字符
_MDV2_ESCAPE_CHARS = frozenset("_*[]()~`>#+-=|{}.!\\")

# code/pre 内只需转义的字符
_CODE_ESCAPE_CHARS = frozenset("`\\")

# URL 内只需转义的字符
_URL_ESCAPE_CHARS = frozenset(")\\")


def _escape_markdownv2(text: str) -> str:
    """普通文本区域的 MarkdownV2 转义（20 个特殊字符）。"""
    result = []
    for ch in text:
        if ch in _MDV2_ESCAPE_CHARS:
            result.append("\\")
        result.append(ch)
    return "".join(result)


def _escape_code(text: str) -> str:
    """code/pre 内部的转义（只转义 ` 和 \\）。"""
    result = []
    for ch in text:
        if ch in _CODE_ESCAPE_CHARS:
            result.append("\\")
        result.append(ch)
    return "".join(result)


def _escape_url(url: str) -> str:
    """URL 内部的转义（只转义 ) 和 \\）。"""
    result = []
    for ch in url:
        if ch in _URL_ESCAPE_CHARS:
            result.append("\\")
        result.append(ch)
    return "".join(result)


def _utf16_offset_to_pyindex(text: str) -> dict[int, int]:
    """构建 UTF-16 offset → Python str index 的映射表。

    返回 dict，key 为 UTF-16 offset，value 为对应的 Python index。
    包含 text 末尾的哨兵位置。
    """
    mapping: dict[int, int] = {}
    utf16_pos = 0
    for i, ch in enumerate(text):
        mapping[utf16_pos] = i
        utf16_pos += 2 if ord(ch) > 0xFFFF else 1
    mapping[utf16_pos] = len(text)  # 哨兵：末尾位置
    return mapping


# entity type → (open_tag, close_tag) 的简单标记映射
_SIMPLE_MARKERS: dict[str, tuple[str, str]] = {
    "bold": ("*", "*"),
    "italic": ("_", "_"),
    "underline": ("__", "__"),
    "strikethrough": ("~", "~"),
    "spoiler": ("||", "||"),
}

# 这些 entity type 的内容在 code 转义区域
_CODE_ENTITY_TYPES = frozenset({"code", "pre"})


def entities_to_markdownv2(text: str, entities: list[MessageEntity] | None = None) -> str:
    """将 (text, entities) 转换为 MarkdownV2 格式字符串。

    :param text: 纯文本内容
    :param entities: MessageEntity 列表（UTF-16 offset/length）
    :return: 可直接用于 Telegram parse_mode="MarkdownV2" 的字符串
    """
    if not text:
        return ""
    if not entities:
        return _escape_markdownv2(text)

    utf16_to_py = _utf16_offset_to_pyindex(text)

    # 分离 blockquote 和其他 entity，并将 blockquote 转为 Python index 范围
    bq_ranges: list[tuple[int, int, str]] = []  # (start_py, end_py, type)
    other_entities: list[MessageEntity] = []
    for ent in entities:
        if ent.type in ("blockquote", "expandable_blockquote"):
            start_py = utf16_to_py.get(ent.offset)
            end_py = utf16_to_py.get(ent.offset + ent.length)
            if start_py is not None and end_py is not None:
                bq_ranges.append((start_py, end_py, ent.type))
        else:
            other_entities.append(ent)

    # blockquote 查询辅助函数
    def _bq_at(py_idx: int) -> str | None:
        """返回 py_idx 位置的 blockquote 类型，不在 blockquote 内返回 None。"""
        for s, e, t in bq_ranges:
            if s <= py_idx < e:
                return t
        return None

    def _is_expandable_start(py_idx: int) -> bool:
        for s, _, t in bq_ranges:
            if py_idx == s and t == "expandable_blockquote":
                return True
        return False

    def _is_expandable_end(py_idx: int) -> bool:
        for _, e, t in bq_ranges:
            if py_idx == e and t == "expandable_blockquote":
                return True
        return False

    # 构建扫描线事件
    events: list[tuple[int, int, int, int, MessageEntity]] = []
    for seq, ent in enumerate(other_entities):
        start_utf16 = ent.offset
        end_utf16 = ent.offset + ent.length
        start_py = utf16_to_py.get(start_utf16)
        end_py = utf16_to_py.get(end_utf16)
        if start_py is None or end_py is None:
            continue
        events.append((start_py, 1, -ent.length, seq, ent))    # open
        events.append((end_py, 0, ent.length, -seq, ent))       # close: -seq 实现 LIFO

    events.sort(key=lambda e: (e[0], e[1], e[2], e[3]))

    # 追踪当前活跃的 code/pre entity
    active_code_entities: set[int] = set()

    # 构建结果
    parts: list[str] = []
    prev_py = 0

    # 输出文本第一行的 blockquote 前缀（如果 position 0 在 blockquote 内）
    if bq_ranges:
        if _is_expandable_start(0):
            parts.append("**>")
        elif _bq_at(0) is not None:
            parts.append(">")

    def _emit_segment(segment: str, seg_start_py: int) -> None:
        """输出文本段，在 \\n 后插入 blockquote 前缀。"""
        escape_fn = _escape_code if active_code_entities else _escape_markdownv2
        if not bq_ranges:
            parts.append(escape_fn(segment))
            return
        # 逐行处理，在每个 \n 后检查下一行是否在 blockquote 内
        line_start = 0
        for i, ch in enumerate(segment):
            if ch == "\n":
                parts.append(escape_fn(segment[line_start:i]))
                parts.append("\n")
                next_py = seg_start_py + i + 1
                # 检查下一行的 blockquote 状态
                if _is_expandable_start(next_py):
                    parts.append("**>")
                elif _bq_at(next_py) is not None:
                    parts.append(">")
                line_start = i + 1
        # 输出最后一段（\n 之后的剩余内容）
        if line_start < len(segment):
            parts.append(escape_fn(segment[line_start:]))

    def _emit_tag(tag: str, pos_py: int) -> None:
        """输出标记字符串，处理 tag 中的 \\n（如 pre 的 ```\\n）。

        tag 中的 \\n 后如果对应的原始文本位置在 blockquote 内，也需加 > 前缀。
        """
        if not bq_ranges or "\n" not in tag:
            parts.append(tag)
            return
        # tag 中的 \n 后需要检查 blockquote
        # pos_py 是 tag 对应的原始文本边界位置
        bq = _bq_at(pos_py)
        if bq is None:
            # pos_py 可能恰好在 blockquote 边界外，检查 pos_py-1
            if pos_py > 0:
                bq = _bq_at(pos_py - 1)
        if bq:
            parts.append(tag.replace("\n", "\n>"))
        else:
            parts.append(tag)

    # 扫描线主循环
    event_idx = 0
    while event_idx < len(events):
        pos = events[event_idx][0]

        # 输出 prev_py 到 pos 之间的文本段
        if pos > prev_py:
            _emit_segment(text[prev_py:pos], prev_py)

        # 检查 expandable blockquote 结束标记
        if bq_ranges and _is_expandable_end(pos):
            parts.append("||")

        # 处理该位置的所有事件
        while event_idx < len(events) and events[event_idx][0] == pos:
            _, event_type, _, _, ent = events[event_idx]
            ent_id = id(ent)

            if event_type == 0:
                # close 事件
                active_code_entities.discard(ent_id)
                _emit_tag(_get_close_tag(ent), pos)
            else:
                # open 事件
                if ent.type in _CODE_ENTITY_TYPES:
                    active_code_entities.add(ent_id)
                _emit_tag(_get_open_tag(ent), pos)

            event_idx += 1

        prev_py = pos

    # 输出剩余文本
    if prev_py < len(text):
        _emit_segment(text[prev_py:], prev_py)

    # 检查 expandable blockquote 在文本末尾结束
    if bq_ranges and _is_expandable_end(len(text)):
        parts.append("||")

    return "".join(parts)


def _get_open_tag(ent: MessageEntity) -> str:
    """获取 entity 的开始标记。"""
    if ent.type in _SIMPLE_MARKERS:
        return _SIMPLE_MARKERS[ent.type][0]
    if ent.type == "code":
        return "`"
    if ent.type == "pre":
        lang = ent.language or ""
        if lang:
            return f"```{lang}\n"
        return "```\n"
    if ent.type == "text_link":
        return "["
    if ent.type == "custom_emoji":
        return "!["
    if ent.type == "text_mention":
        return "["
    return ""


def _get_close_tag(ent: MessageEntity) -> str:
    """获取 entity 的结束标记。"""
    if ent.type in _SIMPLE_MARKERS:
        return _SIMPLE_MARKERS[ent.type][1]
    if ent.type == "code":
        return "`"
    if ent.type == "pre":
        return "\n```"
    if ent.type == "text_link":
        url = _escape_url(ent.url or "")
        return f"]({url})"
    if ent.type == "custom_emoji":
        emoji_id = ent.custom_emoji_id or ""
        return f"](tg://emoji?id={emoji_id})"
    if ent.type == "text_mention":
        return "]"
    return ""
