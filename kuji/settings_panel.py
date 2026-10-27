# 設定画面。ステージの上に重ねて出す (全画面のままでも開ける)
import copy
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import config
from .config import DEFAULT_ORDER, RANDOM_SLOT, DataSettings, relativize, resolve_path
from .effects import ORDER_PREFIX, order_code, planned_slot, write_order_effect
from .history import History, history_path_for
from .roster import RosterError, build_entries, column_labels, guess_header, read_table, remaining

INK = "#222222"
MUTED = "#808080"
RED = "#e60012"
ENCODINGS = {"auto": "自動", "utf-8": "UTF-8", "cp932": "Shift_JIS"}
AFTER_ORDER = {"fallback": "同じ演出", "random": "ランダム", "repeat": "くり返し"}
NO_COLUMN = "なし"
NO_SOUND = "なし"
RANDOM_LABEL = "ランダム"
AUTO_LABEL = "そのまま"
AUTO_FONT = "自動"
IMAGES = [("画像", "*.png *.gif *.jpg"), ("すべて", "*.*")]


def _key(mapping, label, default):
    return next((k for k, v in mapping.items() if v == label), default)


def _int(text, default):
    try:
        return max(0, int(float(text)))
    except ValueError:
        return default


class SettingsPanel(ctk.CTkFrame):
    def __init__(self, app, width, height):
        super().__init__(app, width=width, height=height, corner_radius=6, border_width=1,
                         border_color="#cccccc", fg_color="#ffffff", bg_color="#ffffff")
        self.app = app
        self.s = copy.deepcopy(app.settings)
        self.h1 = ctk.CTkFont(size=20, weight="bold")
        self.h2 = ctk.CTkFont(size=15, weight="bold")
        self.plain = {"fg_color": "transparent", "border_width": 1, "border_color": "#bdbdbd",
                      "text_color": INK, "hover_color": "#eeeeee"}

        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self, text="設定", font=self.h1).grid(row=0, column=0, sticky="w", padx=24, pady=(16, 0))
        tabs = ctk.CTkTabview(self, fg_color="#ffffff")
        tabs.grid(row=1, column=0, sticky="nsew", padx=16)
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=24, pady=(4, 16))
        ctk.CTkButton(footer, text="保存", width=110, fg_color=RED, hover_color="#c4000f",
                      command=self._save).pack(side="right")
        ctk.CTkButton(footer, text="キャンセル", width=110, command=app.close_settings, **self.plain).pack(
            side="right", padx=8)

        self._make_effect_labels()
        self._data_tab(self._scroll(tabs.add("データ")))
        self._effects_tab(self._scroll(tabs.add("演出")))
        self._display_tab(self._scroll(tabs.add("表示")))
        self._history_tab(self._scroll(tabs.add("履歴")))

    def _scroll(self, tab):
        body = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        body.pack(fill="both", expand=True)
        return body

    def _heading(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=self.h2, anchor="w").pack(fill="x", padx=8, pady=(14, 2))

    def _note(self, parent, text):
        ctk.CTkLabel(parent, text=text, text_color=MUTED, anchor="w", justify="left", wraplength=820).pack(
            fill="x", padx=8)

    def _row(self, parent, label=""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=3)
        if label:
            ctk.CTkLabel(row, text=label, width=110, anchor="w").pack(side="left")
        return row

    def _switch(self, parent, text, value):
        var = tk.BooleanVar(value=value)
        ctk.CTkSwitch(parent, text=text, variable=var, onvalue=True, offvalue=False).pack(anchor="w", padx=8, pady=5)
        return var

    # ---- データ

    def _data_tab(self, body):
        d = self.s.data
        self._heading(body, "CSV")
        row = self._row(body, "ファイル")
        self.v_csv = tk.StringVar(value=d.csv_path)
        entry = ctk.CTkEntry(row, textvariable=self.v_csv)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        entry.bind("<Return>", lambda e: self._reload_table(auto_header=True))
        entry.bind("<FocusOut>", lambda e: self._reload_table())
        ctk.CTkButton(row, text="選択", width=70, command=self._browse_csv).pack(side="left")

        row = self._row(body, "文字コード")
        self.seg_encoding = ctk.CTkSegmentedButton(row, values=list(ENCODINGS.values()),
                                                   command=lambda v: self._reload_table())
        self.seg_encoding.set(ENCODINGS.get(d.encoding, "自動"))
        self.seg_encoding.pack(side="left")

        self.v_header = tk.BooleanVar(value=bool(d.has_header))
        ctk.CTkCheckBox(body, text="1行目は見出し", variable=self.v_header, onvalue=True, offvalue=False,
                        command=self._reload_table).pack(anchor="w", padx=8, pady=5)

        self._heading(body, "列")
        self._columns = {"number": d.number_col, "name": d.name_col, "sub": d.sub_col}
        self.col_menus = {}
        for key, label in (("number", "番号"), ("name", "名前"), ("sub", "サブ")):
            menu = ctk.CTkOptionMenu(self._row(body, label), values=[""], width=340, dynamic_resizing=False,
                                     command=lambda v, k=key: self._set_column(k, v))
            menu.pack(side="left")
            self.col_menus[key] = menu
        self.v_strip = tk.BooleanVar(value=d.strip_name_spaces)
        ctk.CTkCheckBox(body, text="名前の全角スペースを消す", variable=self.v_strip, onvalue=True, offvalue=False,
                        command=self._update_preview).pack(anchor="w", padx=8, pady=5)

        self.data_info = ctk.CTkLabel(body, text="", anchor="w", justify="left", fg_color="#f2f2f2",
                                      corner_radius=4)
        self.data_info.pack(fill="x", padx=8, pady=(12, 4), ipadx=10, ipady=8)
        self._note(body, "CSVは読むだけで書き換えません。当選者は results フォルダに記録されます。")
        self._table = None
        self._labels = []
        self._reload_table(auto_header=d.has_header is None)

    def _browse_csv(self):
        current = resolve_path(self.v_csv.get()) if self.v_csv.get() else config.BASE_DIR
        path = filedialog.askopenfilename(
            parent=self, initialdir=str(current.parent if current.is_file() else current),
            filetypes=[("CSV", "*.csv"), ("すべて", "*.*")],
        )
        if path:
            self.v_csv.set(relativize(Path(path)))
            self._reload_table(auto_header=True)

    def _encoding(self):
        return _key(ENCODINGS, self.seg_encoding.get(), "auto")

    def _reload_table(self, auto_header=False):
        if not self.winfo_exists():  # 閉じる途中の FocusOut
            return
        self._table = None
        if not self.v_csv.get().strip():
            self._info("CSVを選んでください", True)
            return
        try:
            self._table = read_table(resolve_path(self.v_csv.get().strip()), self._encoding())
        except RosterError as e:
            self._info(str(e), True)
            return
        if auto_header:
            self.v_header.set(guess_header(self._table.rows))
        self._labels = column_labels(self._table, self.v_header.get())
        for key, menu in self.col_menus.items():
            menu.configure(values=([NO_COLUMN] if key == "sub" else []) + self._labels)
            i = self._columns[key]
            if key == "sub" and not 0 <= i < len(self._labels):
                self._columns[key] = -1
                menu.set(NO_COLUMN)
            else:
                i = min(max(i, 0), len(self._labels) - 1)
                self._columns[key] = i
                menu.set(self._labels[i] if self._labels else "")
        self._update_preview()

    def _set_column(self, key, label):
        self._columns[key] = self._labels.index(label) if label in self._labels else -1
        self._update_preview()

    def _data_settings(self):
        return DataSettings(
            csv_path=self.v_csv.get().strip(),
            encoding=self._encoding(),
            has_header=self.v_header.get(),
            number_col=self._columns["number"],
            name_col=self._columns["name"],
            sub_col=self._columns["sub"],
            strip_name_spaces=self.v_strip.get(),
        )

    def _update_preview(self):
        if not self._table:
            return
        ds = self._data_settings()
        try:
            entries = build_entries(self._table, ds)
        except RosterError as e:
            self._info(str(e), True)
            return
        if not entries:
            self._info("抽選できる行がありません", True)
            return
        history = History(history_path_for(resolve_path(ds.csv_path), config.RESULTS_DIR))
        left = remaining(entries, history.drawn_keys())
        e = entries[0]
        self._info(f"{len(entries)}人 (当選済み {len(entries) - len(left)}人 / 残り {len(left)}人)\n"
                   f"例: {e.number}  {e.name}  {e.sub}")

    def _info(self, text, warn=False):
        self.data_info.configure(text=text, text_color=RED if warn else INK)

    # ---- 演出

    def _make_effect_labels(self):
        effects = sorted(self.app.effects.values(), key=lambda e: (e.id != "normal", e.id.startswith(ORDER_PREFIX), e.name))
        names = [e.name for e in effects]
        self.effect_label = {e.id: e.name if names.count(e.name) == 1 else f"{e.name} ({e.id})" for e in effects}
        self.effect_label[RANDOM_SLOT] = RANDOM_LABEL
        self.effect_id = {label: eid for eid, label in self.effect_label.items()}
        self.effect_labels = [self.effect_label[e.id] for e in effects]

    def _label(self, eid):
        return self.effect_label.get(eid, f"(なし: {eid})")

    def _effects_tab(self, body):
        es = self.s.effects
        for msg in self.app.effect_errors:
            self._note(body, f"読めなかった演出: {msg}")
        if self.app.sounds.missing():
            self._note(body, "見つからない音: " + ", ".join(self.app.sounds.missing()))

        self._heading(body, "順番")
        self.order = list(es.order)
        self.order_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.order_frame.pack(fill="x", padx=8)
        row = self._row(body)
        ctk.CTkButton(row, text="追加", width=80, command=self._add_order).pack(side="left")
        ctk.CTkButton(row, text="初期の順番に戻す", width=140, command=self._reset_order, **self.plain).pack(
            side="left", padx=8)

        row = self._row(body, "そのあと")
        self.om_after = ctk.CTkOptionMenu(row, values=list(AFTER_ORDER.values()), width=120,
                                          command=lambda v: self._update_after())
        self.om_after.set(AFTER_ORDER.get(es.after_order, AFTER_ORDER["fallback"]))
        self.om_after.pack(side="left")
        self.om_fallback = ctk.CTkOptionMenu(row, values=self.effect_labels, width=240,
                                             command=lambda v: self._update_next())
        self.om_fallback.set(self._label(es.fallback))
        self.om_fallback.pack(side="left", padx=8)

        row = self._row(body, "次の1回")
        self.om_override = ctk.CTkOptionMenu(row, values=[AUTO_LABEL] + self.effect_labels, width=240,
                                             command=lambda v: self._update_next())
        self.om_override.set(self._label(self.app.override) if self.app.override else AUTO_LABEL)
        self.om_override.pack(side="left")
        self.next_info = ctk.CTkLabel(row, text="", text_color=MUTED)
        self.next_info.pack(side="left", padx=12)

        self._order_maker(body)

        self._heading(body, "ランダムの割合")
        self.weight_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.weight_frame.pack(fill="x", padx=8)

        self._heading(body, "その他")
        row = self._row(body, "速さ")
        self.speed_label = ctk.CTkLabel(row, text=f"{es.speed:.2f}倍", width=60)
        self.slider_speed = ctk.CTkSlider(row, from_=0.5, to=2.0, number_of_steps=30, width=280,
                                          command=lambda v: self.speed_label.configure(text=f"{v:.2f}倍"))
        self.slider_speed.set(es.speed)
        self.slider_speed.pack(side="left")
        self.speed_label.pack(side="left", padx=8)
        self.v_flash = self._switch(body, "虹フラッシュ", es.flash)

        row = self._row(body, "試し再生")
        self.om_preview = ctk.CTkOptionMenu(row, values=self.effect_labels, width=240)
        self.om_preview.set(self.effect_labels[0])
        self.om_preview.pack(side="left")
        ctk.CTkButton(row, text="再生", width=70, command=self._preview).pack(side="left", padx=8)
        ctk.CTkButton(row, text="記録", width=70, command=lambda: self._preview(record=True), **self.plain).pack(
            side="left")
        self._note(body, "試し再生は当選履歴に残りません。Spaceで最後まで飛ばせます。\n"
                         "記録: at のある所は T を押すまで進まないので、音に合わせて押していくと、その時刻を演出ファイルに書き込めます。")

        self._render_order()
        self._render_weights({eid: es.weights.get(eid, e.weight) for eid, e in self.app.effects.items()})
        self._update_after()

    def _render_order(self):
        for child in self.order_frame.winfo_children():
            child.destroy()
        next_i = self.app.next_draw_no - 1
        values = self.effect_labels + [RANDOM_LABEL]
        for i, eid in enumerate(self.order):
            row = ctk.CTkFrame(self.order_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"{i + 1}回目", width=56, anchor="w").pack(side="left")
            menu = ctk.CTkOptionMenu(row, values=values, width=280, dynamic_resizing=False,
                                     command=lambda v, i=i: self._set_order(i, v))
            menu.set(self._label(eid))
            menu.pack(side="left")
            for text, cmd in (("↑", lambda i=i: self._move_order(i, -1)), ("↓", lambda i=i: self._move_order(i, 1)),
                              ("×", lambda i=i: self._remove_order(i))):
                ctk.CTkButton(row, text=text, width=30, command=cmd, **self.plain).pack(side="left", padx=(4, 0))
            if i == next_i:
                ctk.CTkLabel(row, text="次", text_color=RED).pack(side="left", padx=8)
        self._update_next()

    def _set_order(self, i, label):
        self.order[i] = self.effect_id.get(label, self.order[i])
        self._update_next()

    def _move_order(self, i, d):
        j = i + d
        if 0 <= j < len(self.order):
            self.order[i], self.order[j] = self.order[j], self.order[i]
            self._render_order()

    def _remove_order(self, i):
        del self.order[i]
        self._render_order()

    def _add_order(self):
        self.order.append("normal" if "normal" in self.app.effects else self.effect_id[self.effect_labels[0]])
        self._render_order()

    def _reset_order(self):
        self.order = list(DEFAULT_ORDER)
        self._render_order()

    def _after_order(self):
        return _key(AFTER_ORDER, self.om_after.get(), "fallback")

    def _update_after(self):
        self.om_fallback.configure(state="normal" if self._after_order() == "fallback" else "disabled")
        self._update_next()

    def _override_id(self):
        label = self.om_override.get()
        return None if label == AUTO_LABEL else self.effect_id.get(label)

    def _update_next(self):
        if not hasattr(self, "next_info"):
            return
        es = copy.copy(self.s.effects)
        es.order, es.after_order = self.order, self._after_order()
        es.fallback = self.effect_id.get(self.om_fallback.get(), es.fallback)
        slot = self._override_id() or planned_slot(self.app.next_draw_no, es)
        self.next_info.configure(text=f"第{self.app.next_draw_no}回は {self._label(slot)}")

    def _render_weights(self, weights):
        for child in self.weight_frame.winfo_children():
            child.destroy()
        self.weight_vars, self.weight_pct = {}, {}
        for i, label in enumerate(self.effect_labels):
            eid = self.effect_id[label]
            effect = self.app.effects[eid]
            ctk.CTkLabel(self.weight_frame, text=label, anchor="w").grid(row=i, column=0, sticky="w", pady=1)
            var = tk.StringVar(value=f"{weights.get(eid, effect.weight):g}")
            ent = ctk.CTkEntry(self.weight_frame, textvariable=var, width=60, justify="right")
            ent.grid(row=i, column=1, padx=10, pady=1)
            ent.bind("<KeyRelease>", lambda e: self._update_weights())
            pct = ctk.CTkLabel(self.weight_frame, text="", width=60, anchor="e", text_color=MUTED)
            pct.grid(row=i, column=2, pady=1)
            ctk.CTkLabel(self.weight_frame, text=f"{effect.total_ms(self.app.sounds.length) / 1000:.0f}秒", text_color=MUTED).grid(
                row=i, column=3, padx=10, pady=1)
            self.weight_vars[eid], self.weight_pct[eid] = var, pct
        self._update_weights()

    def _weights(self):
        weights = {}
        for eid, var in self.weight_vars.items():
            if eid in self.app.effects:
                try:
                    weights[eid] = max(0.0, float(var.get()))
                except ValueError:
                    weights[eid] = self.app.effects[eid].weight
        return weights

    def _update_weights(self):
        weights = self._weights()
        total = sum(weights.values())
        for eid, label in self.weight_pct.items():
            label.configure(text=f"{weights.get(eid, 0) / total * 100:.1f}%" if total else "-")

    def _preview(self, record=False):
        eid = self.effect_id.get(self.om_preview.get())
        app = self.app
        if record and eid and not any(s.at is not None for s in app.effects[eid].steps):
            messagebox.showinfo("記録", "この演出には at がないので記録できません", parent=self)
            return
        self._save()
        if eid:
            app.start_draw(preview_effect=eid, record=record)

    def _refresh_effects(self):
        weights = self._weights()
        self._make_effect_labels()
        for menu, extra in ((self.om_fallback, []), (self.om_preview, []), (self.om_override, [AUTO_LABEL])):
            menu.configure(values=extra + self.effect_labels)
            if menu.get() not in extra + self.effect_labels:
                menu.set((extra + self.effect_labels)[0])
        self._render_order()
        self._render_weights(weights)
        self._render_custom()

    # ---- 桁順モード

    def _order_maker(self, body):
        self._heading(body, "桁順モード")
        self._note(body, "止める順に桁をクリックして「作る」を押す")
        row = self._row(body)
        self.picked = []
        self.digit_buttons = []
        for pos in range(self.app.digits):
            b = ctk.CTkButton(row, text="", width=52, height=52, font=ctk.CTkFont(size=20, weight="bold"),
                              command=lambda p=pos: self._pick_digit(p), **self.plain)
            b.pack(side="left", padx=(0, 6))
            self.digit_buttons.append(b)
        ctk.CTkButton(row, text="やり直し", width=80, command=self._clear_digits, **self.plain).pack(
            side="left", padx=(10, 0))

        row = self._row(body, "時間 (ms)")
        self.v_first, self.v_step, self.v_last = tk.StringVar(value="600"), tk.StringVar(value="600"), tk.StringVar(value="900")
        for text, var in (("最初", self.v_first), ("1桁ごと", self.v_step), ("最後", self.v_last)):
            ctk.CTkLabel(row, text=text).pack(side="left", padx=(0, 4))
            ctk.CTkEntry(row, textvariable=var, width=64, justify="right").pack(side="left", padx=(0, 14))

        sounds = [NO_SOUND] + self.app.sounds.files()
        row = self._row(body, "音")
        self.om_stop_sound = ctk.CTkOptionMenu(row, values=sounds, width=150)
        self.om_last_sound = ctk.CTkOptionMenu(row, values=sounds, width=150)
        for text, menu in (("止めるとき", self.om_stop_sound), ("最後", self.om_last_sound)):
            ctk.CTkLabel(row, text=text).pack(side="left", padx=(0, 4))
            menu.set("test.wav" if "test.wav" in sounds else NO_SOUND)
            menu.pack(side="left", padx=(0, 14))

        row = self._row(body, "名前")
        self.v_order_name = tk.StringVar()
        ctk.CTkEntry(row, textvariable=self.v_order_name, width=240, placeholder_text="桁順 31524").pack(side="left")
        ctk.CTkButton(row, text="作る", width=70, command=self._make_order_effect).pack(side="left", padx=8)

        self.custom_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.custom_frame.pack(fill="x", padx=8, pady=(4, 0))
        self._render_custom()

    def _pick_digit(self, pos):
        if pos in self.picked:
            return
        self.picked.append(pos)
        self.digit_buttons[pos].configure(text=str(len(self.picked)), border_color=INK, border_width=2)

    def _clear_digits(self):
        self.picked = []
        for b in self.digit_buttons:
            b.configure(text="", border_color="#bdbdbd", border_width=1)

    def _make_order_effect(self):
        if len(self.picked) != len(self.digit_buttons):
            messagebox.showinfo("桁順モード", "全部の桁をクリックしてください。", parent=self)
            return
        code = order_code(self.picked)
        name = self.v_order_name.get().strip() or f"桁順 {code}"
        if (config.EFFECTS_DIR / f"{ORDER_PREFIX}{code}.toml").exists():
            if not messagebox.askyesno("桁順モード", f"「{code}」はもうあります。上書きしますか？", parent=self):
                return
        stop_sound, last_sound = (("" if m.get() == NO_SOUND else m.get())
                                  for m in (self.om_stop_sound, self.om_last_sound))
        try:
            write_order_effect(
                config.EFFECTS_DIR, name, self.picked,
                step_ms=_int(self.v_step.get(), 600), first_ms=_int(self.v_first.get(), 600),
                last_ms=_int(self.v_last.get(), 900), sound=stop_sound, last_sound=last_sound,
            )
        except OSError as e:
            messagebox.showerror("桁順モード", f"保存できませんでした: {e}", parent=self)
            return
        self.app.reload_effects()
        self._clear_digits()
        self.v_order_name.set("")
        self._refresh_effects()

    def _render_custom(self):
        for child in self.custom_frame.winfo_children():
            child.destroy()
        custom = [e for e in self.app.effects.values() if e.id.startswith(ORDER_PREFIX)]
        if not custom:
            return
        ctk.CTkLabel(self.custom_frame, text="作った演出", text_color=MUTED, anchor="w").pack(fill="x")
        for e in sorted(custom, key=lambda e: e.name):
            row = ctk.CTkFrame(self.custom_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=e.name, width=240, anchor="w").pack(side="left")
            ctk.CTkButton(row, text="削除", width=56, command=lambda e=e: self._delete_custom(e), **self.plain).pack(
                side="left")

    def _delete_custom(self, effect):
        if not messagebox.askyesno("削除", f"「{effect.name}」を削除しますか？", parent=self):
            return
        try:
            (config.EFFECTS_DIR / f"{effect.id}.toml").unlink()
        except OSError as e:
            messagebox.showerror("削除", str(e), parent=self)
            return
        self.app.reload_effects()
        self._refresh_effects()

    # ---- 表示

    def _display_tab(self, body):
        d = self.s.display
        self._heading(body, "画面")
        row = self._row(body, "タイトル")
        self.v_title = tk.StringVar(value=d.title)
        ctk.CTkEntry(row, textvariable=self.v_title, width=320).pack(side="left")
        ctk.CTkLabel(row, text="{year} は今年の西暦になります", text_color=MUTED).pack(side="left", padx=10)

        fonts = [AUTO_FONT] + self.app.families
        self.font_boxes = {}
        for key, label, value in (("digit", "数字のフォント", d.digit_font), ("name", "文字のフォント", d.name_font)):
            box = ctk.CTkComboBox(self._row(body, label), values=fonts, width=300)
            box.set(value or AUTO_FONT)
            box.pack(side="left")
            self.font_boxes[key] = box

        self.v_logo = self._file_row(body, "ロゴ", d.logo_path, IMAGES)
        self.v_credit = self._file_row(body, "同好会ロゴ", d.credit_logo, IMAGES)
        self.v_fullscreen = self._switch(body, "起動時に全画面", d.fullscreen)
        self.v_status = self._switch(body, "回数と残り人数を出す", d.show_status)

        self._heading(body, "タイトル画面")
        self.v_title_screen = self._switch(body, "起動したらタイトル画面を出す (START で動画のあと抽選へ)", d.title_screen)
        self.v_video = self._file_row(body, "動画", d.opening_video,
                                      [("動画", "*.mp4 *.mov *.m4v"), ("すべて", "*.*")])

        self._heading(body, "音")
        row = self._row(body, "音量")
        self.slider_volume = ctk.CTkSlider(row, from_=0, to=1, number_of_steps=20, width=280,
                                           command=lambda v: self.app.sounds.set_volume(v))
        self.slider_volume.set(d.volume)
        self.slider_volume.pack(side="left")
        ctk.CTkButton(row, text="鳴らす", width=70, command=lambda: self.app.sounds.play("test.wav")).pack(
            side="left", padx=8)
        if not self.app.sounds.available:
            self._note(body, f"音が出せません: {self.app.sounds.error}")

    def _file_row(self, body, label, value, filetypes):
        var = tk.StringVar(value=value)
        row = self._row(body, label)
        ctk.CTkEntry(row, textvariable=var, placeholder_text="なし").pack(side="left", fill="x", expand=True,
                                                                         padx=(0, 8))
        ctk.CTkButton(row, text="選択", width=70, command=lambda: self._browse(var, filetypes)).pack(side="left")
        ctk.CTkButton(row, text="外す", width=60, command=lambda: var.set(""), **self.plain).pack(side="left", padx=6)
        return var

    def _browse(self, var, filetypes):
        path = filedialog.askopenfilename(parent=self, filetypes=filetypes)
        if path:
            var.set(relativize(Path(path)))

    # ---- 履歴

    def _history_tab(self, body):
        history = self.app.history
        self._heading(body, "当選履歴")
        if history:
            self._note(body, f"results/{history.path.name}")
        self.history_box = ctk.CTkTextbox(body, height=320, font=ctk.CTkFont(size=14), border_width=1,
                                          border_color="#d0d0d0", fg_color="#ffffff")
        self.history_box.pack(fill="x", padx=8, pady=8)
        row = self._row(body)
        ctk.CTkButton(row, text="直前を取り消す", width=140, command=self._undo).pack(side="left")
        ctk.CTkButton(row, text="リセット", width=100, fg_color=RED, hover_color="#c4000f",
                      command=self._reset_history).pack(side="left", padx=8)
        ctk.CTkButton(row, text="フォルダを開く", width=130, command=self.app.open_results_folder,
                      **self.plain).pack(side="left")
        self._note(body, "ここでの操作はすぐ反映されます。リセット前の履歴は .bak.csv として残ります。")
        self._refresh_history()

    def _refresh_history(self):
        history = self.app.history
        lines = [f"{r.draw_no:>3}  {r.number}  {r.name}  {r.sub}  [{r.effect}]  {r.at}"
                 for r in reversed(history.records)] if history else []
        self.history_box.configure(state="normal")
        self.history_box.delete("1.0", "end")
        self.history_box.insert("1.0", "\n".join(lines) or "まだいません")
        self.history_box.configure(state="disabled")

    def _after_history_change(self):
        self._refresh_history()
        self._render_order()
        self._update_preview()

    def _undo(self):
        history = self.app.history
        if not history or not history.records:
            return
        r = history.records[-1]
        if messagebox.askyesno("取り消し", f"第{r.draw_no}回 {r.number} {r.name} を取り消して抽選に戻しますか？",
                               parent=self):
            self.app.undo_last()
            self._after_history_change()

    def _reset_history(self):
        history = self.app.history
        if not history or not history.records:
            return
        if messagebox.askyesno("リセット", f"当選履歴 {len(history.records)}件をリセットして、全員を抽選に戻しますか？",
                               icon="warning", parent=self):
            self.app.reset_history()
            self._after_history_change()

    # ---- 保存

    def _save(self):
        s = self.s
        s.data = self._data_settings()
        es = s.effects
        es.order = list(self.order)
        es.after_order = self._after_order()
        es.fallback = self.effect_id.get(self.om_fallback.get(), es.fallback)
        es.weights = self._weights()
        es.speed = round(self.slider_speed.get(), 2)
        es.flash = self.v_flash.get()
        d = s.display
        d.title = self.v_title.get()
        fonts = {k: box.get().strip() for k, box in self.font_boxes.items()}
        d.digit_font = "" if fonts["digit"] in ("", AUTO_FONT) else fonts["digit"]
        d.name_font = "" if fonts["name"] in ("", AUTO_FONT) else fonts["name"]
        d.logo_path = self.v_logo.get().strip()
        d.credit_logo = self.v_credit.get().strip()
        d.title_screen = self.v_title_screen.get()
        d.opening_video = self.v_video.get().strip()
        d.fullscreen = self.v_fullscreen.get()
        d.show_status = self.v_status.get()
        d.volume = round(self.slider_volume.get(), 2)
        self.app.apply_settings(s, self._override_id())
