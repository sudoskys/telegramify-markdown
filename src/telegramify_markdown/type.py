from abc import ABCMeta
from enum import Enum
from typing import Tuple, List, Any, Union

from pydantic import BaseModel, Field

TaskType = Tuple[str, List[Tuple[Any, Any]]]
SentType = List[Union["Text", "File", "Photo"]]


class ContentTypes(Enum):
    TEXT = "text"
    FILE = "file"
    PHOTO = "photo"


class ContentTrace(BaseModel):
    """
    The content trace.

    - content: str
    - content_type: ContentTypes
    """
    source_type: str
    extra: dict = Field(default_factory=dict)


class RenderedContent(BaseModel, metaclass=ABCMeta):
    """
    The rendered content.

    - content: str
    - content_type: ContentTypes
    """
    content_trace: ContentTrace
    content_type: ContentTypes


class Text(RenderedContent):
    content: str
    content_trace: ContentTrace
    content_type: ContentTypes = ContentTypes.TEXT


class File(RenderedContent):
    file_name: str
    file_data: bytes

    caption: str = ""
    """Please use render_lines_func to render the content."""

    content_trace: ContentTrace
    content_type: ContentTypes = ContentTypes.FILE


class Photo(RenderedContent):
    file_name: str
    file_data: bytes

    caption: str = ""
    """Please use render_lines_func to render the content."""
    content_trace: ContentTrace
    content_type: ContentTypes = ContentTypes.PHOTO
