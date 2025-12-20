import re
from typing import List

# Known limitation: The regex uses negative lookbehind (?<!\\) to skip escaped brackets.
# However, this does NOT correctly handle double backslash cases like `\\[` which should
# be treated as a valid link start (the backslash itself is escaped, not the bracket).
# This edge case is intentionally left unhandled for simplicity, as it's rare in practice.
_MARKDOWN_LINK_PATTERN = re.compile(
    r"""
    (?<!\\)\[   # match [, but not \[
        (.*?)   # url description (captured group \1)
    (?<!\\)\]   # match ], but not \]
    \(
        .*?     # url content (not counted by Telegram)
    (?<!\\)\)   # match ), but not \)
    """,
    re.VERBOSE,
)


def count_markdown(md: str) -> int:
    """
    Count the effective length of markdown text for Telegram.
    Telegram does not count URL characters in links toward the message length limit.

    :param md: Markdown text to count
    :return: Effective character count
    """
    # Replace [desc](url) with [desc]() to remove URL from count
    md = _MARKDOWN_LINK_PATTERN.sub(r"[\1]()", md)
    return len(md)

def hard_split_markdown(text: str, max_word_count: int) -> List[str]:
    """
    Hard split markdown text based on effective character count.
    Uses iterative approximation to find optimal split points.

    Note: This function is kept for API compatibility but is not currently used
    internally. The BaseInterpreter._hard_split method provides similar functionality
    with additional optimization for the interpreter context.

    :param text: Text to split
    :param max_word_count: Maximum effective character count per chunk
    :return: List of text chunks
    """
    if max_word_count <= 0:
        raise ValueError("max_word_count must be positive")
    chunks = []
    while text:
        limit = len(text)
        # Iteratively reduce limit until chunk fits within max_word_count
        while limit > 0:
            c = count_markdown(text[:limit])
            if c <= max_word_count:
                break
            limit -= c - max_word_count
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks
