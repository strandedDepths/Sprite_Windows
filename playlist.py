"""
playlist.py
===========
Wraps pygame.mixer.music to manage a folder of audio tracks.

Usage:
    pl = Playlist()
    pl.load_folder("/path/to/music/")   # scan for .mp3/.ogg/.wav
    pl.play_random()                    # start a random looping track
    pl.update()                         # call once per frame
    pl.stop()
"""

import os
import random
import pygame

class Playlist:
    """
    Wraps pygame.mixer.music to manage a folder of audio tracks.

    Supports:
        load_folder(folder)   Scan a directory for .mp3/.ogg/.wav files
        play_random()         Pick and loop a random track
        next_track()          Advance to the next track
        update()              Call once per frame — auto-advances when a
                              non-looping intro finishes
        stop()                Stop playback cleanly
        single_track(path)    Convenience: loop one file
    """

    def __init__(self):
        self.tracks       = []   # list of absolute audio file paths
        self.intro        = None # optional intro track played once before the loop
        self.current_idx  = -1
        self.looping      = False
        self.current_path = ""

    def load_folder(self, folder, intro_name=None):
        """
        Populate the track list from all audio files in folder.
        If intro_name is given (basename only), that file is extracted as
        the intro and removed from the looping playlist.
        """
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
        self.looping     = False

    def play_intro(self):
        """Play the intro track once (does not loop)."""
        if self.intro and os.path.exists(self.intro):
            self._play(self.intro, loop=False)
            self.looping = False

    def play_random(self):
        """Start a random track from the playlist on a loop."""
        if not self.tracks:
            return
        self.current_idx = random.randint(0, len(self.tracks) - 1)
        self._play(self.tracks[self.current_idx], loop=True)
        self.looping = True

    def next_track(self):
        """Advance to the next track (wraps around the list)."""
        if not self.tracks:
            return
        self.current_idx = (self.current_idx + 1) % len(self.tracks)
        self._play(self.tracks[self.current_idx], loop=True)
        self.looping = True

    def _play(self, path, loop=False):
        """Internal: load and play a file, looping indefinitely if loop=True."""
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(-1 if loop else 0)
            self.current_path = path
        except Exception as e:
            print(f"Music error: {e}")

    def update(self):
        """
        Call once per frame.
        Automatically starts a random looping track once the intro finishes.
        """
        if not self.looping and not pygame.mixer.music.get_busy():
            self.play_random()

    def stop(self):
        """Stop playback and reset looping state."""
        pygame.mixer.music.stop()
        self.looping = False

    def single_track(self, path):
        """Loop a single audio file (shortcut for one-file playlists)."""
        self._play(path, loop=True)
        self.looping = True
        self.tracks  = [path]

    @property
    def current_name(self):
        """Return the basename of the currently playing file, or 'None'."""
        return os.path.basename(self.current_path) if self.current_path else "None"


