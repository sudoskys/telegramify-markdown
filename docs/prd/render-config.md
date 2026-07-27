# Render Configuration PRD

## Product Boundary

Owns how a caller chooses the symbols and Mermaid settings a conversion uses,
and how those choices are scoped. Covers `src/telegramify_markdown/config.py`
and the `config=` parameter on every conversion entry point.

Does not own what the symbols mean during conversion (that is the converter's
event semantics), nor Rich Message output, which renders structural HTML tags
and takes no symbol configuration.

## Users

| Actor | Need |
|---|---|
| Bot developer, single style | Set heading/list/rule symbols once at startup and forget them |
| Bot developer, per-chat style | Render concurrent requests with different symbols without cross-contamination |
| Library maintainer | Configure symbols in a test without leaking state into the next test |

## Data Flow Model

```text
RenderConfig  ──┬── global instance ── get_runtime_config() / RenderConfig()
                └── independent    ── RenderConfig.isolated() / cfg.copy()
                                       │
                        config= ───────┴──> convert()
                                            convert_with_segments()
                                            markdownify() / standardize()
                                            telegramify() ──> process_markdown()
                                                               └─> mermaid URL builders
```

### Data-Centered Decisions

**Authority.** A `RenderConfig` instance is the sole authority for the symbols
and Mermaid settings of the conversions it is passed to. Passing no config means
the global instance is the authority.

**Value semantics.** `Symbol` and `Mermaid` are mutable value holders owned by
exactly one `RenderConfig`. `isolated()` builds them fresh from defaults;
`copy()` deep-copies them from an existing config. Neither shares a holder with
another config, so mutating one config can never be observed through another.

**Scope is the caller's choice, not the library's.** The global instance exists
because a single-style bot should not have to thread a config through its call
stack. It is shared mutable state: a value written to it is visible to every
concurrent conversion that does not pass its own config. Callers that vary
symbols per request must own an independent config; the library cannot infer
request boundaries.

## Outcomes

| Outcome | Proof |
|---|---|
| A single-style bot configures once at startup | `get_runtime_config()` mutation is visible to later conversions that pass no config |
| Concurrent requests can use different symbols | Two threads rendering with two `isolated()` configs each get their own marker |
| Existing 1.x callers keep working unchanged | `RenderConfig()` returns the global instance; repeated construction does not reset settings |
| A config reaches every documented surface | `config=` changes output for `convert`, `markdownify`, `telegramify`, and Mermaid URLs |

## Public Contract

### Obtaining a config

| Call | Returns |
|---|---|
| `get_runtime_config()` | The process-global instance |
| `RenderConfig()` | The process-global instance (same object) |
| `RenderConfig.isolated()` | A new instance carrying library defaults |
| `cfg.copy()` | A new instance carrying `cfg`'s current values |

`RenderConfig` is a class: `isinstance(cfg, RenderConfig)` is valid, and
`RenderConfig` is usable in type annotations.

Constructing `RenderConfig()` more than once must not reset already-configured
values — the global instance is initialised exactly once per process.

### Configurable fields

`cfg.markdown_symbol` (`Symbol`), read-only attribute holding mutable fields:

| Field | Default | Applies to |
|---|---|---|
| `heading_level_1` … `heading_level_6` | `📌` `✏️` `📚` `🔖` `""` `""` | Heading text prefix |
| `image` | `🖼` | Image placeholder |
| `link` | `🔗` | Link symbol |
| `task_completed` / `task_uncompleted` | `✅` / `☑️` | Task list markers, replacing the list marker |
| `horizontal_rule` | `————————` | Thematic break |
| `unordered_list_item` | `⦁` | Unordered list marker, written after the indent |
| `ordered_list_suffix` | `.` | Follows the item number, as in `1. ` |

`cfg.mermaid` (`Mermaid`), read-only attribute holding `theme`, `width`,
`scale`, `image_type`.

`cfg.cite_expandable` (`bool`, read/write): long blockquotes become
`expandable_blockquote`.

List markers are plain text and carry no entity.

### Accepting a config

| Entry point | Effect of `config=` |
|---|---|
| `convert()` / `convert_with_segments()` | Symbols used while walking events |
| `markdownify()` / `standardize()` | Symbols, before MarkdownV2 rendering |
| `telegramify()` | Symbols, plus Mermaid theme/width/scale/type for rendered diagrams |
| `richify()` / `telegramify_rich()` | None — Rich HTML emits structural tags and reads no symbols |

Omitting `config=` uses the global instance.

## Error Semantics

Symbol fields are unvalidated strings. An empty string renders no prefix; that
is the documented way to suppress heading emoji. A multi-character marker is
written verbatim.

Mutating a config concurrently with a conversion that reads it is a caller
error; the library performs no locking. Independent configs are the mechanism
for concurrent use.

## Acceptance Cases

| Case | Expectation |
|---|---|
| `RenderConfig() is get_runtime_config()` | True |
| `RenderConfig()` twice after setting a field | Field keeps its set value |
| `isinstance(get_runtime_config(), RenderConfig)` | True |
| `isolated()` after mutating the global | Carries library defaults, not the global's values |
| Mutating an `isolated()` config | Global is unchanged |
| `copy()` of a mutated global | Carries the global's values, then diverges independently |
| Two threads, two `isolated()` configs, same markdown | Each renders its own marker |
| `telegramify(config=cfg)` with `unordered_list_item = "-"` | Output uses `-`, global unchanged |
| `get_mermaid_ink_url(diagram, cfg)` with `width = 4242` | URL carries `width=4242`; omitting `cfg` carries the global width |

## External Authority

Telegram imposes no symbol vocabulary: headings, list markers, and thematic
rules do not exist in the entity model, so every symbol here is a rendering
choice this library makes on the caller's behalf, not an API requirement.
