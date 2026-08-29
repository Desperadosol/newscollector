# News Collector — Daily Telegram Digest

A personal bot that once a day fetches curated RSS feeds covering:

- World politics
- Polish politics
- Economics
- Policies affecting Belarusian immigrants in Poland (visas, residency,
  asylum, border rules — not general Belarus-related news)
- News affecting students and young people in Poland (student visas,
  education policy, youth employment/housing)

...filters and dedupes them, asks Claude to pick the most relevant items
and summarize them in English, and sends the result as one Telegram
message. It runs on a free GitHub Actions scheduled workflow — no server,
no database.

## Prerequisites

- Python 3.11+ (for local testing)
- A Telegram account
- An Anthropic account (for the Claude API key)
- A GitHub account (for free hosting via GitHub Actions)

## 1. Create a Telegram bot & get your chat ID

1. Open a chat with **[@BotFather](https://t.me/BotFather)** on Telegram and
   send `/newbot`. Follow the prompts (pick a name and a username ending in
   `bot`). BotFather will reply with a token that looks like
   `123456789:AAExampleTokenHere` — this is your `TELEGRAM_BOT_TOKEN`.
2. Send **any message** to your new bot (it can't message you until you've
   messaged it first).
3. Get your numeric chat ID — either:
   - Message **[@userinfobot](https://t.me/userinfobot)** and it will reply
     with your numeric Telegram ID directly, or
   - Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a
     browser and read the `"chat":{"id": ...}` field from the JSON response.
   - This is your `TELEGRAM_CHAT_ID`.

## 2. Get an Anthropic API key

Go to [console.anthropic.com](https://console.anthropic.com/) → **API Keys**
→ create a new key. This is your `ANTHROPIC_API_KEY`. At the volume this bot
uses (one summarization call per day with `claude-haiku-4-5`), expect roughly
**$1/month**.

## 3. Local setup & testing

```bash
git clone https://github.com/Desperadosol/newscollector.git
cd news_collector
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in the three values from steps 1-2
```

Cheapest first check — validate the feed list without spending any API
calls or sending any Telegram messages:

```bash
python check_feeds.py
```

Full pipeline, but print the digest instead of sending it (still calls
Claude, so it has a small real cost, but no Telegram message is sent):

```bash
python main.py --dry-run
```

Full end-to-end run — this actually sends a message to your Telegram chat:

```bash
python main.py
```

## 4. Editing the source list (`sources.yaml`)

Each feed entry has:

- `name` — shown in the digest as the source.
- `url` — the RSS/Atom feed URL.
- `topic` — a free-form category key. The digest is grouped by whatever
  distinct `topic` values exist in this file. Current topics:
  `world_politics`, `poland_politics`, `poland_economics`,
  `belarusians_in_poland` (narrowed to policy/immigration news, via
  `keywords`), `students_young_people`. To add a 6th category, add a feed
  with a new `topic` string, a line to the `CATEGORY_DISPLAY_NAMES` map in
  `digest.py`, and a corresponding line in `digest.py`'s `SYSTEM_PROMPT`
  category list.
- `keywords` — optional. If non-empty, an article from that feed is only
  kept if at least one keyword (case-insensitive) appears in its title or
  summary. Use this both on broad, general-news feeds (e.g. BBC/Al Jazeera)
  and to narrow an otherwise-broad topic to a specific angle — e.g. the
  `belarusians_in_poland` feeds use a shared `keywords` list (via a YAML
  anchor, `&belarus_policy_keywords`/`*belarus_policy_keywords`) to keep
  only policy/legal/immigration stories rather than all Belarus-related
  news. Leave empty (`[]`) for feeds that are already precisely scoped by
  their query/URL.

If a feed goes stale or a good direct feed doesn't exist for a topic, use a
Google News RSS search query as a fallback:

```
https://news.google.com/rss/search?q=<your+query>&hl=en-US&gl=US&ceid=US:en
```

Run `python check_feeds.py` after any edit to confirm the feed resolves and
returns a reasonable number of articles.

## 5. Deploying via GitHub Actions

1. Push this repo to GitHub (a private repo is fine — GitHub Actions works
   the same either way).
2. In the repo, go to **Settings → Secrets and variables → Actions → New
   repository secret** and add all three:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `ANTHROPIC_API_KEY`
3. Make sure Actions are enabled for the repo (they are by default).
4. **Test before trusting the schedule**: go to the **Actions** tab → select
   the **Daily Digest** workflow → click **Run workflow** (this uses the
   `workflow_dispatch` trigger). Watch the run log for per-feed fetch
   results and the final "Digest sent to Telegram" line, then check
   Telegram for the message.
5. Once that works, the scheduled run (`06:00 UTC` daily — see the comment
   in `.github/workflows/daily-digest.yml` for the DST tradeoff, since
   Warsaw is UTC+1/+2 depending on season) will fire automatically. GitHub
   may delay scheduled runs by a few minutes under load — normal.

## Troubleshooting

- **No message arrives, no error in Actions**: double-check `chat_id` — the
  bot can't message you until you've sent it a message first.
- **`Unauthorized` / 401 from Telegram**: `TELEGRAM_BOT_TOKEN` is wrong or
  the bot was deleted/regenerated in BotFather.
- **A feed shows `[fail]` in the logs**: the URL may have gone dead. Run
  `python check_feeds.py` locally to confirm, then fix or remove it in
  `sources.yaml`.
- **The digest arrives but says "Automatic summarization was unavailable
  today"**: the Claude API call failed (rate limit, quota, or outage) — this
  is the deliberate fallback, not a bug. Check the Actions log for the
  specific error, and check your Anthropic account for quota/billing issues.
- **The whole run fails (red X in Actions)**: an unexpected error occurred.
  Check the log; GitHub also sends a failure-notification email by default,
  which is the monitoring mechanism for this project (no extra alerting is
  set up).
