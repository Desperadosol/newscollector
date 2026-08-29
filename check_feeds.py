"""Cheap iteration helper for tuning sources.yaml: fetches and filters feeds
(same pipeline as main.py) and prints per-topic article counts. No Claude
call, no Telegram send — free and fast to re-run while editing the source
list.
"""

from __future__ import annotations

import config
from feeds import fetch_all
from filtering import filter_articles


def main() -> None:
    sources = config.load_sources()

    print(f"Checking {len(sources.feeds)} feeds:\n")
    articles = fetch_all(sources.feeds)
    print(f"\nFetched {len(articles)} articles total (before filtering).\n")

    feed_keywords = {feed.name: feed.keywords for feed in sources.feeds}
    filtered = filter_articles(
        articles,
        feed_keywords=feed_keywords,
        recency_hours=sources.recency_hours,
        max_per_category=sources.max_per_category,
    )

    print("After filtering (recency + keywords + dedupe + per-category cap):")
    if not filtered:
        print("  (nothing survived filtering)")
    for topic, topic_articles in filtered.items():
        print(f"  {topic}: {len(topic_articles)} articles")
        for article in topic_articles:
            print(f"    - {article.title} ({article.source_name})")


if __name__ == "__main__":
    main()
