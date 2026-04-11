# Crosswording the Situation — Daily News Crossword

A daily 5x5 mini crossword where clues are tied to recent news headlines. Rewards news literacy, not just crossword skill.

## Architecture

- **Front-end:** Vanilla HTML/CSS/JS, no framework. Static files served from any host.
- **Puzzle data:** One JSON file per day in `puzzles/YYYY-MM-DD.json`
- **Generation pipeline:** Python scripts in `tools/` that scrape headlines, generate a valid grid, and use Claude (Sonnet 4.6) to write news-themed clues
- **Hosting:** GitHub Pages at https://crosswordingthesituation.com (repo: daylayown/crossword-puzzle)
- **Daily automation:** GitHub Actions cron job generates a new puzzle at 2am MST daily

## Project Structure

```
index.html          — Main puzzle player page
style.css           — Mobile-first responsive styles
crossword.js        — Game engine (grid, input, clues, timer, hints, share, stats)
puzzles/            — Daily puzzle JSON files
puzzles/headlines/  — Cached headline JSON files (gitignored, built up over daily runs)
tools/
  generate_puzzle.py   — Full pipeline: grid → headlines → Claude clues → dedup check → validate → JSON
  generate_grid.py     — 5x5 crossword grid generator with black squares
  wordlist.json        — 12,720 words from Spread The Wordlist (STWL), score 50+, 3-5 letters
  scrape_headlines.py  — Google News RSS feed scraper across categories
  scrape_bluesky.py    — Bluesky AT Protocol scraper for news org feeds (NYT, Reuters, AP, WSJ, BBC, WashPost)
.github/workflows/
  deploy.yml           — GitHub Pages deployment (triggers on push to main)
  generate-puzzle.yml  — Daily puzzle generation cron (2am MST) + manual trigger
```

## Puzzle Generation Pipeline

1. `generate_grid.py` creates a valid 5x5 grid with rotationally symmetric black squares. All across/down words are real English words from the STWL word list, no duplicates. The generator excludes answer words used in the past 28 days to prevent repetition.
2. **Multi-source headline scraping (60-day window):**
   - `scrape_headlines.py` pulls ~400 headlines from Google News RSS (top stories, world, business, tech, entertainment, sports, science, health). These represent today's trending stories.
   - `scrape_bluesky.py` pulls up to **60 days** of posts from 6 major news orgs on Bluesky (NYT, Reuters, AP, WSJ, BBC, WashPost) via the public AT Protocol API (no auth needed). This provides depth and variety beyond what's trending today.
   - **Headline cache:** Each run saves its scraped headlines to `puzzles/headlines/YYYY-MM-DD.json`. Previous 60 days' cached headlines are loaded and merged, giving the pipeline a growing archive. On GitHub Actions (fresh checkout), the Bluesky 60-day lookback fills this role.
   - All sources are merged, deduplicated by title, sorted freshest-first. Top 200 headlines are sent to Claude, tagged with age (e.g., "today", "3d ago"). The 60-day window is the *only* news universe Claude is allowed to draw from.
3. **Cross-day dedup (answers + clues):** Before generating the grid, the pipeline reads the last 28 days of puzzle JSONs from `puzzles/` and extracts used answer words. These are passed to the grid generator as exclusions so the same answers don't repeat across days. The same 28-day window of clue texts is also injected into Claude's prompt as "stories already used — avoid these" (soft steer for clue topics).
4. `generate_puzzle.py` orchestrates everything: loads recent answers → scrapes headlines from all sources → enters a **grid+clues retry loop** (up to 4 attempts): generates grid → asks Claude for news-only clues → scans for `NO_NEWS_HOOK` markers → if any word couldn't be hooked to news, that word is added to the exclusion set and a fresh grid is generated → repeat. Once every clue is news-based, validate and run the dedup check.
5. **Within-puzzle dedup check (Step 5):** A second Claude call reviews all clues and flags any that reference the same news story. Conflicting clues are automatically rewritten to reference different stories (also news-only — `NO_NEWS_HOOK` is the escape hatch).
6. **News-only enforcement with 10% salvage:** The Claude system prompt mandates that *every* clue tie to a real story from the past 60 days. If Claude cannot find a hook for a word, it returns the literal string `NO_NEWS_HOOK`, which the pipeline detects and uses to retry with that word excluded. **If all 4 grid attempts still leave some words unhooked**, the pipeline picks the best partial attempt (fewest failures) and runs a salvage pass: standard crossword clues are written for the failing words, but only if at most **10% of the puzzle's clues** would be generic (`ceil(total_clues * 0.10)`, which for a typical 5x5 mini means at most 1 generic clue). If even the best attempt exceeds the 10% generic budget, the script exits non-zero and no puzzle is published for that day.

Run manually: `python3 tools/generate_puzzle.py [YYYY-MM-DD]`

Automated: GitHub Actions runs this daily at 2am MST, commits the puzzle JSON, and pushes to main (which triggers a Pages deploy). Can also be triggered manually from the Actions tab.

Requires `ANTHROPIC_API_KEY` env var (stored as a GitHub Actions secret for the cron job). Costs ~$0.01–0.02 per puzzle (two Claude calls when dedup rewrites are needed).

## Key Design Decisions

- Grid is generated first from a broad word list, then Claude writes news-themed clues for the words. This guarantees a valid grid every time (vs. trying to force arbitrary news words into a grid).
- **Word list: Spread The Wordlist (STWL)** — 12,720 words (1,542 three-letter, 3,631 four-letter, 7,547 five-letter) filtered to score 50+ (highest quality tier). Stored in `tools/wordlist.json`. Licensed CC BY-NC-SA 4.0 — attribution required, non-commercial, share-alike. Old hardcoded word lists (~1,700 words) kept as fallback in `generate_grid.py`.
- **Answer dedup across days** — The grid generator accepts an exclusion set of recently used answer words (past 28 days). It generates multiple candidate grids and picks the one with the fewest overlaps. With 12,720 words in the pool, excluding ~280 recent answers still leaves plenty of candidates. Falls back to 7-day exclusions, then no exclusions, if needed.
- **Every clue must be news-themed.** This is a *news* crossword — generic trivia/vocabulary clues defeat the entire point. If a word genuinely has no recent-news angle, that's a signal to regenerate the grid, not to fall back on a dictionary clue.
- Each news-themed clue must reference a DIFFERENT story/topic. No repeating the same headline across multiple clues — enforced both within a single puzzle (two-pass dedup) and across consecutive days (28-day lookback).
- Headlines are sourced from Google News RSS (today's trending) and Bluesky news org feeds (28-day depth). More data = more variety = fewer repeated stories.
- Black squares at (0,4) and (4,0) with rotational symmetry. Gives a mix of 4-letter and 5-letter words.

## What's Working

- Puzzle player UI with grid navigation, clue bar, clue lists, timer
- Hint (reveal letter), Reveal Word, Reveal Puzzle
- Completion detection with shareable emoji grid (green = solved, yellow = revealed)
- **Apple News-inspired completion modal:** encouraging message, stats card (date, solve time, trend vs personal average, current streak), share button
- **Personal solve history** stored in localStorage (`newsword-history` key) — tracks solve time and hint usage per puzzle date
- **Streak tracking** — counts consecutive days with a completed puzzle
- **Trend analysis** — shows how current solve time compares to personal average (hidden on first solve)
- **Auto-completion detection:** When the last cell is filled, the game automatically checks the grid. If all correct, the completion modal appears. If there are errors, incorrect cells flash red and shake to show the player where to look — no need to hit "Reveal Puzzle" to check.
- Progress saves to localStorage
- Full generation pipeline with two-pass dedup producing real news-themed puzzles
- **STWL word list** (12,720 words, score 50+) replacing old hardcoded 1,701-word list — dramatically more grid variety
- **Answer dedup across days:** Grid generator excludes answer words from the past 28 days, preventing the same words from appearing in consecutive puzzles
- **Multi-source headlines:** Google News RSS (today) + Bluesky feeds from 6 news orgs (28-day lookback) + daily headline cache
- **Cross-day story dedup:** Pipeline reads last 28 days of puzzles and steers Sonnet away from recently used stories and answer words
- **Deployed to GitHub Pages** with automated daily puzzle generation via GitHub Actions (2am MST)
- **Custom domain:** crosswordingthesituation.com (registered via Cloudflare, DNS-only mode)
- **Analytics:** Google Analytics 4 (G-F5ZLZD433P) for visitor tracking
- **iOS mobile keyboard support:** iOS Safari doesn't fire `keydown` events for virtual keyboard letters on `<div>` elements. A transparent `<input>` (not hidden — `opacity:0` breaks iOS) is positioned directly over the active cell (`position: absolute`, cell-sized, `z-index: 2`). It moves via `positionInput()` on each cell selection. iOS sees a normally-positioned visible input at the tap location, so it doesn't scroll. Letters are captured via `beforeinput` events. Based on the [Guardian crossword's approach](https://github.com/zetter/react-crossword).
- **Site footer** with author info and contact links

## Next Steps

- Word list quality tuning: some STWL score-50 words are obscure for a mini crossword (e.g. OLEIC, TINGA, ETDS). Consider cross-referencing with a word frequency list to filter out uncommon entries, or bumping the minimum score threshold.
- Clue bucket: let the author manually seed word+clue pairs that the pipeline prefers (see below)
- Firebase Auth (Google sign-in) + Firestore for cross-device personal score sync
- Puzzle archive page
- Custom domain (cts.news, cts.today, or cts.fun)
- Substack integration for distribution
- Monetization (Substack paid tier for archive access / bonus puzzles)

### UX improvements (from Guardian crossword research)

- **Resize/orientation handler** — Recalculate hidden input position on viewport resize. Currently if someone rotates their phone mid-puzzle, the input misaligns. One-liner `resize` event listener calling `positionInput()`.
- **ARIA accessibility** — Add `role="grid"` on the grid container, `aria-label` on cells, `aria-live="polite"` on the clue bar for screen reader support. Important if audience grows.
- **URL fragment deep-linking** — e.g. `#2D` jumps to clue 2-Down. Nice for sharing "I'm stuck on this clue" links.

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
