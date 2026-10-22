# Runeforge: Ivory & Obsidian

An original stylized 3D collection for Battle Chess. The Dawn Guard uses ivory,
antique gold, teal cloth, and sunstones; the Dusk Court uses obsidian armor,
dusksilver, plum cloth, and amethyst. All geometry is authored in this project;
there are no purchased or downloaded models, textures, or fonts.

| Chess piece | Model | Details |
| --- | --- | --- |
| Pawn | Sentinel | Visored helmet, shield, sword, and crested plume |
| Rook | Runic keep | Octagonal tower, battlements, and crystal windows |
| Knight | Wyrm knight | Extruded dragon profile, horns, scales, and wings |
| Bishop | Crystal sage | Split mitre, robes, and crystal-topped staff |
| Queen | Starweaver | Seven-point crown, winged mantle, and gem scepter |
| King | Oathbound king | Five-point crown, pauldrons, cloak, and longsword |

The board has raised stone squares, chisel marks, a stepped basalt foundation,
brass inlays, angular glowing runes, and four corner crystals.

Its background is now an intricate 2D illustration of a volcanic forge, replacing
the modeled scenery. The locally bundled image is `../../backgrounds/runeforge-forge.png`;
see `../../backgrounds/ART_DIRECTION.md` for the built-in imagegen prompts. It stays
fixed beneath the transparent 3D board canvas and is separate from the board/piece
GLB. **Elven 3D** selects the companion
[Sylvan Court collection](../elven/ASSETS.md), with its own forest sanctuary.

## Source and reuse

- `../../../js/fantasy/RuneforgeAssets.js` is the editable source of truth.
  `createMaterials`, `createPiece`, and `createBoardAsset` construct the meshes.
- `runeforge-chess-set.glb` contains the board and 32 named pieces in starting
  formation, with embedded materials. Import it into Blender or another glTF 2.0
  editor. It is a static asset collection, not a rigged character animation pack.
- Units: one unit per square; Y up; the board spans X/Z -4 to 4. Piece origins
  are centered at the bottom of their pedestals. Pieces sit at Y = 0.105.
- Every piece is a group with meshes merged by material. Repeated pieces share
  geometry and materials. Board and piece geometry use solid PBR materials.
- Runtime scene lighting, camera, contact shadow, coordinate lettering, selection rings,
  and movement effects are supplied by `FantasyBoard.js`, outside the GLB.
- The game builds geometry directly from source, so loading the GLB is not a
  startup requirement. After editing the models, use **Download 3D set** to
  regenerate the GLB; replace the committed file to keep the reusable asset current.

## Playing

The new default is **Runeforge 3D**. Select a piece and then a highlighted square.
Camera controls rotate, flip, zoom, reset, or switch to an overhead view. Desktop
users can hold either mouse button and drag to orbit, or drag with one finger on
touchscreens. Horizontal movement rotates; vertical movement tilts within safe
viewing limits. A six-pixel threshold keeps taps/clicks available for play, and
releasing a drag never selects or moves a piece. Scroll outside the canvas to
move the page. The camera never changes chess coordinates.
**Classic 2D** changes only presentation and can be selected during a game.
This preference is stored locally, so online opponents can use different views.

WebGL2 is needed for 3D. If initialization fails or the graphics context is lost,
the game switches to Classic. After context loss, reload the page to retry 3D.
Reduced-motion preferences shorten movement animations. Rendering runs on state,
camera, and resize changes, with animation frames only while a piece moves.

## Dependency and verification

Three.js **0.180.0** is vendored under `../../../lib/three/`, with its MIT license.
It is the only newly downloaded dependency. No npm install, Blender installation,
model service, or runtime CDN is required. See that directory's `VENDOR.md`.

Run from the repository root:

```powershell
.venv/Scripts/python.exe tests/battle_chess_fantasy_browser.py
```

The fantasy browser check uses the already installed Playwright and Edge. It
serves static files, generates desktop/mobile previews under
`prototypes/.qa/runeforge/`, and regenerates the GLB. It exercises actual projected
board clicks, capture, castling, en passant, promotion, check display, camera
changes, mobile layout, view switching, WebGL failure, and context loss.
