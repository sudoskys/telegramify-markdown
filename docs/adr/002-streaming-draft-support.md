---
id: ADR-002
title: Streaming draft support via sendMessageDraft / sendRichMessageDraft
status: Accepted
date: 2026-06-13
author: Lilith
supersedes: []
superseded_by: null
prds:
  - rich-message
summary: Two-layer async streaming architecture — a protocol-agnostic StreamCore (buffer + throttle + concurrency) composed with strategy facades (DraftStream, EditStream) that inject rendering and Telegram transport.
---

# ADR-002: Streaming draft support via sendMessageDraft / sendRichMessageDraft

> **Status**: Accepted.

## Context

LLM bots produce output token-by-token. Users expect to see partial results as
the model generates. Telegram Bot API 9.3+ introduced `sendMessageDraft` (plain
text drafts) and Bot API 10.1 added `sendRichMessageDraft` (rich message drafts)
specifically for this use case.

This library already provides the conversion pipeline (Markdown → Entity and
Markdown → Rich HTML). Streaming draft support adds a **temporal dimension** on
top of the existing spatial pipeline: the same conversion runs repeatedly on a
growing input buffer, with throttled delivery of intermediate results.

### Key constraints

| Constraint | Source | Value |
|---|---|---|
| Draft only in private chats | Telegram API | Group/channel must use `editMessageText` fallback |
| Draft expiry | Community observation (not officially documented) | ~30 seconds without update → draft disappears |
| Draft ID must be nonzero | Telegram API | Caller-chosen identifier; same ID animates updates |
| Empty text shows "Thinking…" | Bot API 10.1 | `sendMessageDraft` with empty text; unavailable in 9.3–10.0 |
| Draft text limit (Entity mode) | Telegram API | 0–4096 characters after entity parsing |
| Re-parse cost | Benchmarked locally | ~0.18ms/2KB, ~0.5ms/10KB, ~2.5ms/50KB (linear growth, pyromark + walker) |
| pyromark tolerance | Verified locally | Gracefully handles incomplete Markdown (unclosed fences, partial emphasis become text) |
| Throttle recommendation | Community practice | 2–5 updates/second avoids client lag; draft API less restricted than `editMessageText` |

### Why re-parse entire buffer (not incremental)

Incremental Markdown parsing is fragile: a backtick at position 50 can
retroactively change the meaning of everything after position 10. pyromark does
not expose an incremental API. Given 0.18ms per parse for 2KB and ~0.5ms for
10KB, re-parsing the full accumulated buffer on each throttled update is
negligible compared to network RTT (~50–200ms) and Telegram's processing time.

For large LLM outputs (~50KB), re-parse cost is ~2.5ms — still well within a
300ms throttle interval. If a future benchmark shows parse+render exceeding
`interval / 2`, the implementation should log a warning and suggest increasing
the interval. For documents under 100KB, re-parse is not the bottleneck.

## Decision

Provide a **two-layer async streaming architecture**:

1. **`StreamCore`** (mechanism layer) — a minimal, protocol-agnostic throttled
   buffer that accepts tokens, renders via an injected function, emits snapshots
   via an injected callback, and finalizes via an injected callback. It knows
   nothing about Telegram, Markdown, Rich HTML, or drafts.

2. **`DraftStream` / `EditStream`** (strategy layer) — thin facades that
   assemble `StreamCore` with the appropriate render function (`convert()` or
   `richify()`), emit callback (draft or edit), and Telegram-specific policies
   (thinking delay, draft ID, sliding window).

This separation ensures the concurrency model, throttle logic, and state machine
are implemented and tested exactly once. New transport modes (webhook push,
WebSocket, future Telegram APIs) only require a new facade — never a change to
the core.

### Architecture diagram

```text
┌────────────────────────────────────────────────────────────┐
│  Strategy Layer (user-facing)                              │
│                                                            │
│  DraftStream(mode, draft_id, thinking_delay, ...)         │
│    └─ assembles: render=richify|convert                    │
│                  emit=send_draft callback                  │
│                  finalize=send_final callback              │
│                  window=sliding_window_rich|entity         │
│                                                            │
│  EditStream(mode, ...)                                     │
│    └─ assembles: render=richify|convert                    │
│                  emit=edit_message callback                │
│                  finalize=send_message callback            │
│                  interval lower-bound=1.0s                 │
│                                                            │
└──────────────────────────┬─────────────────────────────────┘
                           │ injects
┌──────────────────────────▼─────────────────────────────────┐
│  StreamCore (mechanism layer)                              │
│                                                            │
│  Parameters:                                               │
│    render: Callable[[str], T]     # buffer → payload       │
│    emit:   Callable[[T], Awaitable]  # snapshot delivery   │
│    finalize: Callable[[T], Awaitable]  # final delivery    │
│    interval: float                # throttle period        │
│    keepalive_timeout: float       # anti-expiry            │
│                                                            │
│  State machine: IDLE → ACTIVE → DONE                      │
│  Concurrency: _sending guard, timer cancel, drain-await   │
│  API: feed(), consume(), finish(), cancel()               │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### Why two layers (not one)

| Monolithic (rejected) | Layered (chosen) |
|---|---|
| Core class knows about `mode="rich"\|"entity"` | Core receives opaque `render` callable |
| Adding group-chat edit requires `if fallback` branches in core | `EditStream` is a separate facade with different `emit` and `interval` |
| Testing throttle/concurrency requires mocking Telegram payloads | Core tests use trivial `render=str.upper`, `emit=mock_coro` |
| New transport = modify core class | New transport = new facade (one file) |

### StreamCore detail

```python
class StreamCore(Generic[T]):
    """Protocol-agnostic throttled streaming buffer."""

    def __init__(
        self,
        render: Callable[[str], T],
        emit: Callable[[T], Awaitable[None]],
        finalize: Callable[[T], Awaitable[None]],
        interval: float = 0.3,
        keepalive_timeout: float = 25.0,
        on_cancel: Callable[[], Awaitable[None]] | None = None,
    ): ...

    def feed(self, token: str) -> None: ...
    async def consume(self, tokens: AsyncIterator[str]) -> None: ...
    async def finish(self) -> None: ...
    async def cancel(self) -> None: ...
```

**State machine** (3 states):

```text
┌────────┐   feed()/consume()   ┌────────┐   finish()/cancel()   ┌────────┐
│  IDLE  │─────────────────────▶│ ACTIVE │───────────────────────▶│  DONE  │
└────────┘                      └────────┘                        └────────┘
```

- **IDLE**: No tokens received. No timer running. No API calls.
- **ACTIVE**: Buffer growing, timer running, periodic `emit()` on throttled
  schedule. Includes "first emit" behavior (thinking indicator) as a special
  case of the first `emit()` call — not a separate state.
- **DONE**: Terminal. `finish()` called `finalize()` once; or `cancel()` called
  `on_cancel()`. Timer stopped. Further `feed()` raises `RuntimeError`.

### DraftStream (strategy facade)

```python
from telegramify_markdown.stream import DraftStream

async with DraftStream(
    send_draft=my_send_draft_fn,     # async (payload) -> None
    send_final=my_send_final_fn,     # async (payload) -> None
    mode="rich",                     # "rich" | "entity"
    draft_id=None,                   # None = auto-generate; or nonzero int
    interval=0.3,                    # seconds between draft updates
    thinking_delay=0.5,              # seconds before first substantive draft
    keepalive_timeout=25.0,          # seconds without tokens before keepalive
    cancel_clears_draft=True,        # send empty draft on cancel
) as stream:
    # Option A: manual feed
    async for token in llm_response:
        stream.feed(token)

    # Option B: convenience consume
    # await stream.consume(llm_response)
```

`DraftStream` internally:
1. Selects `render` = `richify` or `convert` based on `mode`.
2. Wraps `render` with sliding-window truncation (trailing 4096 chars for entity,
   trailing blocks within 32KB for rich).
3. Wraps `send_draft` as `emit` (prepending thinking-delay logic on first call).
4. Wraps `send_final` as `finalize` (calling `convert()` or `richify()` for
   single-message rendering). Note: the full splitting pipeline
   (`telegramify()` / `telegramify_rich()`) returns multiple content items —
   multi-message orchestration is the caller's responsibility, not the stream's.
5. Passes `on_cancel` = empty-draft sender when `cancel_clears_draft=True`.
6. Delegates everything else to `StreamCore`.

When `draft_id=None`, auto-generates a unique nonzero ID via
`hash(id(self)) & 0x7FFFFFFF | 1`. Callers who need to correlate draft IDs
across streams can pass an explicit value.

### EditStream (group-chat facade)

```python
from telegramify_markdown.stream import EditStream

async with EditStream(
    send_message=my_send_fn,         # async (payload) -> message_id
    edit_message=my_edit_fn,         # async (message_id, payload) -> None
    mode="rich",
    interval=1.0,                    # ≥1.0s enforced (Telegram edit limit)
) as stream:
    await stream.consume(llm_response)
```

`EditStream` internally:
1. On first emit, calls `send_message` to create the placeholder, stores the
   returned `message_id`.
2. Subsequent emits call `edit_message(message_id, payload)`.
3. Enforces `interval >= 1.0` (Telegram's edit rate limit).
4. Finalize = one last `edit_message` with the complete rendered content.

### Throttle and debounce strategy (StreamCore)

```text
token arrives → mark buffer dirty
                     ↓
           timer fires (every `interval` ms)
                     ↓
           if dirty AND NOT _sending:
               payload = render(buffer)
               _sending = True
               try: await emit(payload)
               finally: _sending = False
               clear dirty flag
               reset keepalive timer
```

- **Minimum interval**: 200ms for DraftStream (configurable). EditStream
  enforces ≥1.0s. Below 200ms, Telegram clients struggle to animate smoothly.
- **Keepalive**: If no tokens arrive for `keepalive_timeout` seconds (default
  25s, configurable), auto-resend current state to prevent draft expiry. The
  default is conservative against a ~30s observed expiry window; callers can
  lower this if Telegram tightens the window.
- **Burst absorption**: Multiple tokens between timer fires are batched into one
  re-parse + one `emit()` call.
- **Backpressure**: The buffer grows monotonically regardless of send success.
  For typical LLM outputs (< 100KB), memory is not a concern. The splitting
  pipeline handles overflow at finalization. If buffer exceeds 512KB (an
  implausible but defensive limit), the stream logs a warning — this suggests
  the caller forgot to finalize.

### State machine (StreamCore)

```text
┌────────┐   feed()/consume()   ┌────────┐   finish()/cancel()   ┌────────┐
│  IDLE  │─────────────────────▶│ ACTIVE │───────────────────────▶│  DONE  │
└────────┘                      └────────┘                        └────────┘
```

- **IDLE**: No tokens received. No timer. No API calls.
- **ACTIVE**: Timer running, periodic `emit()`. The strategy facade may inject
  "thinking" behavior as a hook on the first emit — the core does not distinguish.
- **DONE**: Terminal. Reached via `finish()` (calls `finalize`) or `cancel()`
  (calls `on_cancel`). Timer stopped. Subsequent `feed()` raises `RuntimeError`.

### Error handling (StreamCore)

| Failure | Behavior |
|---|---|
| `emit()` raises | Log warning, skip this update, stay dirty for next interval |
| `emit()` raises 3× consecutive | Transition to degraded mode: stop emitting, accumulate silently, still call `finalize` on finish |
| `finalize()` raises | Propagate to caller (critical: final content would be lost) |
| `CancelledError` in wrapping Task | Route to `cancel()` — no `finalize`, calls `on_cancel` if set |

Strategy-layer policies (DraftStream):

| Failure | Behavior |
|---|---|
| Draft expires (no update within expiry window) | Should not happen if keepalive works; if detected, restart draft with fresh ID |
| Token stream stalls > `keepalive_timeout` | Auto-resend current buffer state (keepalive fires as a normal emit tick) |

### Concurrency model (StreamCore)

`StreamCore` operates within a **single asyncio event loop**. It does not
support multi-threaded access. All state transitions are sequential under
asyncio's cooperative scheduling.

**Guards against race conditions:**

1. **`_sending` flag**: A boolean guard that prevents overlapping `emit` and
   `finalize` calls. When the timer fires while a previous send is still
   awaiting, the new tick is a no-op (buffer stays dirty for the next tick).

2. **`finish()` cancels the timer first**: On entry, `finish()` cancels any
   pending timer task, awaits the `_sending` flag to clear (if a send is
   in-flight), then calls `finalize(render(buffer))`.

3. **Post-DONE no-ops**: After transitioning to DONE, any subsequent timer
   fires (from scheduling race) check state and exit immediately.

4. **`CancelledError` path**: If the wrapping asyncio Task is cancelled,
   `__aexit__` receives `CancelledError` and routes to `cancel()` instead of
   `finish()`.

```text
Timer fires:
    if state == DONE: return (no-op)
    if _sending: return (skip this tick, stay dirty)
    _sending = True
    try: await emit(render(buffer))
    finally: _sending = False

finish():
    cancel timer
    await until _sending == False
    state = DONE
    await finalize(render(buffer))

cancel():
    cancel timer
    state = DONE
    if on_cancel: await on_cancel()
```

### Cancellation

Cancellation is a Phase 1 requirement. LLM users frequently stop generation
mid-stream; without explicit cancellation, the context manager would call
`finalize` with partial content the user explicitly abandoned.

```python
# Explicit cancellation
await stream.cancel()

# Implicit via CancelledError (asyncio task cancellation)
# __aexit__ detects CancelledError → calls cancel() internally
```

At the `StreamCore` level, `cancel()`:
- Cancels the timer.
- Transitions state to DONE.
- Calls `on_cancel()` if provided (strategy-injected cleanup).
- Does NOT call `finalize`.

At the `DraftStream` level, `on_cancel` is wired to send an empty draft
(clearing the "Thinking…" indicator) when `cancel_clears_draft=True`.

### Thinking delay (DraftStream policy)

When `thinking_delay > 0`, `DraftStream` hooks into the first `emit` call:

1. On first `feed()`, immediately emit an empty payload (Telegram client renders
   its built-in localized "Thinking…" indicator — not a library-hardcoded string).
2. Start a `thinking_delay` timer. Suppress subsequent `emit` calls until the
   timer expires or buffer exceeds a threshold (whichever comes first).
3. After the delay, normal throttled emission resumes.

This is entirely a strategy-layer concern. `StreamCore` knows nothing about it —
it just calls `emit(render(buffer))` on schedule. The `DraftStream` wrapper
intercepts early emits.

### Splitting during streaming

Both modes face limits on draft content size. The strategy differs by mode.

**Entity mode** (4096 character limit):
- When buffer exceeds 4096 characters after rendering, the draft displays only
  the **trailing 4096 characters** (sliding window). The user sees the most
  recent output scrolling by.
- On finalization, the full buffer is processed through `telegramify()` which
  splits into `list[Text | File | Photo]` as normal.

**Rich mode** (32768 bytes / 500 blocks):
- When buffer exceeds Rich Message limits, the draft displays the **trailing
  window** of blocks that fit within limits (sliding window over rendered
  blocks, not a post-split chunk boundary).
- This avoids the UX cliff where content would suddenly jump from "full 31KB
  document" to "1KB tail of chunk 2" at a split boundary.
- On finalization, `telegramify_rich()` splits and sends all chunks
  sequentially.

**Known trade-off**: in both modes, once the buffer exceeds draft limits, the
user loses sight of earlier content until finalization delivers all chunks. This
is acceptable because (a) the user sees content scrolling naturally, and (b) the
alternative — sending finalized chunks mid-stream — causes confusing message
count jumps.

### Pipeline interaction during streaming

Draft updates use **lightweight rendering only**:
- Entity mode: `convert()` → text + entities. No Mermaid rendering, no code
  extraction to File, no image download.
- Rich mode: `richify()` → `InputRichMessage`. No media attachment resolution.

On finalization, the **full pipeline** runs:
- Entity mode: `telegramify()` → may produce File (long code blocks), Photo
  (Mermaid diagrams), and multiple Text items.
- Rich mode: `telegramify_rich()` → splitting, all rich features active.

This means users see Mermaid source code (as a code block) during streaming,
which transforms into a rendered image on finalization. This is an acceptable
and expected UX trade-off — rendering Mermaid takes seconds and cannot happen at
streaming speed.

## Data-Centered Decisions

1. **Fact vs state**: The accumulated token buffer is mutable state (an
   append-only log of tokens). Each `emit()` output is a projection of the
   current buffer state — ephemeral, overwritten by the next emit. The
   `finalize()` output is the fact (persisted by Telegram).

2. **Value semantics**: `interval` is in seconds (float). `draft_id` is a
   nonzero int64 matching Telegram's type. `thinking_delay` is seconds before
   first substantive emit.

3. **Parse boundary**: Same as ADR-001 — `pyromark.events_with_range()`. The
   streaming layer does not introduce a new parse boundary; it repeatedly
   invokes the existing one via the injected `render` callable.

4. **Field classification**:
   - `StreamCore` internal state (buffer, dirty flag, timer, _sending) — internal
   - `render` output (payload passed to emit/finalize) — public key-fact
   - Error counts, last-emit timestamp — audit detail

5. **Authority**: Telegram Bot API docs for draft semantics. Local benchmarks
   for parse cost. Library's own `convert()` / `richify()` for rendering.
   `StreamCore` has no authority dependency — it is Telegram-agnostic.

6. **Absence semantics**: `thinking_delay=None` means skip the thinking phase
   (immediately start emitting rendered content). `on_cancel=None` means cancel
   is silent (no cleanup call).

7. **Projection strategy**: `StreamCore` is generic over payload type `T`.
   Payload dataclasses are declared once per strategy (matching Telegram API
   parameter names). No intermediate transform types.

## Flags

### Flag 1: Re-parse produces valid output on incomplete Markdown

**Expectation.** pyromark + the walker produce valid (if incomplete) output for
any prefix of a well-formed Markdown document. Unclosed fences, partial emphasis,
and dangling links all render as visible text rather than crashing or producing
broken HTML. Token boundaries at emoji / CJK / surrogate-pair positions do not
affect correctness (Python `str` is UCS-4; no half-surrogate can exist in the
buffer).

**Verification.** Unit test: take a 5KB fixture containing CJK, emoji, and RTL
text; split it at every 100-byte boundary; feed each prefix through `richify()`
and `convert()`. Assert no exceptions and valid output structure.

### Flag 2: Throttle respects minimum interval

**Expectation.** Regardless of `feed()` call frequency, the `send_draft`
callback is invoked at most once per `interval` seconds.

**Verification.** Unit test with mocked time: feed 1000 tokens in 0ms, assert
`send_draft` called exactly once within the first interval.

### Flag 3: Draft keepalive prevents expiry

**Expectation.** If no new tokens arrive for 25+ seconds, the stream
auto-resends the current state to prevent draft expiry.

**Verification.** Unit test with mocked time: feed one token, advance clock 26s
without new tokens, assert `send_draft` called at t=25s.

### Flag 4: Finalization sends complete message

**Expectation.** On `finish()` or `__aexit__`, the full buffer is re-parsed
one final time and `send_final` is called exactly once.

**Verification.** Unit test: feed tokens, call finish, assert `send_final`
called with the complete rendered output.

### Flag 5: EditStream enforces ≥1s interval

**Expectation.** `EditStream` refuses `interval < 1.0` at construction time and
emits edits at exactly the configured interval (never faster than Telegram's
1 edit/second limit).

**Verification.** Unit test: construct `EditStream(interval=0.5)`, assert
`ValueError`. Construct with `interval=1.5`, feed tokens rapidly, assert
`edit_message` called at ≥1.5s intervals.

### Flag 6: Degraded mode after repeated failures

**Expectation.** After 3 consecutive `send_draft` failures, the stream stops
calling `send_draft` and only sends the final message.

**Verification.** Unit test: mock `send_draft` to always raise, feed tokens,
call finish. Assert `send_draft` called ≤3 times, `send_final` called once
with complete content.

### Flag 7: Cancellation does not send final message

**Expectation.** When `cancel()` is called (or `CancelledError` propagates),
no `send_final` is invoked. If `cancel_clears_draft=True`, an empty draft is
sent to clear the indicator.

**Verification.** Unit test: feed tokens, call `cancel()`, assert `send_final`
never called. Assert empty-draft send occurred when `cancel_clears_draft=True`.

### Flag 8: Concurrent send guard prevents overlapping emit calls

**Expectation.** If `emit()` await takes longer than `interval`, the next
timer tick is skipped (not queued). At no point are two `emit` calls in flight
simultaneously.

**Verification.** Unit test: mock `emit` to sleep 2× interval, feed tokens
continuously, assert no overlapping calls (use a counter that raises if > 1).

## Considered Alternatives

| Option | Why rejected |
|---|---|
| Monolithic DraftStream with `mode` + `fallback` params | Mixes mechanism (throttle/buffer/concurrency) with strategy (draft vs edit, rich vs entity). Adding a new transport requires modifying core. Tested via first-principles analysis — see §Prior Art. |
| Incremental Markdown parsing (delta only) | pyromark has no incremental API; a backtick retroactively changes parse tree. The 0.18ms full-reparse cost makes this unnecessary complexity. |
| Library embeds HTTP client | Violates the library boundary (no bot tokens, no network I/O). Different bot frameworks (aiogram, python-telegram-bot, telethon) use different async runtimes. |
| Synchronous streaming API | Draft updates are inherently async (timer-based, network I/O in callbacks). A sync API would require threads and complicate the caller's event loop. |
| Token-level diffing (send only changed portions) | Telegram draft API replaces the entire message content. There is no patch/delta endpoint. |
| Split mid-stream (send multiple drafts simultaneously) | Confusing UX; user sees message count jumping during generation. Defer splitting to finalization. |
| Show post-split last chunk during streaming | Creates a UX cliff (31KB → 1KB jump at boundary). Sliding window is smoother. |

### Prior art

Production LLM Telegram bots (OpenClaw, Hermes Agent, grammY streaming plugin)
converged on the same core pattern: buffer + throttle + overwrite-emit. Key
lessons incorporated:

- **OpenClaw**: Migrated from `sendMessage` + `editMessageText` to
  `sendMessageDraft` (Bot API 9.5+). Documented the "inFlight mutex" pattern
  for preventing overlapping edits — directly maps to our `_sending` guard.
- **Hermes Agent**: UTF-16-aware overflow splitting during edit streaming.
  Confirms the need for sliding-window truncation rather than hard errors.
- **grammY streaming plugin**: Identified that Markdown formatting during
  streaming is the hardest problem (partial entities break). Our approach —
  full re-parse via pyromark on each tick — sidesteps this entirely.

@see OpenClaw PR #32041 — sendMessageDraft migration decision
@see grammY streaming docs — Markdown entity streaming pitfalls

## Implementation Plan

### Phase 1: Core mechanism + Draft facade (this ADR)

1. `src/telegramify_markdown/stream/core.py` — `StreamCore[T]` generic class
   (buffer, throttle, concurrency model, state machine, cancel/finish).
2. `src/telegramify_markdown/stream/draft.py` — `DraftStream` facade (render
   selection, thinking delay, sliding window, draft_id, cancel_clears_draft).
3. `src/telegramify_markdown/stream/edit.py` — `EditStream` facade (send +
   edit callbacks, interval ≥1s enforcement).
4. `src/telegramify_markdown/stream/__init__.py` — public exports.
5. Payload dataclasses in `src/telegramify_markdown/content.py`.
6. Unit tests for all 8 flags (pytest-asyncio + manual event loop advancement).
   Core tests use trivial `render`/`emit` mocks — no Telegram payload knowledge.
7. README documentation.

### Phase 2: Convenience wrappers (future, after community feedback)

- Pre-built callback adapters for popular frameworks (aiogram, python-telegram-bot)
- CLI playground for manual testing with a real bot

### Phase 3: Advanced features (future)

- Cursor/typing indicator position hints
- Multi-message streaming (streaming into message N while messages 1..N-1 are
  already finalized)
- Rich Markdown mode streaming (pass through partial Markdown directly)

## Open Questions

| # | Question | Status |
|---|---|---|
| 1 | Cancellation support | **Resolved** — included in Phase 1 with `cancel()` method and `CancelledError` handling. See §Cancellation. |
| 2 | Should the library provide a rate-limit detector (429 backoff)? | Open — likely out of scope since the library does not own HTTP. Caller can implement backoff in their `send_draft` callback. |
| 3 | `sendRichMessageDraft` parameter shape | **Resolved** — accepts `chat_id` + `draft_id` + `rich_message` (InputRichMessage object). Same callback shape as `send_draft` for rich mode. |
| 4 | Exact draft expiry duration | Open — 30s is community-observed, not officially documented. The `keepalive_timeout` parameter lets callers adapt without a library release. |

## References

- @see [ADR-001](./001-rich-message-pipeline-composition.md) — Rich Message splitting
- @see [Rich Message PRD](../prd/rich-message.md)
- @see https://core.telegram.org/bots/api#sendmessagedraft
- @see https://core.telegram.org/bots/api#sendrichmessagedraft
- @see https://core.telegram.org/bots/api-changelog (Bot API 9.3, 9.5, 10.0, 10.1)
