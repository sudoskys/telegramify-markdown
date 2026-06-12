"""Send a Rich Message showcase through the real Telegram Bot API.

Run: pdm run python playground/rich_message_case.py
"""

from __future__ import annotations

import json
import os
import textwrap
import urllib.error
import urllib.request

from dotenv import load_dotenv

from telegramify_markdown import richify


def _post_bot_api_json(token: str, method_name: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method_name}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Telegram {method_name} rejected request: HTTP {exc.code}: "
            f"{error_body[:500]}"
        ) from exc

    if not result.get("ok"):
        raise RuntimeError(f"Telegram {method_name} returned ok=false: {result!r}")
    return result["result"]


def main() -> int:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")

    markdown = textwrap.dedent(
        r"""
        # Rich Message 实地测评

        这条消息由 `telegramify-markdown.richify()` 生成，并通过 Bot API
        `sendRichMessage` 发送。它验证的是用户可见的 Rich Message 渲染面。

        ## Inline formatting

        **Bold**, *italic*, ~~strike~~, `inline code`, ||spoiler||,
        and [Telegram link](https://telegram.org).

        ## Lists and quote

        - normal list item
        - [x] completed task
        - [ ] pending task

        > Block quote with **bold** text and inline math $x^2 + y^2$.

        ## Table

        | Metric | Value |
        |:--|--:|
        | latency | **42 ms** |
        | status | ready |

        ## Code and formula

        ```python
        print("rich message")
        ```

        $$E = mc^2$$
        """
    ).strip()

    rich_message = richify(markdown, skip_entity_detection=True)
    result = _post_bot_api_json(
        token,
        "sendRichMessage",
        {
            "chat_id": chat_id,
            "rich_message": rich_message.to_dict(),
            "disable_notification": True,
        },
    )

    print(
        json.dumps(
            {
                "ok": True,
                "message_id": result.get("message_id"),
                "has_rich_message": "rich_message" in result,
                "block_count": len(result.get("rich_message", {}).get("blocks", [])),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
