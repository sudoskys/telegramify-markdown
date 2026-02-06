"""Pipeline: convert markdown → list[Text | File | Photo] with splitting."""

from __future__ import annotations

from telegramify_markdown.converter import Segment, convert_with_segments
from telegramify_markdown.entity import MessageEntity, split_entities, utf16_len
from telegramify_markdown.logger import logger
from telegramify_markdown.code_file import get_filename
from telegramify_markdown.content import ContentTrace, File, Photo, Text


def _strip_newlines_adjust(
    text: str, entities: list[MessageEntity]
) -> tuple[str, list[MessageEntity]]:
    """Strip leading/trailing newlines from text and adjust entity offsets."""
    # Count leading newlines
    leading = 0
    for ch in text:
        if ch == "\n":
            leading += 1
        else:
            break

    # Count trailing newlines
    trailing = 0
    for ch in reversed(text):
        if ch == "\n":
            trailing += 1
        else:
            break

    if leading == 0 and trailing == 0:
        return text, entities

    end = len(text) - trailing if trailing else len(text)
    stripped = text[leading:end]
    if not stripped:
        return stripped, []

    # Newlines are each 1 UTF-16 code unit
    leading_utf16 = leading
    new_utf16_len = utf16_len(stripped)

    adjusted: list[MessageEntity] = []
    for ent in entities:
        new_offset = ent.offset - leading_utf16
        new_end = new_offset + ent.length
        # Skip entities entirely outside the stripped range
        if new_end <= 0 or new_offset >= new_utf16_len:
            continue
        # Clip to boundaries
        new_offset = max(0, new_offset)
        new_end = min(new_end, new_utf16_len)
        new_length = new_end - new_offset
        if new_length <= 0:
            continue
        adjusted.append(
            MessageEntity(
                type=ent.type,
                offset=new_offset,
                length=new_length,
                url=ent.url,
                language=ent.language,
                custom_emoji_id=ent.custom_emoji_id,
            )
        )

    return stripped, adjusted


def _slice_text_entities(
    full_text: str,
    full_entities: list[MessageEntity],
    py_start: int,
    py_end: int,
    utf16_start: int,
    utf16_end: int,
) -> tuple[str, list[MessageEntity]]:
    """Extract a substring and its overlapping entities, adjusting offsets."""
    chunk_text = full_text[py_start:py_end]
    chunk_entities: list[MessageEntity] = []
    for ent in full_entities:
        ent_start = ent.offset
        ent_end = ent.offset + ent.length
        # Check overlap with [utf16_start, utf16_end)
        if ent_end <= utf16_start or ent_start >= utf16_end:
            continue
        clipped_start = max(ent_start, utf16_start)
        clipped_end = min(ent_end, utf16_end)
        clipped_length = clipped_end - clipped_start
        if clipped_length <= 0:
            continue
        chunk_entities.append(
            MessageEntity(
                type=ent.type,
                offset=clipped_start - utf16_start,
                length=clipped_length,
                url=ent.url,
                language=ent.language,
                custom_emoji_id=ent.custom_emoji_id,
            )
        )
    return chunk_text, chunk_entities


async def process_markdown(
    content: str,
    *,
    max_message_length: int = 4096,
    latex_escape: bool = True,
) -> list[Text | File | Photo]:
    """Full async pipeline: markdown → list of sendable content pieces.

    1. Convert markdown to (text, entities, segments) via converter
    2. Walk segments in order:
       - mermaid → render as Photo (or File on failure)
       - code_block → extract as File
       - text regions → collect and split by max_message_length
    3. Return ordered list of Text | File | Photo
    """
    full_text, full_entities, segments = convert_with_segments(
        content, latex_escape=latex_escape
    )

    result: list[Text | File | Photo] = []

    # Build a sorted list of code/mermaid segments
    special_segments = [s for s in segments if s.kind in ("code_block", "mermaid")]
    special_segments.sort(key=lambda s: s.text_start)

    # Walk through the text, interleaving text chunks with special segments
    cursor_py = 0
    cursor_utf16 = 0

    for seg in special_segments:
        # Emit text before this segment
        if seg.text_start > cursor_py:
            text_chunk, text_entities = _slice_text_entities(
                full_text, full_entities,
                cursor_py, seg.text_start,
                cursor_utf16, seg.utf16_start,
            )
            text_chunk, text_entities = _strip_newlines_adjust(text_chunk, text_entities)
            if text_chunk:
                _append_text_chunks(result, text_chunk, text_entities, max_message_length)

        # Handle special segment
        if seg.kind == "mermaid":
            await _handle_mermaid(result, seg)
        elif seg.kind == "code_block":
            _handle_code_block(result, seg)

        cursor_py = seg.text_end
        cursor_utf16 = seg.utf16_end

    # Emit remaining text after last special segment
    if cursor_py < len(full_text):
        text_chunk, text_entities = _slice_text_entities(
            full_text, full_entities,
            cursor_py, len(full_text),
            cursor_utf16, utf16_len(full_text),
        )
        text_chunk, text_entities = _strip_newlines_adjust(text_chunk, text_entities)
        if text_chunk:
            _append_text_chunks(result, text_chunk, text_entities, max_message_length)

    # If no output was generated, emit empty text
    if not result and full_text.strip():
        _append_text_chunks(result, full_text.strip(), full_entities, max_message_length)

    return result


def _append_text_chunks(
    result: list[Text | File | Photo],
    text: str,
    entities: list[MessageEntity],
    max_message_length: int,
) -> None:
    """Split text by max_message_length and emit Text objects."""
    chunks = split_entities(text, entities, max_message_length)
    for chunk_text, chunk_entities in chunks:
        chunk_text, chunk_entities = _strip_newlines_adjust(chunk_text, chunk_entities)
        if chunk_text:
            result.append(
                Text(
                    text=chunk_text,
                    entities=chunk_entities,
                    content_trace=ContentTrace(source_type="text"),
                )
            )


def _handle_code_block(
    result: list[Text | File | Photo],
    seg: Segment,
) -> None:
    """Extract a code block as a File."""
    lang = seg.language or ""
    raw_code = seg.raw_code
    file_name = get_filename(raw_code, lang)
    result.append(
        File(
            file_name=file_name,
            file_data=raw_code.encode("utf-8"),
            content_trace=ContentTrace(
                source_type="file",
                extra={"language": lang},
            ),
        )
    )


async def _handle_mermaid(
    result: list[Text | File | Photo],
    seg: Segment,
) -> None:
    """Render a mermaid diagram as a Photo, or fall back to File."""
    from telegramify_markdown.mermaid import support_mermaid

    raw_code = seg.raw_code
    if not support_mermaid():
        logger.warning("Mermaid support not available (missing aiohttp/Pillow). Sending as file.")
        result.append(
            File(
                file_name="mermaid.txt",
                file_data=raw_code.encode("utf-8"),
                content_trace=ContentTrace(source_type="mermaid"),
            )
        )
        return

    try:
        from telegramify_markdown.mermaid import render_mermaid, get_mermaid_live_url

        img_data, _caption_url = await render_mermaid(raw_code)
        edit_url = get_mermaid_live_url(raw_code)
        result.append(
            Photo(
                file_name="mermaid.webp",
                file_data=img_data.read(),
                content_trace=ContentTrace(source_type="mermaid"),
                caption_text=f"Edit: {edit_url}",
            )
        )
    except Exception as e:
        logger.error(f"Mermaid rendering failed: {e}")
        result.append(
            File(
                file_name="invalid_mermaid.txt",
                file_data=raw_code.encode("utf-8"),
                content_trace=ContentTrace(source_type="mermaid"),
            )
        )
