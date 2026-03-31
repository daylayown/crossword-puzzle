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
from datetime import datetime
from pathlib import Path

import requests

# Import our modules
sys.path.insert(0, str(Path(__file__).parent))
from generate_grid import solve_grid, grid_to_json
from scrape_headlines import scrape_all_headlines, format_headlines_for_prompt

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-6"
API_URL = "https://api.anthropic.com/v1/messages"


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


def generate_clues(puzzle_json: dict, headlines_text: str) -> dict:
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

    prompt = f"""Here are today's top news headlines:

{headlines_text}

---

Here is today's crossword grid with the answer words that need clues:

{word_list}

For each word, write a crossword clue.

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

    # Step 1: Generate a valid grid
    print("\nStep 1: Generating crossword grid...")
    random.seed(None)  # Use true randomness
    grid = solve_grid(max_attempts=5000)
    if not grid:
        print("Failed to generate a valid grid. Try again.")
        sys.exit(1)

    puzzle_json = grid_to_json(grid, date)

    # Step 2: Scrape headlines
    print("\nStep 2: Scraping news headlines...")
    headlines = scrape_all_headlines()
    if not headlines:
        print("Warning: No headlines scraped. Clues will be standard crossword clues.")
        headlines_text = "(No current headlines available)"
    else:
        headlines_text = format_headlines_for_prompt(headlines[:100])  # Top 100 headlines

    # Step 3: Generate clues with Claude
    print("\nStep 3: Generating clues with Claude...")
    clues = generate_clues(puzzle_json, headlines_text)

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
