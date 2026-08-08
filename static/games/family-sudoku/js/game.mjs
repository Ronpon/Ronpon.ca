import {
  parseBoardString,
  validatePuzzlePair,
  createFallbackVariant,
  getConflictIndexes,
  isSolved,
} from "./engine.mjs";

const root = document.querySelector("[data-family-sudoku]");
const $ = (selector) => root.querySelector(selector);
const STORAGE_KEY = "ronpon.familySudoku.v1";
const difficulties = new Set(["easy", "medium", "hard"]);

let faces;
let bank;
let state = null;
let worker = null;
let timer = null;
let restoreFocus = null;
let restoreFocusIndex = null;
let previousOverflow = "";
const imageOK = new Map();

const status = (message) => {
  $("[data-status]").textContent = message;
};

function faceURL(face) {
  return new URL(face.image, new URL(root.dataset.facesUrl, location.href)).href;
}

function save() {
  if (!state) return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      ...state,
      updatedAt: new Date().toISOString(),
    }));
  } catch (error) {
    console.warn("Family Sudoku save unavailable", error);
  }
}

function validFaceImagePath(image) {
  if (typeof image !== "string" || !image || /^(?:[a-z][a-z\d+.-]*:|\\|\/\/|\/)/i.test(image)) return false;
  try {
    return new URL(image, new URL(root.dataset.facesUrl, location.href)).origin === location.origin;
  } catch {
    return false;
  }
}

function validateFaces(data) {
  if (!data || data.version !== 1 || !difficulties.has(data.defaultDifficulty) || !Array.isArray(data.faces) || data.faces.length !== 9) {
    throw new Error("Invalid face configuration");
  }
  for (const field of ["gameTitle", "subtitle", "completionTitle", "completionMessage"]) {
    if (typeof data[field] !== "string" || !data[field].trim()) throw new Error("Invalid face configuration");
  }
  const seen = new Set();
  for (const face of data.faces) {
    if (!face || !Number.isInteger(face.value) || face.value < 1 || face.value > 9 || seen.has(face.value)) {
      throw new Error("Invalid face configuration");
    }
    if (typeof face.name !== "string" || !face.name.trim()) throw new Error("Invalid face configuration");
    if (typeof face.shortLabel !== "string" || !face.shortLabel || [...face.shortLabel].length > 2) {
      throw new Error("Invalid face configuration");
    }
    if (!validFaceImagePath(face.image)) throw new Error("Invalid face configuration");
    seen.add(face.value);
  }
  if (seen.size !== 9) throw new Error("Invalid face configuration");
  return data;
}

function validHistory(history) {
  return Array.isArray(history) && history.every((move) => (
    move && Number.isInteger(move.index) && move.index >= 0 && move.index < 81
    && Number.isInteger(move.value) && move.value >= 0 && move.value <= 9
    && Array.isArray(move.notes)
    && move.notes.every((value) => Number.isInteger(value) && value >= 1 && value <= 9)
    && typeof move.hinted === "boolean"
  ));
}

function validateState(value) {
  if (!value || value.version !== 1 || !difficulties.has(value.difficulty) || !["robatron", "fallback"].includes(value.source)) {
    throw new Error("Invalid saved game");
  }
  for (const name of ["puzzle", "solution", "board"]) {
    if (!Array.isArray(value[name]) || value[name].length !== 81 || value[name].some((v) => !Number.isInteger(v) || v < 0 || v > 9)) {
      throw new Error("Invalid saved game");
    }
  }
  validatePuzzlePair(value.puzzle, value.solution);
  if (!Array.isArray(value.givens) || value.givens.length !== 81 || value.givens.some((v) => typeof v !== "boolean")) {
    throw new Error("Invalid givens");
  }
  if (value.puzzle.some((v, i) => Boolean(v) !== value.givens[i] || (v && value.board[i] !== v))) {
    throw new Error("Invalid givens");
  }
  if (!Array.isArray(value.notes) || value.notes.length !== 81 || value.notes.some((notes) => (
    !Array.isArray(notes) || new Set(notes).size !== notes.length
    || notes.some((v) => !Number.isInteger(v) || v < 1 || v > 9)
  ))) throw new Error("Invalid notes");
  if (!Array.isArray(value.hinted) || value.hinted.length !== 81 || value.hinted.some((v) => typeof v !== "boolean")) {
    throw new Error("Invalid hints");
  }
  if (!validHistory(value.history || []) || !Number.isInteger(value.hintsUsed) || value.hintsUsed < 0 || !Number.isInteger(value.checksUsed) || value.checksUsed < 0) {
    throw new Error("Invalid saved game");
  }
  if (value.selectedIndex !== null && (!Number.isInteger(value.selectedIndex) || value.selectedIndex < 0 || value.selectedIndex >= 81)) {
    throw new Error("Invalid selection");
  }
  if (typeof value.noteMode !== "boolean") throw new Error("Invalid note mode");
  return {
    ...value,
    givens: value.puzzle.map(Boolean),
    notes: value.notes.map((notes) => [...notes].sort((a, b) => a - b)),
    history: (value.history || []).slice(-200),
    checkedWrong: [],
    completed: isSolved(value.board, value.solution),
  };
}

function initial(puzzle, solution, difficulty, source, id) {
  const puzzleBoard = parseBoardString(puzzle);
  return {
    version: 1,
    puzzleId: id || `${source}-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    source,
    difficulty,
    puzzle: puzzleBoard,
    solution: parseBoardString(solution),
    board: [...puzzleBoard],
    givens: puzzleBoard.map(Boolean),
    notes: Array.from({ length: 81 }, () => []),
    hinted: Array(81).fill(false),
    selectedIndex: null,
    noteMode: false,
    checkedWrong: [],
    history: [],
    hintsUsed: 0,
    checksUsed: 0,
    completed: false,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

function token(value) {
  const face = faces.faces.find((item) => item.value === value);
  const span = document.createElement("span");
  span.className = "fs-token";
  span.setAttribute("aria-hidden", "true");
  if (imageOK.get(value)) {
    const image = document.createElement("img");
    image.src = faceURL(face);
    image.alt = "";
    span.append(image);
  } else {
    span.textContent = face.shortLabel;
  }
  return span;
}

function render() {
  if (!state) return;
  const board = $("[data-board]");
  const conflicts = getConflictIndexes(state.board);
  board.replaceChildren();
  state.board.forEach((value, index) => {
    const button = document.createElement("button");
    const row = Math.floor(index / 9) + 1;
    const column = index % 9 + 1;
    button.type = "button";
    button.role = "gridcell";
    button.dataset.index = index;
    button.className = state.givens[index] ? "fs-cell--given" : "";
    if (index === state.selectedIndex) button.classList.add("fs-cell--selected");
    if (conflicts.has(index)) button.classList.add("fs-cell--conflict");
    if (state.checkedWrong.includes(index)) button.classList.add("fs-cell--wrong");
    if (value) {
      button.append(token(value));
    } else if (state.notes[index].length) {
      const notes = document.createElement("span");
      notes.className = "fs-notes";
      for (let note = 1; note < 10; note += 1) {
        const item = document.createElement("span");
        item.textContent = state.notes[index].includes(note) ? faces.faces.find((face) => face.value === note).shortLabel : "";
        notes.append(item);
      }
      button.append(notes);
    } else {
      button.textContent = "·";
    }
    const name = value ? faces.faces.find((face) => face.value === value).name : "empty";
    button.setAttribute("aria-label", `Row ${row}, column ${column}, ${state.givens[index] ? "given" : "editable"}, ${name}${conflicts.has(index) ? ", conflict" : ""}${state.checkedWrong.includes(index) ? ", checked incorrect" : ""}`);
    button.disabled = state.completed;
    button.addEventListener("click", () => select(index, true));
    board.append(button);
  });
  $("[data-action=notes]").textContent = `Notes: ${state.noteMode ? "on" : "off"}`;
  $("[data-difficulty]").value = state.difficulty;
  ["notes", "erase", "undo", "hint", "check"].forEach((action) => {
    const button = $(`[data-action=${action}]`);
    if (button) button.disabled = state.completed;
  });
}

function select(index, open) {
  if (!state || state.completed) return;
  const origin = root.querySelector(`[data-index="${index}"]`);
  state.selectedIndex = index;
  render();
  if (open && !state.givens[index]) openPicker(index, origin);
}

function record(index) {
  state.history.push({ index, value: state.board[index], notes: [...state.notes[index]], hinted: state.hinted[index] });
  if (state.history.length > 200) state.history.shift();
}

function apply(value) {
  if (!state) return;
  const index = state.selectedIndex;
  if (index === null || state.givens[index] || state.completed) return;
  if (state.noteMode && state.board[index] === 0) {
    record(index);
    const notes = new Set(state.notes[index]);
    if (notes.has(value)) notes.delete(value); else notes.add(value);
    state.notes[index] = [...notes].sort((a, b) => a - b);
  } else {
    record(index);
    state.board[index] = value;
    state.notes[index] = [];
    state.hinted[index] = false;
  }
  state.checkedWrong = state.checkedWrong.filter((item) => item !== index);
  state.completed = isSolved(state.board, state.solution);
  save();
  closePicker();
  render();
  root.querySelector(`[data-index="${index}"]`)?.focus();
  if (state.completed) {
    $("[data-hints]").textContent = state.hintsUsed;
    $("[data-complete]").hidden = false;
  }
}

function erase() {
  if (!state || state.completed) return;
  const index = state.selectedIndex;
  if (index === null || state.givens[index]) return;
  record(index);
  state.board[index] = 0;
  state.notes[index] = [];
  state.hinted[index] = false;
  save();
  render();
}

function undo() {
  if (!state || state.completed) return;
  const move = state.history.pop();
  if (!move) return;
  state.board[move.index] = move.value;
  state.notes[move.index] = move.notes;
  state.hinted[move.index] = move.hinted;
  state.completed = false;
  save();
  render();
}

function hint() {
  if (!state || state.completed) return;
  const index = state.selectedIndex;
  if (index === null || state.givens[index]) {
    status("Select an open square for a hint.");
    return;
  }
  record(index);
  state.board[index] = state.solution[index];
  state.notes[index] = [];
  state.hinted[index] = true;
  state.hintsUsed += 1;
  state.completed = isSolved(state.board, state.solution);
  save();
  render();
}

function check() {
  if (!state) return;
  state.checkedWrong = state.board.map((value, index) => value && !state.givens[index] && value !== state.solution[index] ? index : -1).filter((index) => index >= 0);
  state.checksUsed += 1;
  save();
  render();
  status(state.checkedWrong.length ? "Some entries need another look." : "Everything entered so far is correct.");
}

function reset() {
  if (!state) return;
  state.board = [...state.puzzle];
  state.notes = Array.from({ length: 81 }, () => []);
  state.hinted = Array(81).fill(false);
  state.history = [];
  state.checkedWrong = [];
  state.completed = false;
  save();
  render();
  status("Puzzle reset.");
}

function focusables() {
  return [...$("[data-picker]").querySelectorAll("button")].filter((button) => !button.disabled);
}

function renderPicker() {
  const grid = $("[data-face-grid]");
  grid.replaceChildren();
  faces.faces.forEach((face) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "fs-face-choice";
    button.dataset.value = face.value;
    button.append(token(face.value));
    const label = document.createElement("span");
    label.textContent = face.name;
    button.append(label);
    const count = state.board.filter((value) => value === face.value).length;
    button.append(Object.assign(document.createElement("small"), { textContent: `${count}/9` }));
    button.addEventListener("click", () => apply(face.value));
    grid.append(button);
  });
}

function openPicker(index, origin = null) {
  if (!state || state.completed || state.givens[index]) return;
  restoreFocus = origin || document.activeElement;
  restoreFocusIndex = index;
  const overlay = $("[data-picker]");
  $("[data-picker-description]").textContent = `Row ${Math.floor(index / 9) + 1}, column ${index % 9 + 1}. ${state.noteMode ? "Choose a note." : "Choose a face."}`;
  renderPicker();
  overlay.hidden = false;
  previousOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  const current = state.board[index];
  (focusables().find((button) => Number(button.dataset.value) === current) || focusables()[0])?.focus();
}

function closePicker() {
  const overlay = $("[data-picker]");
  if (overlay.hidden) return;
  overlay.hidden = true;
  document.body.style.overflow = previousOverflow;
  const target = restoreFocus?.isConnected ? restoreFocus : root.querySelector(`[data-index="${restoreFocusIndex}"]`);
  restoreFocus = null;
  restoreFocusIndex = null;
  if (target?.isConnected) target.focus();
}

function fallback(reason) {
  console.warn("Family Sudoku Robatron generation failed; using fallback.", reason);
  const difficulty = difficulties.has($("[data-difficulty]").value) ? $("[data-difficulty]").value : (state?.difficulty || "easy");
  const records = Array.isArray(bank?.puzzles) ? bank.puzzles.filter((puzzle) => puzzle.difficulty === difficulty) : [];
  if (!records.length) throw new Error("No fallback puzzle available");
  const record = records[Math.floor(Math.random() * records.length)];
  const variant = createFallbackVariant(record);
  state = initial(variant.puzzle, variant.solution, difficulty, "fallback", variant.id);
  save();
  status("A backup puzzle is ready.");
  render();
}

function setBusy(busy) {
  $("[data-action=new]").disabled = busy;
  $("[data-difficulty]").disabled = busy;
  root.querySelectorAll("[data-board] button").forEach((button) => { button.disabled = busy; });
}

function generate(difficulty) {
  if (worker || !difficulties.has(difficulty)) return;
  status("Making a new puzzle...");
  setBusy(true);
  const requestId = `request-${Date.now()}-${Math.random()}`;
  try {
    worker = new Worker(root.dataset.generatorWorkerUrl);
    timer = setTimeout(() => finish(null, "Generation timed out"), 15000);
    worker.onmessage = (event) => {
      if (event.data.requestId !== requestId) return;
      finish(event.data, event.data.message);
    };
    worker.onerror = () => finish(null, "Worker unavailable");
    worker.postMessage({ type: "generate", requestId, difficulty });
  } catch (error) {
    finish(null, error.message);
  }
}

function finish(data, reason) {
  if (timer) clearTimeout(timer);
  timer = null;
  worker?.terminate();
  worker = null;
  setBusy(false);
  if (data?.type === "generated") {
    try {
      if (!difficulties.has(data.difficulty) || typeof data.puzzle !== "string" || typeof data.solution !== "string") throw new Error("Invalid worker response");
      validatePuzzlePair(data.puzzle, data.solution);
      state = initial(data.puzzle, data.solution, data.difficulty, "robatron");
      save();
      status("Puzzle ready.");
      render();
      return;
    } catch {
      reason = "Invalid worker response";
    }
  }
  try {
    fallback(reason);
  } catch (error) {
    console.error("Family Sudoku fallback failed", error);
    $("[data-fatal-message]").textContent = "The puzzle sources are unavailable. Check the local Family Sudoku files.";
    $("[data-fatal]").hidden = false;
  }
}

function keydown(event) {
  const overlay = $("[data-picker]");
  if (!overlay.hidden) {
    if (event.key === "Escape") {
      event.preventDefault();
      closePicker();
    } else if (/^[1-9]$/.test(event.key)) {
      event.preventDefault();
      apply(Number(event.key));
    } else if (event.key === "Tab") {
      const list = focusables();
      const first = list[0];
      const last = list.at(-1);
      if (!list.includes(document.activeElement)) {
        event.preventDefault();
        first?.focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    return;
  }
  if (!state) return;
  if (event.target.matches("input,select,button") && event.target !== $("[data-board]") && !event.target.dataset.index) return;
  let index = state.selectedIndex ?? 0;
  if (event.key.startsWith("Arrow")) {
    event.preventDefault();
    const row = Math.floor(index / 9);
    const column = index % 9;
    if (event.key === "ArrowRight" && column < 8) index += 1;
    else if (event.key === "ArrowLeft" && column > 0) index -= 1;
    else if (event.key === "ArrowDown") index = Math.min(80, index + 9);
    else if (event.key === "ArrowUp") index = Math.max(0, index - 9);
    select(index, false);
  } else if (event.key === "Home") {
    event.preventDefault();
    select(Math.floor(index / 9) * 9, false);
  } else if (event.key === "End") {
    event.preventDefault();
    select(Math.floor(index / 9) * 9 + 8, false);
  } else if (event.key === "Escape") {
    event.preventDefault();
    state.selectedIndex = null;
    render();
  } else if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (!state.completed && !state.givens[index]) openPicker(index);
  } else if (/^[1-9]$/.test(event.key)) {
    apply(Number(event.key));
  } else if (event.key === "Backspace" || event.key === "Delete") {
    erase();
  } else if (event.key.toLowerCase() === "n" && !state.completed) {
    state.noteMode = !state.noteMode;
    render();
  }
}

async function readJSON(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error("Local game data could not load");
  return response.json();
}

async function init() {
  setBusy(true);
  try {
    faces = validateFaces(await readJSON(root.dataset.facesUrl));
    $("[data-game-title]").textContent = faces.gameTitle;
    $("[data-game-subtitle]").textContent = faces.subtitle;
    $("[data-complete-title]").textContent = faces.completionTitle;
    $("[data-complete-message]").textContent = faces.completionMessage;
    document.title = `${faces.gameTitle} - Ronpon.ca`;
    bank = await readJSON(root.dataset.fallbackPuzzlesUrl);
    if (!Array.isArray(bank?.puzzles)) throw new Error("Invalid fallback bank");
    let saved = null;
    try {
      saved = localStorage.getItem(STORAGE_KEY);
    } catch (error) {
      console.warn("Family Sudoku save unavailable", error);
    }
    if (saved) {
      try {
        state = validateState(JSON.parse(saved));
      } catch {
        try { localStorage.removeItem(STORAGE_KEY); } catch { /* unavailable storage */ }
      }
    }
    for (const face of faces.faces) {
      const image = new Image();
      image.onload = () => { imageOK.set(face.value, true); render(); };
      image.onerror = () => { imageOK.set(face.value, false); render(); };
      image.src = faceURL(face);
    }
    if (state) {
      setBusy(false);
      status("Resumed saved puzzle.");
      render();
    } else {
      generate(faces.defaultDifficulty);
    }
  } catch (error) {
    console.error("Family Sudoku setup error", error);
    setBusy(false);
    $("[data-fatal-message]").textContent = "The face or fallback configuration could not load.";
    $("[data-fatal]").hidden = false;
  }
}

root.addEventListener("click", (event) => {
  if (event.target === $("[data-picker]")) closePicker();
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (action === "new") generate($("[data-difficulty]").value);
  if (action === "reset") reset();
  if (action === "undo") undo();
  if (action === "erase") erase();
  if (action === "hint") hint();
  if (action === "check") check();
  if (action === "notes" && state && !state.completed) {
    state.noteMode = !state.noteMode;
    render();
  }
  if (event.target.closest("[data-close]")) closePicker();
  if (event.target.closest("[data-complete-close]")) $("[data-complete]").hidden = true;
});

$("[data-difficulty]").addEventListener("change", () => generate($("[data-difficulty]").value));
document.addEventListener("keydown", keydown);
init();
