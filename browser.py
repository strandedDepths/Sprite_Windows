"""
browser.py
==========
A pure-pygame file/folder/save browser — no OS dialogs required.

Three modes:
    "file"    Pick a single file (filtered by extension).
    "folder"  Navigate to a folder and confirm it.
    "save"    Type a filename; result is the full destination path.

Usage:
    from browser import browse
    path = browse(screen, fonts, clock, mode="file", exts=[".png"])

The blocking browse() helper runs its own mini event loop so the caller
does not need to manage the browser state.
"""

import os
import sys
import pygame
from constants import (
    C_BTN, C_BTNHOV, C_ACCENT, C_ACCENT2,
    C_TEXT, C_DIM, C_BRBG, C_BRROW, C_BRHOV, C_BRSEL,
    C_BRDIR, C_BRFILE,
)
from utils import rrect, txt

class FileBrowser:
    """
    A modal file/folder browser drawn entirely inside the pygame window.

    Modes:
        "file"    The user picks a single file (filtered by exts).
        "folder"  The user navigates to a folder and confirms it.
        "save"    The user types a filename; result is the full destination path.

    After the interaction, self.result holds the selected path (or None if
    cancelled) and self.done is True.

    Usage: instantiate, then call handle_event() and draw() each frame
    inside a blocking loop (see browse() helper below).
    """

    ROW_H  = 26   # height of each file/folder row
    MARGIN = 12   # horizontal margin inside the dialog box
    HDR    = 50   # header area height
    FTR    = 52   # footer area height

    def __init__(self, screen, fonts, mode="file", exts=None,
                 start=None, title=None, default_name="scene.json"):
        self.screen = screen
        self.F      = fonts
        self.mode   = mode

        # Extensions to show in "file" mode (empty = show all)
        self.exts = [e.lower() for e in (exts or [])]

        self.title  = title or ("Pick file"   if mode == "file"
                        else   "Pick folder"  if mode == "folder"
                        else   "Save as")

        self.result   = None
        self.done     = False
        self.cwd      = os.path.abspath(start or ".")
        self.entries  = []   # list of (name, full_path, is_dir)
        self.scroll   = 0
        self.hovered  = -1
        self.sel      = -1

        # Save-mode text input
        self.savename = default_name
        self._blink   = True
        self._bt      = 0.0   # blink timer

        self._refresh()

    def _refresh(self):
        """Reload the directory listing for self.cwd."""
        self.entries = []
        self.scroll  = 0
        self.sel     = -1

        try:
            # Directories first, then files, both alphabetically
            names = sorted(
                os.listdir(self.cwd),
                key=lambda n: (not os.path.isdir(os.path.join(self.cwd, n)), n.lower())
            )
        except PermissionError:
            names = []

        for n in names:
            full   = os.path.join(self.cwd, n)
            is_dir = os.path.isdir(full)

            # In file mode, hide entries that don't match the filter
            if not is_dir and self.exts:
                if not any(n.lower().endswith(e) for e in self.exts):
                    continue

            self.entries.append((n, full, is_dir))

    # ── Layout helpers ──────────────────────────────────────────────────────

    def _br(self):
        """Return the outer dialog Rect (centred on screen)."""
        W, H = self.screen.get_size()
        bw   = min(680, W - 40)
        bh   = min(500, H - 40)
        return pygame.Rect((W - bw) // 2, (H - bh) // 2, bw, bh)

    def _lr(self, br):
        """Return the scrollable list Rect inside the dialog."""
        return pygame.Rect(
            br.x + self.MARGIN,
            br.y + self.HDR,
            br.w - self.MARGIN * 2,
            br.h - self.HDR - self.FTR
        )

    def _vis(self, lr):
        """Number of visible rows in the list area."""
        return lr.h // self.ROW_H

    # ── Event handling ──────────────────────────────────────────────────────

    def update(self, dt):
        """Advance the text-cursor blink timer."""
        self._bt += dt
        if self._bt > 0.5:
            self._bt   = 0
            self._blink = not self._blink

    def handle_event(self, event):
        br  = self._br()
        lr  = self._lr(br)
        vis = self._vis(lr)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.done = True   # cancel without selecting

            elif self.mode == "save":
                # Text input for the filename
                if event.key == pygame.K_BACKSPACE:
                    self.savename = self.savename[:-1]
                elif event.key == pygame.K_RETURN:
                    self._confirm()
                elif event.unicode and event.unicode.isprintable():
                    self.savename += event.unicode

            else:
                # Keyboard navigation of the list
                if event.key == pygame.K_UP:
                    self.sel = max(0, self.sel - 1)
                    self._clamp(vis)
                elif event.key == pygame.K_DOWN:
                    self.sel = min(len(self.entries) - 1, self.sel + 1)
                    self._clamp(vis)
                elif event.key == pygame.K_RETURN:
                    self._activate(self.sel)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:   # scroll wheel up
                self.scroll = max(0, self.scroll - 3)
            elif event.button == 5: # scroll wheel down
                self.scroll = min(max(0, len(self.entries) - vis), self.scroll + 3)
            elif event.button == 1:
                self._click(event.pos, br, lr, vis)

        elif event.type == pygame.MOUSEMOTION:
            # Track which row the mouse is hovering over
            self.hovered = -1
            if lr.collidepoint(event.pos):
                idx = self.scroll + (event.pos[1] - lr.y) // self.ROW_H
                if 0 <= idx < len(self.entries):
                    self.hovered = idx

    def _click(self, pos, br, lr, vis):
        """Handle a left-click anywhere inside the dialog."""
        up_btn  = pygame.Rect(br.x + self.MARGIN, br.y + 11, 60, 26)
        fy      = br.y + br.h - self.FTR + 10
        cancel  = pygame.Rect(br.x + br.w - 105, fy, 88, 30)
        confirm = pygame.Rect(br.x + br.w - 210, fy, 96, 30)

        if up_btn.collidepoint(pos):
            # Navigate to parent directory
            parent = os.path.dirname(self.cwd)
            if parent != self.cwd:
                self.cwd = parent
                self._refresh()

        elif cancel.collidepoint(pos):
            self.done = True   # cancel

        elif confirm.collidepoint(pos):
            self._confirm()

        elif lr.collidepoint(pos):
            idx = self.scroll + (pos[1] - lr.y) // self.ROW_H
            if 0 <= idx < len(self.entries):
                if self.sel == idx:
                    # Second click on the same row → activate (open dir or select file)
                    self._activate(idx)
                else:
                    self.sel = idx
                    # In save mode, clicking a file auto-fills the filename
                    if self.mode == "save":
                        n, full, is_dir = self.entries[idx]
                        if not is_dir:
                            self.savename = n

    def _activate(self, idx):
        """
        Double-click action: open a directory, or confirm a file selection.
        """
        if not (0 <= idx < len(self.entries)):
            return
        n, full, is_dir = self.entries[idx]

        if is_dir:
            self.cwd = full
            self._refresh()
        elif self.mode == "file":
            self.result = full
            self.done   = True

    def _confirm(self):
        """
        Confirm button action — behaves differently per mode:
        - folder: returns self.cwd (or the selected subdir)
        - file:   returns the selected file path
        - save:   returns self.cwd / self.savename (with .json extension enforced)
        """
        if self.mode == "folder":
            if 0 <= self.sel < len(self.entries):
                n, full, is_dir = self.entries[self.sel]
                self.result = full if is_dir else self.cwd
            else:
                self.result = self.cwd
            self.done = True

        elif self.mode == "file":
            if 0 <= self.sel < len(self.entries):
                n, full, is_dir = self.entries[self.sel]
                if not is_dir:
                    self.result = full
                    self.done   = True

        elif self.mode == "save":
            name = self.savename.strip()
            if not name:
                return
            if not name.endswith(".json"):
                name += ".json"
            self.result = os.path.join(self.cwd, name)
            self.done   = True

    def _clamp(self, vis):
        """Keep self.sel visible by adjusting the scroll offset."""
        if self.sel < self.scroll:
            self.scroll = self.sel
        elif self.sel >= self.scroll + vis:
            self.scroll = self.sel - vis + 1

    # ── Drawing ─────────────────────────────────────────────────────────────

    def draw(self):
        """Render the browser overlay onto self.screen."""
        # Dim the content behind the dialog
        ov = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        self.screen.blit(ov, (0, 0))

        br  = self._br()
        lr  = self._lr(br)
        vis = self._vis(lr)
        mp  = pygame.mouse.get_pos()
        fxs = self.F["xs"]
        fsm = self.F["sm"]

        # Dialog box
        rrect(self.screen, C_BRBG, br, 10)
        pygame.draw.rect(self.screen, C_ACCENT, br, 2, border_radius=10)

        # Header: title and current directory path
        txt(self.screen, self.title, fsm, C_ACCENT, br.x + self.MARGIN + 70, br.y + 10)
        cwd_s = self.cwd if len(self.cwd) < 56 else "…" + self.cwd[-53:]
        txt(self.screen, cwd_s, fxs, C_DIM, br.x + self.MARGIN + 70, br.y + 28)

        # "Up" button to navigate to the parent directory
        up = pygame.Rect(br.x + self.MARGIN, br.y + 11, 60, 26)
        rrect(self.screen, C_BTNHOV if up.collidepoint(mp) else C_BTN, up)
        txt(self.screen, "▲ Up", fxs, C_TEXT, up.x + 6, up.y + 6)

        # File list background
        pygame.draw.rect(self.screen, C_BRROW, lr)
        self.screen.set_clip(lr)

        for i in range(vis):
            idx = self.scroll + i
            if idx >= len(self.entries):
                break
            n, full, is_dir = self.entries[idx]
            rr = pygame.Rect(lr.x, lr.y + i * self.ROW_H, lr.w, self.ROW_H)

            # Row highlight
            if idx == self.sel:
                pygame.draw.rect(self.screen, C_BRSEL, rr)
            elif idx == self.hovered:
                pygame.draw.rect(self.screen, C_BRHOV, rr)

            # Directory icon and text
            icon  = "[ ] " if is_dir else "    "
            color = C_BRDIR if is_dir else C_BRFILE
            txt(self.screen, (icon + n)[:64], fxs, color, rr.x + 6, rr.y + 5)

        self.screen.set_clip(None)

        # Scrollbar
        if len(self.entries) > vis:
            sb_h = max(20, lr.h * vis // len(self.entries))
            sb_y = lr.y + lr.h * self.scroll // max(len(self.entries), 1)
            pygame.draw.rect(self.screen, C_DIM, (lr.right - 5, sb_y, 4, sb_h), border_radius=2)

        # Footer separator
        fy = br.y + br.h - self.FTR + 10
        pygame.draw.line(self.screen, C_BTN,
                         (br.x + self.MARGIN, fy - 6),
                         (br.right - self.MARGIN, fy - 6))

        # Footer content
        if self.mode == "save":
            # Editable filename input box
            box = pygame.Rect(br.x + self.MARGIN, fy, br.w - 220, 30)
            rrect(self.screen, C_BTN, box)
            pygame.draw.rect(self.screen, C_ACCENT, box, 1, border_radius=6)
            cursor = "|" if self._blink else " "
            txt(self.screen, self.savename + cursor, fsm, C_TEXT, box.x + 6, box.y + 6)
        else:
            # Selection hint
            if 0 <= self.sel < len(self.entries):
                hint = "Selected: " + self.entries[self.sel][0]
            elif self.mode == "folder":
                hint = "Select folder or press 'Select Folder'"
            else:
                hint = "Click a file to select it"
            txt(self.screen, hint[:54], fxs, C_DIM, br.x + self.MARGIN, fy + 8)

        # Cancel and confirm buttons
        cancel  = pygame.Rect(br.x + br.w - 105, fy, 88, 30)
        confirm = pygame.Rect(br.x + br.w - 210, fy, 96, 30)
        clbl    = ("Select Folder" if self.mode == "folder"
                   else "Save"     if self.mode == "save"
                   else "Open")

        rrect(self.screen, C_BTNHOV if cancel.collidepoint(mp) else C_BTN, cancel)
        txt(self.screen, "Cancel", fsm, C_TEXT, cancel.centerx, cancel.y + 6, align="center")

        rrect(self.screen, C_ACCENT2 if confirm.collidepoint(mp) else C_BTN, confirm)
        txt(self.screen, clbl, fsm, C_TEXT, confirm.centerx, confirm.y + 6, align="center")


def browse(screen, fonts, clock, mode="file", exts=None,
           start=None, title=None, default_name="scene.json"):
    """
    Blocking helper: open a FileBrowser and run its own mini event loop
    until the user picks a file/folder or cancels.
    Returns the selected path string, or None if cancelled.
    """
    b = FileBrowser(screen, fonts, mode=mode, exts=exts,
                    start=start, title=title, default_name=default_name)
    while not b.done:
        dt = clock.tick(60) / 1000.0
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            b.handle_event(ev)
        b.update(dt)
        b.draw()
        pygame.display.flip()
    return b.result

