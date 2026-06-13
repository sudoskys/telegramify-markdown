---
id: ADR-001
title: Rich Message splitting at source block boundaries
status: Accepted
date: 2026-06-12
author: Codex
supersedes: []
superseded_by: null
prds:
  - rich-message
summary: Split Rich Message output at pyromark source block boundaries, not at rendered HTML byte offsets. Rich Message delivery is a parallel pipeline to the Entity pipeline, sharing the same parse boundary.
---

# ADR-001: Rich Message splitting at source block boundaries

> **Status**: Accepted. All open questions resolved. Ready for implementation.

## Context

Telegram Bot API 10.1 added Rich Messages with their own limits: 32768 UTF-8
characters, 500 blocks, 16 nesting levels, 50 media, 20 table columns.

This library already handles splitting for the Entity pipeline: `split_entities()`
cuts plain text at safe character offsets without breaking entity spans. That
works because plain text has no structural grammar — it is just characters plus
offset annotations.

Rich HTML is different. Cutting a rendered HTML string at byte 32000 can:
- Break a tag in half (`<pre>co|de</pre>` → invalid)
- Orphan nesting (`<blockquote><p>...` without close)
- Produce a fragment that is not block-complete (half a table row)

The core decision is: **where does the Rich Message splitter find safe split
points?**

## Decision

Split at **pyromark source block boundaries**.

The walker already processes events sequentially. We extend it to record where
each top-level block starts and ends in the output HTML, plus metadata (byte
length, block count contribution). The splitter then bins these blocks into
chunks, each within Telegram limits.

```text
pyromark events
    ↓
RichHtmlWalker (extended)
    emits: list[RichBlock]
           where RichBlock = (html: str, byte_len: int, block_count: int)
    ↓
split_rich()
    bins blocks into chunks respecting:
      - sum(byte_len) ≤ 32768
      - sum(block_count) ≤ 500
    ↓
list[InputRichMessage]  (each chunk = joined block HTML)
```

A "block" in this context means a top-level pyromark event sequence that
produces one block-level HTML element: `<p>`, `<h1>`–`<h6>`, `<pre>`,
`<blockquote>` (including nested content), `<ul>`, `<ol>`, `<table>`, `<hr/>`,
`<tg-math-block>`, `<img .../>`, `<tg-reference>`.

### Library data flow (complete model)

```text
Markdown (fact)
    │
    ├─ parse boundary: pyromark.events_with_range()
    │
    ├─ Entity pipeline (existing, unchanged)
    │       EventWalker → text + entities
    │       split_entities() → list[Text | File | Photo]
    │
    └─ Rich pipeline (this ADR)
            RichHtmlWalker → list[RichBlock]
            split_rich() → list[InputRichMessage]
            wrap → list[RichMessage]
```

Both pipelines share the same parse boundary. They diverge at the walker. They
never mix output types.

### Public API shape

```python
# Single-payload projection (already implemented)
from telegramify_markdown import richify
payload = richify(markdown).to_dict()

# Delivery pipeline: Markdown → list of sendable Rich Messages
from telegramify_markdown import telegramify_rich
items = telegramify_rich(markdown)

# Standalone splitting for pre-built payloads
from telegramify_markdown import split_rich
chunks = split_rich(rich_message)
```

`telegramify_rich()` is synchronous (no Mermaid rendering in v1).
It returns `list[RichMessage]` where `RichMessage` wraps `InputRichMessage` +
`ContentTrace`.

## Data-Centered Decisions

1. **Fact vs state**: Markdown is the fact. `RichBlock` list and
   `InputRichMessage` are projections. No mutable state across calls.

2. **Value semantics**: `RichBlock.byte_len` is UTF-8 encoded byte length of
   `html`. `RichBlock.block_count` is always 1 per top-level block element
   (verified via live test — see §Q1). These are not Python `len()` of the
   string.

3. **Parse boundary**: `pyromark.events_with_range()`. After this point, no
   downstream stage reparses Markdown.

4. **Field classification**:
   - `InputRichMessage.html` / `.markdown` — public key-fact (sent to Telegram)
   - `RichBlock.html` / `.byte_len` / `.block_count` — internal (never leaves
     the library; used only by `split_rich()`)
   - `RichMessage.trace` — audit detail

5. **Authority**: Telegram Bot API docs for limit values. pyromark for block
   boundaries. Live Telegram tests for acceptance oracle.

6. **Absence semantics**: `InputRichMessage.is_rtl` and
   `.skip_entity_detection` — `None` means N/A (omitted from `to_dict()`), not
   "unknown".

7. **Projection strategy**: `InputRichMessage` declared once, `to_dict()`
   derives payload. `RichBlock` is internal — not exposed, not versioned.

## Flags

### Flag 1: Splitting never breaks a block

**Expectation.** Every `InputRichMessage` chunk emitted by `split_rich()`
contains only complete block-level elements. No chunk has an unclosed tag or
orphaned nesting.

**Verification.** Unit tests feed a document with 10+ blocks where total size
exceeds 32768 bytes. Assert every chunk parses as valid HTML (well-formed tags)
and total block count per chunk ≤ 500.

### Flag 2: Byte and block budgets are both enforced

**Expectation.** `split_rich()` starts a new chunk when either the byte budget
or the block count budget would be exceeded by adding the next block.

**Verification.** Construct inputs that trigger each limit independently:
- A document with 600 short paragraphs (block count overflow, not byte overflow)
- A document with 3 massive code blocks each ~15KB (byte overflow, not block count overflow)

### Flag 3: Splittable oversized atomic blocks are split safely

**Expectation.** A single paragraph, preformatted code block, or Markdown
paragraph that exceeds 32768 bytes is split into multiple complete chunks, each
within the byte budget. The splitter preserves wrapper tags around each HTML
chunk so callers do not receive invalid Rich HTML.

**Verification.** Feed a 40000-byte paragraph, a 40000-byte `<pre>` block, and
a 40000-byte Rich Markdown paragraph. Assert each path produces multiple chunks
and every chunk is at most 32768 UTF-8 bytes.

### Flag 4: Entity pipeline is unaffected

**Expectation.** `convert()`, `telegramify()`, and `split_entities()` behavior
remains identical. No code in the Entity pipeline is modified.

**Verification.** Existing test suite passes without changes.

### Flag 5: Real Telegram accepts the split output

**Expectation.** For a fixture that triggers splitting, every chunk is accepted
by Telegram's `sendRichMessage` endpoint.

**Verification.** The live test sends `telegramify_rich()` output with
`TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. CI runs the test when secrets
exist.

**Reference.**
- `tests/test_server.py` — live Telegram contract tests
- `playground/t_longtext.md` — real markdown fixture

## Considered Alternatives

| Option | Why rejected |
|---|---|
| Split rendered HTML string at byte offset | Breaks tags, produces invalid HTML. The #1 reason this ADR exists. |
| Split by regex on `</p>`, `</pre>`, etc. | Cannot handle nested structures (`<blockquote><ul>...</ul></blockquote>` counts as one block) or empty tags. |
| Re-parse rendered HTML with `html.parser` | Adds complexity; the library already has structural information from pyromark. Parsing twice defeats the single-parse-boundary principle. |
| Estimate from Markdown source byte count | Inaccurate. HTML expansion varies wildly: a table row is 5× longer in HTML than Markdown. A heading gains 9 bytes (`<h1>...</h1>`) regardless of content. |
| Add `telegramify(..., output="rich")` | One function returning unrelated data models depending on a flag. Weakens types, hides the projection boundary. |
| Make `richify(..., split=True)` return list | Overloads return type of a projection function. Projection and splitting are different stages with different concerns. |

## Implementation Log

### 2026-06-12 Initial Proposal

**Executor**: Codex

**Scope**:
- Flags declared: 1-5.
- Deferred: native structured RichBlock builder; rich media attachment
  extraction; Mermaid-as-attachment in Rich pipeline.

**Evidence**:

```bash
# No implementation commands yet. This ADR is awaiting maintainer approval.
```

### 2026-06-13 Review Repair

**Executor**: Codex

**Scope**:
- Replaced the original oversized-block behavior. Splittable oversized
  paragraph/pre/Markdown blocks are split instead of being emitted as oversized
  standalone chunks.
- Made empty `telegramify_rich()` input return no delivery item, matching
  `split_rich(InputRichMessage(html=""))`.
- Re-checked Telegram block counting with the real `sendRichMessage` endpoint:
  600 `<li>` items inside one `<ul>` and 601 table rows inside one `<table>` are
  accepted as one server block; 501 top-level blockquotes are rejected.

**Evidence**:

```bash
pdm run test-rich
pdm run python - <<'PY'
# Live probe summary:
# ul-600-li ACCEPTED server_blocks 1
# table-601-rows ACCEPTED server_blocks 1
# blockquote-501 REJECTED RICH_MESSAGE_BLOCKS_TOO_MANY
PY
```

## Resolved Questions

### Q1: Telegram block counting rule (resolved 2026-06-12)

**Method**: live probing via `playground/probe_block_counting.py` against the
real `sendRichMessage` endpoint.

**Findings**:

| HTML structure | Telegram block count | Evidence |
|---|---|---|
| N × `<p>` | N | 500 `<p>` = 500 blocks; 501 → `RICH_MESSAGE_BLOCKS_TOO_MANY` |
| N × `<h1>`–`<h6>` | N | Confirmed as part of mixed-block test (p + h1 + pre) |
| N × `<pre>` | N | Confirmed as part of mixed-block test |
| N × `<hr/>` | N | 500 `<hr/>` = 500 blocks; 501 → rejected |
| N × `<details>` | N | 500 `<details>` = 500 blocks; 501 → rejected |
| N × `<blockquote><p>...</p></blockquote>` | N (blockquote only) | 500 bq = 500 blocks; inner `<p>` does NOT add to count |
| N × `<blockquote><p>a</p><p>b</p></blockquote>` | N (blockquote only) | 500 bq × 2p = 500 blocks; 501 bq × 2p → rejected |
| 1 × `<ul>` with M `<li>` | 1 | 1000 items in one `<ul>` = 1 block; 2000 items = 1 block |
| N × `<ul><li>x</li></ul>` (1 item each) | N | 500 independent 1-item lists = 500 blocks; 501 → rejected |
| 1 × `<table>` with M `<tr>` | 1 | 501 rows in one table = 1 block |
| nested `<ul><li><ul><li>...</li></ul></li></ul>` | 1 (outermost list) | 260 outer items × 1 inner list each = 1 block total |

**Conclusion**: the 500-block limit counts **top-level block elements as parsed
by the Telegram server**, not raw HTML tags. Internal children (list items, table
rows, paragraphs inside blockquotes, nested lists) do **not** independently add
to the block count. One `<ul>`, `<ol>`, `<table>`, or `<blockquote>` is always
1 block regardless of how many children it contains.

**Caveat**: Telegram server may merge adjacent same-type lists when they contain
multiple items (500 × `<ul>` with 10 items → ~295 blocks instead of 500). This
merge is non-deterministic from our side and makes the actual count lower, so it
is safe to ignore (our estimate will be conservative).

**Impact on splitter design**: the splitter counts top-level blocks only. Each
top-level `<p>`, `<h1>`–`<h6>`, `<pre>`, `<hr/>`, `<blockquote>`, `<ul>`,
`<ol>`, `<table>`, `<details>`, `<tg-math-block>`, `<tg-reference>` = 1 block.
Sub-elements inside them = 0 additional blocks. This makes counting trivial
during the walk.

## Open Questions

All questions resolved. ADR ready for implementation.

| # | Question | Resolution |
|---|---|---|
| 1 | Block counting rule | **Resolved** — see §Q1 above |
| 2 | Budget overrides | **Resolved** — v1 uses Telegram published limits as constants (32768 bytes, 500 blocks). Not configurable. These are server-enforced hard limits. If Telegram changes them, bump the library version. |

## References

- @see [Rich Message PRD](../prd/rich-message.md)
- @see https://core.telegram.org/bots/api#inputrichmessage
- @see https://core.telegram.org/bots/api#sendrichmessage
- @see https://core.telegram.org/bots/api#rich-message-limits
