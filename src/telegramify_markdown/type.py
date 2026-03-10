"""0.x compat module. Migrate to telegramify_markdown.content."""

from __future__ import annotations

import warnings as _warnings

_warnings.warn(
    "telegramify_markdown.type is deprecated and will be removed in 2.0. "
    "Use telegramify_markdown.content instead.",
    DeprecationWarning,
    stacklevel=2,
)

from telegramify_markdown.content import (  # noqa: E402, F401
    ContentTrace,
    ContentType as ContentTypes,
    File,
    Photo,
    Text,
)
from typing import List, Tuple, Any, Union  # noqa: E402, F401

SentType = List[Union[Text, File, Photo]]
TaskType = Tuple[str, List[Tuple[Any, Any]]]

__all__ = [
    "ContentTypes",
    "ContentTrace",
    "Text",
    "File",
    "Photo",
    "SentType",
    "TaskType",
]
