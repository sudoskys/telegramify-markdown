# telegramify-markdown Architecture

This document records code-confirmed or user-confirmed facts. Mark unknowns
honestly; do not guess.

## System Boundary

- In scope:
  - Markdown parsing through pyromark.
  - Telegram text formatting output: `MessageEntity`, MarkdownV2 fallback, and Rich Message input payloads.
  - Long-message splitting and optional code/Mermaid extraction.
- Out of scope:
  - Bot token management and message transport.
  - Telegram wrapper SDK ownership.
  - Non-Telegram rendering targets.

## Modules

| Module | Responsibility | Notes |
|---|---|---|
| `src/telegramify_markdown/converter.py` | pyromark event stream to plain text, entities, and segments | Maintains UTF-16 offsets and block spacing |
| `src/telegramify_markdown/entity.py` | `MessageEntity`, UTF-16 length, entity splitting | Library-agnostic Bot API dict output |
| `src/telegramify_markdown/mdv2.py` | Entity output to MarkdownV2 fallback | Handles escaping and rendered-length splitting |
| `src/telegramify_markdown/pipeline.py` | Async content pipeline | Emits `Text`, `File`, and `Photo` |
| `src/telegramify_markdown/rich.py` | Markdown to Bot API 10.1 Rich Message payload | Parallel backend for structured messages |
| `src/telegramify_markdown/latex_escape/` | LaTeX-to-Unicode conversion | Used by legacy entity output |
| `src/telegramify_markdown/mermaid.py` | Optional Mermaid rendering | Requires optional aiohttp and Pillow |

## Data Flow

```text
Raw Markdown
  -> pyromark event stream
  -> EventWalker
  -> plain text + MessageEntity
  -> Telegram sendMessage(..., entities=...)
```

```text
Raw Markdown
  -> pyromark event stream
  -> RichHtmlWalker
  -> InputRichMessage(html=...)
  -> Telegram sendRichMessage(..., rich_message=...)
```

```text
Raw Markdown
  -> convert_with_segments()
  -> process_markdown()
  -> Text | File | Photo
  -> caller sends via Telegram Bot API wrapper
```

## Authority And State

| Public question or durable fact | Source of truth | Readers | Failure behavior |
|---|---|---|---|
| Entity offsets and lengths | `entity.utf16_len()` and converter buffer accounting | `convert()`, `split_entities()`, `entities_to_markdownv2()` | Telegram rejects malformed entities |
| Rich Message payload shape | Telegram Bot API docs and `rich.InputRichMessage` | `richify()` callers | Telegram rejects malformed rich messages |
| Code/Mermaid extraction boundaries | `Segment` records from `convert_with_segments()` | `pipeline.process_markdown()` | Falls back to text/file behavior |

## External Dependencies

| Dependency | Required? | Purpose | Failure behavior |
|---|---|---|---|
| `pyromark` | yes | Markdown event parser | Conversion cannot run |
| `Pillow` | no | Mermaid image processing | Mermaid support reports unavailable |
| `aiohttp` | no | Mermaid rendering request | Mermaid support reports unavailable |
| Telegram Bot API | no for unit tests, yes for integration validation | Server-side contract oracle | Integration tests skip without token |
| `PyYAML` | no for runtime, yes for ADR tooling | ADR index/lint scripts | ADR Make targets fail until tests deps installed |

## Interfaces

| Interface | Owner | Contract |
|---|---|---|
| `convert(markdown, *, latex_escape=True)` | `converter.py` | Returns `(str, list[MessageEntity])` |
| `telegramify(content, ...)` | `__init__.py` / `pipeline.py` | Returns ordered `Text | File | Photo` items |
| `entities_to_markdownv2(text, entities=None)` | `mdv2.py` | Returns Telegram MarkdownV2 string |
| `richify(markdown, ...)` | `rich.py` | Returns `InputRichMessage` for Bot API 10.1 |

## Verification

```bash
pdm install -G tests
pdm run test
pdm run test-rich
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... pdm run test-live-rich
make adr-lint
make adr-index
```

Rich Message PRs require the live `sendRichMessage` check to pass against the
real Telegram Bot API before a PR is created.

## Known Unknowns

- Bot API 10.1 wrapper support is still catching up across Python Telegram libraries.
- Server-side Rich HTML parsing beyond the live fixture may expose additional
  edge cases as Telegram evolves the Rich Message parser.
