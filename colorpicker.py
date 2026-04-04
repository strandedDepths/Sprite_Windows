"""
colorpicker.py
==============
An HSV colour picker drawn entirely inside the pygame window.

Layout:
    Left square  →  saturation (X) × value/brightness (Y)
    Right strip  →  hue bar
    Footer       →  preview swatch + hex code + Apply/Cancel

Usage:
    from colorpicker import pick_color
    colour = pick_color(screen, fonts, clock, initial=(40, 40, 60))
    # Returns (r,g,b) or None if cancelled.
"""

import sys
import colorsys
import pygame
from constants import C_BG, C_BTN, C_BTNHOV, C_ACCENT, C_ACCENT2, C_TEXT, C_DIM, C_BRBG
from utils import rrect, txt

class ColorPicker:
    """
    A modal HSV colour picker drawn inside the pygame window.

    Layout:
        Left square  →  saturation (X axis) × value/brightness (Y axis)
        Right strip  →  hue bar
        Footer       →  colour preview swatch + hex code + Apply/Cancel

    After interaction:
        self.result  (r,g,b) tuple, or None if cancelled
        self.done    True once the user has confirmed or cancelled
    """

    SIZE = 280  # width/height of the saturation-value square

    def __init__(self, screen, fonts, initial=(40, 40, 60)):
        self.screen = screen
        self.F      = fonts

        # Convert initial RGB to HSV
        r, g, b = [c / 255 for c in initial]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        self.h = h
        self.s = s
        self.v = v

        self.result = None
        self.done   = False
        self._drag  = None  # "sv" or "hue" while dragging

        # Pre-render the SV square and hue strip as surfaces
        sz        = self.SIZE
        self._sv  = pygame.Surface((sz, sz))
        self._hue = pygame.Surface((20, sz))
        self._rebuild_sv()

        for y in range(sz):
            rr, gg, bb = colorsys.hsv_to_rgb(y / sz, 1, 1)
            pygame.draw.line(self._hue,
                             (int(rr * 255), int(gg * 255), int(bb * 255)),
                             (0, y), (19, y))

    def _rebuild_sv(self):
        """Regenerate the SV square for the current hue."""
        sz = self.SIZE
        for x in range(sz):
            for y in range(sz):
                rr, gg, bb = colorsys.hsv_to_rgb(self.h, x / sz, 1 - y / sz)
                self._sv.set_at((x, y), (int(rr * 255), int(gg * 255), int(bb * 255)))

    def _pr(self):
        """Return the outer panel Rect (centred on screen)."""
        W, H = self.screen.get_size()
        pw   = self.SIZE + 60
        ph   = self.SIZE + 100
        return pygame.Rect((W - pw) // 2, (H - ph) // 2, pw, ph)

    @property
    def rgb(self):
        """Current colour as an (r,g,b) tuple."""
        r, g, b = colorsys.hsv_to_rgb(self.h, self.s, self.v)
        return (int(r * 255), int(g * 255), int(b * 255))

    def handle_event(self, ev):
        pr  = self._pr()
        svr = pygame.Rect(pr.x + 10,             pr.y + 50, self.SIZE, self.SIZE)
        hr  = pygame.Rect(pr.x + self.SIZE + 20, pr.y + 50, 20,        self.SIZE)
        fy  = pr.y + pr.h - 44
        ok  = pygame.Rect(pr.x + pr.w - 110, fy, 90, 30)
        ca  = pygame.Rect(pr.x + pr.w - 210, fy, 90, 30)

        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.done = True

        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if ok.collidepoint(ev.pos):
                self.result = self.rgb
                self.done   = True
            elif ca.collidepoint(ev.pos):
                self.done = True
            elif svr.collidepoint(ev.pos):
                self._drag = "sv"
                self._usv(ev.pos, svr)
            elif hr.collidepoint(ev.pos):
                self._drag = "hue"
                self._uh(ev.pos, hr)

        elif ev.type == pygame.MOUSEBUTTONUP:
            self._drag = None

        elif ev.type == pygame.MOUSEMOTION and self._drag:
            # Recalculate rects in case window was resized
            pr2  = self._pr()
            svr2 = pygame.Rect(pr2.x + 10,              pr2.y + 50, self.SIZE, self.SIZE)
            hr2  = pygame.Rect(pr2.x + self.SIZE + 20,  pr2.y + 50, 20,        self.SIZE)
            if self._drag == "sv":
                self._usv(ev.pos, svr2)
            else:
                self._uh(ev.pos, hr2)

    def _usv(self, pos, svr):
        """Update saturation and value from a mouse position inside the SV square."""
        self.s = max(0, min(1, (pos[0] - svr.x) / svr.w))
        self.v = max(0, min(1, 1 - (pos[1] - svr.y) / svr.h))

    def _uh(self, pos, hr):
        """Update hue from a mouse position inside the hue strip."""
        old    = self.h
        self.h = max(0, min(1, (pos[1] - hr.y) / hr.h))
        if abs(self.h - old) > 0.001:
            self._rebuild_sv()

    def draw(self):
        """Render the colour picker overlay onto self.screen."""
        ov = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        self.screen.blit(ov, (0, 0))

        pr  = self._pr()
        svr = pygame.Rect(pr.x + 10,             pr.y + 50, self.SIZE, self.SIZE)
        hr  = pygame.Rect(pr.x + self.SIZE + 20, pr.y + 50, 20,        self.SIZE)
        mp  = pygame.mouse.get_pos()

        # Panel background and border
        rrect(self.screen, C_BRBG, pr, 10)
        pygame.draw.rect(self.screen, C_ACCENT, pr, 2, border_radius=10)
        txt(self.screen, "Background Color", self.F["sm"], C_ACCENT, pr.x + 10, pr.y + 14)

        # SV square and crosshair cursor
        self.screen.blit(self._sv, svr.topleft)
        cx = svr.x + int(self.s * svr.w)
        cy = svr.y + int((1 - self.v) * svr.h)
        pygame.draw.circle(self.screen, C_BG, (cx, cy), 7, 2)
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), 5, 1)

        # Hue strip and marker
        self.screen.blit(self._hue, hr.topleft)
        hy = hr.y + int(self.h * hr.h)
        pygame.draw.rect(self.screen, C_BG,         (hr.x - 3, hy - 3, 26, 6), border_radius=2)
        pygame.draw.rect(self.screen, (255, 255, 255), (hr.x - 2, hy - 2, 24, 4), border_radius=2)

        # Colour preview swatch + hex value
        fy = pr.y + pr.h - 44
        sw = pygame.Rect(pr.x + 10, fy, 60, 30)
        pygame.draw.rect(self.screen, self.rgb, sw, border_radius=4)
        pygame.draw.rect(self.screen, C_TEXT, sw, 1, border_radius=4)
        r, g, b = self.rgb
        txt(self.screen, f"#{r:02X}{g:02X}{b:02X}", self.F["xs"], C_DIM, sw.right + 8, sw.y + 8)

        # Apply and Cancel buttons
        ok = pygame.Rect(pr.x + pr.w - 110, fy, 90, 30)
        ca = pygame.Rect(pr.x + pr.w - 210, fy, 90, 30)

        rrect(self.screen, C_ACCENT2 if ok.collidepoint(mp) else C_BTN, ok)
        txt(self.screen, "Apply",  self.F["sm"], C_TEXT, ok.centerx, ok.y + 7, align="center")

        rrect(self.screen, C_BTNHOV if ca.collidepoint(mp) else C_BTN, ca)
        txt(self.screen, "Cancel", self.F["sm"], C_TEXT, ca.centerx, ca.y + 7, align="center")


def pick_color(screen, fonts, clock, initial=(40, 40, 60)):
    """
    Blocking helper: open a ColorPicker and run its mini event loop.
    Returns (r,g,b) if confirmed, or None if cancelled.
    """
    cp = ColorPicker(screen, fonts, initial)
    while not cp.done:
        clock.tick(60)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            cp.handle_event(ev)
        cp.draw()
        pygame.display.flip()
    return cp.result

