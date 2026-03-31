import pygame
import sys
import os

pygame.init()

# --- Window settings ---
WIDTH, HEIGHT = 480, 360
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("DK Mini Template")
clock = pygame.time.Clock()

# --- Paths (use placeholders for users to add their own) ---
BASE_DIR = os.path.dirname(__file__)
BG_PATH = os.path.join(BASE_DIR, "assets", "background", "placeholder.txt")
SPRITES_DIR = os.path.join(BASE_DIR, "assets", "sprites")
MUSIC_DIR = os.path.join(BASE_DIR, "assets", "music")

# --- Colors ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# --- Placeholder load functions ---
def load_background():
    # Replace this with user image loading
    bg_surface = pygame.Surface((WIDTH, HEIGHT))
    bg_surface.fill(WHITE)
    return bg_surface

def load_sprites():
    # Replace with user sprite frames
    return []

# --- Main loop ---
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # --- Draw ---
    screen.fill(BLACK)  # default background
    bg = load_background()
    screen.blit(bg, (0, 0))

    # TODO: draw sprites, sea, ground, waves here

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()