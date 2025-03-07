class Symbol:
    def __init__(self):
        self.head_level_1: str = "\N{PUSHPIN}"                   # 📌
        self.head_level_2: str = "\N{PENCIL}"                    # ✏️
        self.head_level_3: str = "\N{BOOKS}"                     # 📚
        self.head_level_4: str = "\N{BOOKMARK}"                  # 🔖
        self.image: str = "\N{FRAME WITH PICTURE}"               # 🖼
        self.link: str = "\N{LINK SYMBOL}"                       # 🔗
        self.task_completed: str = "\N{WHITE HEAVY CHECK MARK}"  # ✅
        self.task_uncompleted: str = "\N{BALLOT BOX WITH CHECK}" # ☑️


class CustomConfig:
    _instance = None
    _markdown_symbol: Symbol
    _cite_expandable: bool
    _strict_markdown: bool
    _unescape_html: bool

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._markdown_symbol = Symbol()
            cls._instance._cite_expandable = True
            cls._instance._strict_markdown = True
            cls._instance._unescape_html = False
        return cls._instance

    @property
    def markdown_symbol(self) -> Symbol:
        return self._markdown_symbol

    @property
    def cite_expandable(self) -> bool:
        return self._cite_expandable

    @cite_expandable.setter
    def cite_expandable(self, value: bool):
        self._cite_expandable = value

    @property
    def strict_markdown(self) -> bool:
        return self._strict_markdown

    @strict_markdown.setter
    def strict_markdown(self, value: bool):
        self._strict_markdown = value

    @property
    def unescape_html(self) -> bool:
        return self._unescape_html

    @unescape_html.setter
    def unescape_html(self, value: bool):
        self._unescape_html = value


# Global accessor function for accessing the CustomConfig singleton
def get_config() -> CustomConfig:
    return CustomConfig()


# NOTE: Deprecated global variables included below for backward compatibility.
# These should be removed in the next major version bump following the deprecation warning period.
import inspect
import warnings
warnings.simplefilter("default", DeprecationWarning)

warnings.warn_explicit("markdown_symbol is deprecated, and will be removed in a future release. Use get_config().markdown_symbol instead", DeprecationWarning, filename=__file__, lineno=inspect.currentframe().f_lineno + 1)
markdown_symbol = get_config().markdown_symbol

warnings.warn_explicit("cite_expandable is deprecated, and will be removed in a future release. Use get_config().cite_expandable instead", DeprecationWarning, filename=__file__, lineno=inspect.currentframe().f_lineno + 1)
cite_expandable = get_config().cite_expandable

warnings.warn_explicit("strict_markdown is deprecated, and will be removed in a future release. Use get_config().strict_markdown instead", DeprecationWarning, filename=__file__, lineno=inspect.currentframe().f_lineno + 1)
strict_markdown = get_config().strict_markdown

warnings.warn_explicit("unescape_html is deprecated, and will be removed in a future release. Use get_config().unescape_html instead", DeprecationWarning, filename=__file__, lineno=inspect.currentframe().f_lineno + 1)
unescape_html = get_config().unescape_html
