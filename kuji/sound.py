import os
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402


class SoundBank:
    def __init__(self, directory, volume=0.8):
        self.directory = directory
        self.volume = volume
        self.error = None
        self._cache = {}
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(64)
        except pygame.error as e:
            self.error = str(e)
            print(f"音が出せないので無音で動かします: {e}", file=sys.stderr)

    @property
    def available(self):
        return self.error is None

    def _load(self, name):
        if name not in self._cache:
            try:
                sound = pygame.mixer.Sound(str(self.directory / name))
                sound.set_volume(self.volume)
            except (pygame.error, FileNotFoundError) as e:
                print(f"音声ファイルが読めません: {name} ({e})", file=sys.stderr)
                sound = None
            self._cache[name] = sound
        return self._cache[name]

    def preload(self, names):
        if self.available:
            for name in names:
                self._load(name)

    def play(self, name):
        if self.available and name:
            sound = self._load(name)
            if sound:
                sound.play()

    def length(self, name):
        sound = self._load(name) if self.available and name else None
        return sound.get_length() if sound else 0

    def missing(self):
        return sorted(name for name, sound in self._cache.items() if sound is None)

    def files(self):
        return sorted(p.relative_to(self.directory).as_posix() for p in self.directory.rglob("*.wav")
                      if not p.name.startswith("._"))

    def set_volume(self, volume):
        self.volume = volume
        for sound in self._cache.values():
            if sound:
                sound.set_volume(volume)

    def close(self):
        if self.available:
            pygame.mixer.quit()
