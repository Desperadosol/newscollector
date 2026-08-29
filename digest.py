"""Build the daily digest via a single Claude API call (Messages API,
claude-haiku-4-5). Not an agent, not the tool runner — one summarization
call.
"""

from __future__ import annotations

import time

import anthropic

from feeds import Article

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 4096
MAX_ITEMS_PER_CATEGORY_IN_PROMPT = 5

CATEGORY_DISPLAY_NAMES = {
    "world_politics": "World Politics",
    "poland_politics": "Polish Politics",
    "poland_economics": "Economics",
    "belarusians_in_poland": "Belarusians in Poland",
}

SYSTEM_PROMPT = f"""\
You are a news editor producing a concise daily digest for one reader.

You will be given a pool of recent news articles, grouped by category. For \
each category present in the input, write a short section using this exact \
category order and these exact header names (skip a header entirely if no \
articles were given for it):

1. World Politics
2. Polish Politics
3. Economics
4. Belarusians in Poland

For each category, select only the {MAX_ITEMS_PER_CATEGORY_IN_PROMPT} most \
important or relevant items — do not include everything you were given. \
For each selected item, write a 1-2 sentence summary in English (translate \
if the source was in another language), followed by the source name and \
the article's URL.

Output plain text only. Do not use Markdown or HTML formatting (no `**`, \
no `#`, no `[text](url)` links) — write category headers as a short plain \
line, and put each item's link as a bare URL on its own line so it stays \
clickable. Keep the tone factual and neutral.
"""


def _format_topic_display(topic: str) -> str:
    return CATEGORY_DISPLAY_NAMES.get(topic, topic.replace("_", " ").title())


def _format_date(article: Article) -> str:
    if article.published is None:
        return "unknown"
    return time.strftime("%Y-%m-%d %H:%M UTC", article.published)


def _build_user_message(filtered: dict[str, list[Article]]) -> str:
    sections = []
    for topic, articles in filtered.items():
        lines = [f"### {_format_topic_display(topic)}"]
        for article in articles:
            lines.append(
                f"- {article.title} — {article.source_name} "
                f"(published: {_format_date(article)}) — {article.link}\n"
                f"  Excerpt: {article.summary}"
            )
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def build_digest(filtered: dict[str, list[Article]], api_key: str) -> str | None:
    """Call Claude to select and summarize the filtered article pool into a
    plain-text digest. Returns None on any API failure so the caller can
    fall back to a raw-headline digest instead of failing the whole run.
    """
    client = anthropic.Anthropic(api_key=api_key)
    user_message = _build_user_message(filtered)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
    except (
        anthropic.RateLimitError,
        anthropic.APIStatusError,
        anthropic.APIConnectionError,
    ) as exc:
        print(f"[digest] Claude API call failed, will fall back to raw headlines: {exc}")
        return None

    for block in response.content:
        if block.type == "text":
            return block.text

    print("[digest] Claude response had no text block, falling back to raw headlines")
    return None


def build_fallback_digest(filtered: dict[str, list[Article]]) -> str:
    """Raw-headline digest used when Claude is unavailable, so the user
    still gets a substantive message instead of silence.
    """
    lines = ["⚠️ Automatic summarization was unavailable today — here are today's raw headlines:\n"]
    for topic, articles in filtered.items():
        lines.append(_format_topic_display(topic))
        for article in articles[:MAX_ITEMS_PER_CATEGORY_IN_PROMPT]:
            lines.append(f"- {article.title} — {article.source_name} — {article.link}")
        lines.append("")
    return "\n".join(lines).strip()
