import os
import random
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox

import tkinter as tk

import av
import customtkinter as ctk

from . import config
from .config import resolve_path
from .effects import BUILTIN_NORMAL, EffectError, choose_effect, load_effects, rewrite_at
from .history import History, history_path_for
from .performance import Performance
from .roster import Entry, RosterError, build_entries, digit_count, read_table, remaining
from .sound import SoundBank
from .stage import FLASH_COLORS, NORMAL, Stage, colors_from
from .title import TitleScreen
from .video import VideoPlayer

TICK_MS = 16
DIGIT_FONTS = ["Digital-7", "Digital-7 Mono", "Avenir Next", "Helvetica Neue", "Segoe UI", "Arial"]
TEXT_FONTS = ["Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic UI", "Meiryo",
              "Noto Sans CJK JP", "Noto Sans JP"]
DUMMY = Entry("12345", "テスト太郎", "ﾃｽﾄ ﾀﾛｳ", "")


def fix_tcl_library():
    # uv で入れた Python の venv だと Tk が init.tcl を見つけられないことがある (Windows は tcl フォルダ)
    base = Path(sys.base_prefix)
    for env, name, marker in (("TCL_LIBRARY", "tcl8.6", "init.tcl"), ("TK_LIBRARY", "tk8.6", "tk.tcl")):
        for folder in (base / "lib" / name, base / "tcl" / name):
            if (folder / marker).exists():
                os.environ.setdefault(env, str(folder))
                break


def setup_theme():
    ctk.set_appearance_mode("light")
    t = ctk.ThemeManager.theme
    dark, dark_hover, gray = ["#333333"] * 2, ["#555555"] * 2, ["#a0a0a0"] * 2
    t["CTk"]["fg_color"] = ["#ffffff"] * 2
    t["CTkFrame"].update(corner_radius=4, fg_color=["#f2f2f2"] * 2, top_fg_color=["#e9e9e9"] * 2)
    t["CTkButton"].update(corner_radius=4, fg_color=dark, hover_color=dark_hover, text_color=["#ffffff"] * 2)
    t["CTkOptionMenu"].update(corner_radius=4, fg_color=["#e4e4e4"] * 2, button_color=["#d2d2d2"] * 2,
                              button_hover_color=["#c0c0c0"] * 2, text_color=["#222222"] * 2)
    t["CTkSegmentedButton"].update(corner_radius=4, fg_color=gray, selected_color=dark,
                                   selected_hover_color=dark_hover, unselected_color=gray,
                                   unselected_hover_color=["#8a8a8a"] * 2)
    t["CTkSwitch"].update(progress_color=dark)
    t["CTkCheckBox"].update(corner_radius=3, fg_color=dark, hover_color=dark_hover, border_color=["#666666"] * 2)
    t["CTkSlider"].update(button_color=dark, button_hover_color=dark_hover, progress_color=["#777777"] * 2)
    t["CTkEntry"].update(corner_radius=4, border_color=["#bdbdbd"] * 2)
    t["CTkComboBox"].update(corner_radius=4, border_color=["#bdbdbd"] * 2, button_color=["#bdbdbd"] * 2)
    t["CTkTextbox"].update(corner_radius=4)


class App(ctk.CTk):
    def __init__(self):
        fix_tcl_library()
        setup_theme()
        super().__init__()
        self.title("高専祭くじ")
        self._center(1280, 800)
        self.minsize(800, 520)

        self.settings = config.load()
        self.rng = random.SystemRandom()
        self.families = sorted({f for f in tkfont.families(self) if not f.startswith("@")})
        self.sounds = SoundBank(config.SOUNDS_DIR, self.settings.display.volume)
        self.reload_effects()

        self.entries = []
        self.history = None
        self.data_error = ""
        self.override = None  # 次の1回だけ使う演出
        self.performance = None
        self.preview = False
        self.panel = None
        self.screen = "main"  # title / video / main
        self.title_screen = None
        self.video = None
        self.video_canvas = None
        self.fullscreen = False
        self._flash_i = 0
        self._tick_job = None
        self.taps = []  # 試し再生中に T で記録した (zero の番号, 秒)

        self.stage = Stage(self, self.start_draw, self.toggle_settings, self.toggle_fullscreen, self.quit_app)
        self.stage.pack(fill="both", expand=True)
        self.bind("<Configure>", lambda e: self._resize_panel() if e.widget is self else None, add="+")

        self.apply_display()
        self.load_roster()
        if self.settings.display.title_screen:
            self.show_title()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        if sys.platform == "darwin":
            self.createcommand("::tk::mac::Quit", self.quit_app)  # ⌘Q でも音を止めてから閉じる
        # macOS では lift() のあとだと全画面にならないので順番に注意
        if self.settings.display.fullscreen:
            self.after(300, lambda: self.set_fullscreen(True))
            self.after(1200, self.focus_force)
        else:
            self.after(100, lambda: (self.lift(), self.focus_force()))

    def _center(self, width, height):
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 3)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _bind_keys(self):
        self.bind("<space>", self._on_go)
        self.bind("<Return>", self._on_go)
        self.bind("<Escape>", self._on_escape)
        self.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.bind("<KeyPress-s>", lambda e: None if self.panel else self.toggle_settings())
        self.bind("<KeyPress-f>", lambda e: None if self.panel else self.toggle_fullscreen())
        self.bind("<KeyPress-t>", self._on_tap)
        mod = "Command" if sys.platform == "darwin" else "Control"
        self.bind(f"<{mod}-comma>", lambda e: self.toggle_settings())
        self.bind("<Control-q>", lambda e: self.quit_app())

    def reload_effects(self):
        self.effects, self.effect_errors = load_effects(config.EFFECTS_DIR)
        for msg in self.effect_errors:
            print(f"読めなかった演出: {msg}", file=sys.stderr)
        if not self.effects:
            self.effects = {BUILTIN_NORMAL.id: BUILTIN_NORMAL}
        sounds = {s for e in self.effects.values() for s in e.sounds()}
        self.sounds.preload(sorted(sounds | {self.settings.effects.start_sound}))

    def font_family(self, preferred, candidates):
        if preferred and preferred in self.families:
            return preferred
        return next((c for c in candidates if c in self.families), "Helvetica")

    def apply_display(self):
        d = self.settings.display
        logo = resolve_path(d.logo_path) if d.logo_path else None
        credit = resolve_path(d.credit_logo) if d.credit_logo else None
        self.stage.set_look(self.font_family(d.digit_font, DIGIT_FONTS), self.font_family(d.name_font, TEXT_FONTS),
                            config.format_title(d.title), logo, credit)
        if self.title_screen:
            self.title_screen.set_look(self.font_family(d.name_font, TEXT_FONTS), config.format_title(d.title),
                                       logo, credit)
        self.sounds.set_volume(d.volume)

    # タイトル画面 → 動画 → 抽選の画面
    def show_title(self):
        self.stage.pack_forget()
        self.title_screen = TitleScreen(self, self.start_opening)
        self.title_screen.pack(fill="both", expand=True)
        self.screen = "title"
        self.apply_display()

    def start_opening(self):
        if self.screen != "title" or self.panel:
            return
        d = self.settings.display
        path = resolve_path(d.opening_video) if d.opening_video else None
        if not path or not path.exists():
            self.show_main()
            return
        self.title_screen.destroy()
        self.title_screen = None
        self.video_canvas = tk.Canvas(self, bg="#000000", highlightthickness=0, bd=0)
        self.video_canvas.pack(fill="both", expand=True)
        self.screen = "video"
        try:
            self.video = VideoPlayer(self.video_canvas, path, d.volume, self.show_main)
        except (av.FFmpegError, OSError, IndexError) as e:
            print(f"動画が読めません: {e}", file=sys.stderr)
            self.show_main()
            return
        self.update_idletasks()
        self.video.play()

    def show_main(self):
        if self.video:
            self.video.stop()
            self.video = None
        for widget in (self.video_canvas, self.title_screen):
            if widget:
                widget.destroy()
        self.video_canvas = self.title_screen = None
        if self.screen != "main":
            self.stage.pack(fill="both", expand=True)
            self.screen = "main"
        self.stage.focus_set()

    def load_roster(self):
        ds = self.settings.data
        self.entries, self.history, self.data_error = [], None, ""
        if not ds.csv_path:
            self.data_error = "CSVが選ばれていません"
        else:
            path = resolve_path(ds.csv_path)
            try:
                self.entries = build_entries(read_table(path, ds.encoding), ds)
                self.history = History(history_path_for(path, config.RESULTS_DIR))
                if not self.entries:
                    self.data_error = "CSVが空です"
            except (RosterError, OSError) as e:
                self.data_error = str(e)
        self.show_idle()

    @property
    def digits(self):
        return digit_count(self.entries)

    @property
    def next_draw_no(self):
        return self.history.next_draw_no if self.history else 1

    def pool(self):
        return remaining(self.entries, self.history.drawn_keys() if self.history else Counter())

    def show_idle(self):
        self.stage.reset(self.digits)
        if self.data_error:
            self.stage.set_name(self.data_error, "Sキーで設定を開いてCSVを選んでください", muted=True)
        elif not self.pool():
            self.stage.set_name("全員当選しました", "", muted=True)
        else:
            self.stage.set_name("", "")
        self.update_status(self.next_draw_no)

    def update_status(self, draw_no):
        pool = self.pool()
        self.stage.set_start_enabled(not self.data_error and bool(pool))
        if not self.settings.display.show_status or self.data_error:
            self.stage.set_status("", "")
        else:
            self.stage.set_status(f"第{draw_no}回", f"残り{len(pool)}人")

    def start_draw(self, preview_effect=None, record=False):
        if self.performance or self.panel:
            return
        if self.screen != "main":
            self.show_main()
        preview = preview_effect is not None
        pool = self.pool()
        if preview:
            candidates = pool or self.entries or [DUMMY]
        elif self.data_error or not pool:
            self.bell()
            return
        else:
            candidates = pool

        draw_no = self.next_draw_no
        es = self.settings.effects
        if preview:
            effect = self.effects[preview_effect]
        elif self.override in self.effects:
            effect = self.effects[self.override]
        else:
            effect = choose_effect(draw_no, es, self.effects, self.rng)

        self.sounds.play(es.start_sound if effect.start_sound is None else effect.start_sound)
        self.performance = Performance(
            effect, max(len(c.number) for c in candidates), lambda: self.rng.choice(candidates),
            speed=es.speed, flash_enabled=es.flash, play=self.sounds.play, sound_length=self.sounds.length,
            rng=self.rng, record=preview and record,
        )
        self.preview = preview
        self.taps = []
        self.stage.set_colors(NORMAL)
        self.stage.begin_draw(self._badge_text() if preview else "")
        self.update_status(draw_no)
        self.performance.start(time.perf_counter())
        self._tick()

    def _tick(self):
        perf = self.performance
        if perf is None:
            return
        perf.update(time.perf_counter())
        if perf.done:
            self._finish()
            return
        self.stage.set_digits(perf.frame_digits())
        if perf.flash:
            self._flash_i = (self._flash_i + 1) % len(FLASH_COLORS)
            self.stage.set_flash(FLASH_COLORS[self._flash_i])
        elif self.stage.flash_color:
            self.stage.set_flash(None)
        self._apply_colors(perf)
        self.stage.set_name(perf.message)
        self._tick_job = self.after(TICK_MS, self._tick)

    def _finish(self):
        perf, self.performance = self.performance, None
        self._tick_job = None
        draw_no = self.next_draw_no
        winner = perf.winner
        if not self.preview and self.history:
            try:
                self.history.add(winner, perf.effect.name)
            except OSError as e:
                messagebox.showerror("履歴を保存できませんでした", str(e), parent=self)
            self.override = None
        self._apply_colors(perf)
        self.stage.reveal(perf.frame_digits(), winner.name, winner.sub)
        if self.taps:
            taps = self.taps
            self.after(300, lambda: self._save_taps(perf.effect, taps))
        self.preview = False
        self.taps = []
        self.update_status(draw_no)

    def _apply_colors(self, perf):
        self.stage.set_colors(colors_from(*perf.colors) if perf.colors else NORMAL)

    def _badge_text(self):
        perf = self.performance
        if not perf or not perf.record:
            return "テスト"
        total = sum(1 for s in perf.effect.steps if s.at is not None)
        return f"記録中 {len(self.taps)}/{total}  Tで進む"

    def _on_tap(self, event=None):
        # 記録モードでは at のあるステップは T を押すまで始まらない
        if self.performance and not self.panel:
            tapped = self.performance.tap(time.perf_counter())
            if tapped:
                self.taps.append(tapped)
                self.stage.set_badge(self._badge_text())

    def _save_taps(self, effect, taps):
        new_at = dict(taps)
        lines = [f"{effect.steps[i].at / 1000:.2f}秒 → {ms / 1000:.2f}秒" for i, ms in sorted(new_at.items())]
        if not messagebox.askyesno("タイミング記録", "この時刻に書き換えますか？\n\n" + "\n".join(lines), parent=self):
            return
        try:
            rewrite_at(config.EFFECTS_DIR / f"{effect.id}.toml", effect, new_at)
        except (OSError, EffectError) as e:
            messagebox.showerror("タイミング記録", str(e), parent=self)
            return
        self.reload_effects()

    def _on_go(self, event=None):
        if self.panel:
            return
        if self.screen == "title":
            self.start_opening()
        elif self.screen == "video":
            self.show_main()
        elif self.performance and self.preview:
            self.performance.skip()
        else:
            self.start_draw()

    def undo_last(self):
        record = self.history.undo_last() if self.history else None
        self.show_idle()
        return record

    def reset_history(self):
        backup = self.history.archive() if self.history else None
        self.show_idle()
        return backup

    def open_results_folder(self):
        config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        path = str(config.RESULTS_DIR)
        if sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        elif sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.run(["xdg-open", path], check=False)

    def toggle_settings(self):
        if self.panel:
            self.close_settings()
        elif not self.performance and self.screen != "video":
            from .settings_panel import SettingsPanel
            self.panel = SettingsPanel(self, *self._panel_size())
            self.panel.place(relx=0.5, rely=0.5, anchor="center")
            self.stage.set_autohide(False)

    def close_settings(self):
        if self.panel:
            self.panel.destroy()
            self.panel = None
            self.sounds.set_volume(self.settings.display.volume)
            self.stage.set_autohide(self.fullscreen)
            self.stage.focus_set()

    def _panel_size(self):
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        w, h = self.winfo_width() / scale, self.winfo_height() / scale
        return int(min(1000, w - 40)), int(min(780, h - 40))

    def _resize_panel(self):
        if self.panel:
            w, h = self._panel_size()
            self.panel.configure(width=w, height=h)

    def apply_settings(self, new, override):
        old, self.settings = self.settings, new
        try:
            config.save(new)
        except OSError as e:
            messagebox.showerror("設定を保存できませんでした", str(e), parent=self)
        self.override = override
        self.close_settings()
        self.apply_display()
        if new.data != old.data:
            self.load_roster()
        else:
            self.show_idle()

    def set_fullscreen(self, on):
        self.fullscreen = on
        self.attributes("-fullscreen", on)
        self.stage.set_autohide(on and not self.panel)

    def toggle_fullscreen(self):
        self.set_fullscreen(not self.fullscreen)

    def _on_escape(self, event=None):
        if self.panel:
            self.close_settings()
        elif self.fullscreen:
            self.set_fullscreen(False)

    def quit_app(self):
        if self.performance and not self.preview:
            if not messagebox.askyesno("終了", "抽選中です。終了しますか？ (この回は記録されません)", parent=self):
                return
        if self._tick_job:
            self.after_cancel(self._tick_job)
        if self.video:
            self.video.stop()
        self.sounds.close()
        self.destroy()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
