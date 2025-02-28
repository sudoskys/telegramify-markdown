import dataclasses
from enum import Enum
from typing import Tuple, List, Any, Union

TaskType = Tuple[str, List[Tuple[Any, Any]]]
SentType = List[Union["Text", "File", "Photo"]]


class ContentTypes(Enum):
    TEXT = "text"
    FILE = "file"
    PHOTO = "photo"


@dataclasses.dataclass
class ContentTrace:
    source_type: str
    extra: dict = dataclasses.field(default_factory=dict)

    def __init__(self, source_type: str, *, extra: dict = None):
        self.source_type = source_type
        self.extra = extra if extra is not None else {}


@dataclasses.dataclass
class Text:
    content: str
    content_trace: ContentTrace
    content_type: ContentTypes = ContentTypes.TEXT


@dataclasses.dataclass
class File:
    file_name: str
    file_data: bytes

    content_trace: ContentTrace
    caption: str = ""
    """Please use render_lines_func to render the content."""
    content_type: ContentTypes = ContentTypes.FILE


@dataclasses.dataclass
class Photo:
    file_name: str
    file_data: bytes

    content_trace: ContentTrace
    caption: str = ""
    """Please use render_lines_func to render the content."""
    content_type: ContentTypes = ContentTypes.PHOTO
