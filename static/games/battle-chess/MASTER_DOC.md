# Battle Chess - Master Document

**This is the master document for Battle Chess. Review before making changes. Update when any changes are made.**

---

## Overview

Battle Chess plays like a normal chess game with one key twist: whenever a piece is about to be taken, a minigame is played. The outcome of the minigame determines whether the capture succeeds.

---

## Game Setup Flow

### 1. Player Count Selection (Popup)
- Player chooses **1 or 2 players**.
  - **1 Player:** Play against AI (to be implemented).
  - **2 Players:** Local multiplayer.
- **Local play only** for now, but architecture should support future online multiplayer.

### 2. Player Profile Setup (Popup)
- Each player:
  - Chooses a **player icon** from a set of available icons.
  - Types in a **player name**.

### 3. Minigame Selection Screen (Popup)
- Players choose which minigames to include from the available list.
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
  - **Yes:** If the attacker loses the minigame, their attacking piece is removed from the board (defender's piece stays).
  - **No:** If the attacker loses, both pieces remain where they were (nothing happens).

---

## Core Chess Rules

- Standard chess rules apply (movement, check, checkmate, etc.).
- Minigames replace the normal capture mechanic when enabled.

### Check + Minigame Interaction
- If a player is in **check** and attempts to capture the threatening piece but **loses the minigame**, that counts as **checkmate** — they lose the game.
- When the player attempts to capture a piece that has them in check, a **warning popup** appears:
  - Text: **"Remember: If you fail to take this piece, you will be in checkmate."**
  - Buttons: **"Fight"** | **"Back"**
  - Checkbox: **"Don't show this again this game"**

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
  - If **"Attacker loses piece on loss"** = **Yes:** Attacker's piece is removed; defender's piece stays.
  - If **"Attacker loses piece on loss"** = **No:** Nothing happens; both pieces remain where they were.

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
- A **circle with a Chess Battle icon** starts **1 notch closer to the attacker's side** (attacker disadvantage).
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
- Same bar/notch layout as Mashing Battle. Icon starts **1 notch closer to the attacker's side**.
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

## Architecture Notes

- **Tech stack:** JavaScript / HTML5 (Canvas).
- Build with **local multiplayer** first.
- Support **1-player vs AI** (AI implementation TBD).
- Structure networking/game state so that **online multiplayer** can be added later without major refactoring.
  - Separate game logic from input handling.
  - Use a game state model that could be serialized/sent over a network.

---

## Changelog

| Date       | Change Description                          |
|------------|---------------------------------------------|
| 2026-04-16 | Initial master document created.            |
| 2026-04-16 | Updated with clarifications: 1-2 players + AI, tie rules, check+minigame interaction, set order display, player sides fixed, JS/HTML5 tech stack. |
| 2026-04-17 | Full implementation complete: project foundation, skin system, chess interactions (all special moves), setup wizard (4 screens), minigame framework (base class, manager, 4 selection modes, tie handling), Dodging Battle minigame, info panel with "Next Minigame", check+capture warning popup, forced checkmate on minigame loss, move/capture animations, sound manager stub, extension docs for skins and minigames. |
| 2026-04-17 | Added Mashing Battle and Timing Battle minigames. Bar layout uses Player 1 (left) / Player 2 (right) with attacker/defender labels, not fixed attacker-left. |
