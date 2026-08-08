const SIZE = 81;
const DIGITS = [1, 2, 3, 4, 5, 6, 7, 8, 9];

function assertBoard(board, name = "board") {
  if (!Array.isArray(board) || board.length !== SIZE) throw new Error(`${name} must contain exactly 81 values`);
  if (board.some((value) => !Number.isInteger(value) || value < 0 || value > 9)) throw new Error(`${name} values must be integers from 0 through 9`);
}

export function parseBoardString(value) {
  if (typeof value !== "string" || value.length !== SIZE) throw new Error("Board string must contain exactly 81 characters");
  if (!/^[1-9.0]+$/.test(value)) throw new Error("Board string may contain only digits 1-9, zero, or periods");
  return [...value].map((char) => char === "." || char === "0" ? 0 : Number(char));
}

export function serializeBoard(board) {
  assertBoard(board);
  return board.map((value) => value === 0 ? "." : String(value)).join("");
}

function units(index) {
  const row = Math.floor(index / 9), col = index % 9;
  const indexes = new Set();
  for (let i = 0; i < 9; i++) { indexes.add(row * 9 + i); indexes.add(i * 9 + col); }
  const r0 = Math.floor(row / 3) * 3, c0 = Math.floor(col / 3) * 3;
  for (let r = r0; r < r0 + 3; r++) for (let c = c0; c < c0 + 3; c++) indexes.add(r * 9 + c);
  indexes.delete(index); return indexes;
}

function validUnit(values) { return new Set(values).size === 9 && values.every((v) => DIGITS.includes(v)); }

export function validateCompletedSolution(board) {
  assertBoard(board, "solution");
  if (board.includes(0)) throw new Error("Solution must not contain blanks");
  for (let row = 0; row < 9; row++) if (!validUnit(board.slice(row * 9, row * 9 + 9))) throw new Error(`Invalid solution row ${row + 1}`);
  for (let col = 0; col < 9; col++) if (!validUnit(board.filter((_, i) => i % 9 === col))) throw new Error(`Invalid solution column ${col + 1}`);
  for (let r = 0; r < 9; r += 3) for (let c = 0; c < 9; c += 3) {
    const box = []; for (let dr = 0; dr < 3; dr++) for (let dc = 0; dc < 3; dc++) box.push(board[(r + dr) * 9 + c + dc]);
    if (!validUnit(box)) throw new Error(`Invalid solution box ${r / 3 + 1},${c / 3 + 1}`);
  }
  return true;
}

export function validatePuzzlePair(puzzle, solution) {
  const p = Array.isArray(puzzle) ? puzzle : parseBoardString(puzzle);
  const s = Array.isArray(solution) ? solution : parseBoardString(solution);
  assertBoard(p, "puzzle"); assertBoard(s, "solution"); validateCompletedSolution(s);
  if (p.filter(Boolean).length < 17) throw new Error("Puzzle must contain at least 17 givens");
  p.forEach((value, i) => { if (value && value !== s[i]) throw new Error(`Puzzle clue ${i} does not match solution`); });
  return true;
}

function randomInt(rng, max) { return Math.floor(rng() * max); }
function shuffled(values, rng) { const result = [...values]; for (let i = result.length - 1; i > 0; i--) { const j = randomInt(rng, i + 1); [result[i], result[j]] = [result[j], result[i]]; } return result; }

export function createFallbackVariant(record, rng = Math.random) {
  if (!record || typeof record !== "object") throw new Error("Fallback record is required");
  validatePuzzlePair(record.puzzle, record.solution);
  const digits = [0, ...shuffled(DIGITS, rng)];
  const bands = shuffled([0, 1, 2], rng).flatMap((band) => shuffled([0, 1, 2], rng).map((row) => band * 3 + row));
  const stacks = shuffled([0, 1, 2], rng).flatMap((stack) => shuffled([0, 1, 2], rng).map((col) => stack * 3 + col));
  const transform = (text) => { const board = parseBoardString(text); const output = []; for (const row of bands) for (const col of stacks) output.push(digits[board[row * 9 + col]]); return serializeBoard(output); };
  let puzzle = transform(record.puzzle), solution = transform(record.solution);
  if (rng() < 0.5) { const transpose = (text) => { const b = parseBoardString(text), out = []; for (let r = 0; r < 9; r++) for (let c = 0; c < 9; c++) out.push(b[c * 9 + r]); return serializeBoard(out); }; puzzle = transpose(puzzle); solution = transpose(solution); }
  validatePuzzlePair(puzzle, solution);
  return { ...record, puzzle, solution, id: `${record.id}-variant-${Math.floor(rng() * 1e9)}` };
}

export function getCandidates(board, index) { assertBoard(board); if (!Number.isInteger(index) || index < 0 || index >= SIZE) throw new Error("Cell index must be between 0 and 80"); if (board[index]) return []; const used = new Set([...units(index)].map((i) => board[i]).filter(Boolean)); return DIGITS.filter((value) => !used.has(value)); }

export function getConflictIndexes(board) { assertBoard(board); const conflicts = new Set(); for (let i = 0; i < SIZE; i++) if (board[i]) for (const j of units(i)) if (board[j] === board[i]) { conflicts.add(i); conflicts.add(j); } return conflicts; }

export function isSolved(board, solution) { assertBoard(board); const expected = Array.isArray(solution) ? solution : parseBoardString(solution); assertBoard(expected, "solution"); return board.every((value, index) => value === expected[index] && value !== 0); }

export { SIZE, DIGITS };
