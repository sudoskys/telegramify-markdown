from __future__ import annotations

import dataclasses
import warnings
from enum import Enum

from telegramify_markdown.entity import MessageEntity


class ContentType(Enum):
    TEXT = "text"
    FILE = "file"
    PHOTO = "photo"


# 0.x compat alias
ContentTypes = ContentType


@dataclasses.dataclass
class ContentTrace:
    source_type: str
    extra: dict = dataclasses.field(default_factory=dict)


def _deprecated_property(old: str, new: str, is_mdv2: bool = False):
    """Create a property that emits a DeprecationWarning on access."""

    def _getter(self):
        warnings.warn(
            f".{old} is deprecated and will be removed in 2.0. Use .{new} instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if is_mdv2:
            from telegramify_markdown.mdv2 import entities_to_markdownv2

            text_attr = new  # "text" or "caption_text"
            entities_attr = (
                "entities" if text_attr == "text" else "caption_entities"
            )
            return entities_to_markdownv2(
                getattr(self, text_attr), getattr(self, entities_attr)
            )
        return getattr(self, new)

    return property(_getter)


@dataclasses.dataclass
class Text:
    text: str
    entities: list[MessageEntity]
    content_trace: ContentTrace
    content_type: ContentType = ContentType.TEXT

    # 0.x compat: .content → MarkdownV2 string
    content = _deprecated_property("content", "text", is_mdv2=True)


@dataclasses.dataclass
class File:
    file_name: str
    file_data: bytes
    content_trace: ContentTrace
    caption_text: str = ""
    caption_entities: list[MessageEntity] = dataclasses.field(default_factory=list)
    content_type: ContentType = ContentType.FILE

    # 0.x compat: .caption → MarkdownV2 string
    caption = _deprecated_property("caption", "caption_text", is_mdv2=True)


@dataclasses.dataclass
class Photo:
    file_name: str
    file_data: bytes
    content_trace: ContentTrace
    caption_text: str = ""
    caption_entities: list[MessageEntity] = dataclasses.field(default_factory=list)
    content_type: ContentType = ContentType.PHOTO

    # 0.x compat: .caption → MarkdownV2 string
    caption = _deprecated_property("caption", "caption_text", is_mdv2=True)
