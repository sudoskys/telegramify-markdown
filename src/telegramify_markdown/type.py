import dataclasses
from abc import ABCMeta
from enum import Enum
from typing import Tuple, List, Any, Union

TaskType = Tuple[str, List[Tuple[Any, Any]]]
SentType = List[Union["Text", "File", "Photo"]]


class ContentTypes(Enum):
    TEXT = "text"
    FILE = "file"
    PHOTO = "photo"


class RenderedContent(object, metaclass=ABCMeta):
    """
    The rendered content.

    - content: str
    - content_type: ContentTypes
    """
    content_type: ContentTypes


@dataclasses.dataclass
class Text(RenderedContent):
    content: str
    content_type: ContentTypes = ContentTypes.TEXT


@dataclasses.dataclass
class File(RenderedContent):
    file_name: str
    file_data: bytes
    caption: str = ""
    content_type: ContentTypes = ContentTypes.FILE


@dataclasses.dataclass
class Photo(RenderedContent):
    file_name: str
    file_data: bytes
    caption: str = ""
    content_type: ContentTypes = ContentTypes.PHOTO
