# Sylvan Court: Sunleaf & Moonveil

An original elven 3D collection for Battle Chess, selectable with **Elven 3D**.
The Sunleaf court uses pearlwood, pale fern silk, and gold. The Moonveil court
uses midnight jade, blue silk, moon silver, and opals.

| Piece | Model | Silhouette |
| --- | --- | --- |
| Pawn | Leafwarden | Pointed ears, leaf shield, and curved longbow |
| Rook | Silverwood spire | Open organic spire enclosing a crystal |
| Knight | Royal stag | Stag head with branching antlers |
| Bishop | Moon seer | Robes, pointed headdress, and crescent staff |
| Queen | Bloom queen | Seven-petal crown, leaf mantle, flower scepter |
| King | Antler king | Branching crown, leaf breastplate, spear |

The board combines jade and moonstone tiles, gold leaf inlay, intertwined vine
rails, and glowing lotus corners supported by silverwood roots.

## Editable assets

- `../../../js/fantasy/ElvenAssets.js` constructs every original board and piece
  mesh. It shares simple modeling primitives with `RuneforgeAssets.js`.
- `sylvan-court-chess-set.glb` contains the board and 32 named pieces with embedded
  materials. Use **Download 3D set** while Elven is selected to regenerate it.
- These are static meshes, not rigged animated characters. One unit equals one
  square; Y is up; pieces are placed at Y = 0.105.
- `../../backgrounds/elven-sanctuary.png` is the detailed 2D background, generated
  with built-in imagegen. It replaces the modeled trees, gates, pools and particles.
  See `../../backgrounds/ART_DIRECTION.md` for the final prompts and composition.
- The background stays fixed as the 3D board turns. Its perspective, detailed
  surfaces and lighting provide depth without background geometry. The transparent
  renderer adds contact shadows; the image is separate from GLB exports.
- Both themes share one WebGL renderer; model sets are cached
  on first use. Switching themes preserves game state, camera and selection.
- Theme selection is saved locally, including across reloads. Online opponents
  may choose different appearances. Classic and WebGL fallback still work.

The illustrated backdrop is bundled locally. It uses the existing vendored
Three.js 0.180.0 library and MIT license; no new dependencies were installed.

## Verification

```powershell
.venv/Scripts/python.exe tests/battle_chess_fantasy_browser.py --elven
.venv/Scripts/python.exe tests/battle_chess_fantasy_browser.py
```

The first two commands exercise projected clicks, camera changes, special moves,
mobile layouts, Classic fallback, GLB downloads, persisted preferences and
repeated theme switches without increasing the renderer's geometry count. They
regenerate the respective GLB and previews under `prototypes/.qa/elven/` and
`prototypes/.qa/runeforge/`.
