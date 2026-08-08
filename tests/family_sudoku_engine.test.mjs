import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {
  parseBoardString,
  serializeBoard,
  validateCompletedSolution,
  validatePuzzlePair,
  createFallbackVariant,
  getCandidates,
  getConflictIndexes,
  isSolved,
} from "../static/games/family-sudoku/js/engine.mjs";

const bank = JSON.parse(fs.readFileSync("static/games/family-sudoku/data/fallback-puzzles.json", "utf8"));

test("board parsing and serialization are strict", () => {
  const board = parseBoardString(bank.puzzles[0].puzzle);
  assert.equal(serializeBoard(board), bank.puzzles[0].puzzle);
  assert.throws(() => parseBoardString("."), /81/);
  assert.throws(() => parseBoardString("x".repeat(81)), /only/);
  assert.throws(() => serializeBoard([0]), /81/);
  assert.throws(() => serializeBoard(Array(81).fill(10)), /0 through 9/);
});

test("solutions validate rows, columns, and boxes", () => {
  const solution = parseBoardString(bank.puzzles[0].solution);
  assert.equal(validateCompletedSolution(solution), true);

  const invalidRow = [...solution];
  invalidRow[1] = invalidRow[0];
  assert.throws(() => validateCompletedSolution(invalidRow), /row/);

  const invalidColumn = [...solution];
  invalidColumn[9] = invalidColumn[0];
  assert.throws(() => validateCompletedSolution(invalidColumn), /Invalid solution/);

  const invalidBox = [...solution];
  invalidBox[10] = invalidBox[0];
  assert.throws(() => validateCompletedSolution(invalidBox), /Invalid solution/);
});

test("all supplied fallback records validate", () => {
  const ids = new Set();
  for (const record of bank.puzzles) {
    assert(!ids.has(record.id));
    ids.add(record.id);
    validatePuzzlePair(record.puzzle, record.solution);
    validateCompletedSolution(parseBoardString(record.solution));
  }
  assert.equal(bank.puzzles.filter((record) => record.difficulty === "easy").length, 4);
  assert.equal(bank.puzzles.filter((record) => record.difficulty === "medium").length, 4);
  assert.equal(bank.puzzles.filter((record) => record.difficulty === "hard").length, 4);
});

test("fallback variants preserve Sudoku, clues, and source immutability", () => {
  const source = bank.puzzles[4];
  const before = JSON.stringify(source);
  const variant = createFallbackVariant(source, () => 0.25);
  assert.equal(JSON.stringify(source), before);
  validatePuzzlePair(variant.puzzle, variant.solution);
  assert.equal((variant.puzzle.match(/[1-9]/g) || []).length, (source.puzzle.match(/[1-9]/g) || []).length);
  assert.notEqual(variant.id, source.id);
});

test("candidates, conflicts, and completion are lightweight board helpers", () => {
  const solved = parseBoardString(bank.puzzles[0].solution);
  const board = [...solved];
  board[0] = 0;
  assert.deepEqual(getCandidates(board, 0), [6]);
  board[1] = board[2];
  const conflicts = getConflictIndexes(board);
  assert(conflicts.has(1) && conflicts.has(2));
  assert.deepEqual(getCandidates(board, 0), [6]);
  assert(!isSolved(board, solved));
  assert(isSolved(solved, solved));
});
