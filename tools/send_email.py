#!/usr/bin/env python3
"""
Daily newsletter sender:
1. Load today's puzzle JSON
2. Ask Claude Haiku 4.5 for category tags and a 2-3 sentence email body
3. Wrap the body in a fixed template (greeting, signoff, link)
4. Schedule the email to send at 7am MST via the Buttondown API

Failure is non-fatal: a Buttondown or Claude error logs and exits 0 so the
puzzle pipeline doesn't fail behind it.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
BUTTONDOWN_API_KEY = os.environ.get("BUTTONDOWN_API_KEY")

ANTHROPIC_MODEL = "claude-haiku-4-5"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
BUTTONDOWN_URL = "https://api.buttondown.com/v1/emails"

PUZZLES_DIR = Path(__file__).parent.parent / "puzzles"
PUZZLE_URL = "https://crosswordingthesituation.com"

# Arizona is MST year-round (no DST), so 7am MST = 14:00 UTC always.
SEND_HOUR_UTC = 14


SYSTEM_PROMPT = """You write a short daily newsletter blurb for Crosswording the Situation, a news-themed mini crossword. Each day's puzzle clues reference real recent news. Your job is to tease today's puzzle in a warm, calm voice — like a friend mentioning it over coffee.

Hard rules (these prevent spoilers):
- Never quote any clue verbatim, even partially.
- Never name a specific answer word from the puzzle.
- Never identify which specific story a specific clue references.
- Describe the *flavor* of the puzzle in broad categories only (e.g., "politics", "sports", "tech", "entertainment", "business").
- Don't use specific names of people, companies, or events that appear in the clues.

Style:
- 2-3 sentences. Warm, gentle, slightly literary. No hype.
- The puzzle takes about 3-5 minutes — you can mention this.
- The pitch is that this is a gentler way to check in with the news without falling into the doom scroll.
- No greeting, no sign-off, no link — just the middle paragraphs."""


PROMPT_TEMPLATE = """Here are today's crossword clues (the answers are hidden — only the clue text):

{clues}

Output JSON with two fields:
- "topics": a list of 1-3 short category tags describing what areas of news this puzzle pulls from (e.g., ["politics", "tech", "sports"]).
- "email_body": 2-3 sentences in the voice described in the system prompt. Use the topic mix to flavor your phrasing, but follow the spoiler rules strictly."""


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {"type": "string"},
        },
        "email_body": {"type": "string"},
    },
    "required": ["topics", "email_body"],
    "additionalProperties": False,
}


def load_puzzle(date: str) -> dict:
    path = PUZZLES_DIR / f"{date}.json"
    if not path.exists():
        raise FileNotFoundError(f"No puzzle for {date} at {path}")
    with open(path) as f:
        return json.load(f)


def collect_clues(puzzle: dict) -> str:
    lines = []
    for direction in ("across", "down"):
        for entry in puzzle.get("clues", {}).get(direction, []):
            num = entry.get("number")
            tag = direction[0].upper()
            clue = entry.get("clue", "")
            lines.append(f"  {num}{tag}: {clue}")
    return "\n".join(lines)


def draft_email_body(clues_text: str) -> tuple[list[str], str]:
    """Call Haiku 4.5 to extract topics and draft the email middle."""
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": PROMPT_TEMPLATE.format(clues=clues_text)}
        ],
        "output_config": {
            "format": {
                "type": "json_schema",
                "schema": OUTPUT_SCHEMA,
            }
        },
    }
    resp = requests.post(ANTHROPIC_URL, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    text = resp.json()["content"][0]["text"]
    parsed = json.loads(text)
    return parsed["topics"], parsed["email_body"].strip()


def compose_email(date: str, email_body: str) -> tuple[str, str]:
    """Build subject + full email body from the LLM's middle paragraphs."""
    # Subject: "Today's mini — May 5"
    pretty_date = datetime.strptime(date, "%Y-%m-%d").strftime("%B %-d")
    subject = f"Today's mini — {pretty_date}"

    body = (
        f"Good morning —\n\n"
        f"{email_body}\n\n"
        f"Play today's puzzle: {PUZZLE_URL}\n\n"
        f"Nicholas, Crosswording The Situation"
    )
    return subject, body


def schedule_send(subject: str, body: str, date: str) -> None:
    """Post to Buttondown, scheduled for 7am MST on the puzzle's date."""
    if not BUTTONDOWN_API_KEY:
        print("  BUTTONDOWN_API_KEY not set — skipping send (printing email instead)")
        print("=" * 40)
        print(f"Subject: {subject}")
        print()
        print(body)
        print("=" * 40)
        return

    publish_dt = datetime.strptime(date, "%Y-%m-%d").replace(
        hour=SEND_HOUR_UTC, minute=0, second=0, tzinfo=timezone.utc
    )
    # If we're past the send time today (e.g. running late), push to "now + a few minutes"
    # so Buttondown doesn't reject a past publish_date.
    now = datetime.now(timezone.utc)
    if publish_dt <= now:
        publish_dt = now + timedelta(minutes=5)
        print(f"  Send time already passed — rescheduling for {publish_dt.isoformat()}")

    headers = {
        "Authorization": f"Token {BUTTONDOWN_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "subject": subject,
        "body": body,
        "publish_date": publish_dt.isoformat().replace("+00:00", "Z"),
        "email_type": "public",
    }
    resp = requests.post(BUTTONDOWN_URL, headers=headers, json=payload, timeout=30)
    if resp.status_code >= 400:
        print(f"  Buttondown error {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    data = resp.json()
    print(f"  Email scheduled (id={data.get('id')}) for {publish_dt.isoformat()}")


def main() -> int:
    if not ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY not set — cannot draft email")
        return 0

    date = datetime.now().strftime("%Y-%m-%d")
    if len(sys.argv) > 1:
        date = sys.argv[1]

    print(f"Drafting newsletter for {date}")
    print("=" * 40)

    try:
        puzzle = load_puzzle(date)
    except FileNotFoundError as e:
        print(f"  {e}")
        return 0

    clues_text = collect_clues(puzzle)
    print(f"  Loaded {len(clues_text.splitlines())} clues")

    try:
        topics, email_body = draft_email_body(clues_text)
        print(f"  Topics: {', '.join(topics)}")
    except Exception as e:
        print(f"  Claude error: {e}")
        return 0

    subject, body = compose_email(date, email_body)

    try:
        schedule_send(subject, body, date)
    except Exception as e:
        print(f"  Send error: {e}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
