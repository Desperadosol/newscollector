"""Send the digest to Telegram via a plain HTTP call to the Bot API. No
python-telegram-bot dependency — this is a one-way send, not an interactive
bot.
"""

from __future__ import annotations

import time

import requests

API_BASE = "https://api.telegram.org"
HARD_LIMIT_CHARS = 4096
SAFE_CHUNK_CHARS = 4000
SEND_DELAY_SECONDS = 1


def _split_into_chunks(text: str) -> list[str]:
    if len(text) <= HARD_LIMIT_CHARS:
        return [text]

    # Prefer splitting on the blank-line-separated section boundaries that
    # digest.py's output naturally has, accumulating into chunks under the
    # safe limit.
    sections = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for section in sections:
        candidate = f"{current}\n\n{section}" if current else section

        if len(candidate) <= SAFE_CHUNK_CHARS:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(section) <= SAFE_CHUNK_CHARS:
            current = section
        else:
            # A single section is itself too big (shouldn't normally happen
            # given the per-category item cap) — hard-split at newlines.
            chunks.extend(_hard_split(section))

    if current:
        chunks.append(current)

    return chunks


def _hard_split(text: str) -> list[str]:
    chunks = []
    remaining = text
    while len(remaining) > SAFE_CHUNK_CHARS:
        split_at = remaining.rfind("\n", 0, SAFE_CHUNK_CHARS)
        if split_at <= 0:
            split_at = SAFE_CHUNK_CHARS
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]
    if remaining:
        chunks.append(remaining)
    return chunks


def _send_one(bot_token: str, chat_id: str, text: str) -> None:
    url = f"{API_BASE}/bot{bot_token}/sendMessage"
    resp = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
    data = resp.json()
    if not resp.ok or not data.get("ok"):
        description = data.get("description", resp.text)
        raise RuntimeError(f"Telegram API error ({resp.status_code}): {description}")


def send_digest(bot_token: str, chat_id: str, text: str) -> None:
    """Send `text` to the given chat, splitting into multiple messages if it
    exceeds Telegram's 4096-character limit. Raises on failure — delivery
    failures propagate up to main.py's top-level safety net since there's no
    further fallback once delivery itself fails.
    """
    chunks = _split_into_chunks(text)
    for i, chunk in enumerate(chunks):
        _send_one(bot_token, chat_id, chunk)
        if i < len(chunks) - 1:
            time.sleep(SEND_DELAY_SECONDS)
