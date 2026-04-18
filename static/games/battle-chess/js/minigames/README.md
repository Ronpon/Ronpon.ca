# Creating a Minigame

Minigames are triggered during captures. Each minigame extends `BaseMinigame` and follows a simple lifecycle.

## Quick Start

1. Create a new file in `js/minigames/` (e.g. `MyGame.js`).
2. Extend `BaseMinigame` and implement the required methods.
3. Register it in `js/main.js`.

That's it — your game will appear in the setup wizard automatically.

## Step 1: Create the Class

```js
import { BaseMinigame } from './BaseMinigame.js';

export class MyGame extends BaseMinigame {
    constructor() {
        super();
        this.id = 'my-game';           // unique ID (kebab-case)
        this.name = 'My Game';          // shown in UI
        this.thumbnail = '🎯';          // emoji or image path
        this.description = 'A short explanation shown the first time this game is played.';
        this.controls = {
            player1: 'WASD to move',    // shown on the left sidebar
            player2: 'IJKL to move'     // shown on the right sidebar
        };
    }

    init(container, config) {
        super.init(container, config);
        // Set up your game state, create canvas/DOM elements, bind keys, etc.
    }

    start() {
        // Begin your game loop. The container is ready.
    }

    destroy() {
        // Clean up event listeners, intervals, etc.
        super.destroy(); // always call super
    }
}
```

## Step 2: Register It

In `js/main.js`, add:

```js
import { MyGame } from './minigames/MyGame.js';
```

Then inside the `App` constructor:

```js
this.minigameManager.register(MyGame);
```

## Lifecycle

| Phase | Method | Description |
|---|---|---|
| 1 | `constructor()` | Define metadata (id, name, description, controls, thumbnail) |
| 2 | `init(container, config)` | Receive the DOM container and player config. Set up state |
| 3 | `start()` | Game begins. Start your loop, render, accept input |
| 4 | `end(result)` | Call this yourself when the game finishes |
| 5 | `destroy()` | Framework calls this to clean up after result shown |

## Ending the Game

When a player wins, loses, or it's a tie, call:

```js
this.end({ attackerWins: true, tie: false });   // attacker wins
this.end({ attackerWins: false, tie: false });  // defender wins
this.end({ attackerWins: false, tie: true });   // tie → replay
```

The framework handles:
- Showing the result screen ("Attacker Wins!" / "Defender Wins!")
- Tie handling (shows "Whoa… it's a tie!" and replays the same game)
- Resolving the capture on the chess board

## Available Config

Inside `init(container, config)` you receive:

| Property | Description |
|---|---|
| `this.container` | DOM element to render into (the arena area) |
| `this.players` | Array of `[player1, player2]` objects with `{ name, icon, color }` |
| `this.attackerColor` | `'w'` or `'b'` — which player is the attacker |

## Helpers

| Method | Description |
|---|---|
| `this.getAttacker()` | Returns the attacker's player object |
| `this.getDefender()` | Returns the defender's player object |
| `this.requestFrame(cb)` | Calls `requestAnimationFrame`, auto-cancelled on `destroy()` |

## Controls Convention

- **Player 1** (left side) typically uses **WASD** or mouse left area
- **Player 2** (right side) typically uses **IJKL** or mouse right area
- Controls are per-player, not per-role (attacker/defender)

## Example: DodgingBattle

See `js/minigames/DodgingBattle.js` for a full working example with:
- Canvas-based rendering
- Keyboard input (WASD / IJKL)
- Projectile spawning & collision
- Attacker extra life mechanic
- Proper cleanup in `destroy()`

## Tips

- Always call `super.init(container, config)` and `super.destroy()`
- Use `this._destroyed` to guard against actions after cleanup
- Use `this.requestFrame()` instead of raw `requestAnimationFrame` for auto-cleanup
- Keep the game area responsive — the arena container is flexible in size
- Test with both players as attacker and defender
