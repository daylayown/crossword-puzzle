#!/usr/bin/env python3
"""Scrape recent headlines from Google News RSS feeds across major categories."""

import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape
from urllib.request import urlopen, Request
import re

# Google News RSS feed URLs by category
FEEDS = {
    "us": "https://news.google.com/rss/topics/CAAqIggKIhxDQkFTRHdvSkwyMHZNRFZxYUdjU0FtVnVLQUFQAQ?hl=en-US&gl=US&ceid=US%3Aen",
    "world": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
    "business": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
    "technology": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
    "entertainment": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNREpxYW5RU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
    "sports": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZEdvU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
    "science": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp0Y1RjU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
    "health": "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNR3QwTlRFU0FtVnVLQUFQAQ?hl=en-US&gl=US&ceid=US:en",
}

# Also grab the top stories feed
TOP_STORIES_URL = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"


def fetch_feed(url: str) -> str:
    """Fetch RSS feed content."""
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def parse_feed(xml_text: str, category: str) -> list[dict]:
    """Parse RSS XML into a list of headline dicts."""
    root = ET.fromstring(xml_text)
    items = []

    for item in root.findall(".//item"):
        title = item.findtext("title", "").strip()
        # Google News appends " - Source Name" to titles; strip it
        title_clean = re.sub(r"\s*-\s*[^-]+$", "", title).strip()
        source = ""
        source_el = item.find("{http://search.yahoo.com/mrss/}credit") or item.find("source")
        if source_el is not None and source_el.text:
            source = source_el.text.strip()
        elif " - " in title:
            source = title.split(" - ")[-1].strip()

        pub_date = item.findtext("pubDate", "")

        items.append({
            "title": unescape(title_clean),
            "source": source,
            "category": category,
            "pub_date": pub_date,
        })

    return items


def scrape_all_headlines() -> list[dict]:
    """Scrape headlines from all Google News RSS feeds."""
    all_headlines = []

    # Top stories first
    print("Fetching top stories...")
    try:
        xml = fetch_feed(TOP_STORIES_URL)
        headlines = parse_feed(xml, "top")
        all_headlines.extend(headlines)
        print(f"  Got {len(headlines)} top stories")
    except Exception as e:
        print(f"  Error fetching top stories: {e}")

    # Category feeds
    for category, url in FEEDS.items():
        print(f"Fetching {category}...")
        try:
            xml = fetch_feed(url)
            headlines = parse_feed(xml, category)
            all_headlines.extend(headlines)
            print(f"  Got {len(headlines)} headlines")
        except Exception as e:
            print(f"  Error fetching {category}: {e}")

    # Deduplicate by title
    seen = set()
    unique = []
    for h in all_headlines:
        if h["title"] not in seen:
            seen.add(h["title"])
            unique.append(h)

    print(f"\nTotal unique headlines: {len(unique)}")
    return unique


def format_headlines_for_prompt(headlines: list[dict]) -> str:
    """Format headlines into a text block suitable for a Claude prompt."""
    lines = []
    for h in headlines:
        src = f" ({h['source']})" if h['source'] else ""
        lines.append(f"[{h['category'].upper()}] {h['title']}{src}")
    return "\n".join(lines)


if __name__ == "__main__":
    headlines = scrape_all_headlines()
    print("\n--- Sample headlines ---")
    for h in headlines[:20]:
        src = f" ({h['source']})" if h['source'] else ""
        print(f"  [{h['category'].upper()}] {h['title']}{src}")
