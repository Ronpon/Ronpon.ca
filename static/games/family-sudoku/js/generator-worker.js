"use strict";
let apiError = null;
try { importScripts("../vendor/robatron-sudoku.js"); if (!self.sudoku || ["generate", "solve", "get_candidates", "validate_board"].some((name) => typeof self.sudoku[name] !== "function")) throw new Error("Robatron API is incomplete"); }
catch (error) { apiError = error; }
const safeMessage = (error) => typeof error === "string" ? error : error && error.message ? error.message : "Puzzle generation failed";
const validPuzzle = (value) => typeof value === "string" && /^[1-9.]{81}$/.test(value);
const validSolution = (value) => typeof value === "string" && /^[1-9]{81}$/.test(value);
self.onmessage = (event) => {
  const request = event && event.data;
  if (!request || request.type !== "generate" || !/^(easy|medium|hard)$/.test(request.difficulty || "") || !request.requestId) { self.postMessage({ type: "error", requestId: request && request.requestId || null, code: "INVALID_REQUEST", message: "Invalid puzzle request" }); return; }
  try {
    if (apiError) throw apiError;
    const puzzle = self.sudoku.generate(request.difficulty, true);
    if (!validPuzzle(puzzle)) throw new Error("Invalid generated puzzle");
    const solution = self.sudoku.solve(puzzle), reverse = self.sudoku.solve(puzzle, true);
    if (!validSolution(solution) || !validSolution(reverse) || solution !== reverse) throw new Error("Generated solution failed validation");
    self.postMessage({ type: "generated", requestId: request.requestId, difficulty: request.difficulty, puzzle, solution, source: "robatron" });
  } catch (error) { self.postMessage({ type: "error", requestId: request.requestId, code: "GENERATION_FAILED", message: safeMessage(error) }); }
};
