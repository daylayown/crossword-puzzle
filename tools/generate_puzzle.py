#!/usr/bin/env python3
"""
Full puzzle generation pipeline:
1. Generate a valid 5x5 crossword grid
2. Scrape current news headlines
3. Send grid + headlines to Claude to write news-themed clues
4. Validate and output final puzzle JSON
"""

import json
import os
import random
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

# Import our modules
sys.path.insert(0, str(Path(__file__).parent))
from generate_grid import solve_grid, grid_to_json
from scrape_headlines import scrape_all_headlines, format_headlines_for_prompt
from scrape_bluesky import scrape_bluesky_headlines, format_bluesky_headlines_for_prompt

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-6"
API_URL = "https://api.anthropic.com/v1/messages"

PUZZLES_DIR = Path(__file__).parent.parent / "puzzles"
HEADLINES_DIR = PUZZLES_DIR / "headlines"


def parse_json_response(text: str) -> dict:
    """Parse JSON from a Claude response, handling markdown code blocks."""
    json_str = text.strip()
    if json_str.startswith("```"):
        json_str = re.sub(r"^```\w*\n?", "", json_str)
        json_str = re.sub(r"\n?```$", "", json_str)
    # Also try extracting JSON from surrounding text
    if not json_str.startswith("{"):
        match = re.search(r"\{.*\}", json_str, re.DOTALL)
        if match:
            json_str = match.group(0)
    return json.loads(json_str)


def call_claude(prompt: str, system: str = "") -> str:
    """Call the Anthropic API and return the text response."""
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    body = {
        "model": MODEL,
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system

    resp = requests.post(API_URL, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"]


def cache_headlines(date: str, headlines: list[dict]) -> None:
    """Save scraped headlines to puzzles/headlines/YYYY-MM-DD.json for reuse."""
    HEADLINES_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = HEADLINES_DIR / f"{date}.json"
    with open(cache_path, "w") as f:
        json.dump(headlines, f, indent=2)
    print(f"  Cached {len(headlines)} headlines to {cache_path}")


def load_cached_headlines(days_back: int = 14) -> list[dict]:
    """Load headlines from the cache for the past N days."""
    if not HEADLINES_DIR.exists():
        return []
    all_headlines = []
    today = datetime.now()
    for i in range(1, days_back + 1):  # Skip today (day 0) since we scrape fresh
        date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        cache_path = HEADLINES_DIR / f"{date_str}.json"
        if cache_path.exists():
            with open(cache_path) as f:
                cached = json.load(f)
                for h in cached:
                    h["age_days"] = i
                all_headlines.extend(cached)
    # Deduplicate by title
    seen = set()
    unique = []
    for h in all_headlines:
        if h["title"] not in seen:
            seen.add(h["title"])
            unique.append(h)
    print(f"  Loaded {len(unique)} cached headlines from past {days_back} days")
    return unique


def get_recent_clues_and_words(days_back: int = 7) -> tuple[list[str], list[str]]:
    """Read recent puzzle JSONs and extract used clue texts and answer words."""
    clues = []
    words = []
    today = datetime.now()
    for i in range(1, days_back + 1):
        date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        puzzle_path = PUZZLES_DIR / f"{date_str}.json"
        if puzzle_path.exists():
            with open(puzzle_path) as f:
                puzzle = json.load(f)
            for direction in ("across", "down"):
                for entry in puzzle.get("clues", {}).get(direction, []):
                    clues.append(entry.get("clue", ""))
                    words.append(entry.get("answer", ""))
    return clues, words


def format_headlines_with_age(headlines: list[dict]) -> str:
    """Format headlines with age tags for the prompt."""
    lines = []
    for h in headlines:
        age = h.get("age_days", 0)
        age_label = "today" if age == 0 else f"{age}d ago"
        cat = h.get("category", "news").upper()
        src = f" ({h['source']})" if h.get("source") else ""
        lines.append(f"[{cat} · {age_label}]{src} {h['title']}")
    return "\n".join(lines)


def generate_clues(puzzle_json: dict, headlines_text: str, dedup_context: str = "") -> dict:
    """Use Claude to write news-themed clues for a crossword grid."""

    # Collect all answers
    across_words = [(c["number"], c["answer"], "across") for c in puzzle_json["clues"]["across"]]
    down_words = [(c["number"], c["answer"], "down") for c in puzzle_json["clues"]["down"]]
    all_words = across_words + down_words

    word_list = "\n".join(f"  {num}{d[0].upper()}: {answer}" for num, answer, d in all_words)

    system = """You are an expert crossword puzzle editor for a daily news-themed mini crossword called "Newsword." Your job is to write clever, fair crossword clues that tie to current news whenever possible.

Guidelines:
- For each answer word, try to write a clue connected to recent news headlines provided below. Be creative — the connection can be direct (a person's name, a place, an event) or thematic (a word that relates to a trending story).
- If a word genuinely can't be tied to current news in a fair way, write a good standard crossword clue instead. Not every clue needs to be news-themed — a mix is ideal.
- Clues should reward general news awareness, not hyper-specific trivia. Think "I should have known that" not "how would anyone know that."
- Keep clues concise (under 80 characters ideally).
- Proper nouns are fine when they've been prominent in the news.
- Never repeat the answer word in the clue.
- Clues can be definitional, punny, or use wordplay — variety is good.
- CRITICAL: Every news-themed clue must reference a DIFFERENT news story or topic. Never use the same headline, event, person, or subject in more than one clue. Maximize the breadth of news coverage across the puzzle — each clue is a chance to surface a different story."""

    dedup_section = ""
    if dedup_context:
        dedup_section = f"""

---

STORIES AND WORDS ALREADY USED IN RECENT PUZZLES (avoid these):
{dedup_context}

Strongly prefer referencing DIFFERENT news stories and topics than the ones listed above. If a word in the grid genuinely only connects to one of these already-used stories, write a standard (non-news) crossword clue for it instead.
"""

    prompt = f"""Here are recent news headlines (tagged with age — prefer fresher stories but older ones are fair game):

{headlines_text}

---

Here is today's crossword grid with the answer words that need clues:

{word_list}

For each word, write a crossword clue.
{dedup_section}
IMPORTANT — NO DUPLICATE NEWS STORIES: Each news-themed clue MUST reference a completely different news story, event, person, or topic. Before finalizing, review all your clues and verify that no two clues reference the same story or even closely related aspects of the same story. If you find a collision, rewrite one of the clues to reference a different story, or make it a standard (non-news) crossword clue instead.

Return your answer as a JSON object with this exact format:

{{
  "clues": {{
    "1A": "Your clue for 1-Across here",
    "5A": "Your clue for 5-Across here",
    ...
    "1D": "Your clue for 1-Down here",
    ...
  }}
}}

Return ONLY the JSON object, no other text."""

    print("Calling Claude to generate clues...")
    response = call_claude(prompt, system)

    clue_data = parse_json_response(response)
    return clue_data["clues"]


def apply_clues(puzzle_json: dict, clues: dict) -> dict:
    """Apply Claude-generated clues to the puzzle JSON."""
    for entry in puzzle_json["clues"]["across"]:
        key = f"{entry['number']}A"
        if key in clues:
            entry["clue"] = clues[key]

    for entry in puzzle_json["clues"]["down"]:
        key = f"{entry['number']}D"
        if key in clues:
            entry["clue"] = clues[key]

    return puzzle_json


def validate_puzzle(puzzle_json: dict) -> bool:
    """Validate that the puzzle is internally consistent."""
    grid = puzzle_json["grid"]
    size = puzzle_json["size"]
    errors = []

    # Check each across clue
    for entry in puzzle_json["clues"]["across"]:
        word = ""
        for i in range(entry["length"]):
            word += grid[entry["row"]][entry["col"] + i]
        if word != entry["answer"]:
            errors.append(f"{entry['number']}A: grid reads '{word}' but answer is '{entry['answer']}'")

    # Check each down clue
    for entry in puzzle_json["clues"]["down"]:
        word = ""
        for i in range(entry["length"]):
            word += grid[entry["row"] + i][entry["col"]]
        if word != entry["answer"]:
            errors.append(f"{entry['number']}D: grid reads '{word}' but answer is '{entry['answer']}'")

    # Check no duplicate answers
    all_answers = [e["answer"] for e in puzzle_json["clues"]["across"]] + \
                  [e["answer"] for e in puzzle_json["clues"]["down"]]
    if len(set(all_answers)) != len(all_answers):
        dupes = [a for a in all_answers if all_answers.count(a) > 1]
        errors.append(f"Duplicate answers: {set(dupes)}")

    # Check no empty clues
    for entry in puzzle_json["clues"]["across"] + puzzle_json["clues"]["down"]:
        if not entry["clue"] or entry["clue"].startswith("[Clue for"):
            errors.append(f"{entry['number']}: missing clue")

    if errors:
        print("Validation errors:")
        for e in errors:
            print(f"  - {e}")
        return False

    print("Puzzle validated successfully!")
    return True


def main():
    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    # Date for the puzzle
    date = datetime.now().strftime("%Y-%m-%d")
    if len(sys.argv) > 1:
        date = sys.argv[1]

    print(f"Generating puzzle for {date}")
    print("=" * 40)

    # Step 1: Get recently used answer words and generate a fresh grid
    print("\nStep 1a: Loading recently used answer words...")
    _, recent_words = get_recent_clues_and_words(days_back=28)
    excluded_answers = set(recent_words)
    if excluded_answers:
        print(f"  Excluding {len(excluded_answers)} answer words from recent puzzles")
    else:
        print("  No recent puzzles found — no exclusions")

    print("\nStep 1b: Generating crossword grid...")
    random.seed(None)  # Use true randomness
    grid = solve_grid(max_attempts=5000, excluded_words=excluded_answers)
    if not grid:
        # Fall back to fewer exclusions if we can't find a grid
        print("  Could not find grid with full exclusions, trying with 7-day window...")
        _, recent_words_short = get_recent_clues_and_words(days_back=7)
        grid = solve_grid(max_attempts=5000, excluded_words=set(recent_words_short))
    if not grid:
        print("  Falling back to no exclusions...")
        grid = solve_grid(max_attempts=5000)
    if not grid:
        print("Failed to generate a valid grid. Try again.")
        sys.exit(1)

    puzzle_json = grid_to_json(grid, date)

    # Step 2: Scrape headlines from multiple sources
    print("\nStep 2a: Scraping Google News headlines...")
    google_headlines = scrape_all_headlines()
    for h in google_headlines:
        h["age_days"] = 0  # Google News = today's news

    print("\nStep 2b: Scraping Bluesky news feeds (past 14 days)...")
    try:
        bluesky_headlines = scrape_bluesky_headlines(days_back=28)
    except Exception as e:
        print(f"  Bluesky scrape failed (non-fatal): {e}")
        bluesky_headlines = []

    print("\nStep 2c: Loading cached headlines from previous days...")
    cached_headlines = load_cached_headlines(days_back=28)

    # Merge all headlines, dedup by title
    all_headlines = google_headlines + bluesky_headlines + cached_headlines
    seen_titles = set()
    unique_headlines = []
    for h in all_headlines:
        if h["title"] not in seen_titles:
            seen_titles.add(h["title"])
            unique_headlines.append(h)

    # Sort: freshest first
    unique_headlines.sort(key=lambda h: h.get("age_days", 0))
    print(f"\n  Total unique headlines across all sources: {len(unique_headlines)}")

    # Cache today's headlines (Google News + Bluesky) for future runs
    todays_headlines = [h for h in google_headlines + bluesky_headlines
                        if h.get("age_days", 0) == 0]
    cache_headlines(date, todays_headlines)

    # Format for the prompt — take top 200 (more variety than before)
    if not unique_headlines:
        headlines_text = "(No current headlines available)"
    else:
        headlines_text = format_headlines_with_age(unique_headlines[:200])

    # Step 2d: Build cross-day dedup context
    print("\nStep 2d: Building cross-day dedup context...")
    recent_clues, recent_words = get_recent_clues_and_words(days_back=28)
    dedup_context = ""
    if recent_clues:
        clue_lines = [f"  - {c}" for c in recent_clues if c]
        word_lines = [f"  - {w}" for w in set(recent_words) if w]
        dedup_context = f"Recently used clues:\n{chr(10).join(clue_lines)}\n\nRecently used answer words:\n{chr(10).join(word_lines)}"
        print(f"  Found {len(recent_clues)} clues and {len(set(recent_words))} unique words from recent puzzles")
    else:
        print("  No recent puzzles found for dedup")

    # Step 3: Generate clues with Claude
    print("\nStep 3: Generating clues with Claude...")
    clues = generate_clues(puzzle_json, headlines_text, dedup_context)

    # Step 4: Apply clues and validate
    print("\nStep 4: Applying clues and validating...")
    puzzle_json = apply_clues(puzzle_json, clues)

    if not validate_puzzle(puzzle_json):
        print("\nPuzzle has validation errors!")
        sys.exit(1)

    # Step 5: Check for duplicate news stories across clues
    print("\nStep 5: Checking for duplicate news references...")
    all_clue_texts = []
    for entry in puzzle_json["clues"]["across"]:
        all_clue_texts.append(f"{entry['number']}A: {entry['clue']}")
    for entry in puzzle_json["clues"]["down"]:
        all_clue_texts.append(f"{entry['number']}D: {entry['clue']}")

    dedup_prompt = f"""Review these crossword clues and check if any two clues reference the same news story, event, person, or topic:

{chr(10).join(all_clue_texts)}

If any clues reference the same story, respond with a JSON object listing the conflicting clue numbers. If all clues reference different stories (or are non-news clues), respond with an empty list.

Format: {{"conflicts": ["4D", "7A"]}} or {{"conflicts": []}}

Return ONLY the JSON object."""

    dedup_response = call_claude(dedup_prompt, "You are a careful editor checking crossword clues for duplicate news references.")
    dedup_result = parse_json_response(dedup_response)

    if dedup_result.get("conflicts"):
        conflict_keys = dedup_result["conflicts"]
        print(f"  Found duplicate news references in: {conflict_keys}")
        print("  Regenerating clues for conflicting entries...")

        # Determine which clues to keep vs rewrite — keep the first, rewrite the rest
        keep_key = conflict_keys[0]
        rewrite_keys = conflict_keys[1:]

        # Build list of existing clue topics to avoid
        existing_topics = []
        for entry in puzzle_json["clues"]["across"]:
            key = f"{entry['number']}A"
            if key not in rewrite_keys:
                existing_topics.append(f"{key}: {entry['clue']}")
        for entry in puzzle_json["clues"]["down"]:
            key = f"{entry['number']}D"
            if key not in rewrite_keys:
                existing_topics.append(f"{key}: {entry['clue']}")

        # Get the words that need new clues
        rewrite_words = []
        for entry in puzzle_json["clues"]["across"]:
            key = f"{entry['number']}A"
            if key in rewrite_keys:
                rewrite_words.append(f"{key}: {entry['answer']}")
        for entry in puzzle_json["clues"]["down"]:
            key = f"{entry['number']}D"
            if key in rewrite_keys:
                rewrite_words.append(f"{key}: {entry['answer']}")

        fix_prompt = f"""These crossword clues are already in use and their news topics are OFF LIMITS:

{chr(10).join(existing_topics)}

Write NEW clues for these words that reference DIFFERENT news stories (or use standard crossword clues if needed):

{chr(10).join(rewrite_words)}

Headlines for reference:
{headlines_text}

Return ONLY a JSON object: {{"clues": {{"4D": "new clue here", ...}}}}"""

        fix_response = call_claude(fix_prompt, "You are an expert crossword clue writer. Write clues that do NOT overlap with the existing clue topics.")
        fix_clues = parse_json_response(fix_response)["clues"]
        puzzle_json = apply_clues(puzzle_json, fix_clues)
        print("  Replacement clues applied.")
    else:
        print("  No duplicates found.")

    # Write output
    out_path = Path(__file__).parent.parent / "puzzles" / f"{date}.json"
    with open(out_path, "w") as f:
        json.dump(puzzle_json, f, indent=2)

    print(f"\nPuzzle written to {out_path}")
    print("\n--- Final Puzzle ---")
    print(f"Date: {puzzle_json['date']}")
    for r in range(puzzle_json["size"]):
        row = puzzle_json["grid"][r]
        print(" ".join(c if c != "#" else "." for c in row))
    print("\nAcross:")
    for e in puzzle_json["clues"]["across"]:
        print(f"  {e['number']}. {e['clue']} ({e['answer']})")
    print("\nDown:")
    for e in puzzle_json["clues"]["down"]:
        print(f"  {e['number']}. {e['clue']} ({e['answer']})")


if __name__ == "__main__":
    main()
