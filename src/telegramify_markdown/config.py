"""Render configuration.

``get_runtime_config()`` returns the process-global config; setting it once at
startup is the common case. When rendering must vary per session or per thread,
take an independent config with ``RenderConfig.isolated()`` and pass it to
``convert(config=...)`` / ``telegramify(config=...)`` / ``markdownify(config=...)``.

The global instance is shared mutable state: writing to it inside a handler is
visible to every concurrent conversion that does not carry its own config.
pyTelegramBotAPI runs handlers on multiple threads by default, and on the
asyncio side "mutate global -> await -> render" always yields control in
between. Per-request configuration requires isolated().
"""

from __future__ import annotations

import copy


class Symbol:
    def __init__(self):
        self.heading_level_1: str = "\N{PUSHPIN}"                   # 📌
        self.heading_level_2: str = "\N{PENCIL}"                    # ✏️
        self.heading_level_3: str = "\N{BOOKS}"                     # 📚
        self.heading_level_4: str = "\N{BOOKMARK}"                  # 🔖
        self.heading_level_5: str = ""
        self.heading_level_6: str = ""
        self.image: str = "\N{FRAME WITH PICTURE}"               # 🖼
        self.link: str = "\N{LINK SYMBOL}"                       # 🔗
        self.task_completed: str = "\N{WHITE HEAVY CHECK MARK}"  # ✅
        self.task_uncompleted: str = "\N{BALLOT BOX WITH CHECK}" # ☑️
        self.horizontal_rule: str = "————————"
        # List markers: written after the indent, before the item text.
        # Always plain text, never covered by an entity.
        # @see https://github.com/sudoskys/telegramify-markdown/issues/116
        self.unordered_list_item: str = "\N{Z NOTATION SPOT}"    # ⦁
        self.ordered_list_suffix: str = "."


class Mermaid:
    def __init__(self):
        self.theme: str = "default"
        self.width: int = 1000
        self.scale: int = 2
        self.image_type: str = "webp"


class RenderConfig:
    """Render configuration.

    Bare construction returns the global instance, equivalent to
    ``get_runtime_config()`` and matching 1.x behaviour. For configs that do not
    affect each other, use :meth:`isolated`.
    """

    _global: "RenderConfig | None" = None

    def __new__(cls) -> "RenderConfig":
        if cls._global is None:
            cls._global = super().__new__(cls)
            cls._global._init_defaults()
        return cls._global

    # No __init__ on purpose: repeated construction must not reset settings
    # that have already been applied to the global instance.
    def _init_defaults(self) -> None:
        self._markdown_symbol = Symbol()
        self._mermaid = Mermaid()
        self._cite_expandable = True

    @classmethod
    def isolated(cls) -> "RenderConfig":
        """Build an independent config, sharing nothing with the global one."""
        instance = super().__new__(cls)
        instance._init_defaults()
        return instance

    def copy(self) -> "RenderConfig":
        """Copy this config into an independent one, symbol tables included."""
        instance = super().__new__(type(self))
        instance._markdown_symbol = copy.deepcopy(self._markdown_symbol)
        instance._mermaid = copy.deepcopy(self._mermaid)
        instance._cite_expandable = self._cite_expandable
        return instance

    @property
    def markdown_symbol(self) -> Symbol:
        return self._markdown_symbol

    @property
    def mermaid(self) -> Mermaid:
        return self._mermaid

    @property
    def cite_expandable(self) -> bool:
        return self._cite_expandable

    @cite_expandable.setter
    def cite_expandable(self, value: bool):
        self._cite_expandable = value


# Global accessor function for accessing the RenderConfig singleton
def get_runtime_config() -> RenderConfig:
    return RenderConfig()
