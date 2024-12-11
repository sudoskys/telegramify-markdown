# NOTE: Maybe we can use https://github.com/google/magika/ instead.
language_to_ext = {
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
    "json": "json",
    "yaml": "yaml",
    "go": "go",
    "ruby": "rb",
    "rust": "rs",
    "perl": "pl",
    "swift": "swift",
    "kotlin": "kt",
    "sql": "sql"
}


def get_ext(language: str) -> str:
    return language_to_ext.get(language.lower(), "txt")
