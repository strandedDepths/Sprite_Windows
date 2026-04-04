"""
utils.py
========
Stateless helper functions used throughout the application:
    - Drawing shortcuts (rrect, txt)
    - Colour math (blend_col, brighten_col)
    - Pixel-level surface effects (dim_surface, tint_surface)
    - Folder / path helpers (ensure_save_dir)
    - Blocking confirmation dialog (confirm_dialog)
"""

import sys
import pygame
from constants import (
    SAVE_DIR, C_BG, C_BTN, C_BTNHOV, C_ACCENT, C_ACCENT2,
    C_BRBG, C_DANGER, C_TEXT
)


# ─────────────────────────────────────────────────────────────────────────────
# File-system helpers
# ─────────────────────────────────────────────────────────────────────────────

def ensure_save_dir():
    """Create the scenes/ folder next to the script if it does not exist."""
    import os
    import os.path
    os.makedirs(SAVE_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Drawing shortcuts
# ─────────────────────────────────────────────────────────────────────────────

def rrect(surf, color, rect, r=6):
    """Draw a filled rounded rectangle."""
    pygame.draw.rect(surf, color, rect, border_radius=r)


def txt(surf, text, font, color, x, y, align="left"):
    """
    Render a string onto surf.
    align: "left" (default) | "center" | "right"
    """
    img = font.render(str(text), True, color)
    if align == "center":
        x -= img.get_width() // 2
    elif align == "right":
        x -= img.get_width()
    surf.blit(img, (x, y))


# ─────────────────────────────────────────────────────────────────────────────
# Colour math
# ─────────────────────────────────────────────────────────────────────────────

def blend_col(c1, c2, t):
    """Linear interpolation between two RGB colours. t=0 → c1, t=1 → c2."""
    return tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))


def brighten_col(c, f=1.3):
    """Return a brighter version of colour c by multiplying each channel by f."""
    return tuple(min(int(v * f), 255) for v in c)


# ─────────────────────────────────────────────────────────────────────────────
# Surface pixel effects
# ─────────────────────────────────────────────────────────────────────────────

def dim_surface(surf, factor):
    """
    Return a copy of surf with all RGB channels multiplied by factor (0–1).
    Used to simulate night-time darkness on scene items.
    """
    out = surf.copy()
    arr = pygame.surfarray.pixels3d(out)
    arr[:] = (arr * max(0.0, min(1.0, factor))).astype("uint8")
    del arr
    return out


def tint_surface(surf, tint_rgb, strength=0.72):
    """
    Multiply-blend surf toward tint_rgb to simulate coloured lighting.

    Each channel multiplier is lerped from 1.0 (identity) toward the
    normalised tint value:
        new_r = old_r * lerp(1.0, tint_r/255, strength)

    strength=0    no visible change
    strength=0.72 strong, clearly visible tint (default)
    strength=1.0  full multiply

    Uses pygame.surfarray only — no numpy import required.
    """
    out = surf.copy()
    arr = pygame.surfarray.pixels3d(out)

    tr = tint_rgb[0] / 255.0
    tg = tint_rgb[1] / 255.0
    tb = tint_rgb[2] / 255.0

    mr = 1.0 * (1 - strength) + tr * strength
    mg = 1.0 * (1 - strength) + tg * strength
    mb = 1.0 * (1 - strength) + tb * strength

    arr[:, :, 0] = (arr[:, :, 0] * mr).clip(0, 255).astype("uint8")
    arr[:, :, 1] = (arr[:, :, 1] * mg).clip(0, 255).astype("uint8")
    arr[:, :, 2] = (arr[:, :, 2] * mb).clip(0, 255).astype("uint8")
    del arr
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Confirmation dialog
# ─────────────────────────────────────────────────────────────────────────────

def confirm_dialog(screen, fonts, clock, message="Are you sure?",
                   yes_label="Yes", no_label="No"):
    """
    Show a modal yes/no dialog drawn entirely inside the pygame window.
    Blocks until the user clicks a button or presses Enter/Escape.
    Returns True (yes) or False (no).
    """
    fsm    = fonts["sm"]
    fmd    = fonts["md"]
    result = [None]

    while result[0] is None:
        clock.tick(60)
        W, H = screen.get_size()

        bw, bh = 360, 150
        bx, by = (W - bw) // 2, (H - bh) // 2
        br     = pygame.Rect(bx, by, bw, bh)

        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 170))
        screen.blit(ov, (0, 0))

        rrect(screen, C_BRBG, br, 10)
        pygame.draw.rect(screen, C_ACCENT, br, 2, border_radius=10)

        msg_surf = fmd.render(message, True, C_TEXT)
        screen.blit(msg_surf, msg_surf.get_rect(centerx=br.centerx, top=br.y + 24))

        btn_w, btn_h = 110, 34
        yes_r = pygame.Rect(br.centerx - btn_w - 10, br.y + bh - btn_h - 18, btn_w, btn_h)
        no_r  = pygame.Rect(br.centerx + 10,         br.y + bh - btn_h - 18, btn_w, btn_h)
        mp    = pygame.mouse.get_pos()

        rrect(screen, C_DANGER  if yes_r.collidepoint(mp) else C_BTN, yes_r)
        rrect(screen, C_ACCENT2 if no_r.collidepoint(mp)  else C_BTN, no_r)
        txt(screen, yes_label, fsm, C_TEXT, yes_r.centerx, yes_r.y + 8, align="center")
        txt(screen, no_label,  fsm, C_TEXT, no_r.centerx,  no_r.y + 8,  align="center")

        pygame.display.flip()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_RETURN:   result[0] = True
                elif ev.key == pygame.K_ESCAPE: result[0] = False
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if yes_r.collidepoint(ev.pos):  result[0] = True
                elif no_r.collidepoint(ev.pos): result[0] = False

    return result[0]
