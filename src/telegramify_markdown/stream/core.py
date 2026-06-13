"""Protocol-agnostic throttled streaming buffer.

StreamCore is the mechanism layer: it accumulates tokens into a buffer, renders
on a throttled schedule via an injected callable, emits snapshots via an injected
callback, and finalizes via an injected callback. It knows nothing about Telegram,
Markdown, or Rich HTML.

@see docs/adr/002-streaming-draft-support.md §StreamCore
"""

from __future__ import annotations

import asyncio
import enum
import logging
from typing import AsyncIterator, Awaitable, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_BUFFER_WARNING_BYTES = 512 * 1024  # 512KB


class _State(enum.Enum):
    IDLE = "idle"
    ACTIVE = "active"
    DONE = "done"


class StreamCore(Generic[T]):
    """Protocol-agnostic throttled streaming buffer.

    Generic over payload type T. The core only knows about:
    - buffer (str, append-only)
    - render: Callable[[str], T]
    - emit: Callable[[T], Awaitable[None]]
    - finalize: Callable[[T], Awaitable[None]]
    """

    def __init__(
        self,
        render: Callable[[str], T],
        emit: Callable[[T], Awaitable[None]],
        finalize: Callable[[T], Awaitable[None]],
        interval: float = 0.3,
        keepalive_timeout: float = 25.0,
        on_cancel: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        if interval <= 0:
            raise ValueError(f"interval must be positive, got {interval}")

        self._render = render
        self._emit = emit
        self._finalize = finalize
        self._interval = interval
        self._keepalive_timeout = keepalive_timeout
        self._on_cancel = on_cancel

        self._buffer = ""
        self._dirty = False
        self._sending = False
        self._state = _State.IDLE
        self._consecutive_failures = 0
        self._degraded = False

        self._timer_handle: asyncio.TimerHandle | None = None
        self._keepalive_handle: asyncio.TimerHandle | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._buffer_warned = False
        self._keepalive_expired = False

    @property
    def buffer(self) -> str:
        """当前累积的 buffer 内容（只读）。"""
        return self._buffer

    @property
    def state(self) -> str:
        """当前状态：idle / active / done。"""
        return self._state.value

    async def __aenter__(self) -> "StreamCore[T]":
        self._loop = asyncio.get_running_loop()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._state == _State.DONE:
            return False
        if exc_type is asyncio.CancelledError:
            await self.cancel()
            return True  # suppress CancelledError
        if exc_type is None:
            await self.finish()
        else:
            # 异常退出：尝试 cancel 而非 finalize
            await self.cancel()
        return False

    def feed(self, token: str) -> None:
        """追加 token 到 buffer。"""
        if self._state == _State.DONE:
            raise RuntimeError("Cannot feed after stream is done")

        self._buffer += token
        self._dirty = True

        # 检查 buffer 大小告警
        if not self._buffer_warned and len(self._buffer.encode("utf-8")) > _BUFFER_WARNING_BYTES:
            logger.warning(
                "Stream buffer exceeds 512KB (%d bytes). "
                "Did you forget to call finish()?",
                len(self._buffer.encode("utf-8")),
            )
            self._buffer_warned = True

        if self._state == _State.IDLE:
            self._state = _State.ACTIVE
            self._schedule_tick()

    async def consume(self, tokens: AsyncIterator[str]) -> None:
        """从 async iterator 消费 tokens，结束后自动 finish。

        如果 iterator 抛出 CancelledError，调用 cancel()。
        """
        try:
            async for token in tokens:
                self.feed(token)
        except asyncio.CancelledError:
            await self.cancel()
            return
        await self.finish()

    async def finish(self) -> None:
        """终止流并发送最终消息。"""
        if self._state == _State.DONE:
            return

        self._cancel_timers()

        # 等待飞行中的 emit 完成
        while self._sending:
            await asyncio.sleep(0.01)

        self._state = _State.DONE

        if self._buffer:
            payload = self._render(self._buffer)
            await self._finalize(payload)

    async def cancel(self) -> None:
        """取消流，不发送最终消息。"""
        if self._state == _State.DONE:
            return

        self._cancel_timers()
        self._state = _State.DONE

        if self._on_cancel:
            await self._on_cancel()

    def _schedule_tick(self) -> None:
        """安排下一次 tick。"""
        if self._state == _State.DONE or self._loop is None:
            return
        self._timer_handle = self._loop.call_later(
            self._interval, self._tick_sync
        )

    def _tick_sync(self) -> None:
        """Timer callback（同步入口），创建 async task。"""
        if self._state == _State.DONE:
            return
        if self._loop is not None:
            self._loop.create_task(self._tick())

    async def _tick(self) -> None:
        """执行一次节流 emit。"""
        if self._state == _State.DONE:
            return
        if self._sending:
            # 上一次还在发送中，跳过本次 tick，保持 dirty
            self._schedule_tick()
            return
        if not self._dirty and not self._is_keepalive_due():
            self._schedule_tick()
            return

        if self._degraded:
            # 降级模式：不再 emit，但继续 schedule 以维持 keepalive 计时
            self._dirty = False
            self._schedule_tick()
            return

        self._sending = True
        try:
            payload = self._render(self._buffer)
            await self._emit(payload)
            self._dirty = False
            self._consecutive_failures = 0
            self._reset_keepalive()
        except Exception as e:
            self._consecutive_failures += 1
            logger.warning("emit failed (%d/3): %s", self._consecutive_failures, e)
            if self._consecutive_failures >= 3:
                logger.warning("Entering degraded mode: emit disabled")
                self._degraded = True
        finally:
            self._sending = False

        self._schedule_tick()

    def _is_keepalive_due(self) -> bool:
        """keepalive 是否应当触发（通过 keepalive handle 是否已过期来判断）。"""
        # keepalive 通过独立 handle 标记
        return self._keepalive_expired

    def _reset_keepalive(self) -> None:
        """重置 keepalive 计时器。"""
        if self._keepalive_handle is not None:
            self._keepalive_handle.cancel()
        self._keepalive_expired = False
        if self._loop is not None and self._state != _State.DONE:
            self._keepalive_handle = self._loop.call_later(
                self._keepalive_timeout, self._mark_keepalive_expired
            )

    def _mark_keepalive_expired(self) -> None:
        """标记 keepalive 已过期，下次 tick 将强制发送。"""
        self._keepalive_expired = True

    def _cancel_timers(self) -> None:
        """取消所有 pending timer。"""
        if self._timer_handle is not None:
            self._timer_handle.cancel()
            self._timer_handle = None
        if self._keepalive_handle is not None:
            self._keepalive_handle.cancel()
            self._keepalive_handle = None
