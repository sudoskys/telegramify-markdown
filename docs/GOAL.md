# telegramify-markdown Goal

> **Positioning**: telegramify-markdown converts raw Markdown into Telegram-ready output while avoiding MarkdownV2 escaping failures.

## Users

- Python developers building Telegram bots that send LLM output, README-style Markdown, code snippets, diagrams, and long technical messages.
- Maintainers who need deterministic conversion behavior across Telegram Bot API formatting surfaces.

## What This Project Does

- Converts Markdown into plain text plus Telegram `MessageEntity` lists.
- Splits long output and extracts code blocks or Mermaid diagrams through the async pipeline.
- Converts entity output back to MarkdownV2 when middleware cannot send entities.
- Provides optional Rich Message output for Bot API 10.1 structured messages.

## What This Project Does Not Do

- It does not own Telegram Bot API transport, authentication, retry, or bot lifecycle.
- It does not make Mermaid rendering a core dependency.
- It does not change `convert()` away from `tuple[str, list[MessageEntity]]`.

## Success Criteria

- Conversion output is accepted by Telegram Bot API validation.
- UTF-16 entity offsets remain correct for emoji, CJK, and mixed text.
- Public APIs stay small and documented.
- Optional features do not add required dependencies to the core converter.

## Constraints

- Python 3.10+.
- Project commands run through PDM.
- Core runtime depends on pyromark.
- Telegram `MessageEntity` offsets and lengths are UTF-16 code units.
- Rich Message support follows Telegram Bot API 10.1 contracts.

## Unknowns

- Which Python Telegram wrappers will expose first-class `sendRichMessage` helpers after Bot API 10.1.
- Telegram server-side edge cases for Rich HTML parsing beyond the published Bot API documentation.
