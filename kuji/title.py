# 起動したときのタイトル画面
import tkinter as tk
from tkinter import font as tkfont

from .stage import NORMAL, Picture, round_rect


class TitleScreen(tk.Canvas):
    def __init__(self, master, on_start):
        super().__init__(master, bg=NORMAL.bg, highlightthickness=0, bd=0)
        self._fonts = {k: tkfont.Font(self, family="Helvetica", size=-12, weight="bold")
                       for k in ("title", "sub", "button")}
        self._title = ""
        self._logo = Picture()
        self._credit = Picture()
        self.bind("<Configure>", lambda e: self.redraw())
        self.tag_bind("start", "<Button-1>", lambda e: on_start())
        self.tag_bind("start", "<Enter>", lambda e: self._hover(True))
        self.tag_bind("start", "<Leave>", lambda e: self._hover(False))

    def set_look(self, text_family, title, logo_path, credit_path):
        for f in self._fonts.values():
            f.configure(family=text_family)
        self._title = title
        self._logo = Picture(logo_path)
        self._credit = Picture(credit_path)
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50 or h < 50:
            return
        c = NORMAL
        logo = self._logo.at(int(h * 0.3), self)
        if logo:
            self.create_image(w / 2, h * 0.3, image=logo)
        f = self._fonts["title"]
        f.configure(size=-int(h * 0.09))
        if f.measure(self._title) > w * 0.9:
            f.configure(size=-int(h * 0.09 * w * 0.9 / f.measure(self._title)))
        self.create_text(w / 2, h * 0.58, text=self._title, font=f, fill=c.text)
        f = self._fonts["sub"]
        f.configure(size=-int(h * 0.045))
        self.create_text(w / 2, h * 0.68, text="抽選会", font=f, fill=c.sub)

        f = self._fonts["button"]
        f.configure(size=-int(h * 0.04))
        bw, bh = min(w * 0.2, h * 0.45), h * 0.08
        cx, cy = w / 2, h * 0.84
        round_rect(self, cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2, 6, fill=c.accent, outline="",
                   tags=("start", "start_bg"))
        self.create_text(cx, cy, text="START", font=f, fill=c.on_accent, tags="start")

        pad = max(16, h * 0.025)
        credit = self._credit.at(int(h * 0.13), self)
        if credit:
            self.create_image(w - pad, h - pad, image=credit, anchor="se")

    def _hover(self, inside):
        self.configure(cursor="hand2" if inside else "")
        self.itemconfigure("start_bg", fill=NORMAL.accent_dark if inside else NORMAL.accent)
