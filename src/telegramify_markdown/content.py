from __future__ import annotations

import dataclasses
from enum import Enum

from telegramify_markdown.entity import MessageEntity


class ContentType(Enum):
    TEXT = "text"
    FILE = "file"
    PHOTO = "photo"


@dataclasses.dataclass
class ContentTrace:
    source_type: str
    extra: dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Text:
    text: str
    entities: list[MessageEntity]
    content_trace: ContentTrace
    content_type: ContentType = ContentType.TEXT


@dataclasses.dataclass
class File:
    file_name: str
    file_data: bytes
    content_trace: ContentTrace
    caption_text: str = ""
    caption_entities: list[MessageEntity] = dataclasses.field(default_factory=list)
    content_type: ContentType = ContentType.FILE


@dataclasses.dataclass
class Photo:
    file_name: str
    file_data: bytes
    content_trace: ContentTrace
    caption_text: str = ""
    caption_entities: list[MessageEntity] = dataclasses.field(default_factory=list)
    content_type: ContentType = ContentType.PHOTO
