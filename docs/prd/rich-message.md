# Rich Message Output PRD

## Product Boundary

Rich Message output converts Markdown into Telegram Bot API 10.1
`InputRichMessage` payloads. The payload is suitable for `sendRichMessage`,
`sendRichMessageDraft`, `editMessageText(rich_message=...)`, and
`InputRichMessageContent`.

The boundary ends at payload construction. The library does not send requests,
own bot tokens, retry Telegram calls, or guarantee wrapper SDK support.

## Users

- Bot developers who want Telegram clients to render headings, lists, tables,
  block quotes, code blocks, and formulas as structured Rich Messages.
- LLM application developers who want a richer output target than plain text
  plus `MessageEntity`.
- Maintainers validating Bot API formatting compatibility.

## Outcomes

- A caller can pass raw Markdown to `richify()` and receive an object whose
  `to_dict()` result matches Telegram's `InputRichMessage` shape.
- The existing `convert()` API remains unchanged.
- Rich output preserves document structure where Telegram Rich Messages have a
  corresponding construct.
- Unsupported Markdown remains visible as text rather than disappearing.

## Public Contract

```python
from telegramify_markdown import richify

rich_message = richify(markdown)
payload = rich_message.to_dict()
```

`richify()` accepts:

| Parameter | Type | Default | Contract |
|---|---|---|---|
| `markdown` | `str` | required | Raw Markdown input |
| `mode` | `"html" | "markdown"` | `"html"` | `html` generates Telegram Rich HTML; `markdown` passes Markdown through as Rich Markdown |
| `is_rtl` | `bool | None` | `None` | Adds `is_rtl` only when not `None` |
| `skip_entity_detection` | `bool | None` | `None` | Adds `skip_entity_detection` only when not `None` |
| `latex_escape` | `bool` | `False` | When `html`, `False` keeps formula source for Telegram math rendering; `True` applies legacy Unicode conversion before parsing |

`InputRichMessage.to_dict()` returns exactly one of `html` or `markdown`, plus
optional `is_rtl` and `skip_entity_detection`.

## Conversion Semantics

The default `html` mode uses pyromark events and emits Telegram Rich HTML.

| Markdown / event | Rich HTML output |
|---|---|
| paragraph | `<p>...</p>` |
| heading levels 1-6 | `<h1>` to `<h6>` |
| strong | `<b>` |
| emphasis | `<i>` |
| strikethrough | `<s>` |
| spoiler `||...||` | `<tg-spoiler>` |
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

## Escaping Contract

- Text content is HTML-escaped.
- Attribute values are HTML-escaped.
- Code and formula content is escaped as text content.
- Raw unsupported HTML from input does not gain execution authority through the
  default backend.

## Limits

Telegram Rich Messages are subject to Telegram's published limits:

- 32768 UTF-8 characters in rich message text.
- 500 blocks, including nested blocks, list items, table rows, quotation blocks,
  and details blocks.
- 16 levels of nested formatting and blocks.
- 50 media attachments.
- 20 table columns.

`richify()` creates one payload. It does not split rich messages.

## Error Semantics

- `richify(..., mode=<unknown>)` raises `ValueError`.
- Empty input returns an empty Rich Message payload for the selected mode.
- The converter preserves visible content when a Markdown construct lacks a
  Telegram Rich HTML equivalent.

## Acceptance Cases

- Basic inline formatting produces nested Rich HTML tags without crossing tags.
- Headings, paragraphs, blockquotes, lists, tables, and code blocks produce
  block-level Rich HTML tags.
- Inline and display math preserve formula source in `<tg-math>` and
  `<tg-math-block>` when `latex_escape=False`.
- `to_dict()` omits optional fields when they are `None`.
- `mode="markdown"` passes Markdown through in the `markdown` field.
- Existing `convert()` and `telegramify()` behavior remains unchanged.
- Before opening a PR that changes Rich Message behavior, `pdm run test-live-rich`
  passes with real `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`; the test must
  reach `sendRichMessage` and receive a `Message.rich_message` witness from
  Telegram.

## External Authority

- @see https://core.telegram.org/bots/api#rich-message-formatting-options
- @see https://core.telegram.org/bots/api#inputrichmessage
- @see https://core.telegram.org/bots/api#sendrichmessage
