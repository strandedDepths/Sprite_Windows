"""
playlist.py
===========
Random-shuffle playback of a folder of audio tracks.

Fix: play(0) plays each track once; get_busy() detects end-of-track and
advances to the next random track. The old play(-1) looped the same track
forever and never advanced the playlist.
"""

import os
import random
import pygame


class Playlist:
    """
    Plays tracks from a folder in random order, never repeating
    the same track twice in a row (when 2+ tracks are available).

    Call update() once per frame — it detects track end via get_busy()
    and picks the next random track automatically.
    """

    def __init__(self):
        self.tracks       = []    # absolute paths of all tracks
        self.intro        = None  # optional one-shot intro track
        self.current_idx  = -1
        self._playing     = False # True only when we own the mixer
        self.current_path = ""

    def load_folder(self, folder, intro_name=None):
        """Scan folder for .mp3/.ogg/.wav files and build the track list."""
        exts  = (".mp3", ".ogg", ".wav")
        files = sorted(f for f in os.listdir(folder) if f.lower().endswith(exts))
        self.tracks = [os.path.join(folder, f) for f in files]
        self.intro  = None
        if intro_name:
            full = os.path.join(folder, intro_name)
            if full in self.tracks:
                self.intro = full
                self.tracks.remove(full)
        self.current_idx = -1
        self._playing    = False

    def play_intro(self):
        """Play the intro track once; shuffle starts automatically after."""
        if self.intro and os.path.exists(self.intro):
            self._play_once(self.intro)

    def play_random(self):
        """Pick a random track (different from current) and start it."""
        if not self.tracks:
            return
        if len(self.tracks) > 1:
            choices = [i for i in range(len(self.tracks)) if i != self.current_idx]
            self.current_idx = random.choice(choices)
        else:
            self.current_idx = 0
        self._play_once(self.tracks[self.current_idx])

    def next_track(self):
        """Skip to the next random track immediately."""
        self.play_random()

    def _play_once(self, path):
        """Load and play path once (no loop). update() advances when done."""
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(0)  # 0 = play once, do NOT loop
            self.current_path = path
            self._playing     = True
        except Exception as e:
            print(f"Playlist error: {e}")

    def update(self):
        """
        Call once per frame. Picks the next random track when the current
        one ends. Uses get_busy() — reliable across all pygame versions.
        """
        if self._playing and not pygame.mixer.music.get_busy():
            self.play_random()

    def stop(self):
        """Stop playback."""
        pygame.mixer.music.stop()
        self._playing = False

    def single_track(self, path):
        """Loop a single file forever (fallback for scenes with one music file)."""
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(-1)
            self.current_path = path
            self.tracks       = [path]
            self._playing     = True
        except Exception as e:
            print(f"Playlist error: {e}")

    @property
    def current_name(self):
        return os.path.basename(self.current_path) if self.current_path else "None"
