#!/usr/bin/env python3
"""
Full puzzle generation pipeline:
1. Generate a valid 5x5 crossword grid
2. Scrape current news headlines
3. Send grid + headlines to Claude to write news-themed clues
4. Validate and output final puzzle JSON
"""

import json
import math
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
    """Parse JSON from a Claude response, handling markdown code blocks and trailing prose."""
    json_str = text.strip()
    if json_str.startswith("```"):
        json_str = re.sub(r"^```\w*\n?", "", json_str)
        json_str = re.sub(r"\n?```$", "", json_str)
    # Skip any leading prose before the first '{'
    start = json_str.find("{")
    if start == -1:
        return json.loads(json_str)  # let json raise a clear error
    # raw_decode parses the first valid JSON value and ignores any trailing text
    obj, _ = json.JSONDecoder().raw_decode(json_str[start:])
    return obj


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

    system = """You are an expert crossword puzzle editor for a daily news-themed mini crossword called "Newsword." Every single clue you write MUST be tied to a real news story from the past two months (60 days). This is the entire premise of the puzzle — generic crossword clues are unacceptable.

Guidelines:
- EVERY clue must reference a specific news story from the headlines provided below. The headlines span the past ~60 days; do not invent or reference news outside this window.
- The connection can be direct (a person's name, place, event) or thematic (a word naturally evoked by a story — e.g. EJECT clued via an ICE deportation story). Be creative, but the news hook must be real and identifiable from the headlines list.
- If you cannot find an honest news hook for a word in the provided headlines, return the clue text "NO_NEWS_HOOK" for that entry. Do NOT fall back to a generic dictionary, trivia, or pop-culture clue. The pipeline will regenerate the grid in that case.
- Clues should reward general news awareness, not hyper-specific trivia. Think "I should have known that" not "how would anyone know that."
- Keep clues concise (under 80 characters ideally).
- Proper nouns are fine when they've been prominent in the news.
- Never repeat the answer word in the clue.
- CRITICAL: Every clue must reference a DIFFERENT news story or topic. Never use the same headline, event, person, or subject in more than one clue. Maximize the breadth of news coverage across the puzzle — each clue is a chance to surface a different story."""

    dedup_section = ""
    if dedup_context:
        dedup_section = f"""

---

STORIES AND WORDS ALREADY USED IN RECENT PUZZLES (avoid these):
{dedup_context}

Strongly prefer referencing DIFFERENT news stories and topics than the ones listed above. If a word in the grid genuinely only connects to one of these already-used stories, write a standard (non-news) crossword clue for it instead.
"""

    prompt = f"""Here are news headlines from the past 60 days (tagged with age — prefer fresher stories but anything within the 60-day window is fair game):

{headlines_text}

---

Here is today's crossword grid with the answer words that need clues:

{word_list}

For each word, write a crossword clue tied to one of the news stories above.
{dedup_section}
RULES:
1. EVERY clue must reference a specific news story from the headlines above (within the past 60 days). No generic clues, no dictionary definitions, no trivia unrelated to current news.
2. NO DUPLICATE STORIES: Each clue must reference a completely different news story, event, person, or topic. Review your clues before finalizing — if two clues reference the same story or closely related aspects of one story, rewrite one to use a different story.
3. If you genuinely cannot find a news hook for a particular word in the provided headlines, return "NO_NEWS_HOOK" as the clue text for that word. Do NOT invent a generic clue. The pipeline will regenerate the grid to swap that word out.

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

    # Step 1: Load recently used answer words (for dedup across days)
    print("\nStep 1: Loading recently used answer words...")
    _, recent_words = get_recent_clues_and_words(days_back=28)
    base_excluded_answers = set(recent_words)
    if base_excluded_answers:
        print(f"  Excluding {len(base_excluded_answers)} answer words from recent puzzles")
    else:
        print("  No recent puzzles found — no exclusions")

    # Step 2: Scrape headlines from multiple sources
    print("\nStep 2a: Scraping Google News headlines...")
    google_headlines = scrape_all_headlines()
    for h in google_headlines:
        h["age_days"] = 0  # Google News = today's news

    print("\nStep 2b: Scraping Bluesky news feeds (past 60 days)...")
    try:
        bluesky_headlines = scrape_bluesky_headlines(days_back=60)
    except Exception as e:
        print(f"  Bluesky scrape failed (non-fatal): {e}")
        bluesky_headlines = []

    print("\nStep 2c: Loading cached headlines from previous days...")
    cached_headlines = load_cached_headlines(days_back=60)

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
    recent_clues, _ = get_recent_clues_and_words(days_back=28)
    dedup_context = ""
    if recent_clues:
        clue_lines = [f"  - {c}" for c in recent_clues if c]
        word_lines = [f"  - {w}" for w in base_excluded_answers if w]
        dedup_context = f"Recently used clues:\n{chr(10).join(clue_lines)}\n\nRecently used answer words:\n{chr(10).join(word_lines)}"
        print(f"  Found {len(recent_clues)} clues and {len(base_excluded_answers)} unique words from recent puzzles")
    else:
        print("  No recent puzzles found for dedup")

    # Step 3: Grid + clues with retry. If any clue can't be tied to news,
    # the failing answer word is added to the exclusion set and the grid
    # is regenerated to swap it out. If all retries fail, we may salvage
    # the best attempt by allowing up to 10% of clues to be generic.
    MAX_GRID_ATTEMPTS = 4
    excluded_answers = set(base_excluded_answers)
    failed_words: set[str] = set()
    puzzle_json = None
    best_partial: dict | None = None  # candidate with fewest news-hook failures
    best_partial_failures: set[str] = set()

    for grid_attempt in range(1, MAX_GRID_ATTEMPTS + 1):
        print(f"\n=== Grid attempt {grid_attempt}/{MAX_GRID_ATTEMPTS} ===")
        if failed_words:
            print(f"  Excluding words that previously had no news hook: {sorted(failed_words)}")

        random.seed(None)
        attempt_exclusions = excluded_answers | failed_words
        grid = solve_grid(max_attempts=5000, excluded_words=attempt_exclusions)
        if not grid:
            print("  Could not find grid with full exclusions, trying with 7-day window + failed words...")
            _, recent_words_short = get_recent_clues_and_words(days_back=7)
            grid = solve_grid(max_attempts=5000, excluded_words=set(recent_words_short) | failed_words)
        if not grid:
            print("  Falling back to failed-words-only exclusions...")
            grid = solve_grid(max_attempts=5000, excluded_words=failed_words)
        if not grid:
            print("  Failed to generate a valid grid this attempt; retrying.")
            continue

        candidate = grid_to_json(grid, date)

        print("  Generating clues with Claude...")
        clues = generate_clues(candidate, headlines_text, dedup_context)
        candidate = apply_clues(candidate, clues)

        # Scan for words Claude couldn't hook to news
        new_failures = set()
        for entry in candidate["clues"]["across"] + candidate["clues"]["down"]:
            clue_text = (entry.get("clue") or "").upper()
            if "NO_NEWS_HOOK" in clue_text or not entry.get("clue"):
                new_failures.add(entry["answer"])

        # Track the best partial attempt for possible salvage
        if best_partial is None or len(new_failures) < len(best_partial_failures):
            best_partial = candidate
            best_partial_failures = new_failures

        if new_failures:
            print(f"  Claude couldn't find news hooks for: {sorted(new_failures)}")
            failed_words |= new_failures
            continue

        if not validate_puzzle(candidate):
            print("  Validation failed; retrying with a new grid.")
            continue

        puzzle_json = candidate
        break

    # Salvage path: allow up to 10% of clues to be generic if all-news retries failed
    if puzzle_json is None and best_partial is not None:
        total_clues = len(best_partial["clues"]["across"]) + len(best_partial["clues"]["down"])
        max_generic = max(1, math.ceil(total_clues * 0.10))
        print(f"\nAll-news attempts exhausted. Best partial had {len(best_partial_failures)} word(s) without a news hook.")
        print(f"Salvage threshold: at most {max_generic} of {total_clues} clues may be generic ({max_generic/total_clues:.0%}).")

        if len(best_partial_failures) <= max_generic:
            print(f"  Salvaging: requesting standard crossword clues for {sorted(best_partial_failures)}...")
            salvage_words = []
            for entry in best_partial["clues"]["across"]:
                if entry["answer"] in best_partial_failures:
                    salvage_words.append(f"{entry['number']}A: {entry['answer']}")
            for entry in best_partial["clues"]["down"]:
                if entry["answer"] in best_partial_failures:
                    salvage_words.append(f"{entry['number']}D: {entry['answer']}")

            salvage_prompt = f"""Write good standard (non-news) crossword clues for these words. These are fallback clues for a news-themed mini crossword where we couldn't find a news hook — make them clean, fair, and crossword-appropriate (definitional or wordplay, concise, under 80 chars):

{chr(10).join(salvage_words)}

Return ONLY a JSON object: {{"clues": {{"4D": "clue here", ...}}}}"""

            salvage_response = call_claude(salvage_prompt, "You are an expert crossword clue writer.")
            salvage_clues = parse_json_response(salvage_response)["clues"]
            puzzle_json = apply_clues(best_partial, salvage_clues)

            if not validate_puzzle(puzzle_json):
                print("Salvage produced an invalid puzzle.")
                sys.exit(1)
            print(f"  Salvage successful: {len(best_partial_failures)} generic clue(s), {total_clues - len(best_partial_failures)} news clues.")
        else:
            print(f"  Cannot salvage: {len(best_partial_failures)} failures exceeds the {max_generic}-clue generic budget.")

    if puzzle_json is None:
        print(f"\nFailed to produce a publishable puzzle after {MAX_GRID_ATTEMPTS} grid attempts.")
        print(f"Words that consistently failed: {sorted(failed_words)}")
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

Write NEW clues for these words that reference DIFFERENT news stories from the past 60 days. Every clue MUST be tied to a real news story from the headlines below — do NOT fall back to generic crossword clues. If you genuinely cannot find a news hook for a word, return "NO_NEWS_HOOK" as its clue text:

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
