# Crosswording the Situation — Daily News Crossword

A daily 5x5 mini crossword where clues are tied to recent news headlines. Rewards news literacy, not just crossword skill.

## Architecture

- **Front-end:** Vanilla HTML/CSS/JS, no framework. Static files served from any host.
- **Puzzle data:** One JSON file per day in `puzzles/YYYY-MM-DD.json`
- **Generation pipeline:** Python scripts in `tools/` that scrape headlines, generate a valid grid, and use Claude (Sonnet 4.6) to write news-themed clues
- **Hosting:** GitHub Pages at https://daylayown.github.io/crossword-puzzle/ (private repo: daylayown/crossword-puzzle)
- **Daily automation:** GitHub Actions cron job generates a new puzzle at 2am MST daily

## Project Structure

```
index.html          — Main puzzle player page
style.css           — Mobile-first responsive styles
crossword.js        — Game engine (grid, input, clues, timer, hints, share, stats)
puzzles/            — Daily puzzle JSON files
tools/
  generate_puzzle.py   — Full pipeline: grid → headlines → Claude clues → dedup check → validate → JSON
  generate_grid.py     — 5x5 crossword grid generator with black squares
  scrape_headlines.py  — Google News RSS feed scraper across categories
.github/workflows/
  deploy.yml           — GitHub Pages deployment (triggers on push to main)
  generate-puzzle.yml  — Daily puzzle generation cron (2am MST) + manual trigger
```

## Puzzle Generation Pipeline

1. `generate_grid.py` creates a valid 5x5 grid with rotationally symmetric black squares. All across/down words are real English words, no duplicates.
2. `scrape_headlines.py` pulls ~400 headlines from Google News RSS (top stories, world, business, tech, entertainment, sports, science, health).
3. `generate_puzzle.py` orchestrates everything: generates grid, scrapes headlines, sends grid + headlines to Claude Sonnet 4.6 via the Anthropic API (using `requests`, no SDK), validates output, writes puzzle JSON.
4. **Dedup check (Step 5):** A second Claude call reviews all clues and flags any that reference the same news story. Conflicting clues are automatically rewritten to reference different stories.

Run manually: `python3 tools/generate_puzzle.py [YYYY-MM-DD]`

Automated: GitHub Actions runs this daily at 2am MST, commits the puzzle JSON, and pushes to main (which triggers a Pages deploy). Can also be triggered manually from the Actions tab.

Requires `ANTHROPIC_API_KEY` env var (stored as a GitHub Actions secret for the cron job). Costs ~$0.01–0.02 per puzzle (two Claude calls when dedup rewrites are needed).

## Key Design Decisions

- Grid is generated first from a broad word list, then Claude writes news-themed clues for the words. This guarantees a valid grid every time (vs. trying to force arbitrary news words into a grid).
- Not every clue needs to be news-themed — a mix of news and standard crossword clues is ideal, like the NYT Mini.
- Each news-themed clue must reference a DIFFERENT story/topic. No repeating the same headline across multiple clues.
- Black squares at (0,4) and (4,0) with rotational symmetry. Gives a mix of 4-letter and 5-letter words.

## What's Working

- Puzzle player UI with grid navigation, clue bar, clue lists, timer
- Hint (reveal letter), Reveal Word, Reveal Puzzle
- Completion detection with shareable emoji grid (green = solved, yellow = revealed)
- **Apple News-inspired completion modal:** encouraging message, stats card (date, solve time, trend vs personal average, current streak), share button
- **Personal solve history** stored in localStorage (`newsword-history` key) — tracks solve time and hint usage per puzzle date
- **Streak tracking** — counts consecutive days with a completed puzzle
- **Trend analysis** — shows how current solve time compares to personal average (hidden on first solve)
- Progress saves to localStorage
- Full generation pipeline with two-pass dedup producing real news-themed puzzles
- **Deployed to GitHub Pages** with automated daily puzzle generation via GitHub Actions (2am MST)

## Domain

Top contenders (all available, need to confirm `cts` specifically):
- **cts.news** — Best thematic fit, ~$7–8/yr
- **cts.today** — Fits the daily format, ~$2–3/yr
- **cts.fun** — Cheap and playful, ~$1–2/yr

## Next Steps

- Clue bucket: let the author manually seed word+clue pairs that the pipeline prefers (see below)
- Firebase Auth (Google sign-in) + Firestore for cross-device personal score sync
- Puzzle archive page
- Custom domain (cts.news, cts.today, or cts.fun)
- Substack integration for distribution
- Monetization (Substack paid tier for archive access / bonus puzzles)

### Deferred to v2

- Friends leaderboard (Apple News-style — add specific friends, compare scores privately)

## Clue Bucket (Planned)

A mechanism for the author to manually contribute answer/clue pairs tied to news they've spotted. The pipeline should prefer these words when building the grid and use the manual clue instead of asking Claude.

Three layers:
1. **Grid bias** — The grid generator should prefer (not require) words that are in the bucket, increasing the odds they land in the puzzle.
2. **Clue override** — When a bucket word appears in the final grid, skip Claude for that word and use the manual clue directly.
3. **Forced placement** — A bucket entry can be marked `"force": true`, meaning the grid MUST contain that word. The generator retries/restructures until it finds a valid grid that includes it. For a 5x5 grid with ~8-9 words, forcing one word is very achievable. This is the "build the entire puzzle around this clue" mode for can't-miss news stories.

Bucket entries live in `puzzles/clue_bucket.json`. Each entry has a word, clue, and optional expiry date (news gets stale). Entries are consumed (marked used) after appearing in a published puzzle to avoid repeats.

Interface options (in order of complexity):
1. **Edit JSON directly** — zero engineering, just open `clue_bucket.json`
2. **CLI command** — `python3 tools/add_clue.py TESLA "Musk's EV company..."` — one-liner that appends to the bucket
3. **Web form** — admin page where you type a word + clue (build later if the workflow gets frequent enough)
