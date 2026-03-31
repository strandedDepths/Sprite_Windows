import pygame
import sys
import os
import random

# ------------------------
# --- Pygame Initialization
# ------------------------
pygame.init()
pygame.mixer.init()  # for music

# ------------------------
# --- Window Settings
# ------------------------
WIDTH, HEIGHT = 480, 360
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
screen_x = -WIDTH
screen_y = 0
os.environ['SDL_VIDEO_WINDOW_POS'] = f"{screen_x},{screen_y}"

screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Mini App Template")
clock = pygame.time.Clock()

# ------------------------
# --- Assets Section (EDIT HERE)
# ------------------------
BASE_DIR = os.path.dirname(__file__)
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

BG_PATH = os.path.join(ASSETS_DIR, "background", "bg.png")
GROUND_PATH = os.path.join(ASSETS_DIR, "background", "ground.png")
SPRITES_DIR = os.path.join(ASSETS_DIR, "sprites")
MUSIC_DIR = os.path.join(ASSETS_DIR, "music")
INTRO_TRACK = None  # optional intro track filename, e.g., "intro.mp3"

# ------------------------
# --- Utility Functions
# ------------------------
def brighten_color(color, factor=1.3):
    """Brighten RGB color by factor."""
    return tuple(min(int(c * factor), 255) for c in color)

def blend_colors(c1, c2, factor):
    """Linear interpolation between two RGB colors."""
    return tuple(int(c1[i] * (1 - factor) + c2[i] * factor) for i in range(3))

# ========================
# --- Music Manager Class
# ========================
class MusicManager:
    def __init__(self, music_dir, intro_track=None):
        self.music_dir = music_dir
        self.intro_track = intro_track
        self.loop_tracks = []

        if intro_track:
            self.intro_path = os.path.join(music_dir, intro_track)
        else:
            self.intro_path = None

        # Collect all mp3s except intro
        self.loop_tracks = [
            os.path.join(music_dir, f)
            for f in os.listdir(music_dir)
            if f.endswith(".mp3") and f != intro_track
        ]
        self.current_track = None
        self.looping = False

        # Play intro first
        if self.intro_path and os.path.exists(self.intro_path):
            pygame.mixer.music.load(self.intro_path)
            pygame.mixer.music.play()
        else:
            self.play_random_loop()

    def play_random_loop(self):
        if not self.loop_tracks:
            return
        self.current_track = random.choice(self.loop_tracks)
        pygame.mixer.music.load(self.current_track)
        pygame.mixer.music.play(-1)
        self.looping = True

    def update(self):
        if not pygame.mixer.music.get_busy() and not self.looping:
            self.play_random_loop()

# ========================
# --- Character Class
# ========================
class Character:
    def __init__(self, sprites_dir, base_height=64):
        self.frames = []
        self.current_frame = 0
        self.last_update = pygame.time.get_ticks()
        self.direction = 1
        self.animation_speed = 250  # ms per frame
        self.base_height = base_height

        # Load all PNGs in the folder
        files = sorted([f for f in os.listdir(sprites_dir) if f.endswith(".png")])
        if not files:
            print(f"Warning: No sprite PNGs found in {sprites_dir}")
        for f in files:
            path = os.path.join(sprites_dir, f)
            try:
                frame = pygame.image.load(path).convert_alpha()
                self.frames.append(frame)
            except:
                print(f"Warning: Could not load sprite {f}")

        if not self.frames:
            print("Warning: No frames loaded, adding placeholder")
            self.frames.append(pygame.Surface((base_height, base_height), pygame.SRCALPHA))

    def update_frame(self):
        now = pygame.time.get_ticks()
        if now - self.last_update > self.animation_speed:
            self.last_update = now
            self.current_frame += self.direction
            if self.current_frame >= len(self.frames) - 1:
                self.direction = -1
            elif self.current_frame <= 0:
                self.direction = 1

    def get_scaled_image(self, height_scale=1.0, brightness=1.0):
        frame = self.frames[self.current_frame].copy()
        h_orig = frame.get_height()
        w_orig = frame.get_width()
        new_height = int(h_orig * height_scale)
        new_width = int(w_orig * new_height / h_orig)
        img = pygame.transform.scale(frame, (new_width, new_height))

        # Apply brightness
        arr = pygame.surfarray.pixels3d(img)
        arr[:] = (arr * brightness).astype('uint8')
        del arr
        return img

# ========================
# --- Star Field Class
# ========================
class StarField:
    def __init__(self, num_stars=150):
        self.stars = []
        for _ in range(num_stars):
            self.stars.append({
                'x_norm': random.random(),
                'y_norm': random.random() * 0.5,
                'size': random.randint(1,3),
                'glow_factor': random.uniform(0.5,1.0)
            })

    def draw(self, surface, opacity):
        if opacity <= 0:
            return
        width, height = surface.get_size()
        for star in self.stars:
            x = int(star['x_norm'] * width)
            y = int(star['y_norm'] * height)
            brightness = int(255 * opacity * star['glow_factor'])
            color = (brightness, brightness, brightness)
            pygame.draw.circle(surface, color, (x,y), star['size'])

# ========================
# --- Sea & Wave Class
# ========================
class Sea:
    def __init__(self, height_ratio=0.25, max_waves=20):
        self.height_ratio = height_ratio
        self.max_waves = max_waves
        self.waves = []

    def update_waves(self, width, height):
        SEA_HEIGHT = int(height * self.height_ratio)
        # Spawn waves
        if len(self.waves) < self.max_waves and random.random() < 0.2:
            self.waves.append({
                'x': width,
                'y_norm': random.random() * 0.5,
                'speed': random.uniform(0.05, 1.0),
                'length_norm': random.uniform(0.05, 0.15)
            })
        # Update waves
        for wave in self.waves[:]:
            wave['x'] -= wave['speed']
            if wave['x'] + wave['length_norm']*width < 0:
                self.waves.remove(wave)

    def draw(self, surface, sea_color, wave_color):
        SEA_HEIGHT = surface.get_height()
        width = surface.get_width()
        surface.fill(sea_color)
        for wave in self.waves:
            wave_width = int(wave['length_norm'] * width)
            wave_y = int(wave['y_norm'] * SEA_HEIGHT)
            pygame.draw.line(surface, wave_color,
                             (int(wave['x']), wave_y),
                             (int(wave['x']+wave_width), wave_y),2)

# ========================
# --- Main Game Class
# ========================
class Game:
    def __init__(self):
        # Background
        try:
            self.bg_img = pygame.image.load(BG_PATH).convert_alpha()
        except:
            self.bg_img = None
            print("Warning: Background missing")

        # Ground
        try:
            self.ground_img = pygame.image.load(GROUND_PATH).convert_alpha()
        except:
            self.ground_img = None
            print("Warning: Ground missing")

        # Character
        self.character = Character(SPRITES_DIR)

        # Stars
        self.stars = StarField()

        # Sea
        self.sea = Sea()

        # Music
        self.music_manager = MusicManager(MUSIC_DIR, intro_track=INTRO_TRACK)

        # Day/Night Colors
        self.NOON_COLOR = (135,206,250)
        self.ORANGE_COLOR = (255,140,0)
        self.NIGHT_COLOR = (30,30,80)
        self.SEA_COLOR = (0,105,148)
        self.SUNSET_SEA_COLOR = (255,200,0)
        self.NIGHT_SEA_COLOR = (100,50,150)

        self.day_duration = 60_000
        self.start_time = pygame.time.get_ticks()

        # Ground offset
        self.ground_offset = 60

    def compute_time_factor(self):
        elapsed = (pygame.time.get_ticks() - self.start_time) % self.day_duration
        return elapsed / self.day_duration

    def get_sky_color(self, t):
        if t < 0.28:
            factor = t / 0.28
            return blend_colors(self.NOON_COLOR, self.ORANGE_COLOR, factor)
        elif t < 0.58:
            factor = (t-0.28)/0.30
            return blend_colors(self.ORANGE_COLOR, self.NIGHT_COLOR, factor)
        elif t < 0.85:
            return self.NIGHT_COLOR
        else:
            factor = (t-0.85)/0.15
            return blend_colors(self.NIGHT_COLOR, self.NOON_COLOR, factor)

    def get_sea_color(self, t):
        if t < 0.28:
            factor = t / 0.28
            return blend_colors(self.SEA_COLOR, self.SUNSET_SEA_COLOR, factor)
        elif t < 0.58:
            factor = (t-0.28)/0.30
            return blend_colors(self.SUNSET_SEA_COLOR, self.NIGHT_SEA_COLOR, factor)
        elif t < 0.85:
            return self.NIGHT_SEA_COLOR
        else:
            factor = (t-0.85)/0.15
            return blend_colors(self.NIGHT_SEA_COLOR, self.SEA_COLOR, factor)

    def run(self):
        # --- Buttons ---
        button_font = pygame.font.SysFont(None, 20)
        BUTTON_WIDTH, BUTTON_HEIGHT = 80, 25
        skip_button = pygame.Rect(10, 10, BUTTON_WIDTH, BUTTON_HEIGHT)
        next_button = pygame.Rect(100, 10, BUTTON_WIDTH, BUTTON_HEIGHT)
        BUTTON_COLOR = (50,50,50)
        BUTTON_HOVER_COLOR = (100,100,100)
        BUTTON_TEXT_COLOR = (255,255,255)

        running = True
        while running:
            for event in pygame.event.get():
                if event.type==pygame.QUIT:
                    running=False
                elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                    mx,my = event.pos
                    if skip_button.collidepoint(mx,my):
                        if self.music_manager.loop_tracks:
                            self.music_manager.current_track = random.choice(self.music_manager.loop_tracks)
                            pygame.mixer.music.load(self.music_manager.current_track)
                            pygame.mixer.music.play(-1)
                            self.music_manager.looping = True
                    elif next_button.collidepoint(mx,my):
                        if self.music_manager.loop_tracks:
                            self.music_manager.current_track = random.choice(self.music_manager.loop_tracks)
                            pygame.mixer.music.load(self.music_manager.current_track)
                            pygame.mixer.music.play(-1)
                            self.music_manager.looping = True

            WIDTH, HEIGHT = screen.get_size()
            t = self.compute_time_factor()

            # --- Music Update ---
            self.music_manager.update()

            # --- Draw Sky ---
            sky_color = self.get_sky_color(t)
            screen.fill(sky_color)

            # --- Stars ---
            if t>=0.5 and t<=0.8:
                star_opacity = (t-0.5)/0.3
            elif t>0.8:
                star_opacity = max(0, 1.0 - (t-0.8)/0.2)
            else:
                star_opacity = 0
            self.stars.draw(screen, star_opacity)

            # --- Sea ---
            SEA_HEIGHT = int(HEIGHT * self.sea.height_ratio)
            SEA_Y = HEIGHT - SEA_HEIGHT - self.ground_offset
            sea_surface = pygame.Surface((WIDTH, SEA_HEIGHT))
            sea_color = self.get_sea_color(t)
            wave_color = brighten_color(sea_color)
            self.sea.update_waves(WIDTH, HEIGHT)
            self.sea.draw(sea_surface, sea_color, wave_color)
            screen.blit(sea_surface, (0, SEA_Y))

            # --- Background ---
            if self.bg_img:
                bg_scaled = pygame.transform.scale(self.bg_img, (WIDTH, HEIGHT))
                screen.blit(bg_scaled, (0,0))

            # --- Ground ---
            if self.ground_img:
                ground_scaled = pygame.transform.scale(self.ground_img, (WIDTH, self.ground_img.get_height()))
                screen.blit(ground_scaled, (0, HEIGHT - ground_scaled.get_height() + self.ground_offset))

            # --- Character ---
            self.character.update_frame()
            char_img = self.character.get_scaled_image(height_scale=HEIGHT/360*2, brightness=1.0)
            sprite_x = WIDTH//2 - char_img.get_width()//2
            sprite_y = HEIGHT - self.ground_offset - char_img.get_height()
            screen.blit(char_img, (sprite_x, sprite_y))

            # --- Buttons ---
            mx,my = pygame.mouse.get_pos()
            skip_color = BUTTON_HOVER_COLOR if skip_button.collidepoint(mx,my) else BUTTON_COLOR
            next_color = BUTTON_HOVER_COLOR if next_button.collidepoint(mx,my) else BUTTON_COLOR
            pygame.draw.rect(screen, skip_color, skip_button)
            pygame.draw.rect(screen, next_color, next_button)
            screen.blit(button_font.render("Skip Intro", True, BUTTON_TEXT_COLOR), (skip_button.x+5, skip_button.y+5))
            screen.blit(button_font.render("Next Track", True, BUTTON_TEXT_COLOR), (next_button.x+5, next_button.y+5))

            # --- Now Playing ---
            track_name = os.path.basename(self.music_manager.current_track) if self.music_manager.current_track else "None"
            screen.blit(button_font.render(f"Now Playing: {track_name}", True, (255,255,255)), (10, HEIGHT-20))

            pygame.display.flip()
            clock.tick(60)

        pygame.quit()
        sys.exit()

# ========================
# --- Run Game
# ========================
if __name__ == "__main__":
    Game().run()