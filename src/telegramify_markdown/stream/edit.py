"""EditStream — strategy facade for group-chat streaming via editMessageText.

For group/channel chats where draft API is unavailable: sends the first message
via send_message, then updates it with edit_message on each throttle tick.

@see docs/adr/002-streaming-draft-support.md §EditStream
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable, Literal, Optional

from telegramify_markdown.stream.core import StreamCore
from telegramify_markdown.stream.draft import (
    EntityFinalPayload,
    RichFinalPayload,
)

logger = logging.getLogger(__name__)


class EditStream:
    """Strategy facade for streaming via editMessageText.

    Assembles StreamCore with:
    - render = richify or convert (based on mode)
    - emit = edit_message(message_id, payload) after first send
    - finalize = one last edit_message with complete content
    """

    def __init__(
        self,
        send_message: Callable,  # async (payload) -> message_id
        edit_message: Callable,  # async (message_id, payload) -> None
        mode: Literal["rich", "entity"] = "rich",
        interval: float = 1.0,
        keepalive_timeout: float = 25.0,
    ) -> None:
        if interval < 1.0:
            raise ValueError(
                f"EditStream interval must be >= 1.0s (Telegram edit rate limit), got {interval}"
            )
        if mode not in ("rich", "entity"):
            raise ValueError(f"mode must be 'rich' or 'entity', got {mode!r}")

        self._send_message = send_message
        self._edit_message = edit_message
        self._mode = mode
        self._message_id: Optional[int] = None

        self._core = StreamCore(
            render=self._render,
            emit=self._emit,
            finalize=self._finalize_impl,
            interval=interval,
            keepalive_timeout=keepalive_timeout,
        )

    @property
    def buffer(self) -> str:
        return self._core.buffer

    @property
    def state(self) -> str:
        return self._core.state

    @property
    def message_id(self) -> Optional[int]:
        """已发送消息的 ID（首次 emit 后可用）。"""
        return self._message_id

    async def __aenter__(self) -> "EditStream":
        await self._core.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self._core.__aexit__(exc_type, exc_val, exc_tb)

    def feed(self, token: str) -> None:
        self._core.feed(token)

    async def consume(self, tokens) -> None:
        await self._core.consume(tokens)

    async def finish(self) -> None:
        await self._core.finish()

    async def cancel(self) -> None:
        await self._core.cancel()

    def _render(self, buffer: str):
        """渲染 buffer 为 payload。"""
        if self._mode == "entity":
            return self._render_entity(buffer)
        else:
            return self._render_rich(buffer)

    def _render_entity(self, buffer: str):
        """Entity 模式渲染。"""
        from telegramify_markdown.converter import convert

        text, entities = convert(buffer)
        return EntityFinalPayload(text=text, entities=entities)

    def _render_rich(self, buffer: str):
        """Rich 模式渲染。"""
        from telegramify_markdown.rich import richify

        rich_msg = richify(buffer)
        return RichFinalPayload(rich_message=rich_msg)

    async def _emit(self, payload) -> None:
        """First emit sends message; subsequent edits it."""
        if self._message_id is None:
            # 首次：发送消息，获取 message_id
            self._message_id = await self._send_message(payload)
        else:
            # 后续：编辑消息
            await self._edit_message(self._message_id, payload)

    async def _finalize_impl(self, payload) -> None:
        """Finalize：用完整内容执行最后一次编辑。

        只调用 convert/richify 产生单条消息。完整管线（拆分、Mermaid）
        不在 stream 层处理——由调用者编排。
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

        if self._message_id is None:
            # 如果从未 emit 过（可能全部在 degraded mode），直接 send
            self._message_id = await self._send_message(final)
        else:
            await self._edit_message(self._message_id, final)
