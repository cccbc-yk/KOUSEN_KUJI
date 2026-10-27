# 動画を Canvas に流す。映像は1コマずつ取り出して描き、音は最初に全部読んで pygame で鳴らす。
# Tk は別スレッドから触ると落ちることがあるので、全部メインスレッドでやる (1コマ数msで間に合う)
import sys
import time

import av
import numpy as np
import pygame
from PIL import ImageTk


def decode_audio(path, rate=44100, channels=2):
    with av.open(str(path)) as c:
        if not c.streams.audio:
            return None
        resampler = av.AudioResampler(format="s16", layout="stereo" if channels == 2 else "mono", rate=rate)
        chunks = [f.to_ndarray() for frame in c.decode(audio=0) for f in resampler.resample(frame)]
        chunks += [f.to_ndarray() for f in resampler.resample(None)]
    return np.concatenate(chunks, axis=1) if chunks else None


class VideoPlayer:
    def __init__(self, canvas, path, volume, on_end):
        self.canvas = canvas
        self.on_end = on_end
        self._container = av.open(str(path))
        stream = self._container.streams.video[0]
        self._size = (stream.width, stream.height)
        self._frames = self._container.decode(video=0)
        self._next = None
        self._photo = None
        self._job = None
        self._t0 = 0.0
        self._closed = False
        self._sound = None
        try:
            rate, _, channels = pygame.mixer.get_init() or (0, 0, 0)
            pcm = decode_audio(path, rate, channels) if rate else None
            if pcm is not None:
                self._sound = pygame.mixer.Sound(buffer=pcm.tobytes())
                self._sound.set_volume(volume)
        except (av.FFmpegError, pygame.error, ValueError) as e:
            print(f"動画の音が読めません: {e}", file=sys.stderr)

    def play(self):
        if self._sound:
            self._sound.play()
        self._t0 = time.perf_counter()
        self._tick()

    def stop(self):
        if self._closed:
            return
        self._closed = True
        if self._job:
            self.canvas.after_cancel(self._job)
            self._job = None
        if self._sound:
            self._sound.stop()
        self._container.close()

    def _tick(self):
        elapsed = time.perf_counter() - self._t0
        latest = None
        try:
            # いまの時刻までのコマを読み進めて、一番新しいものだけ出す (遅れたら飛ばす)
            while True:
                if self._next is None:
                    self._next = next(self._frames, None)
                    if self._next is None:
                        break
                if (self._next.time or 0) > elapsed:
                    break
                latest, self._next = self._next, None
        except av.FFmpegError as e:
            print(f"動画が読めません: {e}", file=sys.stderr)
            self._next = None
        if latest is not None:
            self._show(latest)
        elif self._next is None:
            self.stop()
            self.on_end()
            return
        # 次のコマの時刻まで待つ
        wait = (self._next.time or 0) - (time.perf_counter() - self._t0) if self._next else 0.01
        self._job = self.canvas.after(max(1, int(wait * 1000)), self._tick)

    def _show(self, frame):
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        vw, vh = self._size
        scale = min(cw / vw, ch / vh)
        w, h = max(2, int(vw * scale) // 2 * 2), max(2, int(vh * scale) // 2 * 2)
        img = frame.reformat(width=w, height=h, format="rgb24").to_image()
        if self._photo and (self._photo.width(), self._photo.height()) == (w, h):
            self._photo.paste(img)
            return
        self._photo = ImageTk.PhotoImage(img, master=self.canvas)
        self.canvas.delete("video")
        self.canvas.create_image(cw / 2, ch / 2, image=self._photo, tags="video")
