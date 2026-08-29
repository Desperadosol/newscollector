"""Orchestration entrypoint: load config, fetch feeds, filter, summarize via
Claude, send to Telegram. Run with --dry-run to print the digest to stdout
instead of sending it (no Telegram message, still calls Claude).
"""

from __future__ import annotations

import argparse
import sys

import config
import digest
import telegram
from feeds import fetch_all
from filtering import filter_articles

NO_NEWS_MESSAGE = "No significant news found today across the configured sources."


def run(dry_run: bool) -> None:
    env = config.load_env()
    sources = config.load_sources()

    print(f"Fetching {len(sources.feeds)} feeds...")
    articles = fetch_all(sources.feeds)
    print(f"Fetched {len(articles)} articles total.")

    feed_keywords = {feed.name: feed.keywords for feed in sources.feeds}
    filtered = filter_articles(
        articles,
        feed_keywords=feed_keywords,
        recency_hours=sources.recency_hours,
        max_per_category=sources.max_per_category,
    )
    print(f"After filtering: {sum(len(v) for v in filtered.values())} articles "
          f"across {len(filtered)} categories.")

    if not filtered:
        text = NO_NEWS_MESSAGE
    else:
        digest_text = digest.build_digest(filtered, api_key=env["ANTHROPIC_API_KEY"])
        text = digest_text if digest_text else digest.build_fallback_digest(filtered)

    if dry_run:
        print("\n----- DIGEST (dry run, not sent) -----\n")
        print(text)
        return

    telegram.send_digest(env["TELEGRAM_BOT_TOKEN"], env["TELEGRAM_CHAT_ID"], text)
    print("Digest sent to Telegram.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily news digest bot")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full pipeline but print the digest instead of sending it to Telegram.",
    )
    args = parser.parse_args()

    try:
        run(dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001 - top-level safety net, see plan §7
        print(f"[main] Unexpected error: {exc}", file=sys.stderr)
        try:
            env = config.load_env()
            telegram.send_digest(
                env["TELEGRAM_BOT_TOKEN"],
                env["TELEGRAM_CHAT_ID"],
                "⚠️ Daily digest bot hit an unexpected error today — "
                "check the GitHub Actions log.",
            )
        except Exception as notify_exc:  # noqa: BLE001 - best-effort notification only
            print(f"[main] Could not send error notification either: {notify_exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
