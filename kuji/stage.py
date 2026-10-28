# 客席に見せる画面。Canvas に直接描いている。
import math
import random
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont

from PIL import Image, ImageChops, ImageTk


@dataclass(frozen=True)
class Colors:
    bg: str = "#ffffff"
    line: str = "#d0d0d0"
    line_fixed: str = "#222222"
    digit_spin: str = "#b4b4b4"
    digit_fixed: str = "#111111"
    text: str = "#111111"
    sub: str = "#555555"
    muted: str = "#999999"
    accent: str = "#e60012"
    accent_dark: str = "#c4000f"
    on_accent: str = "#ffffff"


NORMAL = Colors()

# 前の版の虹色フリッカーと同じ色
FLASH_COLORS = ["#FF0000", "#FF8C00", "#FFFF00", "#008000", "#0000FF", "#4B0082", "#9400D3"]
CONFETTI_COLORS = ["#ff4d6d", "#ffc83d", "#4dd4ff", "#7cff6b", "#b28dff", "#ff8c42", "#ffffff"]
MAX_CONFETTI = 220  # 降らせ続けるときの数の上限 (多すぎると重い)


def ink_on(color):
    # 塗りつぶした色の上で読める文字の色
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#111111" if 0.299 * r + 0.587 * g + 0.114 * b > 150 else "#ffffff"


def _mix(a, b, t):
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def colors_from(bg, fg):
    # 演出の colors (背景と文字の2色) から、薄い色などを作る
    return Colors(
        bg=bg, line=_mix(fg, bg, 0.75), line_fixed=fg, digit_spin=_mix(fg, bg, 0.6), digit_fixed=fg,
        text=fg, sub=_mix(fg, bg, 0.25), muted=_mix(fg, bg, 0.6),
        accent=fg, accent_dark=_mix(fg, bg, 0.2), on_accent=bg,
    )


def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    pts = [
        x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y1 + r,
        x2, y2 - r, x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


def load_logo(path):
    img = Image.open(path).convert("RGBA")
    # 白背景のPNGは白を透明にする (フラッシュ中に白い四角が出ないように)
    if img.getextrema()[3][0] == 255:
        r, g, b, _ = img.split()
        darkest = ImageChops.darker(ImageChops.darker(r, g), b)
        img.putalpha(darkest.point(lambda v: 0 if v > 245 else 255))
    return img


class Picture:
    # 元の画像を持っておいて、指定した高さに縮めたものを返す
    def __init__(self, path=None):
        self.src = None
        self._photo = None
        if path:
            try:
                self.src = load_logo(path)
            except OSError:
                pass

    def at(self, height, master):
        if not self.src or height <= 0:
            return None
        if not self._photo or self._photo.height() != height:
            size = (max(1, round(self.src.width * height / self.src.height)), height)
            self._photo = ImageTk.PhotoImage(self.src.resize(size, Image.LANCZOS), master=master)
        return self._photo


class Stage(tk.Canvas):
    def __init__(self, master, on_start, on_settings, on_fullscreen, on_quit):
        super().__init__(master, bg=NORMAL.bg, highlightthickness=0, bd=0)
        self.flash_color = None
        self.colors = NORMAL
        self._fonts = {k: tkfont.Font(self, family="Helvetica", size=-12, weight="bold")
                       for k in ("title", "digit", "name", "sub", "small", "button")}
        self._families = ("Helvetica", "Helvetica")
        self._font_override = None
        self._title = ""
        self._digits = [("-", False)] * 5
        self._name, self._sub, self._muted = "", "", False
        self._status = ("", "")
        self._badge = ""
        self._busy = False
        self._won = False
        self._start_enabled = True
        self._cards = []
        self._card_fixed = []
        self._fills = None  # 止まった桁のカードを塗る色 (左から)
        self._confetti = []
        self._confetti_on = False
        self._confetti_palette = CONFETTI_COLORS
        self._confetti_job = None
        self._confetti_last = 0.0
        self._logo = Picture()
        self._credit = Picture()
        self._chrome = True
        self._autohide = False
        self._chrome_job = None

        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Motion>", lambda e: self._show_chrome())
        for tag, callback in (("start", on_start), ("c_settings", on_settings),
                              ("c_fullscreen", on_fullscreen), ("c_quit", on_quit)):
            self.tag_bind(tag, "<Button-1>", lambda e, cb=callback: cb())
            self.tag_bind(tag, "<Enter>", lambda e, t=tag: self._hover(t, True))
            self.tag_bind(tag, "<Leave>", lambda e, t=tag: self._hover(t, False))

    def set_look(self, digit_family, text_family, title, logo_path, credit_path=None):
        self._families = (digit_family, text_family)
        self._apply_fonts()
        self._title = title
        self._logo = Picture(logo_path)
        self._credit = Picture(credit_path)
        self.redraw()

    def set_font(self, family):
        # 演出の途中で全部の文字を family にする。None で元に戻す
        if family != self._font_override:
            self._font_override = family
            self._apply_fonts()
            self.redraw()

    def _apply_fonts(self):
        digit, text = self._families
        weight = "normal" if self._font_override else "bold"  # ドットのフォントは太字にするとつぶれる
        for key, f in self._fonts.items():
            f.configure(family=self._font_override or (digit if key == "digit" else text), weight=weight)

    def set_colors(self, colors):
        if colors != self.colors:
            self.colors = colors
            self.redraw()

    def set_autohide(self, on):
        self._autohide = on
        self._show_chrome()

    def set_digits(self, digits):
        if len(digits) != len(self._cards):
            self._digits = list(digits)
            self.redraw()
            return
        self._digits = list(digits)
        for i, ((rect, text), (ch, fixed)) in enumerate(zip(self._cards, digits)):
            fill, line, ink = self._card_style(i, fixed)
            self.itemconfigure(text, text=ch, fill=ink)
            if self._card_fixed[i] != fixed:
                self._card_fixed[i] = fixed
                self.itemconfigure(rect, fill=fill, outline=line)

    def set_card_fills(self, fills):
        fills = list(fills) if fills else None
        if fills != self._fills:
            self._fills = fills
            self.redraw()

    def _card_style(self, i, fixed):
        # (カードの塗り, 枠, 数字の色)
        c = self.colors
        if self._fills and (fixed or self._won):
            fill = self._fills[i % len(self._fills)]
            return fill, fill, ink_on(fill)
        if self._won:
            return c.bg, c.accent, c.accent
        return c.bg, (c.line_fixed if fixed else c.line), (c.digit_fixed if fixed else c.digit_spin)

    def set_name(self, name, sub="", muted=False):
        if (name, sub, muted) != (self._name, self._sub, self._muted):
            self._name, self._sub, self._muted = name, sub, muted
            self._draw_names()

    def set_status(self, left, right):
        if (left, right) != self._status:
            self._status = (left, right)
            self.redraw()

    def set_badge(self, text):
        if text != self._badge:
            self._badge = text
            self.redraw()

    def set_start_enabled(self, on):
        if on != self._start_enabled:
            self._start_enabled = on
            self.redraw()

    def set_flash(self, color):
        self.flash_color = color
        self.configure(bg=color or self.colors.bg)

    def begin_draw(self, badge=""):
        self._busy, self._won, self._badge = True, False, badge
        self._name, self._sub, self._muted = "", "", False
        self.redraw()

    def reveal(self, digits, name, sub):
        self._busy, self._won = False, True
        self._digits = list(digits)
        self._name, self._sub, self._muted = name, sub, False
        self.flash_color = None
        self.redraw()

    def reset(self, n):
        self._won, self._badge = False, ""
        self._digits = [("-", False)] * n
        self.colors = NORMAL
        self._fills = None
        self.clear_confetti()
        if self._font_override:
            self._font_override = None
            self._apply_fonts()
        self.redraw()

    def redraw(self):
        self.delete("ui")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50 or h < 50:
            return
        c = self.colors
        self.configure(bg=self.flash_color or c.bg)
        pad = max(16, h * 0.025)

        # ロゴとタイトルを横に並べて中央に
        f = self._fonts["title"]
        f.configure(size=-int(h * 0.06))
        y = h * 0.1
        logo = self._logo.at(int(h * 0.12), self)
        gap = h * 0.02
        x = (w - f.measure(self._title) - (logo.width() + gap if logo else 0)) / 2
        if logo:
            self.create_image(x, y, image=logo, anchor="w", tags="ui")
            x += logo.width() + gap
        self.create_text(x, y, text=self._title, font=f, fill=c.text, anchor="w", tags="ui")

        f = self._fonts["small"]
        f.configure(size=-int(max(12, h * 0.024)))
        left, right = self._status
        self.create_text(pad, pad, anchor="nw", text=left, font=f, fill=c.muted, tags="ui")
        self.create_text(w - pad, h - pad, anchor="se", text=right, font=f, fill=c.muted, tags="ui")
        if self._badge:
            self.create_text(pad, pad + h * 0.04, anchor="nw", text=self._badge, font=f, fill=c.accent, tags="ui")
        credit = self._credit.at(int(h * 0.08), self)
        if credit:
            self.create_image(pad, h - pad, image=credit, anchor="sw", tags="ui")

        self._draw_cards(w, h)
        self._draw_names()
        if not self._busy:
            self._draw_start(w, h)
            if self._chrome:
                x = w - pad
                for tag, label in (("c_quit", "終了"), ("c_fullscreen", "全画面"), ("c_settings", "設定")):
                    item = self.create_text(x, pad, anchor="ne", text=label, font=f, fill=c.muted, tags=("ui", tag))
                    x = self.bbox(item)[0] - pad
        self.tag_raise("confetti")

    def _draw_cards(self, w, h):
        c = self.colors
        n = max(1, len(self._digits))
        gap = w * 0.012
        cw = min((w * 0.8 - gap * (n - 1)) / n, h * 0.22)
        ch = cw * 1.35
        top = h * 0.42 - ch / 2
        x0 = (w - n * cw - (n - 1) * gap) / 2
        self._fonts["digit"].configure(size=-int(ch * 0.75))
        self._cards, self._card_fixed = [], []
        for i, (d, fixed) in enumerate(self._digits):
            x = x0 + i * (cw + gap)
            fill, line, color = self._card_style(i, fixed)
            rect = round_rect(self, x, top, x + cw, top + ch, cw * 0.06, fill=fill, outline=line,
                              width=max(2, int(cw * 0.03)), tags="ui")
            text = self.create_text(x + cw / 2, top + ch / 2, text=d, font=self._fonts["digit"],
                                    fill=color, tags="ui")
            self._cards.append((rect, text))
            self._card_fixed.append(fixed)

    def _draw_names(self):
        self.delete("names")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50 or h < 50:
            return
        c = self.colors
        name_size = h * 0.05 if self._muted else h * 0.13
        for key, text, size, y, color in (
            ("name", self._name, name_size, h * 0.68, c.muted if self._muted else c.text),
            ("sub", self._sub, h * 0.045, h * 0.79, c.sub),
        ):
            if not text:
                continue
            f = self._fonts[key]
            f.configure(size=-int(size))
            if f.measure(text) > w * 0.9:
                f.configure(size=-max(8, int(size * w * 0.9 / f.measure(text))))
            self.create_text(w / 2, y, text=text, font=f, fill=color, tags=("ui", "names"))
        self.tag_raise("confetti")

    def _draw_start(self, w, h):
        c = self.colors
        f = self._fonts["button"]
        f.configure(size=-int(h * 0.04))
        bw, bh = min(w * 0.2, h * 0.45), h * 0.08
        cx, cy = w / 2, h * 0.9
        if self._start_enabled:
            round_rect(self, cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2, 6, fill=c.accent, outline="",
                       tags=("ui", "start", "start_bg"))
            self.create_text(cx, cy, text="START", font=f, fill=c.on_accent, tags=("ui", "start"))
        else:
            round_rect(self, cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2, 6, fill=c.line, outline="",
                       tags="ui")
            self.create_text(cx, cy, text="START", font=f, fill=c.muted, tags="ui")

    def _hover(self, tag, inside):
        self._set_cursor("hand2" if inside else "")
        c = self.colors
        if tag == "start":
            self.itemconfigure("start_bg", fill=c.accent_dark if inside else c.accent)
        else:
            self.itemconfigure(tag, fill=c.text if inside else c.muted)

    # 紙吹雪。on のあいだは上から降らせ続ける。burst は一度にまとめて出す
    def set_confetti(self, on, palette=None):
        palette = list(palette) if palette else CONFETTI_COLORS
        if (on, palette) == (self._confetti_on, self._confetti_palette):
            return
        self._confetti_on, self._confetti_palette = on, palette
        if on:
            self._run_confetti()

    def burst(self, count, palette=None):
        if palette:
            self._confetti_palette = list(palette)
        w, h = self.winfo_width(), self.winfo_height()
        for _ in range(min(count, 2 * MAX_CONFETTI)):
            self._spawn(w, h, random.uniform(-h * 0.5, -10))
        self._run_confetti()

    def clear_confetti(self):
        self._confetti_on = False
        if self._confetti_job:
            self.after_cancel(self._confetti_job)
            self._confetti_job = None
        self.delete("confetti")
        self._confetti = []

    def _spawn(self, w, h, y):
        color = random.choice(self._confetti_palette)
        item = self.create_polygon(0, 0, 0, 0, 0, 0, fill=color, outline="", tags="confetti")
        self._confetti.append([
            item, random.uniform(0, w), y,                                 # x, y
            random.uniform(-60, 60), random.uniform(h * 0.18, h * 0.42),   # 速さ (px/秒)
            random.uniform(h * 0.007, h * 0.016),                          # 大きさ
            random.uniform(0, math.tau), random.uniform(3, 9),             # 角度, 回る速さ
            color, random.random() < 0.3,                                  # 色, キラキラ光るか
        ])

    def _run_confetti(self):
        if not self._confetti_job:
            self._confetti_last = time.perf_counter()
            self._confetti_step()

    def _confetti_step(self):
        now = time.perf_counter()
        dt, self._confetti_last = min(now - self._confetti_last, 0.05), now
        w, h = self.winfo_width(), self.winfo_height()
        if self._confetti_on:
            for _ in range(min(4, MAX_CONFETTI - len(self._confetti))):
                self._spawn(w, h, -10)
        alive = []
        for p in self._confetti:
            item, x, y, vx, vy, size, angle, spin, color, glitter = p
            angle += spin * dt
            x += (vx + math.sin(angle) * 40) * dt
            y += vy * dt
            if y > h + 30:
                self.delete(item)
                continue
            p[1], p[2], p[6] = x, y, angle
            # 紙が回りながらひらひらして見えるように、幅を cos で伸び縮みさせる
            cw, ch = size * abs(math.cos(angle)) + 1, size * 0.6
            ca, sa = math.cos(angle * 0.5), math.sin(angle * 0.5)
            pts = []
            for dx, dy in ((-cw, -ch), (cw, -ch), (cw, ch), (-cw, ch)):
                pts += [x + dx * ca - dy * sa, y + dx * sa + dy * ca]
            self.coords(item, *pts)
            if glitter:
                self.itemconfigure(item, fill="#ffffff" if random.random() < 0.35 else color)
            alive.append(p)
        self._confetti = alive
        self._confetti_job = self.after(16, self._confetti_step) if alive or self._confetti_on else None

    # 全画面ではマウスを3秒動かさないと「設定」などを隠す
    def _show_chrome(self):
        if self._chrome_job:
            self.after_cancel(self._chrome_job)
            self._chrome_job = None
        if not self._chrome:
            self._chrome = True
            self._set_cursor("")
            self.redraw()
        if self._autohide:
            self._chrome_job = self.after(3000, self._hide_chrome)

    def _hide_chrome(self):
        self._chrome_job = None
        self._chrome = False
        self._set_cursor("none")
        self.redraw()

    def _set_cursor(self, cursor):
        try:
            self.configure(cursor=cursor)
        except tk.TclError:
            pass
