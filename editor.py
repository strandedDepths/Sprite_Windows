"""
editor.py
=========
The Editor class — the full-screen scene editing environment.

Responsibilities:
    - Canvas rendering (background, items, grid, selection handles, badge)
    - Item selection, multi-select, drag-to-move, corner-resize
    - Undo stack (up to 30 plain-dict snapshots, no pygame surfaces)
    - Collapsible side panel (LAYERS / SELECTION / SCENE OPTIONS)
    - Toolbar actions (load, save, preview, BG colour, canvas size toggle)
    - Context menu (right-click to add images/sprites/music)
    - Keyboard shortcuts (Ctrl+Z, Ctrl+D, Ctrl+M, arrows, layer order)
"""

import os
import json
import pygame
from constants import (
    FPS, PANEL_W, TOOL_H,
    C_BG, C_PANEL, C_TOOLBAR, C_ACCENT, C_ACCENT2, C_DANGER,
    C_TEXT, C_DIM, C_SEL, C_GRID, C_BTN, C_BTNHOV, C_MULTISEL, C_CANVAS,
    HANDLE_SIZE, TL, TR, BL, BR, SAVE_DIR,
)
from utils import rrect, txt, ensure_save_dir, confirm_dialog
from scene import Scene, SceneItem, ResizeState
from browser import browse
from colorpicker import pick_color
from playlist import Playlist
from widgets import Button
from daynight import DayNight

class Editor:
    """
    The full-screen scene editor.

    Responsibilities:
        - Renders the canvas (with optional day/night background)
        - Handles item selection, dragging, resizing, and ordering
        - Hosts the collapsible side panel (LAYERS / SELECTION / SCENE OPTIONS)
        - Drives all toolbar actions (load, save, preview, BG colour, etc.)
        - Manages the undo stack (up to 30 snapshots stored as plain dicts)
    """

    def __init__(self, screen, fonts, clock):
        self.S     = screen
        self.F     = fonts
        self.CL    = clock
        self.scene = Scene()

        # ── Selection state ─────────────────────────────────────────────────
        self.sel        = None   # primary selected SceneItem (or None)
        self.multi_sel  = []     # additional selected items (Ctrl+click)
        self.sel_locked = False  # if True, any canvas click moves the whole group

        # ── Drag and resize state ───────────────────────────────────────────
        self.drag         = False  # True while a move-drag is in progress
        self.doff         = {}     # {item.id: (scene_dx, scene_dy)} drag offsets
        self.resize_state = None   # ResizeState instance while corner-dragging

        # ── Context menu ────────────────────────────────────────────────────
        self.ctx = None   # list of {"label", "fn", "r"} dicts, or None

        # ── Panel state ──────────────────────────────────────────────────────
        # Populated each draw() call; used for hit-testing in handle_event()
        self._item_rows  = []   # (item, name_rect, dim_cb_rect, tint_cb_rect)
        self._order_btns = []   # (rect, direction_string)
        self._sec_rects  = {}   # {section_key: header_rect}

        # Which panel sections are expanded
        self._sections = {"layers": True, "selection": True, "scene": True}

        # Vertical scroll offset for the LAYERS item list
        self._panel_scroll = 0

        # ── Misc ─────────────────────────────────────────────────────────────
        self.last_dir   = os.path.abspath(".")   # last browsed directory
        self._playlist  = None  # active Playlist instance for editor music preview
        self._undo_stack = []   # list of plain-dict snapshots (max 30)
        self.status     = "Right-click canvas to add items  |  Ctrl+click to multi-select"
        self.canvas_half = False   # toggle half-size orange canvas

        # Day/Night renderer instance (resized when needed)
        self._dn    = DayNight(800, 500)
        self._dn_cb = pygame.Rect(0, 0, 1, 1)   # updated each draw; hit-tested in events

    # ── Geometry helpers ────────────────────────────────────────────────────

    def _cr(self):
        """
        Return the pygame.Rect of the orange-bordered canvas area.
        When canvas_half is True the canvas is half the available width and height.
        """
        W, H = self.S.get_size()
        cw   = W - PANEL_W
        ch   = H - TOOL_H
        if self.canvas_half:
            cw //= 2
            ch //= 2
        return pygame.Rect(0, TOOL_H, cw, ch)

    def _to_scene(self, mx, my):
        """Convert screen coordinates to canvas-local (scene) coordinates."""
        cr = self._cr()
        return mx - cr.x, my - cr.y

    def _all_selected(self):
        """Return the primary selection plus any multi-selected items (no duplicates)."""
        result = []
        if self.sel and self.sel not in result:
            result.append(self.sel)
        for item in self.multi_sel:
            if item not in result:
                result.append(item)
        return result

    # ── Per-frame update ────────────────────────────────────────────────────

    def update(self, dt, mp):
        """
        Called once per frame before draw().
        Updates animations, drag/resize positions, and toolbar button hover states.
        """
        # Advance all item animations
        for item in self.scene.items:
            item.update(dt)

        # Advance day/night cycle when enabled
        if self.scene.day_night:
            self._dn.update(int(dt * 1000))

        # Apply active resize drag
        if self.resize_state:
            self.resize_state.update(mp[0], mp[1])

        # Apply active move drag — all selected items follow the mouse
        elif self.drag:
            cr   = self._cr()
            sx   = mp[0] - cr.x
            sy   = mp[1] - cr.y
            for item in self._all_selected():
                if item.id in self.doff:
                    ox, oy    = self.doff[item.id]
                    item.x    = sx - ox
                    item.y    = sy - oy

        # Advance the music playlist (picks next random track when current ends)
        if self._playlist is not None:
            self._playlist.update()

        # Update hover state for all toolbar buttons
        for b in self._all_btns():
            b.update(mp)

    # ── Event handling ──────────────────────────────────────────────────────

    def handle_event(self, ev, mp):
        """
        Route a pygame event to the appropriate handler.

        Priority order (first match wins):
        1. Panel item-row clicks   (layer list — dim/tint checkboxes and name clicks)
        2. Section header toggles  (collapse/expand LAYERS / SELECTION / SCENE)
        3. Inline panel buttons    (order arrows, Dup, Del, Lock, FPS ±)
        4. Panel mousewheel scroll
        5. Day/Night checkbox
        6. Context menu (right-click menu on canvas)
        7. Toolbar Button widgets
        8. Canvas: keyboard shortcuts + mouse drag/select
        """

        # ── 1. Panel item rows ───────────────────────────────────────────────
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for row in self._item_rows:
                item      = row[0]
                name_rect = row[1]
                cb_rect   = row[2]
                tb_rect   = row[3] if len(row) > 3 else None

                if cb_rect.collidepoint(ev.pos):
                    # Toggle the day/night dim flag
                    item.dn_affected = not item.dn_affected
                    self.status = (f"{item.label}: dim "
                                   f"{'ON' if item.dn_affected else 'OFF'}")
                    return

                if tb_rect and tb_rect.collidepoint(ev.pos):
                    # Toggle the day/night colour tint flag
                    item.dn_tint = not item.dn_tint
                    self.status = (f"{item.label}: colour tint "
                                   f"{'ON' if item.dn_tint else 'OFF'}")
                    return

                if name_rect.collidepoint(ev.pos):
                    # Select the clicked item
                    self._clear_selection()
                    self._set_primary(item)
                    self.sel_locked = False
                    self.status = f"Selected: {item.label}"
                    return

        # ── 2. Section header toggles ────────────────────────────────────────
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for sec, r in self._sec_rects.items():
                if r.collidepoint(ev.pos):
                    self._sections[sec] = not self._sections[sec]
                    return

        # ── 3. Inline panel buttons ──────────────────────────────────────────
        if self._handle_inline_panel(ev):
            return

        # ── 4. Panel scroll (mousewheel over the panel area) ────────────────
        W2, H2 = self.S.get_size()
        if ev.type == pygame.MOUSEWHEEL:
            if pygame.mouse.get_pos()[0] > W2 - PANEL_W:
                self._panel_scroll = max(0, self._panel_scroll - ev.y * 3)
                return

        # ── 5. Day/Night checkbox ────────────────────────────────────────────
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self._dn_cb.collidepoint(ev.pos):
                self.scene.day_night = not self.scene.day_night
                self._dn = DayNight(*self._cr().size)
                self.status = f"Day/Night: {'ON' if self.scene.day_night else 'OFF'}"
                return

        # ── 6. Context menu ──────────────────────────────────────────────────
        if self.ctx:
            if ev.type == pygame.MOUSEBUTTONDOWN:
                for opt in self.ctx:
                    if opt["r"].collidepoint(ev.pos):
                        opt["fn"]()
                        self.ctx = None
                        return
                self.ctx = None   # click outside dismisses the menu
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                self.ctx = None
            return

        # ── 7. Toolbar buttons ───────────────────────────────────────────────
        for b in self._all_btns():
            if b.clicked(ev):
                b._action()
                return

        # ── 8. Canvas interactions ───────────────────────────────────────────
        cr   = self._cr()
        ctrl = pygame.key.get_mods() & pygame.KMOD_CTRL

        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_d and ctrl:
                self._push_undo()
                self._duplicate_selected()
            elif ev.key == pygame.K_z and ctrl:
                self._undo()
            elif ev.key == pygame.K_m and ctrl:
                self._push_undo()
                self._mirror_selected()
            elif ev.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                self._push_undo()
                self._del()
            elif ev.key in (pygame.K_UP, pygame.K_DOWN,
                            pygame.K_LEFT, pygame.K_RIGHT):
                step = 10 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1
                self._nudge(ev.key, step)
            elif ev.key == pygame.K_l and self._all_selected():
                # Toggle locked-group movement
                self.sel_locked = not self.sel_locked
                self.status = (
                    "Selection LOCKED — click anywhere to move group"
                    if self.sel_locked else "Selection unlocked"
                )
            elif ev.key == pygame.K_PAGEUP:
                self._push_undo()
                self._order("forward")
            elif ev.key == pygame.K_PAGEDOWN:
                self._push_undo()
                self._order("back")
            elif ev.key == pygame.K_HOME:
                self._push_undo()
                self._order("front")
            elif ev.key == pygame.K_END:
                self._push_undo()
                self._order("bottom")

        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 3 and cr.collidepoint(ev.pos):
                # Right-click → open context menu
                self._open_ctx(ev.pos)

            elif ev.button == 1 and cr.collidepoint(ev.pos):

                if self.sel_locked and self._all_selected():
                    # Locked group: any canvas click starts a group move
                    self._push_undo()
                    self.drag = True
                    self.doff = {}
                    sx, sy = self._to_scene(*mp)
                    for item in self._all_selected():
                        self.doff[item.id] = (sx - item.x, sy - item.y)
                    return

                if self.sel and not ctrl:
                    # Check if the click landed on a corner resize handle
                    for corner, hr in self.sel.corner_handles(cr.x, cr.y).items():
                        if hr.collidepoint(ev.pos):
                            self.resize_state = ResizeState(
                                self.sel, corner, ev.pos[0], ev.pos[1])
                            return

                # Hit-test items (top layer first)
                hit = self._hit(mp)
                if hit:
                    if ctrl:
                        # Ctrl+click: toggle multi-select
                        if hit in self.multi_sel:
                            self.multi_sel.remove(hit)
                            hit.sel = False
                        else:
                            self.multi_sel.append(hit)
                            hit.sel = True
                            if self.sel is None:
                                self._set_primary(hit)
                    else:
                        # Normal click: switch primary selection
                        self._clear_selection()
                        self._set_primary(hit)

                    # Begin dragging the selection
                    self._push_undo()
                    self.drag = True
                    self.doff = {}
                    sx, sy = self._to_scene(*mp)
                    for item in self._all_selected():
                        self.doff[item.id] = (sx - item.x, sy - item.y)

                else:
                    # Click on empty canvas: deselect
                    if not ctrl:
                        self._clear_selection()
                        self.sel_locked = False

        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self.drag         = False
            self.resize_state = None

    # ── Selection helpers ────────────────────────────────────────────────────

    def _clear_selection(self):
        if self.sel:
            self.sel.sel = False
        for i in self.multi_sel:
            i.sel = False
        self.sel       = None
        self.multi_sel = []

    def _set_primary(self, item):
        """Set item as the primary selection without disturbing multi_sel."""
        if self.sel and self.sel is not item:
            self.sel.sel = False
        self.sel       = item
        item.sel       = True

    def _hit(self, mp):
        """Return the topmost item under the mouse, or None."""
        cr = self._cr()
        sx = mp[0] - cr.x
        sy = mp[1] - cr.y
        for item in reversed(self.scene.sorted()):
            if item.rect.collidepoint(sx, sy):
                return item
        return None

    # ── Undo ─────────────────────────────────────────────────────────────────

    def _push_undo(self):
        """
        Save the current scene state as a plain dict snapshot.
        pygame.Surface objects are not copied — only serialisable data is stored.
        The stack is capped at 30 entries.
        """
        snap = {
            "name":         self.scene.name,
            "bgcol":        list(self.scene.bgcol),
            "music":        self.scene.music,
            "music_folder": self.scene.music_folder,
            "day_night":    self.scene.day_night,
            "items":        [i.to_dict() for i in self.scene.items],
        }
        self._undo_stack.append(snap)
        if len(self._undo_stack) > 30:
            self._undo_stack.pop(0)

    def _undo(self):
        """Pop the most recent snapshot and restore the scene from it."""
        if not self._undo_stack:
            self.status = "Nothing to undo"
            return
        snap              = self._undo_stack.pop()
        sc                = Scene(snap["name"])
        sc.bgcol          = snap["bgcol"]
        sc.music          = snap["music"]
        sc.music_folder   = snap["music_folder"]
        sc.day_night      = snap["day_night"]
        for d in snap["items"]:
            sc.items.append(SceneItem.from_dict(d))
        self.scene = sc
        self._clear_selection()
        self.status = "Undo"

    # ── Canvas actions ────────────────────────────────────────────────────────

    def _add_img(self):
        """Open the file browser and add a static image to the scene."""
        p = browse(self.S, self.F, self.CL, "file",
                   [".png", ".jpg", ".bmp"],
                   start=self.last_dir, title="Select image")
        if p:
            self._push_undo()
            self.last_dir = os.path.dirname(p)
            item = SceneItem([p], 50, 50, "background")
            self.scene.add(item)
            self._clear_selection()
            self._set_primary(item)
            self.status = f"Added: {item.label}"

    def _add_anim(self):
        """Open the folder browser; load all PNGs as animation frames."""
        folder = browse(self.S, self.F, self.CL, "folder",
                        start=self.last_dir,
                        title="Select folder of PNG frames")
        if not folder:
            return
        self._push_undo()
        self.last_dir = os.path.dirname(folder)
        paths = [
            os.path.join(folder, f)
            for f in sorted(os.listdir(folder))
            if f.lower().endswith(".png")
        ]
        if not paths:
            self.status = f"No PNGs in: {os.path.basename(folder)}"
            return
        item = SceneItem(paths, 50, 50, "foreground",
                         fps=8, label=os.path.basename(folder))
        self.scene.add(item)
        self._clear_selection()
        self._set_primary(item)
        self.status = f"Animated '{item.label}' — {len(paths)} frames"

    def _set_music(self):
        """Open the folder browser and set the music playlist folder."""
        folder = browse(self.S, self.F, self.CL, "folder",
                        start=self.last_dir, title="Select music folder")
        if not folder:
            return
        exts   = (".mp3", ".ogg", ".wav")
        tracks = [f for f in os.listdir(folder) if f.lower().endswith(exts)]
        if not tracks:
            self.status = "No audio files found in that folder"
            return
        self.last_dir         = os.path.dirname(folder)
        self.scene.music_folder = folder
        self.scene.music      = None   # clear any legacy single-track setting
        self.status = (f"Music folder: {os.path.basename(folder)}"
                       f" ({len(tracks)} tracks)")

    def _play(self):
        """Start music playback in the editor (preview only)."""
        # Stop any currently running playlist before starting a new one
        if self._playlist is not None:
            self._playlist.stop()
        if self.scene.music_folder and os.path.isdir(self.scene.music_folder):
            self._playlist = Playlist()
            self._playlist.load_folder(self.scene.music_folder)
            self._playlist.play_random()
            self.status = "♪ Playing (random folder)"
        elif self.scene.music and os.path.exists(self.scene.music):
            self._playlist = Playlist()
            self._playlist.single_track(self.scene.music)
            self.status = "♪ Playing"
        else:
            self._playlist = None
            self.status = "No music — right-click → Set Music Folder"

    def _launch_player(self):
        """
        Save the current scene to a temp file and open the player window.
        The canvas rect size (respecting canvas_half) is passed as the design size,
        so items appear exactly as they were placed.
        run_player is imported locally to avoid a circular import
        (main.py defines run_player and also imports Editor).
        """
        from main import run_player   # local import breaks the circular dependency
        import tempfile
        self.scene.canvas_half = self.canvas_half
        tmp = os.path.join(tempfile.gettempdir(), "_dk_preview.json")
        self.scene.save(tmp)
        cr       = self._cr()           # orange-bordered canvas rect
        W, H     = self.S.get_size()
        run_player(tmp, canvas_size=(cr.w, cr.h))
        # Restore the editor window after the player closes
        pygame.display.set_mode((W, H), pygame.RESIZABLE)
        pygame.display.set_caption("DK Scene Editor")

    def _stop(self):
        if self._playlist is not None:
            self._playlist.stop()
            self._playlist = None
        else:
            pygame.mixer.music.stop()
        self.status = "Stopped"

    def _save(self):
        """Open the save dialog in the scenes/ folder and write the JSON file."""
        ensure_save_dir()
        p = browse(self.S, self.F, self.CL, "save",
                   start=SAVE_DIR,
                   title="Save scene",
                   default_name=self.scene.name + ".json")
        if p:
            self.scene.canvas_half = self.canvas_half   # persist the current setting
            self.scene.name        = os.path.splitext(os.path.basename(p))[0]
            self.scene.save(p)
            self.status = f"Saved → {os.path.basename(p)}"

    def _load(self):
        """Open the load dialog in the scenes/ folder and replace the current scene."""
        ensure_save_dir()
        p = browse(self.S, self.F, self.CL, "file",
                   [".json"], start=SAVE_DIR, title="Load scene")
        if p:
            self.last_dir   = os.path.dirname(p)
            self.scene      = Scene.load(p)
            self._clear_selection()
            self.canvas_half = self.scene.canvas_half   # restore the setting
            self._dn = DayNight(*self._cr().size)
            self.status = f"Loaded: {self.scene.name}"

    def _pick_bgcolor(self):
        """Open the colour picker and update the scene background colour."""
        col = pick_color(self.S, self.F, self.CL, tuple(self.scene.bgcol))
        if col:
            self.scene.bgcol = list(col)

    def _del(self):
        """Delete all currently selected items."""
        for item in self._all_selected():
            self.scene.remove(item)
        self._clear_selection()
        self.status = "Deleted"

    def _duplicate_selected(self):
        """Duplicate all selected items and select the copies."""
        new = []
        for item in self._all_selected():
            ni = item.duplicate()
            self.scene.add(ni)
            new.append(ni)
        if new:
            self._clear_selection()
            self._set_primary(new[0])
            for ni in new[1:]:
                self.multi_sel.append(ni)
                ni.sel = True
            self.status = f"Duplicated {len(new)} item(s)"

    def _layer(self, l):
        """Set the legacy layer field on all selected items."""
        for item in self._all_selected():
            item.layer = l
        self.status = f"Layer → {l}"

    def _mirror_selected(self):
        """Toggle horizontal mirroring on all selected items."""
        for item in self._all_selected():
            item.mirrored = not item.mirrored
        self.status = "Mirrored"

    def _nudge(self, key, step):
        """Move all selected items by step pixels in the given arrow direction."""
        dx = dy = 0
        if   key == pygame.K_LEFT:  dx = -step
        elif key == pygame.K_RIGHT: dx =  step
        elif key == pygame.K_UP:    dy = -step
        elif key == pygame.K_DOWN:  dy =  step
        for item in self._all_selected():
            item.x += dx
            item.y += dy

    def _order(self, direction):
        """
        Move the primary selected item in the draw-order stack.
        direction: "forward" | "back" | "front" | "bottom"
        """
        if not self.sel:
            return
        if   direction == "forward": self.scene.bring_forward(self.sel)
        elif direction == "back":    self.scene.send_back(self.sel)
        elif direction == "front":   self.scene.bring_to_front(self.sel)
        elif direction == "bottom":  self.scene.send_to_back(self.sel)
        idx = self.scene._idx(self.sel)
        self.status = f"Layer order: position {idx+1}/{len(self.scene.items)}"

    def _fps_dec(self):
        for item in self._all_selected():
            item.fps = max(1, item.fps - 1)
        if self.sel:
            self.status = f"FPS: {self.sel.fps}"

    def _fps_inc(self):
        for item in self._all_selected():
            item.fps = min(60, item.fps + 1)
        if self.sel:
            self.status = f"FPS: {self.sel.fps}"

    def _toggle_lock(self):
        self.sel_locked = not self.sel_locked
        self.status = f"Selection {'LOCKED' if self.sel_locked else 'unlocked'}"

    def _toggle_canvas(self):
        self.canvas_half = not self.canvas_half
        self.status = f"Canvas: {'HALF size' if self.canvas_half else 'FULL size'}"

    # ── Toolbar buttons ───────────────────────────────────────────────────────

    def _toolbar_btns(self):
        """Build and return the list of toolbar Button objects."""
        f       = self.F["sm"]
        cv_lbl  = "Canvas½" if not self.canvas_half else "Canvas①"
        cv_col  = C_BTN    if not self.canvas_half else C_ACCENT2

        specs = [
            (  8, "Load",      self._load,          None),
            (106, "Save",      self._save,           C_ACCENT2),
            (204, "▶ Music",   self._play,           C_ACCENT),
            (302, "■ Stop",    self._stop,           None),
            (400, "BG Color",  self._pick_bgcolor,   None),
            (498, cv_lbl,      self._toggle_canvas,  cv_col),
            (596, "▶ Preview", self._launch_player,  C_ACCENT2),
        ]
        btns = []
        for x, lbl, fn, col in specs:
            b = Button((x, 8, 90, 32), lbl, col, font=f)
            b._action = fn
            btns.append(b)
        return btns

    def _all_btns(self):
        """Return all Button objects that receive update()/clicked() calls."""
        return self._toolbar_btns()

    # ── Inline panel button handler ───────────────────────────────────────────

    def _handle_inline_panel(self, ev):
        """
        Check whether ev is a click on any inline panel button
        (layer order, Dup, Del, Lock, FPS ±).
        These are drawn directly in _draw_panel() and their rects are stored
        in instance variables; they are not Button objects.
        Returns True if the event was consumed.
        """
        if ev.type != pygame.MOUSEBUTTONDOWN or ev.button != 1:
            return False

        pos = ev.pos

        # Layer order arrows (▲▲ ▲ ▼ ▼▼)
        for r, direction in getattr(self, "_order_btns", []):
            if r.collidepoint(pos):
                self._push_undo()
                self._order(direction)
                return True

        # Duplicate
        if getattr(self, "_sel_dup_r", None) and self._sel_dup_r.collidepoint(pos):
            self._push_undo()
            self._duplicate_selected()
            return True

        # Delete
        if getattr(self, "_sel_del_r", None) and self._sel_del_r.collidepoint(pos):
            self._push_undo()
            self._del()
            return True

        # Lock toggle
        if getattr(self, "_sel_lock_r", None) and self._sel_lock_r.collidepoint(pos):
            self._toggle_lock()
            return True

        # FPS decrease / increase
        if getattr(self, "_fps_m_r", None) and self._fps_m_r.collidepoint(pos):
            self._fps_dec()
            return True
        if getattr(self, "_fps_p_r", None) and self._fps_p_r.collidepoint(pos):
            self._fps_inc()
            return True

        return False

    # ── Context menu ─────────────────────────────────────────────────────────

    def _open_ctx(self, pos):
        """Build the right-click context menu at pos."""
        opts = [
            ("Add Image",          self._add_img),
            ("Add Animated Sprite", self._add_anim),
            ("Set Music Folder",   self._set_music),
        ]
        self.ctx = [
            {"label": l, "fn": fn,
             "r": pygame.Rect(pos[0], pos[1] + i * 30, 200, 28)}
            for i, (l, fn) in enumerate(opts)
        ]

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self):
        """Full editor draw: toolbar → canvas → panel → ctx menu → status bar."""
        self.S.fill(C_BG)
        self._draw_toolbar()
        self._draw_canvas()
        self._draw_panel()
        self._draw_ctx()
        self._draw_status()

    def _draw_toolbar(self):
        """Render the top toolbar strip with all action buttons."""
        W = self.S.get_width()
        pygame.draw.rect(self.S, C_TOOLBAR, (0, 0, W, TOOL_H))
        txt(self.S, "◈ DK Scene Editor", self.F["md"], C_ACCENT,
            W - PANEL_W - 10, 15, align="right")
        for b in self._toolbar_btns():
            b.draw(self.S)

    def _draw_canvas(self):
        """
        Render the canvas area:
            - Day/Night background (if enabled) or solid colour + grid
            - All scene items in draw order, with dim/tint applied per-item
            - Orange border
            - Layer badge on selected item
        """
        cr     = self._cr()
        bright = 1.0

        if self.scene.day_night:
            # Render sky/sea into a temp surface then blit to canvas position
            dn_surf = pygame.Surface(cr.size)
            bright  = self._dn.draw(dn_surf)
            self.S.blit(dn_surf, (cr.x, cr.y))
        else:
            # Plain colour fill + grid lines
            pygame.draw.rect(self.S, tuple(self.scene.bgcol), cr)
            for gx in range(cr.x, cr.right, 32):
                pygame.draw.line(self.S, C_GRID, (gx, cr.top), (gx, cr.bottom))
            for gy in range(cr.top, cr.bottom, 32):
                pygame.draw.line(self.S, C_GRID, (cr.left, gy), (cr.right, gy))

        # Draw items clipped to the canvas rect
        self.S.set_clip(cr)
        multi       = len(self._all_selected()) > 1
        dn_tint_col = self._dn.tint_color() if self.scene.day_night else None

        for item in self.scene.sorted():
            d  = bright       if (item.dn_affected and self.scene.day_night) else 1.0
            tc = dn_tint_col  if (item.dn_tint     and self.scene.day_night) else None
            item.draw(self.S, cr.x, cr.y, multi=multi, dim=d, tint_col=tc)

        self.S.set_clip(None)

        # Orange canvas border
        pygame.draw.rect(self.S, C_ACCENT, cr, 2)

        # Layer badge floating above the selected item
        if self.sel:
            idx   = self.scene._idx(self.sel)
            tot   = len(self.scene.items)
            badge = f"[{idx+1}/{tot}]"
            if self.sel_locked:
                badge += "🔒"
            txt(self.S, badge, self.F["xs"], C_ACCENT,
                self.sel.x + cr.x, self.sel.y + cr.y - 16)

    def _draw_panel(self):
        """
        Render the right-side panel with three collapsible sections:
            LAYERS      — scrollable item list with dim (☀) and tint (T) checkboxes
            SELECTION   — layer order, transform info, and action buttons
            SCENE OPTIONS — day/night toggle, BG colour, music info, keyboard hints
        """
        W, H  = self.S.get_size()
        px    = W - PANEL_W

        # Panel background and left border
        pygame.draw.rect(self.S, C_PANEL, (px, 0, PANEL_W, H))
        pygame.draw.line(self.S, C_ACCENT, (px, TOOL_H), (px, H), 1)

        ROW   = 26    # height of each item row in the LAYERS list
        SEC_H = 28    # height of a section header
        PAD   = 8     # horizontal padding inside the panel

        # Reset per-frame hit-test lists
        self._item_rows = []
        self._sec_rects = {}

        y = TOOL_H + 4   # running Y position

        # ── Inner helper: draw a collapsible section header ──────────────────
        def sec_header(key, label):
            nonlocal y
            open_ = self._sections[key]
            r     = pygame.Rect(px + 4, y, PANEL_W - 8, SEC_H - 2)
            pygame.draw.rect(self.S, (35, 35, 55), r, border_radius=4)
            arrow = "▼" if open_ else "▶"
            txt(self.S, f"{arrow}  {label}", self.F["sm"], C_ACCENT, px + PAD + 2, y + 6)
            self._sec_rects[key] = r
            y += SEC_H

        # ══════════════════════════════════════════════════════════════════════
        # SECTION 1 — LAYERS
        # Each row shows:  [☀ dim cb] [T tint cb]  [## item name]
        # ══════════════════════════════════════════════════════════════════════
        sec_header("layers", "LAYERS")

        if self._sections["layers"]:
            items_ordered = self.scene.sorted()
            n             = len(items_ordered)

            # Determine how many rows fit before the halfway point of the panel
            max_rows     = max(1, min(n, (H // 2 - y) // ROW))
            visible_start = min(self._panel_scroll, max(0, n - max_rows))
            self._panel_scroll = visible_start

            # Column headers
            txt(self.S, "☀",      self.F["xs"], C_DIM,         px + PAD,      y + 2)
            txt(self.S, "T",       self.F["xs"], (255, 140, 60), px + PAD + 16, y + 2)
            txt(self.S, "#  name", self.F["xs"], C_DIM,         px + PAD + 32, y + 2)
            y += 16

            # Clip the list area
            list_top = y
            list_h   = max_rows * ROW
            self.S.set_clip(pygame.Rect(px, list_top, PANEL_W, list_h))
            draw_y   = list_top

            # Draw rows in reverse order (top layer displayed first)
            for i, item in enumerate(reversed(items_ordered)):
                if i < visible_start:
                    continue
                if draw_y >= list_top + list_h:
                    break

                lnum   = n - i   # display layer number (1 = bottom)
                is_sel = item.sel

                # Text colour based on selection state
                col = (C_MULTISEL if (is_sel and item in self.multi_sel
                                      and item is not self.sel)
                       else C_SEL if is_sel
                       else C_TEXT)

                # Selected-row highlight background
                if is_sel:
                    pygame.draw.rect(
                        self.S, (45, 45, 70),
                        pygame.Rect(px + 2, draw_y, PANEL_W - 4, ROW - 2),
                        border_radius=3
                    )

                # ── Dim checkbox (☀) ─────────────────────────────────────────
                cb = pygame.Rect(px + PAD, draw_y + 7, 12, 12)
                if item.dn_affected:
                    pygame.draw.rect(self.S, C_ACCENT, cb, border_radius=2)
                    pygame.draw.line(self.S, C_BG, (cb.x+2, cb.y+6), (cb.x+5, cb.y+9), 2)
                    pygame.draw.line(self.S, C_BG, (cb.x+5, cb.y+9), (cb.x+10,cb.y+3), 2)
                else:
                    pygame.draw.rect(self.S, C_BTN, cb, border_radius=2)
                    pygame.draw.rect(self.S, C_DIM, cb, 1, border_radius=2)

                # ── Tint checkbox (T) ─────────────────────────────────────────
                tb = pygame.Rect(px + PAD + 16, draw_y + 7, 12, 12)
                if item.dn_tint:
                    pygame.draw.rect(self.S, (255, 140, 60), tb, border_radius=2)
                    pygame.draw.line(self.S, C_BG, (tb.x+2, tb.y+6), (tb.x+5, tb.y+9), 2)
                    pygame.draw.line(self.S, C_BG, (tb.x+5, tb.y+9), (tb.x+10,tb.y+3), 2)
                else:
                    pygame.draw.rect(self.S, C_BTN, tb, border_radius=2)
                    pygame.draw.rect(self.S, C_DIM, tb, 1, border_radius=2)

                # ── Item name ─────────────────────────────────────────────────
                lock_icon = " 🔒" if (self.sel_locked and is_sel) else ""
                name_txt  = f"{lnum:2d}  {item.label[:13]}{lock_icon}"
                txt(self.S, name_txt, self.F["xs"], col, px + PAD + 32, draw_y + 7)

                # Clickable name area
                name_rect = pygame.Rect(px + PAD + 32, draw_y, PANEL_W - PAD - 34, ROW)
                self._item_rows.append((item, name_rect, cb, tb))
                draw_y += ROW

            self.S.set_clip(None)
            y = list_top + list_h + 4

            # Scrollbar (shown only when the list overflows)
            if n > max_rows:
                sb_h = max(20, list_h * max_rows // n)
                sb_y = list_top + list_h * visible_start // n
                pygame.draw.rect(
                    self.S, C_DIM,
                    (px + PANEL_W - 5, sb_y, 3, sb_h),
                    border_radius=2
                )

            pygame.draw.line(self.S, C_BTN, (px+4, y), (px+PANEL_W-4, y))
            y += 6

        # ══════════════════════════════════════════════════════════════════════
        # SECTION 2 — SELECTION  (always visible)
        # Shows transform info, layer-order buttons, Dup/Del, Lock, FPS
        # ══════════════════════════════════════════════════════════════════════
        sel_items = self._all_selected()
        sec_header("selection", "SELECTION")

        if self._sections["selection"]:
            f  = self.F["sm"]
            bw = 40   # button width
            bh = 24   # button height
            gp = 4    # gap between buttons

            if not sel_items:
                # Empty state hint
                txt(self.S, "No item selected",       self.F["xs"], C_DIM, px+PAD, y+4)
                txt(self.S, "Click an item on canvas", self.F["xs"], C_DIM, px+PAD, y+18)
                txt(self.S, "or its name in LAYERS",  self.F["xs"], C_DIM, px+PAD, y+32)
                y += 48

            if sel_items:
                if self.sel:
                    # Info row: layer position and current scale
                    idx = self.scene._idx(self.sel)
                    tot = len(self.scene.items)
                    txt(self.S, f"Layer {idx+1}/{tot}",     self.F["xs"], C_DIM, px+PAD,    y+2)
                    txt(self.S, f"Scale {self.sel.scale:.2f}×", self.F["xs"], C_DIM, px+PAD+80, y+2)
                    y += 16
                    if len(self.sel.paths) > 1:
                        # Show current animation FPS for animated sprites
                        txt(self.S, f"FPS: {self.sel.fps}", self.F["xs"], C_DIM, px+PAD, y+2)
                        y += 16

                # ── Layer order buttons: ▲▲ ▲ ▼ ▼▼ ─────────────────────────
                order_specs = [
                    ("▲▲", "front",   C_ACCENT),
                    ("▲",  "forward", C_BTN),
                    ("▼",  "back",    C_BTN),
                    ("▼▼", "bottom",  C_DANGER),
                ]
                self._order_btns = []
                bx = px + PAD
                for lbl, direction, col in order_specs:
                    r    = pygame.Rect(bx, y, bw, bh)
                    hcol = C_BTNHOV if r.collidepoint(pygame.mouse.get_pos()) else col
                    rrect(self.S, hcol, r, 4)
                    txt(self.S, lbl, f, C_TEXT, r.centerx, r.y+4, align="center")
                    self._order_btns.append((r, direction))
                    bx += bw + gp
                y += bh + 6

                # ── Duplicate and Delete buttons ─────────────────────────────
                hw    = (PANEL_W - PAD*2 - gp) // 2
                dup_r = pygame.Rect(px+PAD,       y, hw, bh)
                del_r = pygame.Rect(px+PAD+hw+gp, y, hw, bh)
                mp    = pygame.mouse.get_pos()
                rrect(self.S, C_ACCENT2 if dup_r.collidepoint(mp) else C_BTN,    dup_r, 4)
                rrect(self.S, C_DANGER  if del_r.collidepoint(mp) else C_BTN,    del_r, 4)
                txt(self.S, "Dup", f, C_TEXT, dup_r.centerx, dup_r.y+4, align="center")
                txt(self.S, "Del", f, C_TEXT, del_r.centerx, del_r.y+4, align="center")
                self._sel_dup_r = dup_r
                self._sel_del_r = del_r
                y += bh + 6

                # ── Lock group button ────────────────────────────────────────
                lock_col = C_ACCENT if self.sel_locked else C_BTN
                lk_r     = pygame.Rect(px+PAD, y, PANEL_W-PAD*2, bh)
                rrect(self.S, lock_col, lk_r, 4)
                lk_lbl = ("🔒 LOCKED — click to move"
                          if self.sel_locked else "L — Lock & move group")
                txt(self.S, lk_lbl, self.F["xs"], C_TEXT,
                    lk_r.centerx, lk_r.y+6, align="center")
                self._sel_lock_r = lk_r
                y += bh + 6

                # ── Animation speed (only for multi-frame sprites) ───────────
                if self.sel and len(self.sel.paths) > 1:
                    txt(self.S, "SPEED",              self.F["xs"], C_DIM,  px+PAD,    y+2)
                    txt(self.S, f"{self.sel.fps} fps", self.F["xs"], C_TEXT, px+PAD+44, y+2)
                    m_r = pygame.Rect(px+PAD+90,  y, 28, bh)
                    p_r = pygame.Rect(px+PAD+122, y, 28, bh)
                    mp  = pygame.mouse.get_pos()
                    rrect(self.S, C_BTNHOV  if m_r.collidepoint(mp) else C_BTN,    m_r, 4)
                    rrect(self.S, C_ACCENT2 if p_r.collidepoint(mp) else C_BTN,    p_r, 4)
                    txt(self.S, "−", f, C_TEXT, m_r.centerx, m_r.y+4, align="center")
                    txt(self.S, "+", f, C_TEXT, p_r.centerx, p_r.y+4, align="center")
                    self._fps_m_r = m_r
                    self._fps_p_r = p_r
                    y += bh + 6
                else:
                    self._fps_m_r = None
                    self._fps_p_r = None

                txt(self.S, f"{len(sel_items)} item(s) selected",
                    self.F["xs"], C_ACCENT2, px+PAD, y)
                y += 14
                pygame.draw.line(self.S, C_BTN, (px+4, y), (px+PANEL_W-4, y))
                y += 6

        # Reset inline button rects when nothing is selected
        if not sel_items:
            self._sel_dup_r  = None
            self._sel_del_r  = None
            self._sel_lock_r = None
            self._fps_m_r    = None
            self._fps_p_r    = None
            self._order_btns = []

        # ══════════════════════════════════════════════════════════════════════
        # SECTION 3 — SCENE OPTIONS
        # Day/Night toggle, BG colour swatch, music folder, keyboard hints
        # ══════════════════════════════════════════════════════════════════════
        sec_header("scene", "SCENE OPTIONS")

        if self._sections["scene"]:
            # Day/Night checkbox
            cb = pygame.Rect(px+PAD, y+4, 14, 14)
            if self.scene.day_night:
                pygame.draw.rect(self.S, C_ACCENT, cb, border_radius=3)
                txt(self.S, "✓", self.F["xs"], C_BG, px+PAD+1, y+4)
            else:
                pygame.draw.rect(self.S, C_BTN, cb, border_radius=3)
                pygame.draw.rect(self.S, C_DIM, cb, 1, border_radius=3)
            txt(self.S, "Day/Night cycle", self.F["xs"], C_TEXT, px+PAD+20, y+5)
            # Clickable region covers the whole row
            self._dn_cb = pygame.Rect(px+PAD, y, PANEL_W-PAD*2, 20)
            y += 24

            # Background colour swatch
            txt(self.S, "BG COLOR", self.F["xs"], C_DIM, px+PAD, y)
            y += 14
            swatch = pygame.Rect(px+PAD, y, PANEL_W-PAD*2, 14)
            pygame.draw.rect(self.S, tuple(self.scene.bgcol), swatch, border_radius=3)
            pygame.draw.rect(self.S, C_DIM, swatch, 1, border_radius=3)
            y += 20

            # Music folder info
            pygame.draw.line(self.S, C_BTN, (px+4, y), (px+PANEL_W-4, y))
            y += 6
            txt(self.S, "MUSIC FOLDER", self.F["sm"], C_ACCENT, px+PAD, y)
            y += 16

            if self.scene.music_folder:
                mn   = os.path.basename(self.scene.music_folder)
                exts = (".mp3", ".ogg", ".wav")
                try:
                    nt = [f for f in os.listdir(self.scene.music_folder)
                          if f.lower().endswith(exts)]
                except Exception:
                    nt = []
                txt(self.S, f"{mn[:18]} ({len(nt)} tracks)",
                    self.F["xs"], C_DIM, px+PAD, y)
            else:
                mn = ("None" if not self.scene.music
                      else os.path.basename(self.scene.music))
                txt(self.S, mn[:24], self.F["xs"], C_DIM, px+PAD, y)
            y += 16

            # Keyboard shortcut hints
            pygame.draw.line(self.S, C_BTN, (px+4, y), (px+PANEL_W-4, y))
            y += 6
            for hint in [
                "Ctrl+M mirror  Ctrl+Z undo",
                "Arrows nudge  Shift×10",
                "PgUp/Dn fwd/back layer",
                "Home/End front/back",
            ]:
                txt(self.S, hint, self.F["xs"], C_DIM, px+PAD, y)
                y += 14

    def _draw_ctx(self):
        """Render the right-click context menu if it is open."""
        if not self.ctx:
            return
        mp = pygame.mouse.get_pos()
        for opt in self.ctx:
            hov = opt["r"].collidepoint(mp)
            rrect(self.S, C_BTNHOV if hov else C_BTN, opt["r"])
            txt(self.S, opt["label"], self.F["sm"], C_TEXT,
                opt["r"].x + 8, opt["r"].y + 6)

    def _draw_status(self):
        """Render the one-line status message at the bottom of the screen."""
        W, H = self.S.get_size()
        txt(self.S, self.status, self.F["xs"], C_DIM, 8, H - 18)

