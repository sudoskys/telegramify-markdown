# NOTE: Maybe we can use https://github.com/google/magika/ instead.

import re
from pathlib import Path
from typing import Optional

from telegramify_markdown.logger import logger

default_language_to_ext = {
    "python": "py",
    "javascript": "js",
    "typescript": "ts",
    "java": "java",
    "c++": "cpp",
    "c": "c",
    "html": "html",
    "css": "css",
    "bash": "sh",
    "shell": "sh",
    "php": "php",
    "markdown": "md",
    "dotenv": "env",
    "json": "json",
    "yaml": "yaml",
    "xml": "xml",
    "dockerfile": "dockerfile",
    "plaintext": "txt",
    "toml": "toml",
    "go": "go",
    "ruby": "rb",
    "rust": "rs",
    "perl": "pl",
    "swift": "swift",
    "kotlin": "kt",
    "sql": "sql",
    "jsx": "jsx",
    "tsx": "tsx",
    "graphql": "graphql",
    "r": "r",
    "dart": "dart",
    "scala": "scala",
    "groovy": "groovy",
}


def extract_valid_filename(line: str) -> Optional[str]:
    """Extract a valid filename (with extension) from a line of text."""
    pattern = r"([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)"
    matches = re.findall(pattern, line)
    for match in matches:
        file_path = Path(match)
        if file_path.suffix:
            return str(file_path)
    return None


def get_ext(language: str, lang_map=None) -> str:
    if lang_map is None:
        lang_map = default_language_to_ext
    return lang_map.get(language.lower(), "txt")


def get_filename(line: str, language: str, lang_map=None) -> str:
    """Generate a filename for a code block.

    Tries to extract a filename from the first line of the code.
    Falls back to 'readable.<ext>' based on the language.

    :param line: Code content (first lines are examined).
    :param language: Programming language identifier.
    :param lang_map: Optional language-to-extension mapping.
    :return: Generated filename.
    """
    # Take the first two lines
    line = line.strip().split("\n")[0:2]
    sample = "".join(line).replace("\\", "")
    try:
        a_filename = extract_valid_filename(sample)
        b_ext = get_ext(language=language, lang_map=lang_map)
    except Exception as exc:
        logger.error(f"Error occurred: {exc}")
        a_filename = None
        b_ext = "txt"
    if a_filename:
        if a_filename.endswith(f".{b_ext}") and len(a_filename) <= 24:
            return a_filename
        else:
            return f"{a_filename}.{b_ext}"
    return f"readable.{b_ext}"
