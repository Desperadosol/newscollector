"""Configuration loading: environment variables (.env locally, real env in CI)
and the sources.yaml feed list. This is the one place other modules import
configuration from.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

# No-op if .env doesn't exist (e.g. in GitHub Actions, where secrets come
# from the environment directly).
load_dotenv()

REQUIRED_ENV_VARS = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "ANTHROPIC_API_KEY")

SOURCES_PATH = Path(__file__).parent / "sources.yaml"


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    topic: str
    keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SourcesConfig:
    recency_hours: int
    max_per_category: int
    feeds: list[Feed]


def load_env() -> dict[str, str]:
    """Read and validate the required secrets. Fails fast with a clear
    message listing exactly which ones are missing, rather than a deep
    stack trace surfacing later from requests/anthropic.
    """
    values = {name: os.environ.get(name, "") for name in REQUIRED_ENV_VARS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        print(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + "\nSet them in a local .env file (see .env.example) or as "
            "GitHub Actions repository secrets.",
            file=sys.stderr,
        )
        sys.exit(1)
    return values


def load_sources(path: Path = SOURCES_PATH) -> SourcesConfig:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    feeds = [
        Feed(
            name=entry["name"],
            url=entry["url"],
            topic=entry["topic"],
            keywords=entry.get("keywords") or [],
        )
        for entry in raw.get("feeds", [])
    ]

    return SourcesConfig(
        recency_hours=raw.get("recency_hours", 30),
        max_per_category=raw.get("max_per_category", 15),
        feeds=feeds,
    )
