from __future__ import annotations

import dataclasses
from typing import Optional


def utf16_len(text: str) -> int:
    """Return the length of text measured in UTF-16 code units.

    Telegram measures entity offsets and lengths in UTF-16 code units,
    not Python str characters. Characters outside the BMP (codepoint > 0xFFFF)
    take 2 UTF-16 code units (a surrogate pair); all others take 1.
    """
    count = 0
    for ch in text:
        count += 2 if ord(ch) > 0xFFFF else 1
    return count


@dataclasses.dataclass(slots=True)
class MessageEntity:
    """Telegram-compatible MessageEntity.

    offset and length are in UTF-16 code units.
    This is library-agnostic -- not tied to any specific bot library.
    """

    type: str
    offset: int
    length: int
    url: Optional[str] = None
    language: Optional[str] = None
    custom_emoji_id: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to a dict suitable for the Telegram Bot API."""
        result: dict = {"type": self.type, "offset": self.offset, "length": self.length}
        if self.url is not None:
            result["url"] = self.url
        if self.language is not None:
            result["language"] = self.language
        if self.custom_emoji_id is not None:
            result["custom_emoji_id"] = self.custom_emoji_id
        return result


def _find_newline_positions(text: str) -> list[int]:
    """Find newline positions in text suitable for splitting.

    Returns a list of Python string indices right after each newline,
    sorted in order of appearance.
    """
    points: list[int] = []
    for i, ch in enumerate(text):
        if ch == "\n":
            points.append(i + 1)
    return points


def _build_utf16_offset_table(text: str) -> list[int]:
    """Build a cumulative UTF-16 offset table for each character position.

    Returns a list of length len(text)+1 where result[i] is the UTF-16
    offset of text[i] (or the total length for i == len(text)).
    """
    offsets = [0] * (len(text) + 1)
    cum = 0
    for i, ch in enumerate(text):
        offsets[i] = cum
        cum += 2 if ord(ch) > 0xFFFF else 1
    offsets[len(text)] = cum
    return offsets


def split_entities(
    text: str,
    entities: list[MessageEntity],
    max_utf16_len: int,
) -> list[tuple[str, list[MessageEntity]]]:
    """Split (text, entities) into chunks not exceeding max_utf16_len UTF-16 code units.

    Tries to split at newline boundaries. Entities that span a split boundary
    are clipped into both chunks.
    """
    total = utf16_len(text)
    if total <= max_utf16_len:
        return [(text, list(entities))]

    offsets = _build_utf16_offset_table(text)

    # Build list of candidate split points (newline positions)
    split_points = _find_newline_positions(text)

    # Determine actual split positions using greedy packing
    chunks_ranges: list[tuple[int, int]] = []  # (py_start, py_end)
    py_start = 0

    while py_start < len(text):
        utf16_start = offsets[py_start]
        utf16_budget = utf16_start + max_utf16_len

        if offsets[len(text)] <= utf16_budget:
            # Remaining text fits
            chunks_ranges.append((py_start, len(text)))
            break

        # Find the last split point that fits within budget
        best_split = None
        for sp in split_points:
            if sp <= py_start:
                continue
            if offsets[sp] <= utf16_budget:
                best_split = sp
            else:
                break

        if best_split is None or best_split == py_start:
            # No newline split fits -- hard split at max_utf16_len boundary
            best_split = py_start
            for i in range(py_start + 1, len(text) + 1):
                if offsets[i] > utf16_budget:
                    best_split = i - 1
                    break
            if best_split == py_start:
                best_split = py_start + 1  # Force progress

        chunks_ranges.append((py_start, best_split))
        py_start = best_split

    # Assign entities to chunks, clipping as needed
    result: list[tuple[str, list[MessageEntity]]] = []
    for chunk_py_start, chunk_py_end in chunks_ranges:
        chunk_text = text[chunk_py_start:chunk_py_end]
        chunk_utf16_start = offsets[chunk_py_start]
        chunk_utf16_end = offsets[chunk_py_end]
        chunk_entities: list[MessageEntity] = []

        for ent in entities:
            ent_start = ent.offset
            ent_end = ent.offset + ent.length

            # Check overlap
            if ent_end <= chunk_utf16_start or ent_start >= chunk_utf16_end:
                continue  # No overlap

            # Clip to chunk boundaries
            clipped_start = max(ent_start, chunk_utf16_start)
            clipped_end = min(ent_end, chunk_utf16_end)
            clipped_length = clipped_end - clipped_start

            if clipped_length <= 0:
                continue

            chunk_entities.append(
                MessageEntity(
                    type=ent.type,
                    offset=clipped_start - chunk_utf16_start,
                    length=clipped_length,
                    url=ent.url,
                    language=ent.language,
                    custom_emoji_id=ent.custom_emoji_id,
                )
            )

        result.append((chunk_text, chunk_entities))

    return result
