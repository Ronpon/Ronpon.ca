# Battle Chess - Master Document

**This is the master document for Battle Chess. Review before making changes. Update when any changes are made.**

---

## Overview

Battle Chess plays like a normal chess game with one key twist: whenever a piece is about to be taken, a minigame is played. The outcome of the minigame determines whether the capture succeeds.

---

## Game Setup Flow

### 1. Player Count Selection (Popup)
- Player chooses **1 or 2 players**.
  - **1 Player:** Play against the computer on the chessboard and in all five battle minigames.
  - **2 Players:** Local multiplayer.
- **Play Online — Invite a Friend:** Create or join a private two-player room with a six-character code or invite link. The host is White; the guest is Black. No account is required.

### Solo Settings (1 Player Only)
- Choose **Chess difficulty**: Easy, Medium, or Hard. This controls the computer's board strategy and search budget.
- Choose **Battle AI difficulty** independently: Easy, Medium, or Hard. This controls minigame reaction time, mashing rate, hazard prediction, and memory recall.
- Both difficulties default to **Medium** and remain selected when navigating Back.
- Choose **White** to move first or **Black** to let the computer open the game. Players keep their White/Black seats and minigame sides throughout the match.
- Only the human's profile is editable; the opponent is labeled **Computer** with an automaton crest.

### 2. Player Profile Setup (Popup)
- Each player:
  - Chooses one of **16 engraved crests**, with named choices, a live preview, and a visible selected state. Runeforge uses bronze/amethyst accents; Elven uses green/silver accents.
  - Types in a **player name**.
- Crest buttons support keyboard selection and expose their pressed state. Each player's choice stays independent and is retained through Back navigation.
- `js/PlayerEmblems.js` provides the same original vector art for setup, battle sidebars, card games, and canvas avatars. Existing icon values remain compatible with saved game configurations.
- `.venv/Scripts/python.exe tests/battle_chess_profiles_browser.py` checks profile selection, keyboard controls, theme/viewport fit, Back navigation, solo Black, and crest rendering during captures. Use `--url https://ronpon.ca/games/battle-chess` for browser-local checks of the deployed version.

### 3. Minigame Selection Screen (Popup)
- Players choose which minigames to include from the available list.
- **Select all minigames** checks or clears the entire list. It displays a partial-selection state when only some games are selected and stays synchronized with individual choices and Back navigation.
- If **no minigames** are selected, the game plays as standard chess.
- **"Mini Game Selection Mode"** option at the bottom of this screen:
  - **Greyed out** (non-interactable) unless more than 1 minigame is selected.
  - Options:
    - **Random** — A random selected minigame is chosen each time a capture is attempted.
    - **Attacker's Choice** — The attacking player picks the minigame.
    - **Defender's Choice** — The defending player picks the minigame.
    - **Set Order** — Cycles through selected minigames in order.

### 4. Attacker Loss Rule (Popup)
- Only shown if **at least 1 minigame** is selected.
- **"Does attacker lose piece on loss? Y/N"**
  - **Yes:** If the attacker loses the minigame, their attacking non-king piece is removed from the board (defender's piece stays).
  - **No:** If the attacker loses, both pieces remain where they were (nothing happens).
- Kings remain on the board when their capture fails. A minigame loss does not award a chess win.

---

## Core Chess Rules

- Standard chess rules apply (movement, check, checkmate, etc.).
- Minigames replace the normal capture mechanic when enabled.

### Captures While in Check
- Minigames decide only whether a capture succeeds and whether a losing attacking non-king piece is removed. The same rules apply to a human and the computer, for both colors.
- A failed capture never declares an automatic checkmate or skips the selected attacker-removal rule.
- If the attacking player's king is still in check, including when removing a pinned attacker exposes it, that player keeps the turn to make another legal check response. Otherwise the turn passes normally.
- Kings stay in place after losing a capture battle. Standard checkmate and draw detection still apply to the resulting chess position.
- There is no forced-checkmate warning before these captures.

---

## Minigame Trigger Flow

1. A piece attempts to capture another piece.
2. If minigames are enabled, a minigame is triggered instead of an immediate capture.
3. **Game selection depends on mode:**
   - **Random / Set Order:** Goes directly to the minigame.
   - **Attacker's Choice / Defender's Choice:** A selection popup appears showing all selected minigames with **thumbnail images**. The appropriate player sees: **"(Player Name) Chooses Game"**.

### Minigame Ties
- If both players are eliminated simultaneously (e.g., hit on the same frame), popup displays: **"Whoa… it's a tie!"**
- A **"Here we go again"** button appears. Clicking it replays the same minigame.
4. **First-time explanation:** The first time a particular minigame is played in a session, a brief explanation screen is shown. Player clicks **"Got It"** to proceed.
5. **Minigame screen layout:**
   - Game in the **center**.
   - Brief **control graphics** on either side.
   - **Player icons** alongside to show who is on which side.
   - **Left side:** Always **Player 1** — labeled **"[Player Name] (Attacker)"** or **"[Player Name] (Defender)"**
   - **Right side:** Always **Player 2** — labeled **"[Player Name] (Attacker)"** or **"[Player Name] (Defender)"**
   - Players always stay on the **same side** regardless of who is attacking/defending.
6. The minigame is played.

### Minigame Outcome

- **Attacker wins:** Defender's piece is removed; attacker's piece moves to that square (normal capture).
- **Attacker loses:**
  - If **"Attacker loses piece on loss"** = **Yes:** Attacker's non-king piece is removed; defender's piece stays.
  - If **"Attacker loses piece on loss"** = **No:** Nothing happens; both pieces remain where they were.
- The result panel states the capture consequence before returning to the board. A king that remains in check must still receive a legal response; it is not an automatic minigame forfeit.

---

## Minigame List

### 1. Dodging Battle

**Controls:**
- Player 1 (Left side): **WASD**
- Player 2 (Right side): **IJKL**

*Note: Controls are per-player, not per-role. Controls may vary per minigame.*

**Gameplay:**
- Each player controls a **small circle** with their **player icon** on it.
- Players maneuver around a **square arena**.
- **Projectiles** come in from all angles:
  - Start slow, **1 at a time**.
  - Quickly **increase in number and speed**.
- A player is **eliminated** when hit by a projectile.
- **Attacker advantage — Extra Life:**
  - If the attacker is hit first, they get a second chance.
  - All projectiles disappear.
  - Game pauses with popup: **"Attacker has 1 life remaining"**.
  - A **countdown from 5** is shown.
  - Game resumes at the **same speed/projectile density** as when the attacker was hit.
- The player who is hit (with no lives remaining) **loses**.
- If both players are hit on the same frame, see **Minigame Ties** rule above.

### 2. Mashing Battle

**Controls:**
- Player 1 (Left side): **Mash A**
- Player 2 (Right side): **Mash L**

*Player 1 is always on the left, Player 2 always on the right.*

**Gameplay:**
- A thin horizontal bar with **9 notches** (1 center, 4 each side).
- Player icons sit on either side: **Player 1 on left**, **Player 2 on right**.
- A **circle with a Chess Battle icon** starts **1 notch toward the opponent of the advantaged player**. White advantage starts at notch 5, Black at notch 3, and no advantage at the center (4).
- A **3, 2, 1, GO!** countdown plays, then a **20-second timer** begins.
- Players mash their key as fast as possible.
- Every **5 presses** moves the icon **1 notch toward the opponent**.
- Whichever side the icon is **closest to** at the end of 20 seconds **loses**.
- If exactly in the center → **tie** (see Minigame Ties rule).

### 3. Timing Battle

**Controls:**
- Player 1 (Left side): **Press A on "NOW!"**
- Player 2 (Right side): **Press L on "NOW!"**

*Player 1 is always on the left, Player 2 always on the right.*

**Gameplay:**
- Same bar/notch layout and correctly directed one-notch advantage as Mashing Battle.
- **"NOW!"** pops up at **random intervals** (every 2–6 seconds).
- Players press their key as fast as possible after "NOW!" — reaction time shown in ms under each player.
- **Faster press** → icon moves **1 notch toward the slower player's side** (winner gets point).
- Pressing **before** "NOW!" → **penalty**, icon moves 1 notch toward the early presser's side.
- **No timer** — plays until the icon reaches one end.
- First to push the icon to the **opponent's end** wins.

---

## Board UI — Info Panel

- A small **info section above the board** displays extra game info.
- **"Next Minigame:"** display:
  - **Random** or **Player's Choice** mode: Shows **"?"**
  - **Set Order** mode: Shows the **name of the next minigame** in the cycle.
- The Set Order cycle **resets each game**.

---

## Fantasy Board Collection

- **Runeforge 3D** and **Elven 3D / Sylvan Court** provide original fantasy boards and six piece models in two factions. Classic 2D remains available during play.
- Original intricate 2D image backgrounds are composited beneath the transparent WebGL board. Images and generation prompts are in `assets/backgrounds/`; board/piece source is in `js/fantasy/`.
- Hold either mouse button or one finger and drag to rotate and tilt. A six-pixel gesture threshold distinguishes taps from drags; releasing a drag cannot move a piece. Scroll outside the canvas to move the page. Camera buttons offer rotation, flip, top view, zoom and reset.
- Theme switching preserves game state and selection; preferences are saved locally. Reduced-motion preferences shorten animations. WebGL failure returns to Classic without losing the game.
- **Download 3D set** exports the selected board and 32 pieces as GLB. Each collection also has a bundled GLB and asset documentation under `assets/skins/`.
- Three.js 0.180.0 is vendored in `lib/three/` with its MIT license. There is no runtime CDN or new server dependency.
- `tests/battle_chess_fantasy_browser.py` checks real desktop/touch input, drag gestures, special moves, image loading, responsive layouts, theme persistence, GLB export and WebGL fallback. Run it using the existing Python environment; add `--elven` for Sylvan Court.

---

## Fullscreen Board

- **Full screen** expands only the game surface beyond the surrounding site and embedded frame. The decorative game heading and caption are hidden while the board, turn indicator, board-style choices, camera controls, and **Exit full screen** remain available.
- The board stays square and fits the available viewport without page or game-frame scrolling. Its size follows the actual control heights, window resizing, and switches between Classic, Runeforge, and Elven views. Classic retains its 640-pixel backing canvas; only its displayed size changes.
- Setup, battle, promotion, and game-over overlays remain within the fullscreen surface. Long setup/card content may scroll inside its own panel when needed. The exit control remains accessible above overlays.
- Use **Exit full screen** or **Escape** to return to the embedded game. Denied browser requests leave the normal game usable and show a short error message.
- `js/FullscreenController.js` owns browser fullscreen state and responsive board sizing; `css/fullscreen.css` scopes the layout. The existing iframe fullscreen permission is sufficient.
- `.venv/Scripts/python.exe tests/battle_chess_fullscreen_browser.py` verifies native fullscreen inside the iframe, Select All/partial selection, all three playable views, short PC screens, capture/promotion overlays, exit/re-entry, and request rejection. Use `--url https://ronpon.ca/games/battle-chess` to check the deployed game; fixtures affect only browser-local play.

## Solo AI

- `js/ai/ChessAI.js` searches a private copy of the current chess position using iterative deepening, alpha-beta pruning, material, and piece placement. Easy searches one ply with occasional variation; Medium and Hard allow deeper searches with increasing time/node limits. Difficulty levels describe relative strength, not a chess rating.
- `ChessAIWorker.js` runs the chess search in a Web Worker using the existing vendored chess rules library. Browsers without a working worker use a bounded search that yields to the UI. Resetting, replaying, entering a battle, or switching to online play invalidates pending computer moves.
- Human board input is blocked during computer turns. Computer captures use the same pending capture, explanation, minigame, tie, piece-removal, and result flow as human captures. The computer automatically chooses an enabled minigame when Attacker's Choice or Defender's Choice belongs to it; the human still chooses on their own turns.
- **Dodging Battle:** the computer predicts visible projectile paths and chooses a safe movement direction. Higher difficulty reacts more frequently and looks further ahead; movement speed and lives follow the same rules as the human.
- **Mashing Battle:** the computer presses at a difficulty-dependent rate after the countdown. Keyboard auto-repeat is ignored and the human cannot mash for the computer's seat.
- **Timing Battle:** the computer waits for NOW! before reacting, using a difficulty-dependent delay. The human cannot submit reactions for the computer.
- **Memory Match:** the computer remembers only cards revealed through normal play. Difficulty controls memory capacity, recall, and selection delay; hidden card values are never consulted to select a card.
- **Highest Card:** the computer chooses an available face-down card automatically. Picks remain random at every difficulty; the AI does not see or change hidden card values.
- Battle sidebars identify the computer's controls as automatic. AI timers and animation callbacks stop on results, reset, teardown, and replay.
- Failed captures remove the attacking non-king piece when enabled, including checked or pinned attackers. An attacker whose king remains checked keeps the turn; the AI automatically finds another legal response. Failed king captures leave both pieces in place.
- Failed captures rebuild the chess position before history/draw inspection, revoke castling rights for a removed corner rook, and clear en passant. Move clocks advance only when a turn passes, and piece removal resets the halfmove clock.

### Solo verification

- `node --test tests/battle_chess_ai_engine.test.mjs tests/battle_chess_ai_minigames.test.mjs` checks chess search, legal moves, turn ownership, cancellation, battle behavior, and cleanup.
- `.venv/Scripts/python.exe tests/battle_chess_ai_browser.py` checks solo startup, independent difficulties, playing Black, AI captures and game selection, all five battle bots, reset cancellation, switching to local multiplayer, and phone-width setup with temporary databases.
- `node --test tests/battle_chess_capture_rules.test.mjs` checks symmetric capture outcomes, checks/pins, kings, castling rights, en passant, history safety, real AI replies, and normal chess endings.
- `.venv/Scripts/python.exe tests/battle_chess_capture_rules_browser.py` reproduces twelve real capture battles using both human colors, both attacker-removal settings, successful captures, checked/pinned attackers, and legal continued play. `--url https://ronpon.ca/games/battle-chess` verifies browser-local games on the deployed site.

## Architecture Notes

- **Tech stack:** JavaScript / HTML5 Canvas / Three.js, with Flask and database-backed rooms for online play.
- Local multiplayer runs entirely in the browser.
- Solo chess and battle AI run entirely in the browser, without an external AI service.
- Online multiplayer uses server-validated chess and battle state; clients render snapshots and submit only their own moves and controls.

## Online Multiplayer

- Local and online battles share the five minigame classes, card artwork, canvas renderers, player sidebars, explanations, and result components. Online instances use `applyNetworkState` to display server snapshots; local timers, bots, and winner calculation never run in a network instance. Keyboard, touch, and card controls submit actions only for the current seat. Cards remain hidden on the server until revealed through play.
- Online mode offers **all five capture minigames** or **classic chess**. Choose a single game or a mix, with random selection, set order, attacker choice, or defender choice. Set order follows the listed checked games and advances on each new capture; ties replay the same game.
- The host chooses battle advantage (attacker, defender, or none) and whether a losing attacker is removed. In **Highest Card**, the attacker picks a face-down card first, then the defender picks a different card. Either player presses **Reveal** once both have chosen. Both cards are revealed together, and both players acknowledge the result before play continues. Refresh preserves the picks and pending reveal. Ties with no advantage use a new shuffled deck.
- **Memory Match:** attacker goes first. Both players see each revealed card; hidden card values stay on the server. Flip four cards per turn and match four suits of a rank to win. An advantaged player flips and matches three instead. Unmatched cards remain visible for two seconds before the other player's turn. Refresh restores the current turn and revealed cards.
- **Mashing Battle:** both players confirm readiness, then share a three-second countdown and a twenty-second battle. White presses A, Black presses L, or either uses Space/the tap button for their own seat. Every five presses pushes one notch toward the opponent; the side past the center wins. Key auto-repeat is ignored. Inputs are batched and rate-bounded. The advantaged player starts one notch ahead toward the opponent (White at 5, Black at 3); no advantage starts at 4.
- **Timing Battle:** both players confirm readiness. A hidden server schedule reveals NOW! after two to six seconds; each player can respond once per round. Early presses lose a point. The server measures reactions from when it first sent that player the signal, reducing polling-order bias without trusting client timestamps. A round ends when both respond or the response window closes. First to push to the far end wins. Stable connections give the fairest results; unequal network latency can still affect measured reactions. Reconnecting restarts an unfinished reaction round with a new hidden cue while retaining the score.
- **Dodging Battle:** each browser controls only its own circle with WASD, IJKL, arrows, or pointer/touch direction buttons. The server simulates movement, shared projectiles, speed increases, and collisions in fixed 20 ms steps. An advantaged player receives a second life, with a five-second countdown after using it. Simultaneous final hits cause a tie. Lost key-up events expire; clients cannot supply positions, lives, or collision outcomes.
- A failed battle follows the same capture/removal rules as local play. Kings stay on the board. A checked attacker keeps the turn to answer check, including after a pinned attacker is removed; there are no automatic battle forfeits. Normal chess endings still apply.
- Only the player whose turn it is can move. Standard special moves, promotion choices, checkmate, stalemate, insufficient material, threefold repetition, and the fifty-move draw rule are validated on the server.
- Players can resign, leave, and request a rematch. A rematch needs both players' consent and keeps the same colors and settings. Leaving during play concedes the game.
- Refreshing the same tab restores its seat and any pending battle. Disconnections retry automatically; the opponent sees connection status. Timed battles pause after two seconds without either player's control heartbeat. Both players must explicitly confirm readiness to resume after a new countdown; Mashing preserves its remaining time and score, and Dodging preserves its arena. There is no automatic disconnect forfeit. Rooms expire after 24 hours without activity. Closing a tab does not immediately resign; a seat token is stored in session storage, so a new browser/device cannot recover that seat just from the public invite link.
- `OnlineMultiplayer.js` connects the existing board/input flow to `/games/battle-chess/api`. The existing local minigame engine continues to handle local games.
- `models/battle_chess.py` owns authoritative rules and hidden card decks using `chess==1.11.2`. Room state is stored in `battle_chess_rooms`, created at application startup on SQLite or PostgreSQL. SQLite write transactions and PostgreSQL row locks serialize updates across threads/workers. Revision checks reject stale commands; action IDs prevent duplicate execution after a lost response.
- Clients poll roughly every 1.2 seconds on the chessboard and every 250 ms during card battles. Timed games exchange sequenced control frames about every 100 ms, with immediate reaction/key-change submissions when possible. One control request per browser is in flight at a time; retries use the same sequence number, so presses cannot be counted twice. Independent player inputs and battle acknowledgements use battle/game identifiers rather than conflicting chessboard revisions. `models/chess_minigames.py` advances simulations inside the room's database lock; no worker-local simulation or timer is needed. Reconnect retries wait one second. Mutations use the site's CSRF protection and room-specific random seat tokens; only token hashes are persisted. API responses are private and uncached, with creation/join/action/poll/control rate limits. Production capacity still depends on database and request latency; these fast control exchanges are intended for private two-player rooms.
- Install the updated `requirements.txt` and restart the Flask/Gunicorn app to activate the API and create the table. No additional service or WebSocket infrastructure is required. Online mode requires the Flask app; serving only the static game files supports local play.

### Multiplayer verification

- `node --test tests/battle_chess_online_input.test.mjs` checks queued presses and key releases during a request, duplicate-safe retries, timing seat ownership, auto-repeat, and teardown.
- `.venv/Scripts/python.exe tests/battle_chess_online_presentation_browser.py` compares all five local/online presentations, card images, crests, Black attacker roles, desktop/phone layouts, and native online fullscreen. Set `BATTLE_CHESS_VISUAL_DIR` to retain screenshots.
- Set `BATTLE_CHESS_INPUT_DELAY_MS=150` when running `tests/battle_chess_minigames_browser.py` to check gameplay with delayed control responses.
- `.venv/Scripts/python.exe -m unittest discover -s tests -p test_battle_chess.py` — temporary-database tests for room access, CSRF, concurrency, legal turns, special moves, hidden cards, battle rules, reconnect state, draws, rematches, and expiration.
- `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_battle_chess*.py"` — includes all minigame rules, server timers, input sequencing, game selection, extra lives, shared collisions, pause/resume, and hidden-card/cue tests.
- `.venv/Scripts/python.exe tests/battle_chess_browser.py` — optional Playwright integration test using Microsoft Edge (or installed Chromium), independent browsers, and temporary databases. Covers invites, actual board clicks, battle refresh, connection loss/recovery, resignation, rematch, local setup, and the mobile lobby. Install Playwright separately for this check; it is not a production dependency.
- `.venv/Scripts/python.exe tests/battle_chess_minigames_browser.py` — two-browser gameplay checks for all four additional games and defender-choice selection, including the real Mashing countdown/timer, keyboard and mobile direction controls, disconnect/rejoin, and shared capture outcomes. Optional game IDs as arguments narrow this check.

---

## Changelog

| Date       | Change Description                          |
|------------|---------------------------------------------|
| 2026-10-30 | Unified local/online minigame presentation, restored Highest Card's shared reveal flow, added responsive battle layouts and immediate queued controls, and verified all five games with paired browsers and presentation comparisons. |
| 2026-10-30 | Released private online rooms, invite links, all five server-controlled battle minigames, reconnect and disconnect handling, resignation, rematches, and multiplayer API/browser checks. |
| 2026-10-23 | Corrected failed capture resolution: apply attacker removal symmetrically, remove automatic battle forfeits, retain the turn to answer check, preserve kings and valid castling/history state, explain capture consequences, and fix reversed Mashing/Timing advantages. |
| 2026-10-23 | Replaced the emoji player picker with 16 original engraved crests, theme-aware profile cards, live previews, named keyboard-accessible choices, and matching SVG/canvas avatars throughout the battle minigames. |
| 2026-10-23 | Added a scroll-free fullscreen board with responsive sizing, retained battle/promotion controls, browser exit handling, and Select All for minigame setup. |
| 2026-10-23 | Enabled solo play with independent chess and battle AI difficulties, White/Black selection, a bounded worker chess engine, bots for all five capture minigames, safe turn ownership/cancellation, and solo regression checks. |
| 2026-10-22 | Added Runeforge and Sylvan Court 3D boards, original illustrated backgrounds, mouse/touch orbit controls, GLB exports, Classic fallback, and browser regression checks. |
| 2026-04-16 | Initial master document created.            |
| 2026-04-16 | Updated with clarifications: 1-2 players + AI, tie rules, check+minigame interaction, set order display, player sides fixed, JS/HTML5 tech stack. |
| 2026-04-17 | Full implementation complete: project foundation, skin system, chess interactions (all special moves), setup wizard (4 screens), minigame framework (base class, manager, 4 selection modes, tie handling), Dodging Battle minigame, info panel with "Next Minigame", check+capture warning popup, forced checkmate on minigame loss, move/capture animations, sound manager stub, extension docs for skins and minigames. |
| 2026-04-17 | Added Mashing Battle and Timing Battle minigames. Bar layout uses Player 1 (left) / Player 2 (right) with attacker/defender labels, not fixed attacker-left. |
