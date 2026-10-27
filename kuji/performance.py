import random

from .effects import normalize_mask
from .roster import pad_number


class Performance:
    """1回分の演出。時間 (秒) を渡すと進む。"""

    def __init__(self, effect, digits, pick, speed=1.0, flash_enabled=True, play=None, sound_length=None,
                 rng=None, record=False):
        self.effect = effect
        self.digits = digits
        self._pick = pick
        self._speed = max(speed, 0.05)
        self._flash_enabled = flash_enabled
        self._play = play or (lambda name: None)
        self._sound_length = sound_length or (lambda name: 0)
        self._rng = rng or random.Random()
        self.record = record  # 記録モード: at のあるステップは tap() されるまで始めない

        self.winner = pick()
        self.target = pad_number(self.winner.number, digits)
        self.mask = (False,) * digits
        self.blank = False
        self.flash = False
        self.colors = None  # (背景, 文字) の色。None ならいつもの色
        self.message = ""
        self.done = False
        self.zero_index = -1
        self.waiting_tap = False
        self._zero = 0.0
        self._index = -1
        self._step_end = 0.0

    def start(self, now):
        self._step_end = self._zero = now
        self.update(now)

    def update(self, now):
        while not self.done and now >= self._step_end:
            self._index += 1
            if self._index >= len(self.effect.steps):
                self._finish()
                break
            steps = self.effect.steps
            step = steps[self._index]
            start = self._step_end
            if step.zero:
                self._zero, self.zero_index = start, self._index
            self._enter(step)
            nxt = steps[self._index + 1] if self._index + 1 < len(steps) else None
            if nxt and nxt.at is not None and self.record:
                self.waiting_tap = True
                self._step_end = float("inf")
            elif nxt and nxt.at is not None:
                # 音ハメ用。次のステップが始まる時刻が決まっている (速さの設定は効かない)
                self._step_end = max(start, self._zero + nxt.at / 1000)
            else:
                ms = step.ms / self._speed
                if step.wait and step.sound:
                    ms = max(ms, self._sound_length(step.sound) * 1000)
                # 前のステップの終わりから足していくので、描画が遅れても全体の長さは変わらない
                self._step_end = start + ms / 1000

    def skip(self):
        self._finish()

    def tap(self, now):
        # 記録モードで、次の at のステップをいま始める。(ステップの番号, zero からのms) を返す
        if not self.waiting_tap:
            return None
        self.waiting_tap = False
        self._step_end = now
        tapped = (self._index + 1, (now - self._zero) * 1000)
        self.update(now)
        return tapped

    def frame_digits(self):
        if self.blank:
            return [("-", False)] * self.digits
        return [(self.target[i], True) if self.mask[i] else (str(self._rng.randrange(10)), False)
                for i in range(self.digits)]

    def _enter(self, step):
        if step.sound:
            self._play(step.sound)
        if step.action == "spin":
            self.mask = normalize_mask(step.fix, self.digits)
            self.blank = False
        elif step.action == "blank":
            self.blank = True
        elif step.action == "redraw":
            self.winner = self._pick()
            self.target = pad_number(self.winner.number, self.digits)
        elif step.action == "fake":
            n = step.number
            self.target = (n[0] * self.digits + n)[-self.digits:] if len(n) < self.digits else n[:self.digits]
        elif step.action == "flash":
            self.flash = step.on and self._flash_enabled
        elif step.action == "colors":
            self.colors = (step.bg, step.fg) if step.bg else None
        elif step.action == "message":
            self.message = step.text

    def _finish(self):
        self.done = True
        self.waiting_tap = False
        self.blank = False
        self.flash = False
        self.message = ""
        self.target = pad_number(self.winner.number, self.digits)  # fake のまま終わっても本物を出す
        self.mask = (True,) * self.digits
