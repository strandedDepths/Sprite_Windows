"""
scene.py
========
Data-model classes for the scene editor.

SceneItem
    A single placeable element: static image or animated sprite (N PNG frames).
    Handles loading, scaled rendering, day/night dim/tint, serialisation.

ResizeState
    Encapsulates corner-drag resize maths.
    Keeps the opposite corner fixed in scene space using a snapshot of the
    displayed pixel dimensions taken at drag-start.

Scene
    Container for all scene data: ordered item list, background colour,
    music folder, and flags (day_night, canvas_half).
    Provides Photoshop-style layer-order helpers and JSON save/load.
"""

import os
import json
import pygame
from constants import (
    C_BG, C_ACCENT, C_SEL, C_MULTISEL, C_CANVAS,
    HANDLE_SIZE, TL, TR, BL, BR,
)
from utils import dim_surface, tint_surface

class SceneItem:
    """
    A single placeable element on the canvas: a static image or an animated
    sprite (sequence of PNG frames).

    Key attributes:
        paths         list of file paths (1 = static, N = animated)
        x, y          position on the canvas (top-left corner)
        scale         uniform scale factor (1.0 = original size)
        mirrored      horizontal flip flag
        fps           animation playback speed in frames-per-second
        layer         legacy string kept for JSON compatibility
        dn_affected   if True, the item is dimmed by the day/night brightness
        dn_tint       if True, the item is colour-tinted by the day/night light
        sel           True while the item is selected in the editor

    Raw frames are kept at original resolution; scaled copies are cached
    by (scale, mirrored) key to avoid repeated smoothscale calls.
    The draw() method always scales from raw to avoid double-scale blur.
    """

    _n = 0  # global counter used to assign unique IDs

    def __init__(self, paths, x=100, y=100, layer="background", fps=8,
                 label=None, scale=1.0, mirrored=False,
                 dn_affected=True, dn_tint=False):
        SceneItem._n += 1
        self.id    = SceneItem._n
        self.paths = paths
        self.x     = x
        self.y     = y
        self.layer = layer
        self.fps   = fps
        self.label = label or os.path.basename(paths[0])
        self.sel   = False
        self.fi    = 0.0       # fractional frame index (incremented in update)

        self.scale      = scale
        self.mirrored   = mirrored
        self.dn_affected = dn_affected
        self.dn_tint     = dn_tint

        self.raw_frames = []   # original-resolution pygame.Surface list
        self._cache     = {}   # scaled-frame cache keyed by (scale, mirrored)
        self._load()

    def _load(self):
        """Load all raw frames from disk. Falls back to a magenta placeholder."""
        self.raw_frames = []
        for p in self.paths:
            try:
                self.raw_frames.append(pygame.image.load(p).convert_alpha())
            except Exception as e:
                print(f"Load error {p}: {e}")

        if not self.raw_frames:
            placeholder = pygame.Surface((64, 64), pygame.SRCALPHA)
            placeholder.fill((200, 0, 200, 180))
            self.raw_frames = [placeholder]

        self._cache = {}

    def _get_frames(self):
        """
        Return the list of scaled (and optionally flipped) surfaces for the
        current scale and mirrored state, building the cache entry if needed.
        """
        key = (round(self.scale, 3), self.mirrored)
        if key not in self._cache:
            out = []
            for rf in self.raw_frames:
                w = max(8, int(rf.get_width()  * self.scale))
                h = max(8, int(rf.get_height() * self.scale))
                s = pygame.transform.smoothscale(rf, (w, h))
                if self.mirrored:
                    s = pygame.transform.flip(s, True, False)
                out.append(s)
            self._cache[key] = out
        return self._cache[key]

    def set_scale(self, s):
        """Clamp and set the scale factor (min 5%, max 2000%)."""
        self.scale = max(0.05, min(s, 20.0))

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def frames(self):
        return self._get_frames()

    @property
    def frame(self):
        """The current animation frame surface (cached, scaled)."""
        return self.frames[int(self.fi) % len(self.frames)]

    @property
    def rect(self):
        """
        Bounding Rect of the item at its current position and scale.
        Computed from raw frame dimensions to stay scale-accurate.
        """
        raw = self.raw_frames[0] if self.raw_frames else None
        if raw is None:
            return pygame.Rect(self.x, self.y, 64, 64)
        w = max(8, int(raw.get_width()  * self.scale))
        h = max(8, int(raw.get_height() * self.scale))
        return pygame.Rect(self.x, self.y, w, h)

    # ── Corner handles ──────────────────────────────────────────────────────

    def corner_handles(self, ox=0, oy=0):
        """
        Return a dict mapping corner ID → pygame.Rect for the four resize handles.
        ox, oy are canvas offsets added to scene coordinates.
        """
        r  = self.rect
        cx = r.x + ox
        cy = r.y + oy
        hs = HANDLE_SIZE
        return {
            TL: pygame.Rect(cx - hs,        cy - hs,        hs * 2, hs * 2),
            TR: pygame.Rect(cx + r.w - hs,  cy - hs,        hs * 2, hs * 2),
            BL: pygame.Rect(cx - hs,        cy + r.h - hs,  hs * 2, hs * 2),
            BR: pygame.Rect(cx + r.w - hs,  cy + r.h - hs,  hs * 2, hs * 2),
        }

    # ── Per-frame logic ──────────────────────────────────────────────────────

    def update(self, dt):
        """Advance the animation frame index based on self.fps and elapsed time."""
        if len(self.frames) > 1:
            self.fi = (self.fi + self.fps * dt) % len(self.frames)

    def draw(self, surf, ox=0, oy=0, multi=False, dim=1.0, tint_col=None):
        """
        Render the item onto surf at (self.x + ox, self.y + oy).

        Parameters:
            ox, oy     Canvas offsets (top-left of the canvas rect on screen).
            multi      If True, use the multi-select highlight colour.
            dim        Brightness factor [0,1] — applied via dim_surface().
            tint_col   (r,g,b) colour tint — applied via tint_surface() if not None.

        Always scales directly from raw frames for maximum quality,
        avoiding the blurriness that would result from double-scaling.
        """
        raw   = self.raw_frames[int(self.fi) % len(self.raw_frames)]
        w     = max(8, int(raw.get_width()  * self.scale))
        h     = max(8, int(raw.get_height() * self.scale))
        frame = pygame.transform.smoothscale(raw, (w, h))

        if self.mirrored:
            frame = pygame.transform.flip(frame, True, False)
        if tint_col is not None:
            frame = tint_surface(frame, tint_col)
        if dim < 0.999:
            frame = dim_surface(frame, dim)

        surf.blit(frame, (self.x + ox, self.y + oy))

        # Draw selection border and corner handles when selected
        if self.sel:
            rr = pygame.Rect(self.x + ox, self.y + oy, frame.get_width(), frame.get_height())
            pygame.draw.rect(surf, C_MULTISEL if multi else C_SEL, rr, 2)
            for _, hr in self.corner_handles(ox, oy).items():
                pygame.draw.rect(surf, C_ACCENT, hr, border_radius=2)
                pygame.draw.rect(surf, C_BG, hr, 1, border_radius=2)

    # ── Serialisation ────────────────────────────────────────────────────────

    def to_dict(self):
        """Serialise item state to a plain Python dict (no pygame objects)."""
        return {
            "paths":       self.paths,
            "x":           self.x,
            "y":           self.y,
            "layer":       self.layer,
            "fps":         self.fps,
            "label":       self.label,
            "scale":       self.scale,
            "mirrored":    self.mirrored,
            "dn_affected": self.dn_affected,
            "dn_tint":     self.dn_tint,
        }

    @staticmethod
    def from_dict(d):
        """Reconstruct a SceneItem from a dict produced by to_dict()."""
        return SceneItem(
            d["paths"], d["x"], d["y"],
            d.get("layer",       "background"),
            d.get("fps",         8),
            d.get("label"),
            d.get("scale",       1.0),
            d.get("mirrored",    False),
            d.get("dn_affected", True),
            d.get("dn_tint",     False),
        )

    def duplicate(self):
        """Return a copy of this item offset by 20 px in both axes."""
        return SceneItem(
            self.paths, self.x + 20, self.y + 20,
            self.layer, self.fps, self.label,
            self.scale, self.mirrored,
            self.dn_affected, self.dn_tint,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Resize state (corner-drag resizing)
# ─────────────────────────────────────────────────────────────────────────────

class ResizeState:
    """
    Captures the state at the moment the user starts dragging a corner handle
    and updates the item's scale and position on every mouse-move.

    Design principle:
        All calculations use the *displayed pixel size* at drag-start
        (orig_pw × orig_ph) rather than the post-scale frame size, so the
        opposite corner stays exactly fixed regardless of how fast the user moves.
    """

    def __init__(self, item, corner, mx, my):
        self.item   = item
        self.corner = corner      # TL | TR | BL | BR
        self.mx0    = mx          # mouse X at drag start
        self.my0    = my          # mouse Y at drag start

        # Snapshot of the item's state at drag start
        self.orig_scale = item.scale
        self.orig_pw    = item.frame.get_width()   # displayed width  at drag start
        self.orig_ph    = item.frame.get_height()  # displayed height at drag start
        self.orig_x     = item.x
        self.orig_y     = item.y
        self.orig_r     = item.x + self.orig_pw    # right edge (fixed for TL/TR drags)
        self.orig_b     = item.y + self.orig_ph    # bottom edge (fixed for TL/BL drags)

    def update(self, mx, my):
        """
        Called every frame while the mouse button is held.
        Computes the new scale so that the dragged corner tracks the mouse
        while the opposite corner stays fixed in scene space.
        """
        dx  = mx - self.mx0
        dy  = my - self.my0
        item = self.item
        opw  = self.orig_pw
        oph  = self.orig_ph
        os   = self.orig_scale

        # Average the X and Y scale factors to maintain aspect ratio
        if self.corner == BR:
            nw = max(8, opw + dx)
            nh = max(8, oph + dy)
            item.set_scale(os * max(nw / opw, nh / oph) / 2 +
                           os * min(nw / opw, nh / oph) / 2)
            item.x = self.orig_x
            item.y = self.orig_y

        elif self.corner == BL:
            nw = max(8, opw - dx)
            nh = max(8, oph + dy)
            item.set_scale(os * max(nw / opw, nh / oph) / 2 +
                           os * min(nw / opw, nh / oph) / 2)
            # Right edge stays fixed
            item.x = self.orig_r - item.frame.get_width()
            item.y = self.orig_y

        elif self.corner == TR:
            nw = max(8, opw + dx)
            nh = max(8, oph - dy)
            item.set_scale(os * max(nw / opw, nh / oph) / 2 +
                           os * min(nw / opw, nh / oph) / 2)
            item.x = self.orig_x
            # Bottom edge stays fixed
            item.y = self.orig_b - item.frame.get_height()

        elif self.corner == TL:
            nw = max(8, opw - dx)
            nh = max(8, oph - dy)
            item.set_scale(os * max(nw / opw, nh / oph) / 2 +
                           os * min(nw / opw, nh / oph) / 2)
            # Both right and bottom edges stay fixed
            item.x = self.orig_r - item.frame.get_width()
            item.y = self.orig_b - item.frame.get_height()


# ─────────────────────────────────────────────────────────────────────────────
# Scene — the data model
# ─────────────────────────────────────────────────────────────────────────────

class Scene:
    """
    Container for all scene data: items, background colour, music, and flags.

    Items are stored in a flat list; draw order equals list order
    (index 0 = bottom layer, last index = top layer).
    The layer-order helper methods replicate Photoshop-style operations.

    Serialised to / from a JSON file via save() and load().
    """

    def __init__(self, name="untitled"):
        self.name         = name
        self.items        = []            # ordered list of SceneItem objects
        self.bgcol        = list(C_CANVAS)  # background fill colour [R, G, B]
        self.music        = None          # (legacy) single music file path
        self.music_folder = None          # folder of tracks for the random playlist
        self.day_night    = False         # enable the day/night background cycle
        self.canvas_half  = False         # if True, player opens at half canvas size

    # ── Draw order ──────────────────────────────────────────────────────────

    def sorted(self):
        """Return items in draw order (bottom to top)."""
        return list(self.items)

    def _idx(self, item):
        """Return the list index of item, or -1 if not found."""
        try:
            return self.items.index(item)
        except ValueError:
            return -1

    def bring_forward(self, item):
        """Move item one position toward the top (swap with the item above it)."""
        i = self._idx(item)
        if 0 <= i < len(self.items) - 1:
            self.items[i], self.items[i + 1] = self.items[i + 1], self.items[i]

    def send_back(self, item):
        """Move item one position toward the bottom."""
        i = self._idx(item)
        if i > 0:
            self.items[i], self.items[i - 1] = self.items[i - 1], self.items[i]

    def bring_to_front(self, item):
        """Move item to the very top of the draw order."""
        if item in self.items:
            self.items.remove(item)
            self.items.append(item)

    def send_to_back(self, item):
        """Move item to the very bottom of the draw order."""
        if item in self.items:
            self.items.remove(item)
            self.items.insert(0, item)

    # ── CRUD helpers ─────────────────────────────────────────────────────────

    def add(self, item):
        self.items.append(item)

    def remove(self, item):
        self.items = [i for i in self.items if i.id != item.id]

    # ── Serialisation ────────────────────────────────────────────────────────

    def save(self, path):
        """Write the scene to a JSON file at path."""
        with open(path, "w") as f:
            json.dump({
                "name":         self.name,
                "bgcol":        self.bgcol,
                "music":        self.music,
                "music_folder": self.music_folder,
                "day_night":    self.day_night,
                "canvas_half":  self.canvas_half,
                "items":        [i.to_dict() for i in self.items],
            }, f, indent=2)

    @staticmethod
    def load(path):
        """Read a scene from a JSON file and return a populated Scene instance."""
        with open(path) as f:
            d = json.load(f)
        sc = Scene(d.get("name", "untitled"))
        sc.bgcol        = d.get("bgcol",        list(C_CANVAS))
        sc.music        = d.get("music")
        sc.music_folder = d.get("music_folder", None)
        sc.day_night    = d.get("day_night",    False)
        sc.canvas_half  = d.get("canvas_half",  False)
        for item_d in d.get("items", []):
            sc.items.append(SceneItem.from_dict(item_d))
        return sc

