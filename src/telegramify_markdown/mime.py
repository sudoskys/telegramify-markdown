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
    """
    从输入的一行数据中提取有效的文件名，并验证是否为合法文件名（必须有后缀）。
    """
    # 正则表达式，用于匹配潜在的文件名
    pattern = r"([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)"  # 只匹配包含后缀的文件名
    # 搜索所有潜在的文件名
    matches = re.findall(pattern, line)
    # 验证并返回一个合法的文件名
    for match in matches:
        file_path = Path(match)
        if file_path.suffix:  # 验证是否存在后缀
            return str(file_path)  # 返回有效文件名
    return None  # 如果没有合法文件名，返回 None


def get_ext(language: str, lang_map=None) -> str:
    if lang_map is None:
        lang_map = default_language_to_ext
    return lang_map.get(language.lower(), "txt")


def get_filename(line: str, language: str, lang_map=None) -> str:
    """
    12 为标准
    :param line: first line of the readable file
    :param language: language of the file
    :param lang_map: language to extension map
    :return: filename
    """
    # 取第一行
    line = line.strip().split("\n")[0:2]
    # 替换 \ 为空
    sample = "".join(line).replace("\\", "")
    try:
        # 提取文件名
        a_filename = extract_valid_filename(sample)
        # 从语言代码获取扩展名
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


if __name__ == "__main__":
    # 示例测试用例
    lines = [
        "text.md",
        "text.dev.env",
        "// KnapsackProblem.jsx",
        "-- index.lua",
        "# python.py",
        "kotlin.kt",
        "88a.java",
        ".dev.env",
        "python.py ##",  # 额外测试的含有注释的情况
        "not_a_file ## just text",
        "no match line here"
    ]

    # 应用函数并打印结果
    print("提取的文件名:")
    for _line in lines:
        filename = extract_valid_filename(_line)
        if filename:
            print("T", filename)
        else:
            print("F", _line)
