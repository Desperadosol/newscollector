"""Narrow the raw article pool before it's sent to Claude: recency window,
per-feed keyword filter, dedupe, and a per-category cap. This is the primary
token-cost control for the LLM call.
"""

from __future__ import annotations

import calendar
import re
import time
from collections import defaultdict
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit

from feeds import Article

TITLE_SIMILARITY_THRESHOLD = 0.85

_PUNCT_RE = re.compile(r"[^\w\s]")


def _epoch(published: time.struct_time | None) -> float | None:
    if published is None:
        return None
    return calendar.timegm(published)


def _within_recency(article: Article, cutoff_epoch: float) -> bool:
    epoch = _epoch(article.published)
    # Undated articles are kept (some feeds omit dates) — they're sorted
    # last later on, so they only survive the per-category cap if there's
    # room.
    if epoch is None:
        return True
    return epoch >= cutoff_epoch


def _passes_keyword_filter(article: Article, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = f"{article.title} {article.summary}".lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _normalize_title(title: str) -> str:
    return _PUNCT_RE.sub("", title.lower()).strip()


def _dedupe(articles: list[Article]) -> list[Article]:
    seen_urls: set[str] = set()
    kept: list[Article] = []
    kept_normalized_titles: list[str] = []

    for article in articles:
        norm_url = _normalize_url(article.link)
        if norm_url and norm_url in seen_urls:
            continue

        norm_title = _normalize_title(article.title)
        is_dupe = any(
            SequenceMatcher(None, norm_title, existing).ratio() > TITLE_SIMILARITY_THRESHOLD
            for existing in kept_normalized_titles
        )
        if is_dupe:
            continue

        seen_urls.add(norm_url)
        kept_normalized_titles.append(norm_title)
        kept.append(article)

    return kept


def filter_articles(
    articles: list[Article],
    feed_keywords: dict[str, list[str]],
    recency_hours: int,
    max_per_category: int,
) -> dict[str, list[Article]]:
    """Run the full filtering pipeline and return articles grouped by topic,
    each group capped at `max_per_category` and sorted most-recent-first
    (undated articles last).

    `feed_keywords` maps source_name -> keywords, since keyword filtering is
    a per-feed setting.
    """
    cutoff_epoch = time.time() - recency_hours * 3600

    survivors = [
        a
        for a in articles
        if _within_recency(a, cutoff_epoch)
        and _passes_keyword_filter(a, feed_keywords.get(a.source_name, []))
    ]

    survivors = _dedupe(survivors)

    grouped: dict[str, list[Article]] = defaultdict(list)
    for article in survivors:
        grouped[article.topic].append(article)

    result: dict[str, list[Article]] = {}
    for topic, topic_articles in grouped.items():
        topic_articles.sort(
            key=lambda a: (_epoch(a.published) is None, -(_epoch(a.published) or 0))
        )
        capped = topic_articles[:max_per_category]
        if capped:
            result[topic] = capped

    return result
