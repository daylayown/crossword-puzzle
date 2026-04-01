#!/usr/bin/env python3
"""Scrape recent headlines from major news organizations on Bluesky via the public AT Protocol API."""

from datetime import datetime, timedelta, timezone
from urllib.request import urlopen, Request
import json
import re

# Major news org Bluesky handles
NEWS_ACCOUNTS = [
    "nytimes.bsky.social",
    "reuters.com",
    "apnews.bsky.social",
    "wsj.bsky.social",
    "bbc.bsky.social",
    "washingtonpost.bsky.social",
]

BSKY_API = "https://public.api.bsky.app/xrpc"


def fetch_author_feed(actor: str, limit: int = 100, cursor: str = "") -> dict:
    """Fetch a page of posts from a Bluesky account."""
    url = f"{BSKY_API}/app.bsky.feed.getAuthorFeed?actor={actor}&limit={limit}&filter=posts_no_replies"
    if cursor:
        url += f"&cursor={cursor}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_headline(post: dict) -> str | None:
    """Extract a headline-like string from a Bluesky post.

    News orgs typically post a headline + link. We grab the text and strip
    URLs and trailing whitespace.
    """
    record = post.get("post", {}).get("record", {})
    text = record.get("text", "").strip()
    if not text:
        return None
    # Strip URLs
    text = re.sub(r"https?://\S+", "", text).strip()
    # Skip very short posts (likely just a link or emoji)
    if len(text) < 15:
        return None
    return text


def scrape_bluesky_headlines(days_back: int = 14) -> list[dict]:
    """Scrape headlines from news org Bluesky feeds going back `days_back` days.

    Returns a list of headline dicts with keys: title, source, category, pub_date, age_days.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    all_headlines = []

    for actor in NEWS_ACCOUNTS:
        source_name = actor.split(".")[0].upper()  # e.g. "NYTIMES", "REUTERS"
        print(f"Fetching Bluesky feed: {actor}...")
        cursor = ""
        account_count = 0
        reached_cutoff = False

        # Paginate through the feed until we hit the cutoff date
        for _ in range(10):  # Max 10 pages (~1000 posts) per account
            try:
                data = fetch_author_feed(actor, limit=100, cursor=cursor)
            except Exception as e:
                print(f"  Error fetching {actor}: {e}")
                break

            feed = data.get("feed", [])
            if not feed:
                break

            for item in feed:
                created_at = item.get("post", {}).get("record", {}).get("createdAt", "")
                if not created_at:
                    continue

                # Parse the timestamp
                try:
                    post_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except ValueError:
                    continue

                if post_time < cutoff:
                    reached_cutoff = True
                    break

                headline = extract_headline(item)
                if not headline:
                    continue

                age_days = (datetime.now(timezone.utc) - post_time).days

                all_headlines.append({
                    "title": headline,
                    "source": source_name,
                    "category": "bluesky",
                    "pub_date": created_at,
                    "age_days": age_days,
                })
                account_count += 1

            if reached_cutoff:
                break

            cursor = data.get("cursor", "")
            if not cursor:
                break

        print(f"  Got {account_count} headlines from {actor}")

    # Deduplicate by title
    seen = set()
    unique = []
    for h in all_headlines:
        if h["title"] not in seen:
            seen.add(h["title"])
            unique.append(h)

    print(f"\nTotal unique Bluesky headlines: {len(unique)}")
    return unique


def format_bluesky_headlines_for_prompt(headlines: list[dict]) -> str:
    """Format Bluesky headlines into a text block for the Claude prompt, tagged with age."""
    lines = []
    for h in headlines:
        age = h.get("age_days", 0)
        age_label = "today" if age == 0 else f"{age}d ago"
        lines.append(f"[{h['source']} · {age_label}] {h['title']}")
    return "\n".join(lines)


if __name__ == "__main__":
    headlines = scrape_bluesky_headlines()
    print("\n--- Sample Bluesky headlines ---")
    for h in headlines[:20]:
        age = h.get("age_days", 0)
        age_label = "today" if age == 0 else f"{age}d ago"
        print(f"  [{h['source']} · {age_label}] {h['title']}")
