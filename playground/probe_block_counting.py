"""Probe Telegram's block counting rule for Rich Messages.

ADR-001 Open Question 1:
  Does `<ul><li><ul><li>...</li></ul></li></ul>` count as 2 blocks or 4?

Strategy: send Rich Messages with increasing nested structure near the 500 block
limit to discover the exact counting rule via Telegram's acceptance/rejection.

Run: pdm run python playground/probe_block_counting.py
"""

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    print("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required")
    sys.exit(1)

BASE = f"https://api.telegram.org/bot{TOKEN}"


def send_rich(html: str, label: str) -> dict | None:
    """Send Rich Message and return result or None on rejection."""
    payload = {
        "chat_id": CHAT_ID,
        "rich_message": {"html": html, "skip_entity_detection": True},
        "disable_notification": True,
    }
    resp = requests.post(f"{BASE}/sendRichMessage", json=payload, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        if data.get("ok"):
            msg_id = data["result"].get("message_id")
            _delete(msg_id)
            return data["result"]
        else:
            print(f"  [{label}] ok=false: {str(data)[:200]}")
            return None
    else:
        print(f"  [{label}] HTTP {resp.status_code}: {resp.text[:300]}")
        return None


def _delete(msg_id):
    if not msg_id:
        return
    try:
        requests.post(
            f"{BASE}/deleteMessage",
            json={"chat_id": CHAT_ID, "message_id": msg_id},
            timeout=10,
        )
    except Exception:
        pass


# ─── Test 1: Flat list items ───────────────────────────────────────────────
# N <li> items in a flat <ul>. How many "blocks" does Telegram count?
print("═══ Test 1: Flat list — how does Telegram count <li> blocks? ═══")
for n in [490, 495, 498, 499, 500, 501, 502, 510]:
    items = "".join(f"<li>item {i}</li>" for i in range(n))
    html = f"<ul>{items}</ul>"
    label = f"flat-{n}-items"
    result = send_rich(html, label)
    status = "ACCEPTED" if result else "REJECTED"
    blocks_info = ""
    if result and "rich_message" in result:
        blocks = result["rich_message"].get("blocks", [])
        blocks_info = f" (server returned {len(blocks)} blocks)"
    print(f"  {label}: {status}{blocks_info}")

# ─── Test 2: Nested lists ─────────────────────────────────────────────────
# <ul><li><ul><li>inner</li></ul></li></ul> — is that 2 blocks or 4?
print("\n═══ Test 2: Nested list block counting ═══")

# 2a: Simple 2-level nesting — small quantity to see what Telegram returns
html_2level = "<ul>" + "".join(
    f"<li>outer {i}<ul><li>inner {i}a</li><li>inner {i}b</li></ul></li>"
    for i in range(5)
) + "</ul>"
result = send_rich(html_2level, "2level-5outer-10inner")
if result and "rich_message" in result:
    blocks = result["rich_message"].get("blocks", [])
    print(f"  2-level, 5 outer × 2 inner: ACCEPTED, server blocks={len(blocks)}")
    # 打印 block 结构看 Telegram 如何计数
    for i, b in enumerate(blocks[:20]):
        btype = b.get("type", "?")
        print(f"    block[{i}]: type={btype}")
else:
    print("  2-level small: REJECTED (unexpected)")

# 2b: Push nested lists toward the 500 limit
# If each <li> counts as 1 block, then 250 outer items × 1 inner = 500 blocks (250 outer li + 250 inner li)
print("\n  Probing nested list near limit...")
for outer_n, inner_per_outer in [(100, 4), (150, 2), (200, 1), (245, 1), (248, 1), (250, 1), (260, 1)]:
    total_li = outer_n + outer_n * inner_per_outer
    items = "".join(
        "<li>o" + "".join(f"<ul><li>i</li></ul>" for _ in range(inner_per_outer)) + "</li>"
        for _ in range(outer_n)
    )
    html = f"<ul>{items}</ul>"
    label = f"nested-{outer_n}outer-{inner_per_outer}inner(total_li={total_li})"
    result = send_rich(html, label)
    status = "ACCEPTED" if result else "REJECTED"
    blocks_info = ""
    if result and "rich_message" in result:
        blocks = result["rich_message"].get("blocks", [])
        blocks_info = f" (server blocks={len(blocks)})"
    print(f"  {label}: {status}{blocks_info}")

# ─── Test 3: Blockquotes with nested content ──────────────────────────────
print("\n═══ Test 3: Blockquotes — does the blockquote itself + inner p both count? ═══")
# N blockquotes each containing 1 paragraph
for n in [245, 249, 250, 251, 260, 300, 490, 499, 500, 501]:
    html = "".join(f"<blockquote><p>quote {i}</p></blockquote>" for i in range(n))
    label = f"blockquote-{n}"
    result = send_rich(html, label)
    status = "ACCEPTED" if result else "REJECTED"
    blocks_info = ""
    if result and "rich_message" in result:
        blocks = result["rich_message"].get("blocks", [])
        blocks_info = f" (server blocks={len(blocks)})"
    print(f"  {label}: {status}{blocks_info}")

# ─── Test 4: Table rows ──────────────────────────────────────────────────
print("\n═══ Test 4: Table rows — does each <tr> count as a block? ═══")
for n in [100, 250, 400, 490, 498, 499, 500, 501]:
    rows = "<tr><th>H</th></tr>" + "".join(f"<tr><td>r{i}</td></tr>" for i in range(n))
    html = f"<table>{rows}</table>"
    label = f"table-{n}rows"
    result = send_rich(html, label)
    status = "ACCEPTED" if result else "REJECTED"
    blocks_info = ""
    if result and "rich_message" in result:
        blocks = result["rich_message"].get("blocks", [])
        blocks_info = f" (server blocks={len(blocks)})"
    print(f"  {label}: {status}{blocks_info}")

print("\n═══ Done ═══")
