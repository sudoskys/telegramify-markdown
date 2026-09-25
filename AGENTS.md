# telegramify-markdown Agent Guide

This file routes agent work. It is not a README, tutorial, or changelog.

## Task Routing

| Task type | First read | Workflow / skill | Verification gate |
|---|---|---|---|
| Understand purpose | `docs/GOAL.md` or `README.md` | goal and boundary extraction | Restate goal, users, non-goals, unknowns |
| Plan roadmap work | `docs/ROADMAP.md` | Flag-based decomposition | Updated Flag set or explicit no-change reason |
| Product/API contract change | `docs/prd/README.md` | per-boundary PRD update | Living PRD updated; outcomes and contracts changed, not cutover steps |
| Rich Message support | `docs/prd/rich-message.md` | PRD contract + converter implementation | Golden HTML tests, payload tests, `pdm run test`, and live `pdm run test-live-rich` before PR |
| Architecture decision | `docs/adr/ACTIVE.md` | ADR decision workflow | ADR has invariant, alternatives, verification, and `frontmatter.prds` when applicable |
| Code change | nearest source file and tests | Python/unittest workflow | Focused tests; broader `pdm run test` when conversion behavior changes |
| Test strategy | existing tests and failure evidence | `testing-methodology` | Risk, oracle, and fidelity are named |
| Telegram API compatibility | official Bot API docs and `tests/test_server.py` | research + integration validation | Raw Bot API or wrapper-specific validation when available |

## Quick Commands

```bash
pdm install
pdm install -G tests
pdm install -G mermaid
pdm run test
pdm run test-rich
pdm run test-live-rich
pdm build
make adr-lint
make adr-index
```

## Project Rules

always:
- Communicate with the user in Chinese and address them as "研究员".
- Route the task before editing.
- Use PDM for project commands. Do not use `pip install -e .` or direct `python -m unittest` for normal verification.
- Understand the pyromark event-stream state machine before changing conversion logic.
- Keep core runtime dependencies minimal. The core converter depends on pyromark; Mermaid rendering uses optional Pillow and aiohttp.
- Preserve all Telegram entity offsets and lengths as UTF-16 code units.
- Add public API docstrings.
- Write code comments and docstrings in English. Chat with the user in Chinese.
- Do not create a PR for Rich Message changes until `pdm run test-live-rich` passes against the real Telegram Bot API with `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

ask first:
- Delete files or discard uncommitted changes.
- Add new infrastructure, paid services, or broad compatibility layers.
- Assume backward compatibility is required when consumers are unknown.

never:
- Commit secrets.
- Invent project commands, goals, architecture, or Telegram API behavior.
- Treat generated output, screenshots, or mocks as source of truth.
- Modify `convert()` to return a different shape; it returns `tuple[str, list[MessageEntity]]`.

## Architecture Map

```text
Markdown
  -> preprocessing: spoiler and optional LaTeX-to-Unicode for legacy entity output
  -> pyromark.events_with_range(...)
  -> converter.EventWalker
  -> convert(): plain text + MessageEntity
  -> telegramify(): Text | File | Photo pipeline
  -> entities_to_markdownv2(): MarkdownV2 fallback
```

Rich Message support is a parallel backend, not a replacement for `convert()`.
Read `docs/prd/rich-message.md` before editing `src/telegramify_markdown/rich.py`.
