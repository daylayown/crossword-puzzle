(() => {
  "use strict";

  // --- State ---
  let puzzle = null;
  let userGrid = [];
  let revealedCells = []; // Track which cells were revealed (for share result)
  let selectedRow = 0;
  let selectedCol = 0;
  let direction = "across"; // "across" or "down"
  let currentClueIndex = 0;
  let allClues = []; // Flat ordered list: all across then all down
  let timerStart = null;
  let timerInterval = null;
  let solved = false;
  let usedHints = false;

  // --- DOM refs ---
  const gridEl = document.getElementById("grid");
  const clueTextEl = document.getElementById("clue-text");
  const cluesAcrossEl = document.getElementById("clues-across");
  const cluesDownEl = document.getElementById("clues-down");
  const timerEl = document.getElementById("timer");
  const dateEl = document.getElementById("puzzle-date");
  const overlay = document.getElementById("complete-overlay");
  const shareGrid = document.getElementById("share-grid");
  const shareBtn = document.getElementById("share-btn");
  const copiedMsg = document.getElementById("copied-msg");
  const cluePrev = document.getElementById("clue-prev");
  const clueNext = document.getElementById("clue-next");
  const hiddenInput = document.getElementById("hidden-input");
  const btnHint = document.getElementById("btn-hint");
  const btnRevealWord = document.getElementById("btn-reveal-word");
  const btnRevealPuzzle = document.getElementById("btn-reveal-puzzle");

  // --- Load puzzle ---
  async function loadPuzzle() {
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    const urls = [`puzzles/${today}.json`, "puzzles/2026-03-27.json"];

    for (const url of urls) {
      try {
        const res = await fetch(url);
        if (res.ok) {
          puzzle = await res.json();
          break;
        }
      } catch (_) { /* try next */ }
    }

    if (!puzzle) {
      document.getElementById("app").innerHTML = "<p>No puzzle available today. Check back tomorrow!</p>";
      return;
    }

    init();
  }

  function init() {
    const size = puzzle.size;

    // Init user grid and revealed tracking
    userGrid = puzzle.grid.map(row =>
      row.map(cell => (cell === "#" ? null : ""))
    );
    revealedCells = puzzle.grid.map(row =>
      row.map(cell => (cell === "#" ? null : false))
    );

    // Restore saved progress
    const saved = localStorage.getItem(`newsword-${puzzle.date}`);
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.grid) userGrid = parsed.grid;
        if (parsed.revealed) revealedCells = parsed.revealed;
        if (parsed.usedHints) usedHints = parsed.usedHints;
        if (parsed.solved) solved = true;
      } catch (_) { /* ignore */ }
    }

    // Set date
    const d = new Date(puzzle.date + "T12:00:00");
    dateEl.textContent = d.toLocaleDateString("en-US", {
      weekday: "long",
      month: "long",
      day: "numeric",
      year: "numeric",
    });

    // Build flat clue list
    allClues = [
      ...puzzle.clues.across.map(c => ({ ...c, dir: "across" })),
      ...puzzle.clues.down.map(c => ({ ...c, dir: "down" })),
    ];

    buildGrid(size);
    buildClueLists();

    // Select first non-black cell
    let startR = 0, startC = 0;
    for (let r = 0; r < size; r++) {
      for (let c = 0; c < size; c++) {
        if (puzzle.grid[r][c] !== "#") {
          startR = r;
          startC = c;
          r = size; // break outer
          break;
        }
      }
    }
    selectCell(startR, startC, "across");
    startTimer();

    // Event listeners
    document.addEventListener("keydown", handleKeydown);

    // Hidden input for mobile soft keyboard support (iOS doesn't fire keydown for virtual keyboard)
    hiddenInput.addEventListener("beforeinput", handleBeforeInput);
    hiddenInput.addEventListener("input", () => { hiddenInput.value = ""; });
    // Taps on the transparent input overlay → determine which grid cell was hit
    hiddenInput.addEventListener("click", handleInputOverlayClick);

    cluePrev.addEventListener("click", () => cycleClue(-1));
    clueNext.addEventListener("click", () => cycleClue(1));
    shareBtn.addEventListener("click", handleShare);
    btnHint.addEventListener("click", handleHint);
    btnRevealWord.addEventListener("click", handleRevealWord);
    btnRevealPuzzle.addEventListener("click", handleRevealPuzzle);
    document.getElementById("close-modal").addEventListener("click", closeOverlay);
    document.getElementById("done-btn").addEventListener("click", closeOverlay);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeOverlay();
    });

    if (solved) showCompletion();
  }

  // --- Grid ---
  function buildGrid(size) {
    gridEl.innerHTML = "";
    // Compute which cells get clue numbers
    const numberMap = {};
    for (const c of allClues) {
      const key = `${c.row},${c.col}`;
      if (!(key in numberMap)) {
        numberMap[key] = c.number;
      }
    }

    for (let r = 0; r < size; r++) {
      for (let c = 0; c < size; c++) {
        const cell = document.createElement("div");
        cell.className = "cell";
        cell.dataset.row = r;
        cell.dataset.col = c;

        if (puzzle.grid[r][c] === "#") {
          cell.classList.add("black");
        } else {
          // Number
          const key = `${r},${c}`;
          if (numberMap[key] !== undefined) {
            const num = document.createElement("span");
            num.className = "cell-number";
            num.textContent = numberMap[key];
            cell.appendChild(num);
          }

          // Letter
          const letter = document.createElement("span");
          letter.className = "cell-letter";
          letter.textContent = userGrid[r][c] || "";
          cell.appendChild(letter);

          // Mark revealed cells
          if (revealedCells[r][c]) {
            cell.classList.add("revealed");
          }

          cell.addEventListener("click", () => onCellClick(r, c));
        }

        gridEl.appendChild(cell);
      }
    }
  }

  function getCellEl(r, c) {
    return gridEl.children[r * puzzle.size + c];
  }

  function updateCellDisplay(r, c) {
    const cell = getCellEl(r, c);
    const letterEl = cell.querySelector(".cell-letter");
    if (letterEl) letterEl.textContent = userGrid[r][c] || "";
    if (revealedCells[r]?.[c]) {
      cell.classList.add("revealed");
    }
  }

  // --- Selection & highlighting ---
  function selectCell(r, c, dir) {
    if (r < 0 || r >= puzzle.size || c < 0 || c >= puzzle.size) return;
    if (puzzle.grid[r][c] === "#") return;

    selectedRow = r;
    selectedCol = c;
    if (dir) direction = dir;

    // Verify current direction has a valid clue for this cell
    const clue = getClueForCell(r, c, direction);
    if (!clue) {
      // Try the other direction
      const otherDir = direction === "across" ? "down" : "across";
      if (getClueForCell(r, c, otherDir)) {
        direction = otherDir;
      }
    }

    updateHighlighting();
    updateClueBar();
    updateClueListHighlight();
  }

  function getClueForCell(r, c, dir) {
    const clues = dir === "across" ? puzzle.clues.across : puzzle.clues.down;
    for (const clue of clues) {
      const cells = getClueCells(clue, dir);
      if (cells.some(([cr, cc]) => cr === r && cc === c)) {
        return { ...clue, dir };
      }
    }
    return null;
  }

  function getClueCells(clue, dir) {
    const cells = [];
    for (let i = 0; i < clue.length; i++) {
      if (dir === "across") {
        cells.push([clue.row, clue.col + i]);
      } else {
        cells.push([clue.row + i, clue.col]);
      }
    }
    return cells;
  }

  function getCurrentClue() {
    return getClueForCell(selectedRow, selectedCol, direction);
  }

  function updateHighlighting() {
    for (const cell of gridEl.children) {
      cell.classList.remove("selected", "highlighted");
    }

    const clue = getCurrentClue();
    if (clue) {
      const cells = getClueCells(clue, clue.dir);
      for (const [r, c] of cells) {
        getCellEl(r, c).classList.add("highlighted");
      }
    }

    getCellEl(selectedRow, selectedCol).classList.add("selected");
  }

  // --- Clue bar ---
  function updateClueBar() {
    const clue = getCurrentClue();
    if (clue) {
      clueTextEl.innerHTML = `<span class="clue-label">${clue.number}${clue.dir === "across" ? "A" : "D"}</span> ${clue.clue}`;
      currentClueIndex = allClues.findIndex(
        c => c.number === clue.number && c.dir === clue.dir
      );
    }
  }

  function cycleClue(delta) {
    currentClueIndex = (currentClueIndex + delta + allClues.length) % allClues.length;
    const clue = allClues[currentClueIndex];
    direction = clue.dir;
    selectCell(clue.row, clue.col, clue.dir);
  }

  // --- Clue lists ---
  function buildClueLists() {
    cluesAcrossEl.innerHTML = "";
    cluesDownEl.innerHTML = "";

    for (const clue of puzzle.clues.across) {
      const li = document.createElement("li");
      li.innerHTML = `<span class="clue-number">${clue.number}</span>${clue.clue}`;
      li.dataset.number = clue.number;
      li.dataset.dir = "across";
      li.addEventListener("click", () => {
        direction = "across";
        selectCell(clue.row, clue.col, "across");
      });
      cluesAcrossEl.appendChild(li);
    }

    for (const clue of puzzle.clues.down) {
      const li = document.createElement("li");
      li.innerHTML = `<span class="clue-number">${clue.number}</span>${clue.clue}`;
      li.dataset.number = clue.number;
      li.dataset.dir = "down";
      li.addEventListener("click", () => {
        direction = "down";
        selectCell(clue.row, clue.col, "down");
      });
      cluesDownEl.appendChild(li);
    }
  }

  function updateClueListHighlight() {
    for (const li of cluesAcrossEl.children) li.classList.remove("active");
    for (const li of cluesDownEl.children) li.classList.remove("active");

    const clue = getCurrentClue();
    if (!clue) return;

    const container = clue.dir === "across" ? cluesAcrossEl : cluesDownEl;
    for (const li of container.children) {
      if (li.dataset.number === String(clue.number) && li.dataset.dir === clue.dir) {
        li.classList.add("active");
      }
    }
  }

  // --- Input handling ---
  function onCellClick(r, c) {
    if (r === selectedRow && c === selectedCol) {
      // Clicking same cell toggles direction
      const otherDir = direction === "across" ? "down" : "across";
      if (getClueForCell(r, c, otherDir)) {
        direction = otherDir;
      }
    }
    selectCell(r, c);
  }

  function handleInputOverlayClick(e) {
    const gridRect = gridEl.getBoundingClientRect();
    const x = e.clientX - gridRect.left;
    const y = e.clientY - gridRect.top;

    if (x < 0 || y < 0 || x > gridRect.width || y > gridRect.height) return;

    const cellWidth = gridRect.width / puzzle.size;
    const cellHeight = gridRect.height / puzzle.size;
    const col = Math.floor(x / cellWidth);
    const row = Math.floor(y / cellHeight);

    if (row >= 0 && row < puzzle.size && col >= 0 && col < puzzle.size) {
      if (puzzle.grid[row][col] !== "#") {
        onCellClick(row, col);
      }
    }
  }

  function handleBeforeInput(e) {
    if (solved) return;

    if (e.inputType === "insertText" && e.data && /^[a-zA-Z]$/.test(e.data)) {
      e.preventDefault();
      handleLetterInput(e.data.toUpperCase());
    } else if (e.inputType === "deleteContentBackward") {
      e.preventDefault();
      handleBackspace();
    }
  }

  function handleKeydown(e) {
    if (solved) return;

    const key = e.key;

    if (key === "ArrowRight") {
      e.preventDefault();
      moveSelection(0, 1);
    } else if (key === "ArrowLeft") {
      e.preventDefault();
      moveSelection(0, -1);
    } else if (key === "ArrowDown") {
      e.preventDefault();
      moveSelection(1, 0);
    } else if (key === "ArrowUp") {
      e.preventDefault();
      moveSelection(-1, 0);
    } else if (key === "Tab") {
      e.preventDefault();
      cycleClue(e.shiftKey ? -1 : 1);
    } else if (key === "Backspace" || key === "Delete") {
      e.preventDefault();
      handleBackspace();
    } else if (/^[a-zA-Z]$/.test(key)) {
      e.preventDefault();
      handleLetterInput(key.toUpperCase());
    }
  }

  function handleLetterInput(letter) {
    if (puzzle.grid[selectedRow][selectedCol] === "#") return;

    userGrid[selectedRow][selectedCol] = letter;
    updateCellDisplay(selectedRow, selectedCol);
    saveProgress();
    advanceCursor();
    checkCompletion();
  }

  function handleBackspace() {
    if (userGrid[selectedRow][selectedCol] !== "") {
      userGrid[selectedRow][selectedCol] = "";
      updateCellDisplay(selectedRow, selectedCol);
      saveProgress();
    } else {
      retreatCursor();
      if (userGrid[selectedRow]?.[selectedCol] !== undefined &&
          userGrid[selectedRow][selectedCol] !== null) {
        userGrid[selectedRow][selectedCol] = "";
        updateCellDisplay(selectedRow, selectedCol);
        saveProgress();
      }
    }
  }

  function advanceCursor() {
    const clue = getCurrentClue();
    if (!clue) return;

    const cells = getClueCells(clue, clue.dir);
    const idx = cells.findIndex(([r, c]) => r === selectedRow && c === selectedCol);

    // Move to next empty cell in current word
    for (let i = idx + 1; i < cells.length; i++) {
      const [r, c] = cells[i];
      if (userGrid[r][c] === "") {
        selectCell(r, c);
        return;
      }
    }

    // If no empty cell ahead, move to next cell (if any)
    if (idx + 1 < cells.length) {
      const [r, c] = cells[idx + 1];
      selectCell(r, c);
    }
  }

  function retreatCursor() {
    const clue = getCurrentClue();
    if (!clue) return;

    const cells = getClueCells(clue, clue.dir);
    const idx = cells.findIndex(([r, c]) => r === selectedRow && c === selectedCol);

    if (idx > 0) {
      const [r, c] = cells[idx - 1];
      selectCell(r, c);
    }
  }

  function moveSelection(dr, dc) {
    if (dc !== 0) direction = "across";
    if (dr !== 0) direction = "down";

    let r = selectedRow + dr;
    let c = selectedCol + dc;

    while (r >= 0 && r < puzzle.size && c >= 0 && c < puzzle.size) {
      if (puzzle.grid[r][c] !== "#") {
        selectCell(r, c);
        return;
      }
      r += dr;
      c += dc;
    }
  }

  // --- Hints & Reveals ---
  function revealCell(r, c) {
    if (puzzle.grid[r][c] === "#") return;
    if (userGrid[r][c] === puzzle.grid[r][c] && !revealedCells[r][c]) return; // Already correct by user

    userGrid[r][c] = puzzle.grid[r][c];
    revealedCells[r][c] = true;
    usedHints = true;
    updateCellDisplay(r, c);
  }

  function handleHint() {
    if (solved) return;

    // Reveal the selected cell
    revealCell(selectedRow, selectedCol);
    saveProgress();
    advanceCursor();
    checkCompletion();
  }

  function handleRevealWord() {
    if (solved) return;

    const clue = getCurrentClue();
    if (!clue) return;

    const cells = getClueCells(clue, clue.dir);
    for (const [r, c] of cells) {
      revealCell(r, c);
    }
    saveProgress();
    checkCompletion();
  }

  function handleRevealPuzzle() {
    if (solved) return;

    for (let r = 0; r < puzzle.size; r++) {
      for (let c = 0; c < puzzle.size; c++) {
        if (puzzle.grid[r][c] !== "#") {
          revealCell(r, c);
        }
      }
    }
    saveProgress();
    checkCompletion();
  }

  // --- Timer ---
  function startTimer() {
    if (solved) return;

    timerStart = Date.now();
    const savedStart = localStorage.getItem(`newsword-timer-${puzzle.date}`);
    if (savedStart) {
      timerStart = parseInt(savedStart);
    } else {
      localStorage.setItem(`newsword-timer-${puzzle.date}`, timerStart);
    }

    timerInterval = setInterval(updateTimer, 1000);
    updateTimer();
  }

  function updateTimer() {
    if (solved) return;
    const elapsed = Math.floor((Date.now() - timerStart) / 1000);
    const min = Math.floor(elapsed / 60);
    const sec = elapsed % 60;
    timerEl.textContent = `${min}:${sec.toString().padStart(2, "0")}`;
  }

  function getElapsedTime() {
    const elapsed = Math.floor((Date.now() - timerStart) / 1000);
    const min = Math.floor(elapsed / 60);
    const sec = elapsed % 60;
    return `${min}:${sec.toString().padStart(2, "0")}`;
  }

  // --- Completion ---
  function checkCompletion() {
    let allFilled = true;
    let allCorrect = true;

    for (let r = 0; r < puzzle.size; r++) {
      for (let c = 0; c < puzzle.size; c++) {
        if (puzzle.grid[r][c] === "#") continue;
        if (userGrid[r][c] === "") {
          allFilled = false;
          allCorrect = false;
        } else if (userGrid[r][c] !== puzzle.grid[r][c]) {
          allCorrect = false;
        }
      }
    }

    if (allCorrect) {
      solved = true;
      clearInterval(timerInterval);

      // Save solve time to history
      const elapsedSeconds = Math.floor((Date.now() - timerStart) / 1000);
      saveSolveRecord(puzzle.date, elapsedSeconds, usedHints);

      saveProgress();
      showCompletion();
    } else if (allFilled) {
      // Grid is full but has errors — flash incorrect cells
      for (let r = 0; r < puzzle.size; r++) {
        for (let c = 0; c < puzzle.size; c++) {
          if (puzzle.grid[r][c] === "#") continue;
          if (userGrid[r][c] !== puzzle.grid[r][c]) {
            const cell = getCellEl(r, c);
            cell.classList.add("incorrect");
            setTimeout(() => cell.classList.remove("incorrect"), 1000);
          }
        }
      }
    }
  }

  function showCompletion() {
    // Use saved history time if available (handles page reload after solve)
    const history = getSolveHistory();
    const savedRecord = history[puzzle.date];
    const elapsedSeconds = savedRecord
      ? savedRecord.time
      : Math.floor((Date.now() - timerStart) / 1000);
    const min = Math.floor(elapsedSeconds / 60);
    const sec = elapsedSeconds % 60;
    const time = `${min}:${sec.toString().padStart(2, "0")}`;

    // Encouraging message
    document.getElementById("complete-message").textContent = getEncouragingMessage();

    // Stats: date
    const d = new Date(puzzle.date + "T12:00:00");
    document.getElementById("stats-date").textContent = d.toLocaleDateString("en-US", {
      weekday: "long",
      month: "short",
      day: "numeric",
      year: "numeric",
    });

    // Stats: solve time
    const timeDisplay = usedHints ? `${time} (hints)` : time;
    document.getElementById("stats-time").textContent = timeDisplay;

    // Stats: trend
    const trendRow = document.getElementById("stats-trend-row");
    const trend = getTrend(elapsedSeconds);
    if (trend !== null) {
      document.getElementById("stats-trend").textContent = formatTrend(trend);
      trendRow.style.display = "";
    } else {
      trendRow.style.display = "none";
    }

    // Stats: streak
    const streak = getCurrentStreak();
    document.getElementById("stats-streak").textContent =
      streak === 1 ? "1 day" : `${streak} days`;

    // Build share grid
    const lines = [];
    for (let r = 0; r < puzzle.size; r++) {
      let line = "";
      for (let c = 0; c < puzzle.size; c++) {
        if (puzzle.grid[r][c] === "#") {
          line += "\u2b1b";
        } else if (revealedCells[r][c]) {
          line += "\ud83d\udfe8";
        } else {
          line += "\ud83d\udfe9";
        }
      }
      lines.push(line);
    }
    shareGrid.textContent = lines.join("\n");

    overlay.classList.remove("hidden");
  }

  function closeOverlay() {
    overlay.classList.add("hidden");
  }

  function handleShare() {
    const time = getElapsedTime();
    const d = new Date(puzzle.date + "T12:00:00");
    const dateStr = d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

    const lines = [];
    for (let r = 0; r < puzzle.size; r++) {
      let line = "";
      for (let c = 0; c < puzzle.size; c++) {
        if (puzzle.grid[r][c] === "#") {
          line += "\u2b1b";
        } else if (revealedCells[r][c]) {
          line += "\ud83d\udfe8";
        } else {
          line += "\ud83d\udfe9";
        }
      }
      lines.push(line);
    }

    const hint_note = usedHints ? " (with hints)" : "";
    const text = `Crosswording The Situation ${dateStr}\n${time}${hint_note}\n\n${lines.join("\n")}`;

    if (navigator.share) {
      navigator.share({ text }).catch(() => copyToClipboard(text));
    } else {
      copyToClipboard(text);
    }
  }

  function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
      copiedMsg.classList.remove("hidden");
      setTimeout(() => copiedMsg.classList.add("hidden"), 2000);
    });
  }

  // --- Solve history (for stats, streaks, trends) ---
  function getSolveHistory() {
    try {
      return JSON.parse(localStorage.getItem("newsword-history") || "{}");
    } catch (_) { return {}; }
  }

  function saveSolveRecord(date, timeSeconds, usedHints) {
    const history = getSolveHistory();
    // Don't overwrite — keep the first solve
    if (history[date]) return;
    history[date] = { time: timeSeconds, hints: usedHints };
    localStorage.setItem("newsword-history", JSON.stringify(history));
  }

  function getPersonalAverage() {
    const history = getSolveHistory();
    const times = Object.values(history).map(h => h.time);
    if (times.length === 0) return null;
    return Math.round(times.reduce((a, b) => a + b, 0) / times.length);
  }

  function getTrend(currentTimeSeconds) {
    const avg = getPersonalAverage();
    if (avg === null) return null;
    const diff = currentTimeSeconds - avg;
    return diff; // negative = faster than average
  }

  function getCurrentStreak() {
    const history = getSolveHistory();
    const dates = Object.keys(history).sort().reverse();
    if (dates.length === 0) return 0;

    // Check if today (or the current puzzle date) is in the history
    const today = puzzle.date;
    if (!history[today]) return 0;

    let streak = 1;
    let current = new Date(today + "T12:00:00");

    for (let i = 0; i < 365; i++) {
      current.setDate(current.getDate() - 1);
      const dateStr = current.toISOString().slice(0, 10);
      if (history[dateStr]) {
        streak++;
      } else {
        break;
      }
    }

    return streak;
  }

  function getEncouragingMessage() {
    const messages = [
      "Brilliant Work!",
      "Nailed It!",
      "Well Done!",
      "Impressive!",
      "Sharp Mind!",
      "You're on Fire!",
      "Crushed It!",
      "Nice Solve!",
    ];
    return messages[Math.floor(Math.random() * messages.length)];
  }

  function formatTrend(diffSeconds) {
    if (diffSeconds === null) return null;
    const absDiff = Math.abs(diffSeconds);
    const min = Math.floor(absDiff / 60);
    const sec = absDiff % 60;
    let timeStr;
    if (min > 0 && sec > 0) timeStr = `${min}m ${sec}s`;
    else if (min > 0) timeStr = `${min}m`;
    else timeStr = `${sec}s`;

    if (diffSeconds < 0) return `${timeStr} faster than average`;
    if (diffSeconds > 0) return `${timeStr} slower than average`;
    return "Right at your average";
  }

  // --- Save/restore ---
  function saveProgress() {
    localStorage.setItem(`newsword-${puzzle.date}`, JSON.stringify({
      grid: userGrid,
      revealed: revealedCells,
      usedHints,
      solved,
    }));
  }

  // --- Start ---
  loadPuzzle();
})();
