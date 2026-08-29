"""RSS/Atom fetching and parsing, tolerant of individual feed failures."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import feedparser
import requests

from config import Feed

REQUEST_TIMEOUT_SECONDS = 10
SUMMARY_MAX_CHARS = 300
USER_AGENT = "news-collector/1.0 (+personal daily digest bot)"

_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Article:
    title: str
    link: str
    summary: str
    published: time.struct_time | None
    source_name: str
    topic: str


def _strip_html(text: str) -> str:
    return _TAG_RE.sub("", text or "").strip()


def _parse_entry(entry, feed: Feed) -> Article:
    raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
    summary = _strip_html(raw_summary)[:SUMMARY_MAX_CHARS]

    published = getattr(entry, "published_parsed", None) or getattr(
        entry, "updated_parsed", None
    )

    return Article(
        title=_strip_html(getattr(entry, "title", "(untitled)")),
        link=getattr(entry, "link", ""),
        summary=summary,
        published=published,
        source_name=feed.name,
        topic=feed.topic,
    )


def fetch_feed(feed: Feed) -> list[Article]:
    """Fetch and parse a single feed. Raises on failure — callers should
    catch per-feed so one broken feed doesn't kill the whole run.
    """
    resp = requests.get(
        feed.url, timeout=REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}
    )
    resp.raise_for_status()

    parsed = feedparser.parse(resp.content)

    if parsed.bozo and not parsed.entries:
        raise ValueError(f"malformed feed with no usable entries: {parsed.get('bozo_exception')}")
    if parsed.bozo:
        print(f"  [warn] {feed.name}: feed is malformed (bozo) but has entries, using anyway")

    return [_parse_entry(entry, feed) for entry in parsed.entries]


def fetch_all(feeds: list[Feed]) -> list[Article]:
    """Fetch every configured feed, tolerating per-feed failures. Returns the
    combined list of articles from every feed that succeeded (possibly empty
    if every feed failed — callers must handle that case, not treat it as a
    fatal error).
    """
    articles: list[Article] = []
    for feed in feeds:
        try:
            feed_articles = fetch_feed(feed)
            print(f"  [ok]   {feed.name}: {len(feed_articles)} entries")
            articles.extend(feed_articles)
        except Exception as exc:  # noqa: BLE001 - intentional: one bad feed must not stop the run
            print(f"  [fail] {feed.name}: {exc}")
            continue
    return articles
