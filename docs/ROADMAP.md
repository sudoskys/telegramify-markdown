# telegramify-markdown Roadmap

> **Goal**: [GOAL.md](GOAL.md) | **ADR Board**: [ACTIVE.md](adr/ACTIVE.md)

Decompose work into Flags: discrete end-state declarations, each independently verifiable.

## Current Focus

Rich Message support for Telegram Bot API 10.1 while preserving the existing entity-based API.

## Dependency Map

```text
Flag A: Project control plane exists ← no dependencies
  Flag B: Rich Message PRD defines the product contract ← depends on Flag A
    Flag C: richify emits Bot API 10.1 InputRichMessage payloads ← depends on Flag B
    Flag D: MessageEntity supports current date_time fields ← depends on Flag B
      Flag E: Conversion and compatibility tests pass ← depends on Flag C and Flag D
      Flag F: Real Telegram sendRichMessage accepts richify output ← depends on Flag C
```

## Flags

| Flag | End-state (WHAT, not HOW) | Depends on | Verification | Status |
|---|---|---|---|---|
| A | Project docs, ADR board, and ADR Make targets exist | none | `make adr-lint`, `make adr-index` | Completed |
| B | Rich Message behavior has a living PRD | Flag A | `docs/prd/rich-message.md` exists and matches Bot API docs | Completed |
| C | `richify()` returns documented Rich Message payloads | Flag B | `tests/test_rich.py` and `pdm run test` | Completed |
| D | `MessageEntity` covers Bot API `date_time` fields | Flag B | entity and MarkdownV2 tests | Completed |
| E | Existing public API remains compatible | Flag C, Flag D | full `pdm run test` | Completed |
| F | Telegram accepts `richify()` output through real `sendRichMessage` | Flag C | `pdm run test-live-rich` with `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` | Completed |

## Deferred Work

| Item | Trigger | Why deferred |
|---|---|---|
| First-class `telegramify_rich()` splitting | Users need rich messages over Bot API 10.1 32768-character or 500-block limits | Rich splitting has different semantics from `split_entities()` |
| Native structured RichBlock object builder | Telegram exposes or wrappers stabilize a typed RichBlock send path | `InputRichMessage(html=...)` is the official input contract |

## Recent Evidence

- 2026-06-12: `pdm run test` passed before Rich Message implementation, 196 tests OK and 1 skipped.
- 2026-06-12: `pyromark.events_with_range()` confirmed heading, list, task list, table, code block, display math, image, and footnote events are available.
- 2026-06-12: `pdm run test-rich` passed, 15 tests OK.
- 2026-06-12: `pdm run test-live-rich` passed against the real Telegram Bot API and returned `Message.rich_message`.
- 2026-06-12: `pdm run test` passed, 218 tests OK and 1 skipped.
- 2026-06-12: `make adr-lint`, `make adr-index`, and `pdm build` passed.
