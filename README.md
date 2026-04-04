# Sprite Windows Scene Editor

A lightweight, **self-contained scene editor** built entirely with pygame.  
No external GUI libraries — every dialog, file browser and colour picker is drawn inside the pygame window itself.

The goal is simple: **compose a small animated scene** (background image, sprites, music) and play it as a compact floating window on your desktop.  

---

## Features

| Category | What you can do |
|---|---|
| **Images** | Add static PNG/JPG images to the canvas |
| **Animated sprites** | Point to a folder of PNGs — they become an animation |
| **Resizing** | Drag any of the four corner handles to scale items |
| **Layers** | Photoshop-style layer order with ▲▲ ▲ ▼ ▼▼ buttons |
| **Multi-select** | Ctrl+click, then move/duplicate/delete the whole group |
| **Lock group** | Press L to lock a selection; any click then moves the group |
| **Mirror** | Ctrl+M for horizontal flip |
| **Nudge** | Arrow keys (1 px) or Shift+Arrow (10 px) |
| **Undo** | Ctrl+Z — up to 30 steps, stored as plain-dict snapshots |
| **Music** | Point to a folder of .mp3/.ogg/.wav files — played randomly on loop |
| **Day/Night cycle** | Animated procedural sky + sea background (5-minute cycle) |
| **Dim per item** | ☀ checkbox: item brightness follows the day/night cycle |
| **Tint per item** | T checkbox: item colour shifts with the sky light colour |
| **BG colour** | Built-in HSV colour picker |
| **Canvas size** | Toggle between full and half-size canvas |
| **Save / Load** | JSON format, auto-saved to a `scenes/` folder |
| **Player** | Standalone playback window — no editor UI, just your scene |

---

## Requirements

```bash
pip install pygame
```

Python 3.8 or later. `numpy` is **not** required.

---

## Running

```bash
python main.py
```

A `scenes/` folder is created automatically next to `main.py` on first launch.

---

## Project structure

```
SpriteWindows_scene_editor/
│
├── main.py          Entry point: MainMenu, run_player(), application loop
├── constants.py     All colours, sizes, DAY_MS, SAVE_DIR
├── utils.py         Drawing helpers, colour math, surface effects, confirm_dialog
├── daynight.py      DayNight — procedural sky/sea/stars background
├── playlist.py      Playlist — random-shuffle music player wrapper
├── browser.py       FileBrowser + browse() — pure-pygame file/folder dialog
├── colorpicker.py   ColorPicker + pick_color() — HSV colour picker overlay
├── widgets.py       Button widget
├── scene.py         SceneItem, ResizeState, Scene — the data model
├── editor.py        Editor — the full editing environment
│
├── scenes/          Auto-created; your saved .json scene files live here
│   └── my_scene.json
│
└── assets/          Suggested layout for your own assets
    ├── backgrounds/
    ├── sprites/
    │   └── character_sprite_idle/
    │       ├── frame_00.png
    │       └── frame_01.png
    └── music/
```

### File sizes at a glance

| File | Lines | Responsibility |
|---|---|---|
| `constants.py` | ~60 | One place to change any colour or timing |
| `widgets.py` | ~55 | Reusable Button widget |
| `playlist.py` | ~115 | Music folder shuffle |
| `utils.py` | ~175 | Helpers used everywhere |
| `daynight.py` | ~200 | Procedural sky animation |
| `colorpicker.py` | ~210 | HSV picker overlay |
| `main.py` | ~360 | Entry point + MainMenu + player |
| `browser.py` | ~390 | File/folder dialog |
| `scene.py` | ~425 | Data model (items, scene, resize) |
| `editor.py` | ~1100 | The editor UI |

---

## Architecture

### Module dependency graph

```
main.py
 ├── constants.py        (no deps)
 ├── utils.py            ← constants
 ├── widgets.py          ← constants, utils
 ├── scene.py            ← constants, utils
 ├── playlist.py         (pygame only)
 ├── daynight.py         ← constants, utils
 ├── browser.py          ← constants, utils
 ├── colorpicker.py      ← constants, utils
 └── editor.py           ← all of the above
      └── main.run_player (local import to break the circular dep)
```

`constants.py` and `playlist.py` have no internal dependencies — they are the leaves of the tree.  
`editor.py` imports everything; `main.py` imports `editor.py` and defines `run_player()` which the editor calls via a local import to avoid a circular dependency.

### State machine

```
          ┌──────────────┐
          │  main menu   │◄──────────────────────────┐
          └──────┬───────┘                           │
    New / Load   │          Launch Player             │
                 ▼                 │                 │
          ┌──────────────┐         │         ┌───────┴──────┐
          │    editor    │──Preview─┤         │    player    │
          └──────────────┘         └────────►│  run_player()│
                                             └──────────────┘
```

### Scene JSON format

```json
{
  "name": "jungle",
  "bgcol": [40, 40, 60],
  "music": null,
  "music_folder": "/absolute/path/to/music/",
  "day_night": true,
  "canvas_half": false,
  "items": [
    {
      "paths":       ["/path/to/bg.png"],
      "x": 0,  "y": 0,
      "layer":       "background",
      "fps":         8,
      "label":       "jungle_bg",
      "scale":       1.0,
      "mirrored":    false,
      "dn_affected": true,
      "dn_tint":     true
    }
  ]
}
```

---

## Editor controls

### Toolbar buttons

| Button | Action |
|---|---|
| Load | Open a scene JSON from `scenes/` |
| Save | Save current scene to `scenes/` |
| ▶ Music | Start music playback in the editor |
| ■ Stop | Stop music |
| BG Color | Open the HSV colour picker |
| Canvas½ / Canvas① | Toggle half / full canvas size |
| ▶ Preview | Launch the player with the current scene |

### Mouse

| Action | Result |
|---|---|
| Right-click canvas | Context menu (Add Image / Add Animated Sprite / Set Music Folder) |
| Left-click item | Select it |
| Ctrl + left-click | Toggle item in multi-selection |
| Left-drag item | Move it |
| Left-drag corner handle | Resize (aspect-ratio preserved) |
| Click item name in panel | Select without touching canvas |
| Click ☀ checkbox | Toggle day/night brightness dim |
| Click T checkbox | Toggle day/night colour tint |
| Mousewheel on panel | Scroll the LAYERS list |
| Click section header | Collapse / expand panel section |

### Keyboard

| Key | Action |
|---|---|
| Ctrl+Z | Undo |
| Ctrl+D | Duplicate selection |
| Ctrl+M | Mirror (flip H) selection |
| Del / Backspace | Delete selection |
| Arrows | Nudge 1 px |
| Shift+Arrows | Nudge 10 px |
| L | Lock selection — any click moves the group |
| PgUp / PgDn | Move item one step forward / back in layer order |
| Home / End | Bring to front / send to back |
| Escape | Back to main menu (confirmation dialog) |

---

## Day / Night cycle

Enable the cycle in the **SCENE OPTIONS** panel section.  
The cycle runs over **5 minutes** by default — change `DAY_MS` in `constants.py`.

Per-item flags in the LAYERS list:

| Column | Effect when checked |
|---|---|
| ☀ (dim) | Item brightness follows the night darkness |
| T (tint) | Item colour shifts with the sky light |

Tint colour stops (defined in `daynight.py → tint_color()`):

| Phase | Colour |
|---|---|
| Noon | Warm golden white (255, 240, 180) |
| Sunset | Deep saturated orange (255, 80, 10) |
| Night | Cold deep blue (20, 30, 180) |
| Dawn | Violet (160, 80, 255) |

Tint strength is the `strength=0.72` parameter in `utils.py → tint_surface()`.

---

## Customisation

| What to change | Where |
|---|---|
| UI colours | `constants.py` — `C_*` variables |
| Day/night cycle duration | `constants.py` — `DAY_MS` |
| Tint intensity | `utils.py` — `tint_surface(strength=...)` |
| Sky / sea colour stops | `daynight.py` — `_sky()`, `_sea()`, `tint_color()` |
| Save folder location | `constants.py` — `SAVE_DIR` |

---

## Tips

- **Animated sprites**: name your frames `frame_00.png`, `frame_01.png`, etc. — they are sorted alphabetically.
- **Canvas½ mode**: design at half size to get a compact desktop widget. The player opens at that exact size automatically.
- **Layer order**: the topmost row in the LAYERS panel is drawn on top. Use ▲▲ to bring an item to the front instantly.
- **Music folder**: put all your tracks in one folder — the player picks randomly and loops forever.

---

## License

MIT — do whatever you want with it.
