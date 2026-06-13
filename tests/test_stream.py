"""Tests for the streaming module — all 8 ADR-002 verification flags.

Flag 1: Re-parse produces valid output on incomplete Markdown
Flag 2: Throttle respects minimum interval
Flag 3: Keepalive prevents expiry
Flag 4: Finalization sends complete message
Flag 5: EditStream enforces ≥1s interval
Flag 6: Degraded mode after 3 failures
Flag 7: Cancellation does not send final message
Flag 8: Concurrent send guard prevents overlapping emit calls

@see docs/adr/002-streaming-draft-support.md §Verification
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from telegramify_markdown.stream.core import StreamCore
from telegramify_markdown.stream.edit import EditStream


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def trivial_render(buf: str) -> str:
    """简单 render：返回 buffer 本身。"""
    return buf


def upper_render(buf: str) -> str:
    """render = str.upper，方便验证 payload 来自 render。"""
    return buf.upper()


# ---------------------------------------------------------------------------
# Flag 1: Re-parse produces valid output on incomplete Markdown
# ---------------------------------------------------------------------------


class TestFlag1IncompleteParsing:
    """StreamCore should produce valid output even with incomplete Markdown.

    This tests that the render callable (which in real usage calls convert/richify)
    is always invoked on the full buffer — even when content is mid-syntax.
    """

    @pytest.mark.asyncio
    async def test_incomplete_fence(self):
        """Unclosed code fence should still produce output."""
        emitted = []

        async def emit(payload):
            emitted.append(payload)

        async def finalize(payload):
            pass

        core = StreamCore(render=trivial_render, emit=emit, finalize=finalize, interval=0.05)
        async with core:
            # Feed incomplete markdown with CJK and emoji
            core.feed("```python\ndef hello():\n    print('你好世界 🌍')")
            # Let at least one tick fire
            await asyncio.sleep(0.1)

        # At least one emit should have happened with the incomplete markdown
        assert len(emitted) >= 1
        assert "你好世界 🌍" in emitted[0]

    @pytest.mark.asyncio
    async def test_incomplete_emphasis(self):
        """Unclosed bold/italic should still produce output."""
        emitted = []

        async def emit(payload):
            emitted.append(payload)

        async def finalize(payload):
            pass

        core = StreamCore(render=trivial_render, emit=emit, finalize=finalize, interval=0.05)
        async with core:
            core.feed("**これは太字で")
            await asyncio.sleep(0.1)

        assert len(emitted) >= 1
        assert "これは太字で" in emitted[0]

    @pytest.mark.asyncio
    async def test_emoji_and_cjk_in_buffer(self):
        """Buffer with mixed emoji/CJK/ASCII renders correctly."""
        emitted = []

        async def emit(payload):
            emitted.append(payload)

        async def finalize(payload):
            pass

        core = StreamCore(render=upper_render, emit=emit, finalize=finalize, interval=0.05)
        async with core:
            core.feed("Hello 世界 🎉 テスト")
            await asyncio.sleep(0.1)

        assert len(emitted) >= 1
        # upper_render uppercases ASCII only
        assert "HELLO" in emitted[0]
        assert "世界" in emitted[0]
        assert "🎉" in emitted[0]


# ---------------------------------------------------------------------------
# Flag 2: Throttle respects minimum interval
# ---------------------------------------------------------------------------


class TestFlag2Throttle:
    """Throttle should not emit more frequently than interval."""

    @pytest.mark.asyncio
    async def test_throttle_interval(self):
        """Emits should be spaced at least `interval` apart."""
        emit_times = []

        async def emit(payload):
            emit_times.append(asyncio.get_event_loop().time())

        async def finalize(payload):
            pass

        interval = 0.15
        core = StreamCore(
            render=trivial_render, emit=emit, finalize=finalize, interval=interval
        )
        async with core:
            # Feed multiple tokens rapidly
            for i in range(20):
                core.feed(f"token{i} ")
                await asyncio.sleep(0.02)  # 20 tokens * 20ms = 400ms total

        # Should have ~2-3 emits in 400ms with 150ms interval (not 20)
        assert len(emit_times) >= 2
        assert len(emit_times) <= 6  # generous upper bound

        # Verify spacing: consecutive emit times are >= interval apart
        for i in range(1, len(emit_times)):
            gap = emit_times[i] - emit_times[i - 1]
            # Allow 20ms tolerance for async scheduling
            assert gap >= interval - 0.02, f"Gap {gap:.3f}s < interval {interval}s"

    @pytest.mark.asyncio
    async def test_burst_absorption(self):
        """Multiple tokens in one tick interval produce only one emit."""
        emit_count = 0

        async def emit(payload):
            nonlocal emit_count
            emit_count += 1

        async def finalize(payload):
            pass

        core = StreamCore(
            render=trivial_render, emit=emit, finalize=finalize, interval=0.2
        )
        async with core:
            # Feed 10 tokens instantly
            for i in range(10):
                core.feed(f"t{i}")
            # Wait for exactly one tick
            await asyncio.sleep(0.25)

        # Should have emitted exactly once (one tick)
        assert emit_count == 1


# ---------------------------------------------------------------------------
# Flag 3: Keepalive prevents expiry
# ---------------------------------------------------------------------------


class TestFlag3Keepalive:
    """Keepalive should fire when no tokens arrive within timeout."""

    @pytest.mark.asyncio
    async def test_keepalive_fires(self):
        """After keepalive_timeout with no new tokens, emit is called again."""
        emitted = []

        async def emit(payload):
            emitted.append(("emit", asyncio.get_event_loop().time()))

        async def finalize(payload):
            pass

        # 使用极短的 keepalive_timeout 进行测试
        core = StreamCore(
            render=trivial_render,
            emit=emit,
            finalize=finalize,
            interval=0.05,
            keepalive_timeout=0.2,
        )
        async with core:
            # Feed once, then stop feeding
            core.feed("initial content")
            # Wait for first emit
            await asyncio.sleep(0.1)
            first_count = len(emitted)
            assert first_count >= 1

            # Now wait longer than keepalive_timeout without feeding
            await asyncio.sleep(0.35)

        # Should have received at least one more emit from keepalive
        assert len(emitted) > first_count


# ---------------------------------------------------------------------------
# Flag 4: Finalization sends complete message
# ---------------------------------------------------------------------------


class TestFlag4Finalization:
    """finish() should call finalize with the complete rendered buffer."""

    @pytest.mark.asyncio
    async def test_finalize_called_with_full_buffer(self):
        """finalize receives the entire accumulated buffer."""
        finalized = []

        async def emit(payload):
            pass

        async def finalize(payload):
            finalized.append(payload)

        core = StreamCore(
            render=upper_render, emit=emit, finalize=finalize, interval=0.05
        )
        async with core:
            core.feed("hello ")
            core.feed("world")

        # __aexit__ calls finish(), which calls finalize
        assert len(finalized) == 1
        assert finalized[0] == "HELLO WORLD"

    @pytest.mark.asyncio
    async def test_finalize_after_many_tokens(self):
        """Finalization runs the full pipeline regardless of intermediate emit state."""
        emitted = []
        finalized = []

        async def emit(payload):
            emitted.append(payload)

        async def finalize(payload):
            finalized.append(payload)

        core = StreamCore(
            render=trivial_render, emit=emit, finalize=finalize, interval=0.05
        )
        async with core:
            for i in range(50):
                core.feed(f"token{i} ")
            await asyncio.sleep(0.15)

        expected = "".join(f"token{i} " for i in range(50))
        assert finalized[0] == expected


# ---------------------------------------------------------------------------
# Flag 5: EditStream enforces ≥1s interval
# ---------------------------------------------------------------------------


class TestFlag5EditStreamInterval:
    """EditStream should reject interval < 1.0."""

    def test_interval_too_low_raises(self):
        """Interval < 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="must be >= 1.0s"):
            EditStream(
                send_message=AsyncMock(return_value=123),
                edit_message=AsyncMock(),
                interval=0.5,
            )

    def test_interval_at_minimum_ok(self):
        """Interval = 1.0 is accepted."""
        stream = EditStream(
            send_message=AsyncMock(return_value=123),
            edit_message=AsyncMock(),
            interval=1.0,
        )
        assert stream is not None

    def test_interval_above_minimum_ok(self):
        """Interval > 1.0 is accepted."""
        stream = EditStream(
            send_message=AsyncMock(return_value=123),
            edit_message=AsyncMock(),
            interval=2.5,
        )
        assert stream is not None


# ---------------------------------------------------------------------------
# Flag 6: Degraded mode after 3 failures
# ---------------------------------------------------------------------------


class TestFlag6DegradedMode:
    """After 3 consecutive emit failures, enter degraded mode."""

    @pytest.mark.asyncio
    async def test_degraded_after_three_failures(self):
        """After 3 emit failures, no more emit calls but finalize still works."""
        emit_count = 0
        finalized = []

        async def failing_emit(payload):
            nonlocal emit_count
            emit_count += 1
            raise RuntimeError("network error")

        async def finalize(payload):
            finalized.append(payload)

        core = StreamCore(
            render=trivial_render,
            emit=failing_emit,
            finalize=finalize,
            interval=0.05,
        )
        async with core:
            core.feed("content")
            # Wait enough ticks for 3+ failures
            await asyncio.sleep(0.25)

            # Feed more content
            core.feed(" more")
            await asyncio.sleep(0.15)

        # emit was called exactly 3 times (then degraded mode stops calling)
        assert emit_count == 3

        # But finalize still fires with complete content
        assert len(finalized) == 1
        assert finalized[0] == "content more"


# ---------------------------------------------------------------------------
# Flag 7: Cancellation does not send final message
# ---------------------------------------------------------------------------


class TestFlag7Cancellation:
    """cancel() should NOT call finalize."""

    @pytest.mark.asyncio
    async def test_cancel_skips_finalize(self):
        """Cancellation invokes on_cancel but not finalize."""
        finalized = []
        cancelled = []

        async def emit(payload):
            pass

        async def finalize(payload):
            finalized.append(payload)

        async def on_cancel():
            cancelled.append(True)

        core = StreamCore(
            render=trivial_render,
            emit=emit,
            finalize=finalize,
            interval=0.05,
            on_cancel=on_cancel,
        )
        async with core:
            core.feed("some content")
            await asyncio.sleep(0.1)
            await core.cancel()

        assert len(finalized) == 0
        assert len(cancelled) == 1

    @pytest.mark.asyncio
    async def test_cancel_via_exception_in_context_manager(self):
        """Exception in context triggers cancel, not finalize."""
        finalized = []
        cancelled = []

        async def emit(payload):
            pass

        async def finalize(payload):
            finalized.append(payload)

        async def on_cancel():
            cancelled.append(True)

        core = StreamCore(
            render=trivial_render,
            emit=emit,
            finalize=finalize,
            interval=0.05,
            on_cancel=on_cancel,
        )
        with pytest.raises(ValueError):
            async with core:
                core.feed("data")
                raise ValueError("simulated error")

        assert len(finalized) == 0
        assert len(cancelled) == 1


# ---------------------------------------------------------------------------
# Flag 8: Concurrent send guard prevents overlapping emit calls
# ---------------------------------------------------------------------------


class TestFlag8ConcurrentGuard:
    """_sending guard should prevent overlapping emit calls."""

    @pytest.mark.asyncio
    async def test_no_overlapping_emits(self):
        """While one emit is in flight, subsequent ticks should skip."""
        concurrent_count = 0
        max_concurrent = 0
        emitted = []

        async def slow_emit(payload):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            emitted.append(payload)
            await asyncio.sleep(0.1)  # simulate slow network
            concurrent_count -= 1

        async def finalize(payload):
            pass

        core = StreamCore(
            render=trivial_render,
            emit=slow_emit,
            finalize=finalize,
            interval=0.03,  # ticks faster than emit completes
        )
        async with core:
            for i in range(10):
                core.feed(f"tok{i} ")
                await asyncio.sleep(0.02)

        # The _sending guard ensures at most 1 concurrent emit
        assert max_concurrent == 1
        # Despite 10 tokens, not 10 emits due to throttle + guard
        assert len(emitted) >= 1
        assert len(emitted) < 10


# ---------------------------------------------------------------------------
# Integration: EditStream send then edit pattern
# ---------------------------------------------------------------------------


class TestEditStreamIntegration:
    """EditStream sends first, then edits."""

    @pytest.mark.asyncio
    async def test_send_then_edit(self):
        """First emit calls send_message; subsequent call edit_message."""
        sent = []
        edited = []

        async def send_message(payload):
            sent.append(payload)
            return 42  # message_id

        async def edit_message(msg_id, payload):
            edited.append((msg_id, payload))

        # Patch convert to avoid needing pyromark for entity mode
        def mock_convert(buf):
            return buf, []

        with patch(
            "telegramify_markdown.stream.edit.EditStream._render",
            side_effect=lambda self, buf: buf,
        ):
            stream = EditStream(
                send_message=send_message,
                edit_message=edit_message,
                mode="entity",
                interval=1.0,
            )
            # 直接测试 _emit 逻辑
            await stream._emit("first payload")
            assert stream.message_id == 42
            assert len(sent) == 1

            await stream._emit("second payload")
            assert len(edited) == 1
            assert edited[0] == (42, "second payload")


# ---------------------------------------------------------------------------
# DraftStream strategy-layer tests
# ---------------------------------------------------------------------------


class TestDraftStreamThinkingDelay:
    """DraftStream thinking delay: first emit sends empty payload, suppresses
    subsequent emits until delay expires, then resumes normal emit."""

    @pytest.mark.asyncio
    async def test_thinking_delay_sends_empty_first(self):
        """First emit should send an empty draft (thinking indicator)."""
        from telegramify_markdown.stream.draft import DraftStream, EntityDraftPayload

        drafts_sent = []

        async def send_draft(payload):
            drafts_sent.append(payload)

        async def send_final(payload):
            pass

        # Use entity mode with a mock convert that avoids pyromark
        with patch("telegramify_markdown.stream.draft.DraftStream._render_entity") as mock_render:
            mock_render.return_value = EntityDraftPayload(text="hello", entities=[], draft_id=1)

            stream = DraftStream(
                send_draft=send_draft,
                send_final=send_final,
                mode="entity",
                interval=0.05,
                thinking_delay=0.2,
            )
            async with stream:
                stream.feed("hello")
                # Wait for first tick
                await asyncio.sleep(0.1)

                # First emit should be the thinking (empty) payload
                assert len(drafts_sent) >= 1
                first = drafts_sent[0]
                assert isinstance(first, EntityDraftPayload)
                assert first.text == ""

                # During thinking_delay, no real content emitted
                real_drafts = [d for d in drafts_sent if d.text != ""]
                assert len(real_drafts) == 0

                # Wait for thinking delay to expire + another tick
                await asyncio.sleep(0.25)

            # After delay, real content should have been emitted
            real_drafts = [d for d in drafts_sent if d.text != ""]
            assert len(real_drafts) >= 1

    @pytest.mark.asyncio
    async def test_no_thinking_delay(self):
        """With thinking_delay=None, first emit sends content immediately."""
        from telegramify_markdown.stream.draft import DraftStream, EntityDraftPayload

        drafts_sent = []

        async def send_draft(payload):
            drafts_sent.append(payload)

        async def send_final(payload):
            pass

        with patch("telegramify_markdown.stream.draft.DraftStream._render_entity") as mock_render:
            mock_render.return_value = EntityDraftPayload(text="content", entities=[], draft_id=1)

            stream = DraftStream(
                send_draft=send_draft,
                send_final=send_final,
                mode="entity",
                interval=0.05,
                thinking_delay=None,
            )
            async with stream:
                stream.feed("content")
                await asyncio.sleep(0.1)

            # No empty "thinking" payload — first draft has content
            assert len(drafts_sent) >= 1
            assert all(d.text == "content" for d in drafts_sent)


class TestDraftStreamCancelClearsDraft:
    """cancel_clears_draft sends empty draft on cancel."""

    @pytest.mark.asyncio
    async def test_cancel_sends_empty_draft(self):
        """When cancel_clears_draft=True, cancel sends empty payload."""
        from telegramify_markdown.stream.draft import DraftStream, EntityDraftPayload

        drafts_sent = []

        async def send_draft(payload):
            drafts_sent.append(payload)

        async def send_final(payload):
            pass

        with patch("telegramify_markdown.stream.draft.DraftStream._render_entity") as mock_render:
            mock_render.return_value = EntityDraftPayload(text="hi", entities=[], draft_id=1)

            stream = DraftStream(
                send_draft=send_draft,
                send_final=send_final,
                mode="entity",
                interval=0.05,
                thinking_delay=None,
                cancel_clears_draft=True,
            )
            async with stream:
                stream.feed("hi")
                await asyncio.sleep(0.1)
                await stream.cancel()

        # Last draft sent should be the empty clear payload
        clear_payloads = [d for d in drafts_sent if d.text == "" and d.entities == []]
        assert len(clear_payloads) >= 1

    @pytest.mark.asyncio
    async def test_cancel_no_clear_when_disabled(self):
        """When cancel_clears_draft=False, cancel does NOT send empty payload."""
        from telegramify_markdown.stream.draft import DraftStream, EntityDraftPayload

        drafts_sent = []

        async def send_draft(payload):
            drafts_sent.append(payload)

        async def send_final(payload):
            pass

        with patch("telegramify_markdown.stream.draft.DraftStream._render_entity") as mock_render:
            mock_render.return_value = EntityDraftPayload(text="hi", entities=[], draft_id=1)

            stream = DraftStream(
                send_draft=send_draft,
                send_final=send_final,
                mode="entity",
                interval=0.05,
                thinking_delay=None,
                cancel_clears_draft=False,
            )
            async with stream:
                stream.feed("hi")
                await asyncio.sleep(0.1)
                await stream.cancel()

        # No empty clear payload after the content drafts
        # (there may still be content emits before cancel)
        drafts_after_content = drafts_sent[len([d for d in drafts_sent if d.text == "hi"]):]
        empty_clears = [d for d in drafts_after_content if d.text == ""]
        assert len(empty_clears) == 0


class TestDraftStreamSlidingWindow:
    """Entity sliding window truncates to 4096 chars."""

    def test_entity_truncation(self):
        """Text longer than 4096 is truncated to trailing 4096 chars."""
        from telegramify_markdown.stream.draft import DraftStream, EntityDraftPayload

        # Build a long text and mock convert to return it
        long_text = "A" * 5000
        entities = [{"offset": 0, "length": 10, "type": "bold"}]

        with patch("telegramify_markdown.converter.convert", return_value=(long_text, entities)):
            stream = DraftStream(
                send_draft=AsyncMock(),
                send_final=AsyncMock(),
                mode="entity",
                thinking_delay=None,
            )
            payload = stream._render_entity("x" * 5000)

        assert isinstance(payload, EntityDraftPayload)
        assert len(payload.text) == 4096
        # Entities dropped after truncation
        assert payload.entities == []

    def test_entity_no_truncation_under_limit(self):
        """Text under 4096 is kept intact with entities."""
        from telegramify_markdown.stream.draft import DraftStream, EntityDraftPayload

        text = "Hello world"
        entities = [{"offset": 0, "length": 5, "type": "bold"}]

        with patch("telegramify_markdown.converter.convert", return_value=(text, entities)):
            stream = DraftStream(
                send_draft=AsyncMock(),
                send_final=AsyncMock(),
                mode="entity",
                thinking_delay=None,
            )
            payload = stream._render_entity("Hello world")

        assert payload.text == "Hello world"
        assert payload.entities == entities
