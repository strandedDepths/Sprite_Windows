"""
daynight.py
===========
Procedural animated sky/sea background that cycles over DAY_MS milliseconds.

Timeline (t = 0 → 1):
    0.00–0.25  Midday   (bright sky, calm sea)
    0.25–0.55  Sunset   (orange sky, golden sea)
    0.55–0.65  Dusk     (rapid transition to night)
    0.65–0.82  Night    (dark blue, stars, purple sea)
    0.82–1.00  Dawn     (violet → back to noon)

Public API used by editor.py and main.py:
    DayNight(W, H)
    .update(dt_ms)
    .draw(surf)        → returns brightness float (0–1)
    .brightness()      → float (0=night, 1=day)
    .tint_color()      → (r,g,b) dominant light colour
"""

import random
import pygame
from utils import blend_col, brighten_col
from constants import (
    SKY_NOON, SKY_ORANGE, SKY_NIGHT,
    SEA_DAY, SEA_SUNSET, SEA_NIGHT,
    DAY_MS,
)

class DayNight:
    """
    Procedural sky/sea background that cycles over DAY_MS milliseconds.

    Timeline (t = 0 → 1 over DAY_MS):
        0.00 – 0.25  Midday   (bright sky, calm sea)
        0.25 – 0.55  Sunset   (orange sky, golden sea)
        0.55 – 0.65  Dusk     (rapid transition to night)
        0.65 – 0.82  Night    (dark blue sky, stars, purple sea)
        0.82 – 1.00  Dawn     (violet → back to noon)

    Provides:
        draw(surf)      → renders sky + stars + sea, returns brightness (0–1)
        brightness()    → float 0–1 (1=full day, 0=full night)
        tint_color()    → (r,g,b) representing the dominant light colour
    """

    NUM_STARS = 150   # total pre-generated stars
    MAX_WAVES = 20    # maximum simultaneous wave lines on the sea
    SEA_RATIO = 0.25  # fraction of canvas height occupied by the sea

    def __init__(self, W, H):
        self._ms    = 0       # elapsed milliseconds within the current cycle
        self.t      = 0.0     # normalised cycle position [0, 1)
        self.W      = W
        self.H      = H

        # Pre-generate randomised star positions and sizes
        self._stars = [
            {
                "xn":   random.random(),          # normalised X position
                "yn":   random.random() * 0.5,    # upper half of the sky only
                "r":    random.randint(1, 3),      # radius in pixels
                "glow": random.uniform(0.5, 1.0), # brightness multiplier
            }
            for _ in range(self.NUM_STARS)
        ]

        # Active wave lines on the sea surface
        self._waves = []

    def resize(self, W, H):
        """Update internal dimensions when the window is resized."""
        self.W = W
        self.H = H

    def update(self, dt_ms):
        """
        Advance the cycle by dt_ms milliseconds.
        Also spawns and moves sea waves.
        """
        self._ms = (self._ms + dt_ms) % DAY_MS
        self.t   = self._ms / DAY_MS

        # Occasionally spawn a new wave entering from the right edge
        if len(self._waves) < self.MAX_WAVES and random.random() < 0.2:
            self._waves.append({
                "x":   self.W,                          # start at right edge
                "yn":  random.random() * 0.5,           # vertical position (normalised)
                "spd": random.uniform(0.05, 1.0),       # horizontal speed (px/frame)
                "ln":  random.uniform(0.05, 0.15),      # wave length (fraction of W)
            })

        # Move waves left and remove those that have scrolled off screen
        for w in self._waves[:]:
            w["x"] -= w["spd"]
            if w["x"] + w["ln"] * self.W < 0:
                self._waves.remove(w)

    # ── Private colour helpers ──────────────────────────────────────────────

    def _sky(self):
        """Return the current sky background colour."""
        t = self.t
        if t < 0.28: return blend_col(SKY_NOON,   SKY_ORANGE, t / 0.28)
        if t < 0.58: return blend_col(SKY_ORANGE,  SKY_NIGHT,  (t - 0.28) / 0.30)
        if t < 0.85: return SKY_NIGHT
        return blend_col(SKY_NIGHT, SKY_NOON, (t - 0.85) / 0.15)

    def _sea(self):
        """Return the current sea fill colour."""
        t = self.t
        if t < 0.28: return blend_col(SEA_DAY,    SEA_SUNSET, t / 0.28)
        if t < 0.58: return blend_col(SEA_SUNSET,  SEA_NIGHT,  (t - 0.28) / 0.30)
        if t < 0.85: return SEA_NIGHT
        return blend_col(SEA_NIGHT, SEA_DAY, (t - 0.85) / 0.15)

    # ── Public accessors ────────────────────────────────────────────────────

    def brightness(self):
        """
        Return overall scene brightness as a float in [0, 1].
        Used to dim sprites that have the 'dn_affected' flag set.
        """
        t = self.t
        if t < 0.4: return 1.0
        if t < 0.6: return 1.0 - (t - 0.4) / 0.2
        if t < 0.8: return 0.0
        return (t - 0.8) / 0.2

    def tint_color(self):
        """
        Return (r,g,b) representing the dominant light colour at this time.
        Used by tint_surface() to colour-shift sprites as the cycle progresses.

        Colour stops:
            Noon   (255, 240, 180)  warm golden daylight
            Sunset (255,  80,  10)  deep saturated orange
            Night  ( 20,  30, 180)  cold deep blue
            Dawn   (160,  80, 255)  violet pre-sunrise
        """
        t      = self.t
        NOON   = (255, 240, 180)
        SUNSET = (255,  80,  10)
        NIGHT  = ( 20,  30, 180)
        DAWN   = (160,  80, 255)

        if t < 0.25: return NOON
        if t < 0.50: return blend_col(NOON,   SUNSET, (t - 0.25) / 0.25)
        if t < 0.60: return blend_col(SUNSET, NIGHT,  (t - 0.50) / 0.10)
        if t < 0.82: return NIGHT
        if t < 0.92: return blend_col(NIGHT,  DAWN,   (t - 0.82) / 0.10)
        return             blend_col(DAWN,   NOON,   (t - 0.92) / 0.08)

    def star_opacity(self):
        """Return star opacity [0, 1] — stars appear during night and fade at dawn."""
        t = self.t
        if 0.5 <= t <= 0.8: return (t - 0.5) / 0.3
        if t > 0.8:         return max(0.0, 1.0 - (t - 0.8) / 0.2)
        return 0.0

    def draw(self, surf):
        """
        Render sky, stars, and sea onto surf.
        Returns the current brightness value so callers can dim sprites.
        """
        W, H = surf.get_size()

        # Fill with the current sky colour
        surf.fill(self._sky())

        # Draw stars with opacity proportional to night depth
        op = self.star_opacity()
        if op > 0:
            for s in self._stars:
                br = int(255 * op * s["glow"])
                pygame.draw.circle(
                    surf, (br, br, br),
                    (int(s["xn"] * W), int(s["yn"] * H)),
                    s["r"]
                )

        # Draw the sea strip at the bottom of the surface
        sc  = self._sea()
        wc  = brighten_col(sc)        # brighter wave-crest colour
        sh  = int(H * self.SEA_RATIO) # sea strip height
        sy  = H - H // 4 - sh         # sea strip top Y
        sea = pygame.Surface((W, sh))
        sea.fill(sc)

        for w in self._waves:
            wx = int(w["x"])
            wy = int(w["yn"] * sh)
            ww = int(w["ln"] * W)
            pygame.draw.line(sea, wc, (wx, wy), (wx + ww, wy), 2)

        surf.blit(sea, (0, sy))
        return self.brightness()

