"""Live streaming draft showcase — sends token-by-token via sendRichMessageDraft.

Demonstrates DraftStream with the real Telegram Bot API.
The bot will show a "thinking" indicator, then progressively render markdown
as rich message draft updates, and finally send the complete message.

Run: pdm run python playground/stream_draft_case.py

Requires:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID (must be a private chat with the bot)
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

from telegramify_markdown.stream.draft import (
    DraftStream,
    RichDraftPayload,
    RichFinalPayload,
)


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
            f"Telegram {method_name} rejected: HTTP {exc.code}: {error_body[:500]}"
        ) from exc

    if not result.get("ok"):
        raise RuntimeError(f"Telegram {method_name} ok=false: {result!r}")
    return result["result"]


# ---------------------------------------------------------------------------
# 模拟 LLM token 流
# ---------------------------------------------------------------------------

SAMPLE_MARKDOWN = """\
# Streaming Draft Demo

This message is being **streamed** token-by-token via `sendRichMessageDraft`.

## Features

- Thinking indicator on first emit
- Throttled updates (~300ms interval)
- Keepalive prevents draft expiry
- Final message via `sendRichMessage`

## Code Example

```python
async with DraftStream(send_draft, send_final, mode="rich") as stream:
    async for token in llm_response:
        stream.feed(token)
```

## Table

| Layer | Responsibility |
| --- | --- |
| StreamCore | Buffer + throttle + concurrency |
| DraftStream | Telegram draft API + thinking delay |
| EditStream | Group chat edit fallback |

> 流式输出完成 ✅
"""


async def simulate_llm_tokens(text: str, delay: float = 0.03):
    """模拟 LLM 逐 token 输出。"""
    # 按词+标点切分，模拟真实 token
    tokens = []
    current = ""
    for ch in text:
        current += ch
        if ch in (" ", "\n", ".", ",", "!", "?", "`", "*", "|", "-"):
            tokens.append(current)
            current = ""
    if current:
        tokens.append(current)

    for token in tokens:
        yield token
        await asyncio.sleep(delay)


# ---------------------------------------------------------------------------
# Telegram callback 实现
# ---------------------------------------------------------------------------


class TelegramDraftCallbacks:
    """将 DraftStream 的 emit/finalize 映射到 Telegram Bot API 调用。"""

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.draft_count = 0
        self.final_message_id: int | None = None

    async def send_draft(self, payload: RichDraftPayload) -> None:
        """调用 sendRichMessageDraft。"""
        self.draft_count += 1
        api_payload = {
            "chat_id": self.chat_id,
            "draft_id": payload.draft_id,
            "rich_message": payload.rich_message.to_dict(),
        }
        try:
            _post_bot_api_json(self.token, "sendRichMessageDraft", api_payload)
            print(f"  [draft #{self.draft_count}] sent ({len(payload.rich_message.html or '')} bytes HTML)")
        except Exception as e:
            print(f"  [draft #{self.draft_count}] FAILED: {e}")
            raise

    async def send_final(self, payload: RichFinalPayload) -> None:
        """调用 sendRichMessage 发送最终消息。"""
        api_payload = {
            "chat_id": self.chat_id,
            "rich_message": payload.rich_message.to_dict(),
            "disable_notification": True,
        }
        result = _post_bot_api_json(self.token, "sendRichMessage", api_payload)
        self.final_message_id = result.get("message_id")
        print(f"  [final] message_id={self.final_message_id}")


async def main() -> int:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
        print("       (chat must be a private chat with the bot for draft API)")
        return 1

    print("=== Streaming Draft Live Test ===")
    print(f"Chat ID: {chat_id}")
    print()

    callbacks = TelegramDraftCallbacks(token, chat_id)

    print("[1] Starting DraftStream (mode=rich, interval=0.3s, thinking_delay=0.5s)")
    async with DraftStream(
        send_draft=callbacks.send_draft,
        send_final=callbacks.send_final,
        mode="rich",
        interval=0.3,
        thinking_delay=0.5,
        keepalive_timeout=25.0,
        cancel_clears_draft=True,
    ) as stream:
        print("[2] Feeding tokens...")
        async for token in simulate_llm_tokens(SAMPLE_MARKDOWN, delay=0.03):
            stream.feed(token)

    print()
    print("=== Results ===")
    print(f"  Drafts sent: {callbacks.draft_count}")
    print(f"  Final message ID: {callbacks.final_message_id}")
    print(f"  Status: {'SUCCESS' if callbacks.final_message_id else 'FAILED'}")

    return 0 if callbacks.final_message_id else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
