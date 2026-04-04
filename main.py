"""
main.py
=======
Application entry point.

Initialises pygame, builds the shared font dictionary, and runs the
three-state application loop:

    menu    MainMenu is shown.
    editor  Editor is active.
    player  run_player() blocks until the player window is closed.

State transitions:
    menu → editor   New Scene or Load Scene
    editor → menu   Escape (with confirmation dialog)
    menu → player   Launch Player (run_player blocks)
    editor → player ▶ Preview button (run_player blocks)
"""

import sys
import os
import json
import pygame

from constants import (
    FPS, PANEL_W, TOOL_H, SAVE_DIR,
    C_BG, C_PANEL, C_TOOLBAR, C_ACCENT, C_ACCENT2,
    C_TEXT, C_DIM, C_GRID, C_BTN, C_BTNHOV,
    C_SEL, C_CANVAS, C_BRBG,
)
from utils import (
    rrect, txt, ensure_save_dir, confirm_dialog,
    tint_surface, dim_surface,
)
from scene import Scene
from playlist import Playlist
from daynight import DayNight
from widgets import Button
from browser import browse
from editor import Editor

class MainMenu:
    """
    The application's home screen.

    Offers three actions:
        New Scene       Start a blank editor session.
        Load Scene      Pick a .json file from the scenes/ folder and edit it.
        Launch Player   Pick a .json file and play it immediately.
    """

    def __init__(self, screen, fonts, clock):
        self.S      = screen
        self.F      = fonts
        self.CL     = clock
        self.result = None   # "new" | "load" | "play" | None
        self._lp    = None   # path of the scene chosen for load/play

    def _cb(self, y, w=220, h=50):
        """Return a horizontally centred Rect at the given Y position."""
        W = self.S.get_width()
        return pygame.Rect(W // 2 - w // 2, y, w, h)

    def handle_event(self, ev):
        W, H = self.S.get_size()
        cy   = H // 2

        bn = Button(self._cb(cy -  10),"New Scene",     C_ACCENT,  (30,30,30), self.F["lg"])
        bl = Button(self._cb(cy +  60),"Load Scene",    C_BTN,     C_TEXT,     self.F["lg"])
        bp = Button(self._cb(cy + 120, 220, 44), "▶ Launch Player", C_ACCENT2, (20,20,20), self.F["lg"])

        if bn.clicked(ev):
            self.result = "new"

        if bl.clicked(ev):
            ensure_save_dir()
            p = browse(self.S, self.F, self.CL, "file", [".json"],
                       start=SAVE_DIR, title="Load a saved scene")
            if p:
                self._lp    = p
                self.result = "load"

        if bp.clicked(ev):
            ensure_save_dir()
            p = browse(self.S, self.F, self.CL, "file", [".json"],
                       start=SAVE_DIR, title="Pick scene to play")
            if p:
                self._lp    = p
                self.result = "play"

    def draw(self):
        W, H = self.S.get_size()
        cy   = H // 2

        # Background grid
        self.S.fill(C_BG)
        for gx in range(0, W, 40):
            pygame.draw.line(self.S, C_GRID, (gx, 0), (gx, H))
        for gy in range(0, H, 40):
            pygame.draw.line(self.S, C_GRID, (0, gy), (W, gy))

        # Title and subtitle
        txt(self.S, "SPRITE WINDOWS SCENE EDITOR",        self.F["xl"], C_ACCENT, W//2, cy-100, align="center")
        txt(self.S, "Create · Animate · Enjoy", self.F["md"], C_DIM,    W//2, cy- 58, align="center")

        # Buttons
        mp = pygame.mouse.get_pos()
        for b in [
            Button(self._cb(cy -  10),        "New Scene",     C_ACCENT,  (30,30,30), self.F["lg"]),
            Button(self._cb(cy +  60),        "Load Scene",    C_BTN,     C_TEXT,     self.F["lg"]),
            Button(self._cb(cy + 120, 220, 44), "▶ Launch Player", C_ACCENT2, (20,20,20), self.F["lg"]),
        ]:
            b.update(mp)
            b.draw(self.S)


# ─────────────────────────────────────────────────────────────────────────────
# Player  — clean playback window, no editor UI
# ─────────────────────────────────────────────────────────────────────────────

def run_player(scene_path, canvas_size):
    """
    Open a standalone player window for scene_path.

    canvas_size — (width, height) in pixels, which must match the coordinate
                  space in which the items were placed (i.e. the editor canvas
                  rect size, already accounting for canvas_half).
    The window opens at exactly canvas_size and scales all item positions and
    sizes proportionally if the user resizes it.

    Controls:
        Skip Intro   jump straight to the looping playlist
        Next Track   advance to the next track
        Escape       close the player
    """
    sc      = Scene.load(scene_path)
    CW, CH  = canvas_size

    win = pygame.display.set_mode((CW, CH), pygame.RESIZABLE)
    pygame.display.set_caption(f"▶ {sc.name}")

    # ── Set up music ────────────────────────────────────────────────────────
    playlist = Playlist()
    if sc.music_folder and os.path.isdir(sc.music_folder):
        playlist.load_folder(sc.music_folder)
        playlist.play_random()
    elif sc.music and os.path.exists(sc.music):
        playlist.single_track(sc.music)
    # If no music is configured the playlist stays silent (no crash)

    # ── Optional day/night background ───────────────────────────────────────
    dn = DayNight(CW, CH) if sc.day_night else None

    clock   = pygame.time.Clock()
    font_xs = pygame.font.SysFont("consolas,monospace", 11)

    # Minimal UI buttons (top-left corner)
    skip_r  = pygame.Rect(10,  10, 90, 26)
    next_r  = pygame.Rect(106, 10, 90, 26)

    show_hint = True
    hint_t    = 3.0   # seconds the "Esc — close" hint is visible
    running   = True

    while running:
        dt      = clock.tick(60) / 1000.0
        hint_t -= dt
        if hint_t <= 0:
            show_hint = False
        playlist.update()   # auto-advance when a non-looping track ends

        # ── Events ──────────────────────────────────────────────────────────
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                running = False
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if skip_r.collidepoint(ev.pos):
                    playlist.play_random()
                elif next_r.collidepoint(ev.pos):
                    playlist.next_track()

        # ── Draw ────────────────────────────────────────────────────────────
        W, H = win.get_size()

        # Scale factors relative to the design size (canvas_size)
        sx = W / CW
        sy = H / CH

        bright = 1.0
        if dn:
            dn.resize(W, H)
            dn.update(int(dt * 1000))
            bright = dn.draw(win)
        else:
            win.fill(tuple(sc.bgcol))

        # Draw items — always scale raw frames for maximum quality
        dn_tint_col = dn.tint_color() if dn else None

        for item in sc.sorted():
            item.update(dt)
            raw = item.raw_frames[int(item.fi) % len(item.raw_frames)]
            tw  = max(1, int(raw.get_width()  * item.scale * sx))
            th  = max(1, int(raw.get_height() * item.scale * sy))
            frame = pygame.transform.smoothscale(raw, (tw, th))

            if item.mirrored:
                frame = pygame.transform.flip(frame, True, False)
            if item.dn_tint and dn:
                frame = tint_surface(frame, dn_tint_col)
            if item.dn_affected and dn:
                frame = dim_surface(frame, bright)

            win.blit(frame, (int(item.x * sx), int(item.y * sy)))

        # ── Player UI overlay (minimal) ──────────────────────────────────────
        mp = pygame.mouse.get_pos()
        for r, lbl in [(skip_r, "Skip Intro"), (next_r, "Next Track")]:
            col = (100, 100, 100) if r.collidepoint(mp) else (45, 45, 45)
            pygame.draw.rect(win, col, r, border_radius=4)
            pygame.draw.rect(win, (130, 130, 130), r, 1, border_radius=4)
            ls = font_xs.render(lbl, True, (255, 255, 255))
            win.blit(ls, ls.get_rect(center=r.center))

        # Currently playing track name (bottom-left)
        np_s = font_xs.render(f"♪ {playlist.current_name}", True, (220, 220, 220))
        win.blit(np_s, (10, H - 18))

        # "Esc — close" hint (bottom-right, fades after 3 s)
        if show_hint:
            h = font_xs.render("Esc — close player", True, (160, 160, 160))
            win.blit(h, (W - h.get_width() - 8, H - 18))

        pygame.display.flip()

    # Stop music cleanly before returning to the caller
    playlist.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Application entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """
    Initialise pygame, build shared resources, and run the main application loop.

    States:
        "menu"    MainMenu is active.
        "editor"  Editor is active.

    Transitions:
        menu  → editor   on "New Scene" or "Load Scene"
        editor → menu    on Escape (after confirmation dialog)
        menu  → player   on "Launch Player" (run_player blocks until closed)
        editor → player  on "▶ Preview" button (run_player blocks)
    """
    pygame.init()
    pygame.mixer.init()
    ensure_save_dir()

    # Initial window size (resizable)
    W0, H0 = 900, 600
    screen  = pygame.display.set_mode((W0, H0), pygame.RESIZABLE)
    pygame.display.set_caption("Sprite Windows Scene Editor")
    clock   = pygame.time.Clock()

    # Font dictionary shared across all widgets
    fonts = {
        k: pygame.font.SysFont("consolas,monospace", s, bold=b)
        for k, s, b in [
            ("xl", 32, True),
            ("lg", 20, True),
            ("md", 16, False),
            ("sm", 13, False),
            ("xs", 11, False),
        ]
    }

    menu   = MainMenu(screen, fonts, clock)
    editor = None
    state  = "menu"

    while True:
        dt = clock.tick(FPS) / 1000.0
        mp = pygame.mouse.get_pos()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            # ── Menu state ──────────────────────────────────────────────────
            if state == "menu":
                menu.handle_event(ev)

                if menu.result == "new":
                    editor       = Editor(screen, fonts, clock)
                    state        = "editor"
                    menu.result  = None

                elif menu.result == "load" and menu._lp:
                    editor       = Editor(screen, fonts, clock)
                    editor.scene = Scene.load(menu._lp)
                    state        = "editor"
                    menu.result  = None

                elif menu.result == "play" and menu._lp:
                    sw, sh       = screen.get_size()
                    full_cw      = sw - PANEL_W
                    full_ch      = sh - TOOL_H

                    # Peek at canvas_half in the JSON to compute the correct size
                    try:
                        import json as _j
                        with open(menu._lp) as _f:
                            _d = _j.load(_f)
                        _half = _d.get("canvas_half", False)
                    except Exception:
                        _half = False

                    canvas_size = (
                        (full_cw // 2, full_ch // 2) if _half
                        else (full_cw, full_ch)
                    )
                    run_player(menu._lp, canvas_size=canvas_size)

                    # Restore the editor window after the player closes
                    screen = pygame.display.set_mode((sw, sh), pygame.RESIZABLE)
                    pygame.display.set_caption("Sprite Windows Scene Editor")
                    menu.result = None

            # ── Editor state ────────────────────────────────────────────────
            elif state == "editor":
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    # Ask for confirmation before discarding unsaved changes
                    if confirm_dialog(screen, fonts, clock,
                                      message="Leave the editor?",
                                      yes_label="Leave", no_label="Stay"):
                        pygame.mixer.music.stop()
                        state       = "menu"
                        menu.result = None
                else:
                    editor.handle_event(ev, mp)

        # ── Draw current state ───────────────────────────────────────────────
        if state == "menu":
            menu.draw()
        elif state == "editor":
            editor.update(dt, mp)
            editor.draw()

        pygame.display.flip()


if __name__ == "__main__":
    main()
