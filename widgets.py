"""
widgets.py
==========
Reusable UI widgets.

Button
    A clickable rectangle with label, idle/hover colours, and an ._action
    callback assigned externally after construction.
    Call .update(mp) each frame and .clicked(ev) to detect presses.
"""

import pygame
from constants import C_BTN, C_BTNHOV, C_TEXT
from utils import rrect

class Button:
    """
    Simple clickable button used in the toolbar and panel.
    The ._action callback is set externally after construction.
    """

    def __init__(self, rect, label, color=None, tc=None, font=None, r=6):
        self.rect  = pygame.Rect(rect)
        self.label = label
        self.color = color or C_BTN    # idle background colour
        self.hc    = C_BTNHOV          # hover background colour
        self.tc    = tc or C_TEXT      # text colour
        self.font  = font
        self.r     = r                 # corner radius
        self.hov   = False
        self._action = lambda: None

    def draw(self, surf):
        rrect(surf, self.hc if self.hov else self.color, self.rect, self.r)
        if self.font:
            lbl = self.font.render(self.label, True, self.tc)
            surf.blit(lbl, lbl.get_rect(center=self.rect.center))

    def update(self, mp):
        """Call each frame with the current mouse position to update hover state."""
        self.hov = self.rect.collidepoint(mp)

    def clicked(self, ev):
        """Return True if ev is a left-click inside this button."""
        return (ev.type == pygame.MOUSEBUTTONDOWN
                and ev.button == 1
                and self.rect.collidepoint(ev.pos))


