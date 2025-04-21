import re


def escape(body: str) -> str:
    parse = re.sub(r"([_*\[\]()~`>\#\+\-=|\.!\{\}\\])", r"\\\1", body)
    reparse = re.sub(r"\\\\([_*\[\]()~`>\#\+\-=|\.!\{\}\\])", r"\1", parse)
    return reparse


def bold(body: str) -> str:
    return f"*{body}*"


def code(body: str) -> str:
    return f"```\n{body}\n```"


def link(body: str, href: str) -> str:
    return f"[{escape(body)}]({escape(href)})"
