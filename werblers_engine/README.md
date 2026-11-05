# Werblers developer guide

Werblers has one Python rules engine, local desktop and mobile clients, and
persistent private online rooms. Run commands below from the repository root.

## Code map

| Location | Responsibility |
| --- | --- |
| `werblers_engine/game.py` | Game state, turn rotation, movement decks, legacy auto-play |
| `werblers_engine/turn.py` | Interactive actions, combat previews, offers, explicit loss choices |
| `werblers_engine/combat.py` | Shared strength totals and win/loss/tie comparison |
| `werblers_engine/content.py`, `effects.py` | Card definitions, tooltips, effect hooks |
| `werblers_engine/save_load.py` | JSON saves, deck RNG state, shared-reference restoration |
| `werblers_web/decisions.py` | Current decision and its owner, used for local recovery and online rooms |
| `werblers_web/routes/` | HTTP handlers and local-session access |
| `werblers_web/rooms.py` | Room persistence, seat authorization, version checks, request deduplication, AI |
| `werblers_web/serializers.py` | Public state and card-image metadata |
| `static/games/werblers/js/choices.js` | Shared reactions, Slurp! choices and saved-game recovery |
| `static/games/werblers/js/game.js` | Desktop presentation |
| `static/games/werblers-mobile/js/ios_game.js` | Mobile presentation |
| `static/games/werblers/js/online.js` | Online interface shared by desktop and mobile |

The local routes use a browser-session game in memory. Online rooms serialize
their state into the site database after actions and use database locking.
Local games require manual saves; private rooms save automatically. Local
sessions do not survive a process restart. Do not treat the room invitation
code as a seat credential: guest seat tokens remain private to that browser.

## Running locally

Install `requirements.txt` in a Python virtual environment, then run `python
app.py`. The default development port is 5000. The two local interfaces are
`/games/werblers` and `/games/werblers-mobile`; both expose Play Online.

Development defaults to SQLite when `DATABASE_URL` is unset. A production
environment requires a configured `SECRET_KEY`. Use the isolated fixtures in
the tests when experimenting with accounts, saves, or room state; they create
temporary databases instead of changing normal application data.

## Turn and decision contract

`begin_move()` does not necessarily finish a turn. It returns `done`,
`offer_chest`, `offer_shop`, `combat`, `charlie_work`, or `mystery`. The web
decision descriptor uses `chest` and `shop` for the corresponding offers.
Follow `state.decision` for the next input and its `player_id`; a reward or
reaction can belong to someone other than `current_player_id`.

| Decision phase | Resolution |
| --- | --- |
| `move` | `begin_move` |
| `combat` | `fight`, permitted flee actions, equipment or consumables |
| `bystander` | Online opponent uses a consumable or passes; local clients show the remaining reaction queue in combat |
| `charlie_work` | `resolve_charlie_work` |
| `chest`, `shop` | `resolve_offer`, or eligible `scavenger_swap` |
| `rake_it_in` | `resolve_rake_it_in` |
| `mystery` | `resolve_mystery` |
| `fairy_king_reward` | `resolve_fairy_king_reward`, then place its item |
| `item`, `minion` | `place_trait_item`, `resolve_minion`, using the reward owner's ID |
| `me_too` | `resolve_me_too`, with the pending choice ID |
| `trait_loss` | `resolve_trait_loss`, with the choice ID and exactly two distinct trait indices |
| `finished` | No further gameplay actions |

Joh'Neil's Slurp! queues a saved choice when the loser has more than two traits.
The fight's penalties are applied once; turn advancement waits for the selected
traits to be discarded. Touchdown enters the same interactive boss flow. Failed
fight resolution restores the pre-fight game state so the action can be retried.

Keep rules in the engine, rather than only hiding controls in a client:

- Scavenger replaces **one selected offer** once per chest or shop. The used
  flag is saved. Mystery-event item rewards are not eligible. An empty item
  deck rejects the redraw without spending it.
- Fair Exchange validates every selected item before removing any. Active
  curse locks, invalid indices, and duplicate selections reject the whole
  sacrifice in local and online play.
- `combat_totals()` is used by previews and actual resolution. Include night,
  boss, equipment and pre-fight consumable modifiers. Preserve the totals from
  combat before rewards or loss effects alter the inventory or traits.

`Game._decide()` and `_select()` are legacy auto-play callbacks. Some older
effects still use them; they are not asynchronous UI prompts. New player choices
should have an explicit, serializable decision and an owner. The legacy select
contract is `(prompt, labels, log) -> index`, not a list of selected objects.

## Save compatibility

The JSON format remains version 1 with additive fields. Missing
`_pending_trait_loss` and `_next_trait_loss_id` in older saves default to no
pending loss and choice ID 1. Pending offers retain their type, offered items,
and one-use flags. Pending combat must refer to the game's actual decks,
players, and bosses after deserialization, rather than independent copies.

`/api/load` returns a full state plus `resume`, derived from the shared decision
descriptor. `choices.resumeGame()` opens the correct local interaction for
combat, offers, events, reactions, and rewards. Do not add a new phase without
also updating its recovery path, online authorization, AI/host handling, and
save/load tests. Never replay a fight or draw rewards again merely to recover
its presentation.

## Verification

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_werblers*.py'
node --test tests/werblers_choices.test.mjs
.\.venv\Scripts\python.exe -B tests/werblers_online_browser.py
.\.venv\Scripts\python.exe -B tests/werblers_recovery_browser.py
```

The browser scripts require Python Playwright and use Edge when installed,
otherwise Playwright's Chromium. They run headlessly against temporary local
databases. The recovery script checks actual desktop/mobile dialogs, reward
ownership, redraw limits, and layout. Screenshots are written to the system
temporary directory as `werblers-fixed-desktop.png` and
`werblers-fixed-mobile.png`.

Keep source files UTF-8. Readable symbols should remain ordinary Unicode in
JavaScript and HTML; do not re-encode UTF-8 text as Windows-1252. Bump the game
asset version in both templates when changing the client/server decision
contract so browsers receive matching clients.
