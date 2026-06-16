(function () {
    "use strict";

    const root = document.querySelector("[data-ttt-game]");
    if (!root) {
        return;
    }

    const lines = [
        [0, 1, 2],
        [3, 4, 5],
        [6, 7, 8],
        [0, 3, 6],
        [1, 4, 7],
        [2, 5, 8],
        [0, 4, 8],
        [2, 4, 6]
    ];
    const positionWeight = [3, 2, 3, 2, 4, 2, 3, 2, 3];
    const scores = { X: 0, O: 0, ties: 0 };
    const els = {
        board: root.querySelector("[data-board]"),
        status: root.querySelector("[data-status]"),
        turnChip: root.querySelector("[data-turn-chip]"),
        scoreX: root.querySelector("[data-score-x]"),
        scoreO: root.querySelector("[data-score-o]"),
        scoreTies: root.querySelector("[data-score-ties]"),
        modeButtons: Array.from(root.querySelectorAll("[data-mode]")),
        opponentButtons: Array.from(root.querySelectorAll("[data-opponent]")),
        resetButtons: Array.from(root.querySelectorAll("[data-reset]"))
    };

    let state = createState("classic", "friend");
    let aiTimer = null;

    function emptyBoard() {
        return Array(9).fill(null);
    }

    function createState(mode, opponent) {
        return {
            mode: mode,
            opponent: opponent,
            current: "X",
            board: emptyBoard(),
            queues: { X: [], O: [] },
            miniBoards: Array.from({ length: 9 }, emptyBoard),
            claimed: emptyBoard(),
            activeBoard: null,
            gameOver: false,
            winner: null,
            draw: false,
            winningLine: null,
            mainWinningLine: null,
            flashBoard: null,
            aiThinking: false
        };
    }

    function other(player) {
        return player === "X" ? "O" : "X";
    }

    function getWinnerInfo(board) {
        for (const line of lines) {
            const [a, b, c] = line;
            if (board[a] && board[a] === board[b] && board[a] === board[c]) {
                return { winner: board[a], line: line };
            }
        }
        return { winner: null, line: null };
    }

    function isFull(board) {
        return board.every(Boolean);
    }

    function setMode(mode) {
        if (state.mode === mode) {
            return;
        }
        resetRound(mode, state.opponent);
    }

    function setOpponent(opponent) {
        if (state.opponent === opponent) {
            return;
        }
        resetRound(state.mode, opponent);
    }

    function resetRound(mode, opponent) {
        window.clearTimeout(aiTimer);
        state = createState(mode || state.mode, opponent || state.opponent);
        render();
        scheduleAiTurn();
    }

    function endGame(winner, line) {
        if (state.gameOver) {
            return;
        }
        state.gameOver = true;
        state.winner = winner;
        state.draw = !winner;
        if (state.mode === "ticception") {
            state.mainWinningLine = line || null;
        } else {
            state.winningLine = line || null;
        }
        if (winner) {
            scores[winner] += 1;
        } else {
            scores.ties += 1;
        }
        render();
    }

    function switchTurn() {
        state.current = other(state.current);
        render();
        scheduleAiTurn();
    }

    function isInputLocked() {
        return state.gameOver || state.aiThinking || (state.opponent === "computer" && state.current === "O");
    }

    function handleBoardClick(event) {
        const button = event.target.closest("button");
        if (!button || !els.board.contains(button) || isInputLocked()) {
            return;
        }

        if (state.mode === "ticception") {
            const boardIndex = Number(button.dataset.board);
            const cellIndex = Number(button.dataset.cell);
            if (Number.isInteger(boardIndex) && Number.isInteger(cellIndex)) {
                applyUltimateMove(boardIndex, cellIndex);
            }
            return;
        }

        const index = Number(button.dataset.index);
        if (Number.isInteger(index)) {
            applySimpleMove(index);
        }
    }

    function applySimpleMove(index) {
        if (state.gameOver || state.board[index]) {
            return false;
        }

        state.board[index] = state.current;
        if (state.mode === "trio") {
            state.queues[state.current].push(index);
            if (state.queues[state.current].length > 3) {
                const removed = state.queues[state.current].shift();
                state.board[removed] = null;
            }
        }

        const info = getWinnerInfo(state.board);
        if (info.winner) {
            endGame(info.winner, info.line);
            return true;
        }

        if (state.mode === "classic" && isFull(state.board)) {
            endGame(null, null);
            return true;
        }

        switchTurn();
        return true;
    }

    function canPlayUltimateBoard(boardIndex) {
        return !state.claimed[boardIndex];
    }

    function applyUltimateMove(boardIndex, cellIndex) {
        if (
            state.gameOver ||
            !canPlayUltimateBoard(boardIndex) ||
            state.miniBoards[boardIndex][cellIndex]
        ) {
            return false;
        }

        state.miniBoards[boardIndex][cellIndex] = state.current;
        const miniInfo = getWinnerInfo(state.miniBoards[boardIndex]);
        if (miniInfo.winner) {
            state.claimed[boardIndex] = state.current;
        } else if (isFull(state.miniBoards[boardIndex])) {
            state.miniBoards[boardIndex] = emptyBoard();
            state.flashBoard = boardIndex;
            window.setTimeout(function () {
                if (state.flashBoard === boardIndex) {
                    state.flashBoard = null;
                    render();
                }
            }, 550);
        }

        const mainInfo = getWinnerInfo(state.claimed);
        if (mainInfo.winner) {
            endGame(mainInfo.winner, mainInfo.line);
            return true;
        }

        if (state.claimed.every(Boolean)) {
            endGame(null, null);
            return true;
        }

        state.activeBoard = null;
        switchTurn();
        return true;
    }

    function scheduleAiTurn() {
        window.clearTimeout(aiTimer);
        if (state.gameOver || state.opponent !== "computer" || state.current !== "O") {
            return;
        }
        state.aiThinking = true;
        render();
        aiTimer = window.setTimeout(function () {
            state.aiThinking = false;
            makeAiMove();
        }, 360);
    }

    function makeAiMove() {
        if (state.gameOver || state.opponent !== "computer" || state.current !== "O") {
            render();
            return;
        }

        if (state.mode === "ticception") {
            const move = chooseUltimateMove();
            if (move) {
                applyUltimateMove(move.board, move.cell);
                return;
            }
        } else {
            const index = chooseSimpleMove();
            if (Number.isInteger(index)) {
                applySimpleMove(index);
                return;
            }
        }

        endGame(null, null);
    }

    function chooseSimpleMove() {
        if (state.mode === "classic") {
            return chooseClassicMove();
        }
        return chooseTrioMove();
    }

    function legalSimpleMoves(board) {
        return board.map(function (cell, index) {
            return cell ? null : index;
        }).filter(function (index) {
            return index !== null;
        });
    }

    function chooseClassicMove() {
        const moves = legalSimpleMoves(state.board);
        let bestScore = -Infinity;
        let bestMoves = [];

        for (const index of moves) {
            const next = state.board.slice();
            next[index] = "O";
            const score = minimax(next, "X", 0, -Infinity, Infinity);
            if (score > bestScore) {
                bestScore = score;
                bestMoves = [index];
            } else if (score === bestScore) {
                bestMoves.push(index);
            }
        }

        return pick(bestMoves);
    }

    function minimax(board, player, depth, alpha, beta) {
        const info = getWinnerInfo(board);
        if (info.winner === "O") {
            return 10 - depth;
        }
        if (info.winner === "X") {
            return depth - 10;
        }
        if (isFull(board)) {
            return 0;
        }

        const moves = legalSimpleMoves(board);
        if (player === "O") {
            let best = -Infinity;
            for (const index of moves) {
                const next = board.slice();
                next[index] = player;
                best = Math.max(best, minimax(next, "X", depth + 1, alpha, beta));
                alpha = Math.max(alpha, best);
                if (beta <= alpha) {
                    break;
                }
            }
            return best;
        }

        let best = Infinity;
        for (const index of moves) {
            const next = board.slice();
            next[index] = player;
            best = Math.min(best, minimax(next, "O", depth + 1, alpha, beta));
            beta = Math.min(beta, best);
            if (beta <= alpha) {
                break;
            }
        }
        return best;
    }

    function chooseTrioMove() {
        const moves = legalSimpleMoves(state.board);
        const winningMove = findImmediateSimpleWins("O", state.board, state.queues, "trio")[0];
        if (Number.isInteger(winningMove)) {
            return winningMove;
        }

        const blockingMove = findImmediateSimpleWins("X", state.board, state.queues, "trio")[0];
        if (Number.isInteger(blockingMove) && !state.board[blockingMove]) {
            return blockingMove;
        }

        let best = -Infinity;
        let bestMoves = [];
        for (const index of moves) {
            const simulated = simulateSimpleMove(state.board, state.queues, "O", index, "trio");
            const score = evaluateSimpleBoard(simulated.board) + positionWeight[index];
            if (score > best) {
                best = score;
                bestMoves = [index];
            } else if (score === best) {
                bestMoves.push(index);
            }
        }

        return pick(bestMoves);
    }

    function cloneQueues(queues) {
        return {
            X: queues.X.slice(),
            O: queues.O.slice()
        };
    }

    function simulateSimpleMove(board, queues, player, index, mode) {
        const nextBoard = board.slice();
        const nextQueues = cloneQueues(queues);
        nextBoard[index] = player;
        if (mode === "trio") {
            nextQueues[player].push(index);
            if (nextQueues[player].length > 3) {
                const removed = nextQueues[player].shift();
                nextBoard[removed] = null;
            }
        }
        return { board: nextBoard, queues: nextQueues };
    }

    function findImmediateSimpleWins(player, board, queues, mode) {
        return legalSimpleMoves(board).filter(function (index) {
            const simulated = simulateSimpleMove(board, queues, player, index, mode);
            return getWinnerInfo(simulated.board).winner === player;
        });
    }

    function evaluateSimpleBoard(board) {
        let score = 0;
        for (const line of lines) {
            const values = line.map(function (index) { return board[index]; });
            const oCount = values.filter(function (value) { return value === "O"; }).length;
            const xCount = values.filter(function (value) { return value === "X"; }).length;
            if (xCount === 0) {
                score += [0, 3, 18, 120][oCount];
            }
            if (oCount === 0) {
                score -= [0, 3, 16, 120][xCount];
            }
        }
        return score;
    }

    function chooseUltimateMove() {
        const moves = legalUltimateMoves(state);
        let best = -Infinity;
        let bestMoves = [];

        for (const move of moves) {
            const score = evaluateUltimateMove(move);
            if (score > best) {
                best = score;
                bestMoves = [move];
            } else if (score === best) {
                bestMoves.push(move);
            }
        }

        return pick(bestMoves);
    }

    function legalUltimateMoves(source) {
        const boardIndexes = source.activeBoard === null
            ? source.claimed.map(function (claim, index) { return claim ? null : index; }).filter(function (index) { return index !== null; })
            : [source.activeBoard];

        const moves = [];
        for (const boardIndex of boardIndexes) {
            if (source.claimed[boardIndex]) {
                continue;
            }
            source.miniBoards[boardIndex].forEach(function (cell, cellIndex) {
                if (!cell) {
                    moves.push({ board: boardIndex, cell: cellIndex });
                }
            });
        }
        return moves;
    }

    function simulateUltimateMove(source, player, move) {
        const next = {
            miniBoards: source.miniBoards.map(function (board) { return board.slice(); }),
            claimed: source.claimed.slice(),
            activeBoard: source.activeBoard,
            mainWinner: null,
            mainLine: null,
            mainDraw: false
        };

        next.miniBoards[move.board][move.cell] = player;
        const miniInfo = getWinnerInfo(next.miniBoards[move.board]);
        if (miniInfo.winner) {
            next.claimed[move.board] = player;
        } else if (isFull(next.miniBoards[move.board])) {
            next.miniBoards[move.board] = emptyBoard();
        }

        const mainInfo = getWinnerInfo(next.claimed);
        next.mainWinner = mainInfo.winner;
        next.mainLine = mainInfo.line;
        next.mainDraw = !mainInfo.winner && next.claimed.every(Boolean);
        next.activeBoard = null;
        return next;
    }

    function evaluateUltimateMove(move) {
        const beforeClaim = state.claimed[move.board];
        const next = simulateUltimateMove(state, "O", move);
        if (next.mainWinner === "O") {
            return 100000;
        }
        if (next.mainWinner === "X") {
            return -100000;
        }

        let score = positionWeight[move.cell] + positionWeight[move.board] * 2;
        if (!beforeClaim && next.claimed[move.board] === "O") {
            score += 1500;
        }

        const humanMiniThreats = findImmediateMiniWins(state.miniBoards[move.board], "X");
        if (humanMiniThreats.includes(move.cell)) {
            score += 300;
        }

        score += evaluateClaimedBoard(next.claimed) * 70;
        score += evaluateMiniBoard(next.miniBoards[move.board]) * 8;

        return score;
    }

    function findImmediateMiniWins(board, player) {
        return legalSimpleMoves(board).filter(function (index) {
            const next = board.slice();
            next[index] = player;
            return getWinnerInfo(next).winner === player;
        });
    }

    function evaluateMiniBoard(board) {
        let score = 0;
        for (const line of lines) {
            const values = line.map(function (index) { return board[index]; });
            const oCount = values.filter(function (value) { return value === "O"; }).length;
            const xCount = values.filter(function (value) { return value === "X"; }).length;
            if (xCount === 0) {
                score += [0, 2, 14, 90][oCount];
            }
            if (oCount === 0) {
                score -= [0, 2, 12, 90][xCount];
            }
        }
        return score;
    }

    function evaluateClaimedBoard(claimed) {
        let score = 0;
        for (const line of lines) {
            const values = line.map(function (index) { return claimed[index]; });
            const oCount = values.filter(function (value) { return value === "O"; }).length;
            const xCount = values.filter(function (value) { return value === "X"; }).length;
            if (xCount === 0) {
                score += [0, 1, 12, 180][oCount];
            }
            if (oCount === 0) {
                score -= [0, 1, 14, 180][xCount];
            }
        }
        return score;
    }

    function pick(items) {
        if (!items.length) {
            return null;
        }
        return items[Math.floor(Math.random() * items.length)];
    }

    function render() {
        renderControls();
        renderScores();
        renderStatus();
        if (state.mode === "ticception") {
            renderUltimateBoard();
        } else {
            renderSimpleBoard();
        }
    }

    function renderControls() {
        els.modeButtons.forEach(function (button) {
            const active = button.dataset.mode === state.mode;
            button.classList.toggle("active", active);
            button.setAttribute("aria-pressed", active ? "true" : "false");
        });
        els.opponentButtons.forEach(function (button) {
            const active = button.dataset.opponent === state.opponent;
            button.classList.toggle("active", active);
            button.setAttribute("aria-pressed", active ? "true" : "false");
        });
    }

    function renderScores() {
        els.scoreX.textContent = String(scores.X);
        els.scoreO.textContent = String(scores.O);
        els.scoreTies.textContent = String(scores.ties);
    }

    function renderStatus() {
        els.turnChip.textContent = state.winner || state.current;
        els.turnChip.classList.toggle("mark-o", (state.winner || state.current) === "O");

        if (state.gameOver) {
            els.status.textContent = state.winner ? state.winner + " wins" : "Draw";
            return;
        }

        if (state.aiThinking) {
            els.status.textContent = "Computer is thinking...";
            return;
        }

        const playerName = state.opponent === "computer" && state.current === "O" ? "Computer (O)" : state.current;
        if (state.mode === "ticception") {
            els.status.textContent = state.activeBoard === null
                ? playerName + " turn - any board"
                : playerName + " turn - board " + (state.activeBoard + 1);
            return;
        }

        els.status.textContent = playerName + " turn";
    }

    function renderSimpleBoard() {
        clear(els.board);
        els.board.className = "ttt-board ttt-simple ttt-" + state.mode;

        state.board.forEach(function (value, index) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "ttt-cell";
            button.dataset.index = String(index);
            button.disabled = Boolean(value) || isInputLocked();
            button.setAttribute("aria-label", value ? value + " in cell " + (index + 1) : "Cell " + (index + 1));

            if (value) {
                button.textContent = value;
                button.classList.add("mark-" + value.toLowerCase());
                if (state.mode === "trio" && state.queues[value][0] === index && state.queues[value].length === 3) {
                    button.classList.add("is-oldest");
                }
            }

            if (state.winningLine && state.winningLine.includes(index)) {
                button.classList.add("is-winner");
            }

            els.board.appendChild(button);
        });
    }

    function renderUltimateBoard() {
        clear(els.board);
        els.board.className = "ttt-board ttt-ception";

        state.miniBoards.forEach(function (miniBoard, boardIndex) {
            const mini = document.createElement("div");
            mini.className = "ttt-mini-board";
            mini.setAttribute("aria-label", "Board " + (boardIndex + 1));
            if (canPlayUltimateBoard(boardIndex) && !isInputLocked()) {
                mini.classList.add("is-playable");
            }
            if (state.claimed[boardIndex]) {
                mini.classList.add("is-claimed");
            }
            if (state.flashBoard === boardIndex) {
                mini.classList.add("is-resetting");
            }
            if (state.mainWinningLine && state.mainWinningLine.includes(boardIndex)) {
                mini.classList.add("is-winner");
            }

            const label = document.createElement("span");
            label.className = "ttt-mini-label";
            label.textContent = String(boardIndex + 1);
            mini.appendChild(label);

            miniBoard.forEach(function (value, cellIndex) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "ttt-mini-cell";
                button.dataset.board = String(boardIndex);
                button.dataset.cell = String(cellIndex);
                button.disabled = Boolean(value) || !canPlayUltimateBoard(boardIndex) || isInputLocked();
                button.setAttribute("aria-label", value ? value + " in board " + (boardIndex + 1) + ", cell " + (cellIndex + 1) : "Board " + (boardIndex + 1) + ", cell " + (cellIndex + 1));
                if (value) {
                    button.textContent = value;
                    button.classList.add("mark-" + value.toLowerCase());
                }
                mini.appendChild(button);
            });

            if (state.claimed[boardIndex]) {
                const overlay = document.createElement("div");
                overlay.className = "ttt-mini-overlay mark-" + state.claimed[boardIndex].toLowerCase();
                overlay.textContent = state.claimed[boardIndex];
                mini.appendChild(overlay);
            }

            els.board.appendChild(mini);
        });
    }

    function clear(element) {
        while (element.firstChild) {
            element.removeChild(element.firstChild);
        }
    }

    els.board.addEventListener("click", handleBoardClick);
    els.modeButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            setMode(button.dataset.mode);
        });
    });
    els.opponentButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            setOpponent(button.dataset.opponent);
        });
    });
    els.resetButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            resetRound(state.mode, state.opponent);
        });
    });

    render();
}());
