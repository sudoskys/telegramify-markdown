"""DraftStream — strategy facade for Telegram sendMessageDraft / sendRichMessageDraft.

@see docs/adr/002-streaming-draft-support.md §DraftStream
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from typing import Awaitable, Callable, Literal, Optional

from telegramify_markdown.stream.core import StreamCore

logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class EntityDraftPayload:
    """Entity mode draft payload — matches sendMessageDraft params."""

    text: str
    entities: list
    draft_id: int


@dataclasses.dataclass(slots=True)
class RichDraftPayload:
    """Rich mode draft payload — matches sendRichMessageDraft params."""

    rich_message: object  # InputRichMessage
    draft_id: int


@dataclasses.dataclass(slots=True)
class EntityFinalPayload:
    """Entity mode final payload — matches sendMessage params."""

    text: str
    entities: list


@dataclasses.dataclass(slots=True)
class RichFinalPayload:
    """Rich mode final payload — matches sendRichMessage params."""

    rich_message: object  # InputRichMessage


class DraftStream:
    """Strategy facade for streaming via Telegram draft API.

    Assembles StreamCore with:
    - render = richify or convert (based on mode)
    - emit = send_draft callback (with thinking delay and sliding window)
    - finalize = send_final callback
    - on_cancel = empty draft sender (if cancel_clears_draft)
    """

    def __init__(
        self,
        send_draft: Callable[[EntityDraftPayload | RichDraftPayload], Awaitable[None]],
        send_final: Callable[[EntityFinalPayload | RichFinalPayload], Awaitable[None]],
        mode: Literal["rich", "entity"] = "rich",
        draft_id: Optional[int] = None,
        interval: float = 0.3,
        thinking_delay: Optional[float] = 0.5,
        keepalive_timeout: float = 25.0,
        cancel_clears_draft: bool = True,
    ) -> None:
        if mode not in ("rich", "entity"):
            raise ValueError(f"mode must be 'rich' or 'entity', got {mode!r}")

        self._send_draft = send_draft
        self._send_final = send_final
        self._mode = mode
        self._draft_id = draft_id if draft_id is not None else (hash(id(self)) & 0x7FFFFFFF | 1)
        self._thinking_delay = thinking_delay
        self._cancel_clears_draft = cancel_clears_draft

        # thinking 状态
        self._first_emit = True
        self._thinking_suppressed = False
        self._thinking_timer: asyncio.TimerHandle | None = None

        # 构建 on_cancel
        on_cancel = self._do_cancel_clear if cancel_clears_draft else None

        self._core = StreamCore(
            render=self._render,
            emit=self._emit,
            finalize=self._finalize_impl,
            interval=interval,
            keepalive_timeout=keepalive_timeout,
            on_cancel=on_cancel,
        )

    @property
    def buffer(self) -> str:
        return self._core.buffer

    @property
    def state(self) -> str:
        return self._core.state

    async def __aenter__(self) -> "DraftStream":
        await self._core.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self._core.__aexit__(exc_type, exc_val, exc_tb)

    def feed(self, token: str) -> None:
        self._core.feed(token)

    async def consume(self, tokens) -> None:
        await self._core.consume(tokens)

    async def finish(self) -> None:
        self._cancel_thinking_timer()
        await self._core.finish()

    async def cancel(self) -> None:
        self._cancel_thinking_timer()
        await self._core.cancel()

    def _render(self, buffer: str):
        """渲染 buffer 为 payload（带 sliding window 截断）。"""
        if self._mode == "entity":
            return self._render_entity(buffer)
        else:
            return self._render_rich(buffer)

    def _render_entity(self, buffer: str):
        """Entity 模式渲染：convert() + 尾部 4096 字符截断。"""
        from telegramify_markdown.converter import convert

        text, entities = convert(buffer)

        # sliding window: 只取尾部 4096 字符
        # draft 是临时显示，截断后 entities 偏移会失效，直接丢弃
        if len(text) > 4096:
            text = text[-4096:]
            entities = []

        return EntityDraftPayload(
            text=text,
            entities=entities,
            draft_id=self._draft_id,
        )

    def _render_rich(self, buffer: str):
        """Rich 模式渲染：richify() + 尾部 32KB 截断。"""
        from telegramify_markdown.rich import richify, RICH_BYTE_LIMIT

        rich_msg = richify(buffer)

        # sliding window: 如果超出字节限制，截断 HTML
        if rich_msg.html is not None:
            encoded = rich_msg.html.encode("utf-8")
            if len(encoded) > RICH_BYTE_LIMIT:
                # 从尾部取 RICH_BYTE_LIMIT 字节（在 tag 边界处可能不完美，
                # 但 draft 是临时的，Telegram 会拒绝无效 HTML 并静默降级）
                truncated = encoded[-RICH_BYTE_LIMIT:]
                # 尝试在第一个 '<' 处对齐
                idx = truncated.find(b"<")
                if idx > 0:
                    truncated = truncated[idx:]
                rich_msg = type(rich_msg)(html=truncated.decode("utf-8", errors="ignore"))

        return RichDraftPayload(
            rich_message=rich_msg,
            draft_id=self._draft_id,
        )

    async def _emit(self, payload) -> None:
        """Emit 包装：处理 thinking delay。"""
        if self._first_emit:
            self._first_emit = False
            if self._thinking_delay and self._thinking_delay > 0:
                # 发送空 payload 触发 "Thinking..." 指示器
                await self._send_thinking()
                # 标记抑制后续 emit 直到 delay 过期
                self._thinking_suppressed = True
                loop = asyncio.get_running_loop()
                self._thinking_timer = loop.call_later(
                    self._thinking_delay, self._end_thinking_suppression
                )
                return  # 不发送实际内容

        if self._thinking_suppressed:
            return  # 仍在 thinking delay 期间，跳过

        await self._send_draft(payload)

    async def _send_thinking(self) -> None:
        """发送 thinking 指示器。

        Entity 模式：空 text 触发 Telegram "Thinking…" 显示。
        Rich 模式：Telegram 不接受空 HTML，使用 "…" 占位符。
        """
        if self._mode == "entity":
            payload = EntityDraftPayload(text="", entities=[], draft_id=self._draft_id)
        else:
            from telegramify_markdown.rich import InputRichMessage
            payload = RichDraftPayload(
                rich_message=InputRichMessage(html="<p>\u2026</p>"),
                draft_id=self._draft_id,
            )
        await self._send_draft(payload)

    def _end_thinking_suppression(self) -> None:
        """Thinking delay 结束，标记 buffer 为 dirty 以触发下次 emit。"""
        self._thinking_suppressed = False
        # 让 core 在下一个 tick 重新发送（因为 thinking 期间 emit 被跳过但 dirty 已清除）
        self._core._dirty = True

    def _cancel_thinking_timer(self) -> None:
        if self._thinking_timer is not None:
            self._thinking_timer.cancel()
            self._thinking_timer = None
        self._thinking_suppressed = False

    async def _finalize_impl(self, payload) -> None:
        """Finalize：渲染完整 buffer 并调用 send_final。

        注意：这里只调用 convert/richify 产生单条消息 payload。
        完整管线（telegramify/telegramify_rich）会返回 list[Text|File|Photo]，
        涉及多条消息的发送编排，不属于 stream 层职责——由调用者自行处理。
        """
        buffer = self._core.buffer
        if self._mode == "entity":
            from telegramify_markdown.converter import convert
            text, entities = convert(buffer)
            final = EntityFinalPayload(text=text, entities=entities)
        else:
            from telegramify_markdown.rich import richify
            rich_msg = richify(buffer)
            final = RichFinalPayload(rich_message=rich_msg)
        await self._send_final(final)

    async def _do_cancel_clear(self) -> None:
        """取消时发送最小 draft 清除指示器。

        Entity 模式用空 text，Rich 模式用 "…" 占位（Telegram 不接受空 HTML）。
        """
        if self._mode == "entity":
            payload = EntityDraftPayload(text="", entities=[], draft_id=self._draft_id)
        else:
            from telegramify_markdown.rich import InputRichMessage
            payload = RichDraftPayload(
                rich_message=InputRichMessage(html="<p>\u2026</p>"),
                draft_id=self._draft_id,
            )
        try:
            await self._send_draft(payload)
        except Exception:
            pass  # best-effort
