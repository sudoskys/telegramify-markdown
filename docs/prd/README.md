# PRD Index

`docs/prd/` holds product and API specifications: what the system should do,
what is out of scope, and what we currently accept as true. Revising a PRD is
normal design work. `docs/adr/` holds architecture decisions: why a path was
chosen and what was rejected. The two link in one direction: ADR frontmatter
`prds: [slug]` references PRD slugs; PRDs do not back-link ADRs.

## Product Boundaries

| PRD | Boundary | Owner |
|---|---|---|
| [render-config](./render-config.md) | Symbol/Mermaid configuration and its scoping | `src/telegramify_markdown/config.py` |
| [rich-message](./rich-message.md) | Telegram Bot API 10.1 Rich Message output | `src/telegramify_markdown/rich.py` |

## System Architecture

telegramify-markdown owns Markdown-to-Telegram formatting transformations. It
does not own Telegram transport or wrapper SDK compatibility.

```text
Markdown input
  -> pyromark event stream
  -> one output backend:
       - plain text + MessageEntity
       - MarkdownV2 string
       - InputRichMessage
```

The existing entity backend remains the stable default. Rich Message support is
a parallel output surface for Bot API 10.1 structured messages.

## Split Standard

Do not split PRDs by table count. Split by product boundary. A PRD deserves its
own file when at least one boundary is independent enough that merging would
hide real decisions:

| Boundary | Split signal |
|---|---|
| Actor | Different primary actor: bot developer, maintainer, Telegram API consumer |
| Business outcome | Different success metric or product promise |
| State machine | Different lifecycle: message conversion, splitting, media rendering |
| Authority | Different source of truth: Telegram API contract, parser event stream, generated output |
| Vocabulary | Same word means different things across backends |
| Acceptance gate | Different proof: unit golden, server validation, pipeline output |
| Interface boundary | Different public/internal contract |

## PRD Standard

A PRD must let a new engineer rebuild the owned product surface without reading
the code. If the current implementation disappeared, an engineer should be able
to use the PRD to derive:

- owned data facts and authorities;
- public/internal interfaces and required fields;
- conversion semantics;
- error semantics;
- acceptance cases that prove the contract works.

Forbidden content in PRD:

- Implementation steps or cutover order
- Compatibility stance labels
- Status-machine vocabulary
- "we might" or "we will probably" phrasing
- ADR rationale that belongs in `docs/adr/`
