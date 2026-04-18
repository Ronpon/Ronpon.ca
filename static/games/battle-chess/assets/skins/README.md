# Creating a Skin Pack

Skins let you customise the look of the chess board and pieces.

## Quick Start

1. Create a folder inside `assets/skins/` with a short unique name (e.g. `assets/skins/ocean`).
2. Add a `manifest.json` file describing your skin.
3. (Optional) Add piece images.

The `SkinManager` loads skins at runtime — no code changes needed.

## manifest.json Format

```json
{
  "name": "Ocean Theme",
  "author": "Your Name",
  "description": "A cool blue ocean-themed board",
  "boardColors": {
    "light": "#D6EAF8",
    "dark": "#2E86C1",
    "selected": "rgba(255, 255, 0, 0.5)",
    "validMove": "rgba(0, 0, 0, 0.25)",
    "lastMove": "rgba(255, 255, 0, 0.2)",
    "check": "rgba(255, 0, 0, 0.5)"
  },
  "pieceStyle": "default"
}
```

### Fields

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Display name of the skin |
| `author` | No | Creator name |
| `description` | No | Short description |
| `boardColors.light` | Yes | Light square colour (CSS colour) |
| `boardColors.dark` | Yes | Dark square colour |
| `boardColors.selected` | Yes | Selected piece highlight |
| `boardColors.validMove` | Yes | Valid move dot / ring colour |
| `boardColors.lastMove` | Yes | Last move highlight |
| `boardColors.check` | Yes | Check highlight |
| `pieceStyle` | Yes | `"default"` for Unicode pieces, or `"images"` for custom images |
| `pieces` | If images | Object mapping piece keys to image filenames |

## Custom Piece Images

Set `"pieceStyle": "images"` and provide a `pieces` map:

```json
{
  "pieceStyle": "images",
  "pieces": {
    "wK": "wK.png",
    "wQ": "wQ.png",
    "wR": "wR.png",
    "wB": "wB.png",
    "wN": "wN.png",
    "wP": "wP.png",
    "bK": "bK.png",
    "bQ": "bQ.png",
    "bR": "bR.png",
    "bB": "bB.png",
    "bN": "bN.png",
    "bP": "bP.png"
  }
}
```

Place the image files in the same folder as the manifest. Images should be square (recommended 160×160px or higher). PNG or SVG are both supported.

**Piece key format:** `{color}{Type}` — color is `w` or `b`, type is uppercase: K Q R B N P.

If a piece image is missing, the engine falls back to the Unicode character for that piece.

## Loading a Skin

In code, skins are loaded by folder name:

```js
await skinManager.loadSkin('ocean');
```

Currently the default skin is loaded at startup. Skin switching UI will be added in a future update.

## Example Folder Structure

```
assets/skins/ocean/
├── manifest.json
├── wK.png
├── wQ.png
├── ...
└── bP.png
```
