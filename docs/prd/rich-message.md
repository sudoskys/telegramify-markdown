# Rich Message PRD

## Product Boundary

Rich Message output converts Markdown into Telegram Bot API 10.1
`InputRichMessage` payloads. The payload is suitable for `sendRichMessage`,
`sendRichMessageDraft`, `editMessageText(rich_message=...)`, and
`InputRichMessageContent`.

The boundary ends at payload construction and splitting. The library does not
send requests, own bot tokens, retry Telegram calls, or guarantee wrapper SDK
support.

## Users

- Bot developers who want Telegram clients to render headings, lists, tables,
  block quotes, code blocks, and formulas as structured Rich Messages.
- LLM application developers who want a richer output target than plain text
  plus `MessageEntity`.
- Maintainers validating Bot API formatting compatibility.

## Data Flow Model

The library is a pipeline of pure stages. Each stage takes a value, returns a
value, and does not persist state across calls.

```text
Markdown (fact, immutable input)
  │
  ├─ parse boundary ─────── pyromark.events_with_range()
  │       │
  │       ↓
  │  Structured Events + Source Ranges (strong type; downstream trusts)
  │       │
  │       ├─ Projection A: Entity path
  │       │       EventWalker → plain text + list[MessageEntity]
  │       │           ↓
  │       │       split_entities() — UTF-16 limit, entity-boundary-safe
  │       │           ↓
  │       │       list[Text | File | Photo]
  │       │
  │       └─ Projection B: Rich Message path
  │               RichHtmlWalker → Rich HTML string (+ source block ranges)
  │                   ↓
  │               split_rich() — source-block-boundary splitting
  │                   ↓
  │               list[RichMessage]
  │
  └─ (future: Projection C, etc.)
```

### Data-Centered Decisions

1. **Fact vs state**: Markdown input is the fact. All outputs are projections
   derived from that fact. The library does not persist or mutate conversion
   state across calls. Each function call is a pure transform.

2. **Parse boundary**: Raw Markdown crosses the parse boundary exactly once at
   `pyromark.events_with_range()`. After that point, downstream stages consume
   structured events — they never reparse Markdown with ad hoc rules.

3. **Two projections, one parse**: Both the Entity path and the Rich Message
   path share the same parse boundary. They diverge only at the walker stage.
   This means pyromark options and preprocessing (spoiler, LaTeX) apply uniformly.

4. **Split semantics differ by projection**: Each projection has its own
   splitting stage because the limits are structurally different:
   - Entity path: 4096 UTF-16 code units; splitting must not break entity spans.
   - Rich path: 32768 UTF-8 characters + 500 blocks; splitting must not break
     HTML tags or split a block-level element in half.

5. **Delivery items are typed by projection**: `Text | File | Photo` belongs to
   the Entity pipeline. `RichMessage` belongs to the Rich pipeline. They are
   never mixed in the same list. Each delivery item carries a `ContentTrace` for
   debuggability.

6. **Authority**: Telegram Bot API documentation is the authority for payload
   shape and limits. pyromark event ranges are the authority for source block
   boundaries. Telegram live tests are the contract oracle.

7. **Projection strategy**: `InputRichMessage` is declared once. `to_dict()`
   derives the request payload. Tests, docs, and playground derive from the same
   type.

## Outcomes

- A caller can pass raw Markdown to `richify()` and receive a single
  `InputRichMessage` whose `to_dict()` matches Telegram's shape.
- A caller can pass raw Markdown to `telegramify_rich()` and receive a list of
  `RichMessage` delivery items, each within Telegram limits and ready to send.
- The existing `convert()` / `telegramify()` API remains unchanged.
- Rich output preserves document structure where Telegram Rich Messages have a
  corresponding construct.
- Unsupported Markdown remains visible as text rather than disappearing.

## Public Contract

### Single-payload projection

```python
from telegramify_markdown import richify

rich_message = richify(markdown)
payload = rich_message.to_dict()
```

`richify()` accepts:

| Parameter | Type | Default | Contract |
|---|---|---|---|
| `markdown` | `str` | required | Raw Markdown input |
| `mode` | `"html" \| "markdown"` | `"html"` | `html` generates Telegram Rich HTML; `markdown` passes Markdown through as Rich Markdown |
| `is_rtl` | `bool \| None` | `None` | Adds `is_rtl` only when not `None` |
| `skip_entity_detection` | `bool \| None` | `None` | Adds `skip_entity_detection` only when not `None` |
| `latex_escape` | `bool` | `False` | When `html`, `False` keeps formula source for Telegram math rendering; `True` applies legacy Unicode conversion before parsing |

`InputRichMessage.to_dict()` returns exactly one of `html` or `markdown`, plus
optional `is_rtl` and `skip_entity_detection`.

### Delivery pipeline (splitting + wrapping)

```python
from telegramify_markdown import telegramify_rich

items = telegramify_rich(markdown)
for item in items:
    payload = item.to_dict()
    # send via sendRichMessage
```

`telegramify_rich()` is synchronous. It composes `richify()` + splitting and
returns `list[RichMessage]`. Each `RichMessage` is within Telegram limits.

`telegramify_rich()` accepts all parameters of `richify()` and does not
introduce additional ones in v1 (splitting budgets use Telegram's published
limits directly).

### Splitting (exposed for `mode="markdown"` callers)

```python
from telegramify_markdown import split_rich

chunks = split_rich(rich_message)
```

`split_rich()` accepts a single `InputRichMessage` and returns
`list[InputRichMessage]`, each within Telegram Rich Message limits. This is
useful when the caller already has a payload (e.g., from `mode="markdown"` on
long text) and only needs splitting.

## Conversion Semantics

The default `html` mode uses pyromark events and emits Telegram Rich HTML.

| Markdown / event | Rich HTML output |
|---|---|
| paragraph | `<p>...</p>` |
| heading levels 1-6 | `<h1>` to `<h6>` |
| strong | `<b>` |
| emphasis | `<i>` |
| strikethrough | `<s>` |
| spoiler `\|\|...\|\|` | `<tg-spoiler>` |
| inline code | `<code>` |
| fenced code block | `<pre><code class="language-{lang}">...</code></pre>` when language exists, otherwise `<pre>...</pre>` |
| inline math | `<tg-math>...</tg-math>` |
| display math or `math` fenced block | `<tg-math-block>...</tg-math-block>` |
| link | `<a href="...">...</a>` |
| image with HTTP/HTTPS URL | `<img src="..." alt="..." title="..."/>` when it appears as its own block |
| image with `tg://emoji?id=...` | `<tg-emoji emoji-id="...">alt</tg-emoji>` |
| unordered list | `<ul><li>...</li></ul>` |
| ordered list | `<ol start="..."><li>...</li></ol>` |
| task list item | `<li>` text starts with `☑ ` or `✅ ` |
| block quote | `<blockquote>...</blockquote>` |
| table | `<table><tr><th>...</th></tr><tr><td>...</td></tr></table>` |
| thematic break | `<hr/>` |
| footnote reference | visible bracketed text, e.g. `[note]` |
| unsupported inline HTML | escaped visible text or omitted only when pyromark treats it as structural HTML without text |

The `markdown` mode returns the input Markdown as Telegram Rich Markdown. This
mode lets Telegram parse constructs that the HTML backend does not model yet,
such as native Rich Markdown task list semantics and arbitrary supported Rich
HTML embedded by the caller.

## Splitting Strategy

This is the core technical design for the Rich Message delivery pipeline.

### Why splitting is needed

A single Markdown document (e.g., LLM output) can exceed Telegram Rich Message
limits. The library must split it into multiple sendable payloads, each valid
Rich HTML.

### Why splitting Rich HTML is harder than splitting Entity text

Entity-path splitting is character-offset-based: find a safe split point in
plain text and adjust entity offsets. The text itself has no structural grammar.

Rich HTML splitting cannot cut at an arbitrary byte offset because:
- Tags would be broken (`<pre>code he|re</pre>` → invalid)
- Nesting would be orphaned (`<blockquote><p>...` without closing tags)
- Block semantics would be lost (half a table row is not a table)

### Chosen strategy: source-block-boundary splitting

The splitter operates at the **pyromark source block boundary** level, not at
the rendered HTML string level.

```text
pyromark events → RichHtmlWalker emits per-block HTML fragments
                  + records block metadata (byte range, estimated size)
                      ↓
                  split_rich() bins blocks into chunks
                  that respect Telegram limits
                      ↓
                  each chunk → joined HTML string → InputRichMessage
```

**Invariants**:
- A block is the atomic unit of splitting. Blocks are never cut in half.
- Each chunk is a valid, self-contained Rich HTML fragment.
- Block count, UTF-8 byte length, and nesting depth are tracked per chunk.
- When a single block exceeds the limit alone (e.g., a 40KB code block), the
  splitter must handle it as an oversized atom — either truncate with indication
  or emit it as a standalone chunk that exceeds the soft limit (the Telegram
  server may reject it, and the caller must handle that).

**What is a "block"**: a top-level pyromark event sequence that produces one
block-level HTML element. Specifically: `<p>`, `<h1>`-`<h6>`, `<pre>`,
`<blockquote>`, `<ul>`, `<ol>`, `<table>`, `<hr/>`, `<tg-math-block>`,
`<img .../>` (block-level), `<tg-reference>`.

### Considered and rejected splitting strategies

| Strategy | Why rejected |
|---|---|
| Split rendered HTML string by byte offset | Breaks tags, produces invalid HTML |
| Split by regex on block-level tags | Fragile; cannot handle nested structures like `<blockquote><ul>...</ul></blockquote>` |
| Re-parse rendered HTML with an HTML parser | Adds a dependency; the library already has structural info from pyromark |
| Estimate from Markdown source line count | Inaccurate; HTML expansion varies (a table row is much more bytes in HTML than in Markdown) |

## Escaping Contract

- Text content is HTML-escaped.
- Attribute values are HTML-escaped.
- Code and formula content is escaped as text content.
- Raw unsupported HTML from input does not gain execution authority through the
  default backend.

## Limits

Telegram Rich Messages are subject to Telegram's published limits:

- 32768 UTF-8 characters in rich message text.
- 500 top-level blocks.
- 16 levels of nested formatting and blocks.
- 50 media attachments.
- 20 table columns.

### Block counting rule (verified via live testing)

The 500-block limit counts **top-level block elements as parsed by the Telegram
server**. Internal children do not independently add to the count:

- Each top-level `<p>`, `<h1>`–`<h6>`, `<pre>`, `<hr/>`, `<blockquote>`,
  `<ul>`, `<ol>`, `<table>`, `<details>`, `<tg-math-block>` = 1 block.
- List items (`<li>`), table rows (`<tr>`), paragraphs inside blockquotes, and
  nested lists inside list items = 0 additional blocks.
- A single `<ul>` with 2000 items is still 1 block. A single `<table>` with
  500 rows is still 1 block.

This means the splitter only needs to count top-level blocks emitted by the
walker — a trivial increment per block-level event.

@see ADR-001 Resolved Questions §Q1 for full evidence table.

`richify()` creates one payload. `telegramify_rich()` and `split_rich()`
produce multiple payloads when the input exceeds these limits.

## Error Semantics

- `richify(..., mode=<unknown>)` raises `ValueError`.
- Empty input returns an empty Rich Message payload for the selected mode.
- The converter preserves visible content when a Markdown construct lacks a
  Telegram Rich HTML equivalent.
- `split_rich()` on an empty payload returns `[]`.
- An oversized paragraph, preformatted code block, or Rich Markdown paragraph is
  split into multiple valid chunks. Rich HTML wrapper tags are preserved on each
  chunk.
- An oversized Rich HTML block that the library cannot split safely is emitted
  as-is with a warning log. The caller is responsible for handling Telegram
  rejection.

## Acceptance Cases

- Basic inline formatting produces nested Rich HTML tags without crossing tags.
- Headings, paragraphs, blockquotes, lists, tables, and code blocks produce
  block-level Rich HTML tags.
- Inline and display math preserve formula source in `<tg-math>` and
  `<tg-math-block>` when `latex_escape=False`.
- `to_dict()` omits optional fields when they are `None`.
- `mode="markdown"` passes Markdown through in the `markdown` field.
- Existing `convert()` and `telegramify()` behavior remains unchanged.
- `telegramify_rich()` on a 50KB paragraph or code block produces multiple
  chunks, each within 32768 UTF-8 characters and 500 blocks.
- Every chunk from `telegramify_rich()` is valid Rich HTML (no broken tags, no
  orphaned nesting).
- Before opening a PR that changes Rich Message behavior, `pdm run test-live-rich`
  passes with real `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`; the test must
  reach `sendRichMessage` and receive a `Message.rich_message` witness from
  Telegram.

## External Authority

- @see https://core.telegram.org/bots/api#rich-message-formatting-options
- @see https://core.telegram.org/bots/api#inputrichmessage
- @see https://core.telegram.org/bots/api#sendrichmessage
- @see https://core.telegram.org/bots/api#rich-message-limits
