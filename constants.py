"""
constants.py
============
All global constants: UI dimensions, colour palette, day/night colour stops.
Import with:  from constants import *
"""

import os

# ── Frame rate and window layout ─────────────────────────────────────────────
FPS     = 60          # editor target frame rate
PANEL_W = 210         # right-side panel width in pixels
TOOL_H  = 48          # top toolbar height in pixels

# ── UI colour palette (dark-navy retro theme) ─────────────────────────────
C_BG       = (18,  18,  28)   # window background
C_PANEL    = (28,  28,  44)   # right panel background
C_TOOLBAR  = (22,  22,  36)   # top toolbar strip
C_ACCENT   = (255, 180,  30)  # golden yellow — primary highlight
C_ACCENT2  = ( 80, 200, 120)  # green — positive actions
C_DANGER   = (220,  60,  60)  # red — destructive actions
C_TEXT     = (230, 230, 240)  # default text
C_DIM      = (120, 120, 150)  # muted / secondary text
C_CANVAS   = ( 40,  40,  60)  # default canvas fill colour
C_SEL      = (255, 180,  30)  # selection outline (single)
C_GRID     = ( 50,  50,  72)  # canvas grid lines
C_BTN      = ( 45,  45,  70)  # idle button
C_BTNHOV   = ( 65,  65, 100)  # hovered button
C_BG_BTN   = C_BG              # alias used inside widgets
C_BRBG     = ( 15,  15,  25)  # file-browser / overlay background
C_BRROW    = ( 30,  30,  48)  # file-browser list background
C_BRHOV    = ( 50,  50,  80)  # file-browser hovered row
C_BRSEL    = ( 70,  55,  20)  # file-browser selected row
C_BRDIR    = (120, 180, 255)  # file-browser directory colour
C_BRFILE   = (200, 200, 220)  # file-browser file colour
C_MULTISEL = (100, 200, 255)  # selection outline (multi-select)

# ── Resize handle ─────────────────────────────────────────────────────────
HANDLE_SIZE = 8   # half-width of a corner resize handle (pixels)

# Corner identifiers used by ResizeState
TL, TR, BL, BR = "tl", "tr", "bl", "br"

# ── File paths ───────────────────────────────────────────────────────────────
# Scenes are saved in a subfolder next to the entry-point script.
# main.py sets this at startup; the default here is a fallback.
SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenes")

# ── Day / Night sky and sea colour stops ─────────────────────────────────────
SKY_NOON   = (135, 206, 250)  # light blue midday sky
SKY_ORANGE = (255, 140,   0)  # sunset orange
SKY_NIGHT  = ( 30,  30,  80)  # deep night blue
SEA_DAY    = (  0, 105, 148)  # daytime sea
SEA_SUNSET = (255, 200,   0)  # glowing sunset sea
SEA_NIGHT  = (100,  50, 150)  # night sea

# Duration of one full day/night cycle in milliseconds (5 minutes)
DAY_MS = 300_000
