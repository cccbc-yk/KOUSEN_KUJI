import numpy as np
import sys
import pandas as pd
import tkinter as tk
import datetime
import os
import pygame
import threading

# -------------------------------------------------------------------------------
# Pygameサウンドマネージャ (変更なし)
# -------------------------------------------------------------------------------

count = 0

class PygameMixer:
    """Pygameの初期化、サウンドファイルのロード、再生を管理する"""
    def __init__(self):
        try:
            pygame.mixer.init()
            self.sound_hoge = pygame.mixer.Sound("./music/test.wav")        # 最終確定音 (hoge)
            self.sound_push = pygame.mixer.Sound("./music/push.wav")        # スタートボタン音
            self.sound_digit = pygame.mixer.Sound("./music/test.wav")       # 桁確定音
            self.sound_yy = pygame.mixer.Sound("./music/YY.wav")            # YY.wav: きゅいーーんという当たり音 (確変用)
            self.sound_xx = pygame.mixer.Sound("./music/XX.wav")            # YY.wav: きゅいーーんという当たり音 (確変用)
            self.sound_dd = pygame.mixer.Sound("./music/DD.wav")            # YY.wav: きゅいーーんという当たり音 (確変用)
            self.sound_jt = pygame.mixer.Sound("./music/J_bet.wav")            # YY.wav: きゅいーーんという当たり音 (確変用)
            self.sound_jb = pygame.mixer.Sound("./music/J_button.wav")            # YY.wav: きゅいーーんという当たり音 (確変用)
            self.sound_jg = pygame.mixer.Sound("./music/J_gak.wav")            # YY.wav: きゅいーーんという当たり音 (確変用)
            self.sound_jr = pygame.mixer.Sound("./music/J_reba.wav")            # YY.wav: きゅいーーんという当たり音 (確変用)
            self.sound_8 = pygame.mixer.Sound("./music/8.wav")            # YY.wav: きゅいーーんという当たり音 (確変用)
            self.sound_UN_EN = pygame.mixer.Sound("./music/en.wav")            # YY.wav: きゅいーーんという当たり音 (確変用)
            self.sound_UN_rA = pygame.mixer.Sound("./music/rA.wav")            # YY.wav: きゅいーーんという当たり音 (確変用)
            self.sound_UN_deth = pygame.mixer.Sound("./music/deth.wav")            # YY.wav: きゅいーーんという当たり音 (確変用)
            self.sound_UN_resp = pygame.mixer.Sound("./music/resp.wav")            # YY.wav: きゅいーーんという当たり音 (確変用)
            self.sound_UN_suns = pygame.mixer.Sound("./music/suns.wav")            # YY.wav: きゅいーーんという当たり音 (確変用)
            self.sound_UN_hA = pygame.mixer.Sound("./music/hA.wav")            # YY.wav: きゅいーーんという当たり音 (確変用)
            self.sound_UN_pr = pygame.mixer.Sound("./music/pr.wav")            # YY.wav: きゅいーーんという当たり音 (確変用)
            
        except pygame.error as e:
            print(f"警告: Pygameの初期化またはサウンドファイルのロードに失敗しました。音無しで実行します: {e}", file=sys.stderr)
            self.sound_hoge = None
            self.sound_push = None
            self.sound_digit = None
            self.sound_yy = None
            self.sound_xx = None

    def play_sound(self, sound_type):
        """指定されたサウンドを新しいスレッドで非同期再生する"""
        sound_map = {
            "hoge": self.sound_hoge,
            "push": self.sound_push,
            "digit": self.sound_digit,
            "yy": self.sound_yy,
            "xx": self.sound_xx,
            "dd": self.sound_dd,
            "jr": self.sound_jr,
            "jg": self.sound_jg,
            "jb": self.sound_jb,
            "jt": self.sound_jt,
            "8" : self.sound_8,
            "UN_EN": self.sound_UN_EN,
            "UN_rA": self.sound_UN_rA,
            "UN_deth": self.sound_UN_deth,
            "UN_resp": self.sound_UN_resp,
            "UN_suns": self.sound_UN_suns,
            "UN_hA": self.sound_UN_hA,
            "UN_pr": self.sound_UN_pr,
            
        }
        
        sound = sound_map.get(sound_type)
        if sound:
            threading.Thread(target=self._play_sync, args=(sound,)).start()

    def _play_sync(self, sound):
        """サウンドの同期再生（別スレッド用）"""
        sound.play()

# -------------------------------------------------------------------------------
# 抽選ルーレットアプリ クラスベース改良版 (虹色フリッカー修正 & REGENERATE修正)
# -------------------------------------------------------------------------------
class RouletteApp:
    def __init__(self, master):
        self.master = master
        self.mixer = PygameMixer() 
        
        self.ABCDE = 0  
        self.law_num = -1  
        self.df = pd.DataFrame() 
        self.animation_sequence = [] 
        self.current_sequence_index = -1
        
        # --- 画面フリッカー制御用変数 ---
        self.flicker_active = False
        # 虹の7色（赤、橙、黄、緑、青、藍、紫）を定義
        self.flicker_colors = ['#FF0000', '#FF8C00', '#FFFF00', '#008000', '#0000FF', '#4B0082', '#9400D3'] 
        self.flicker_color_index = 0
        self.flicker_interval = 2 # フリッカー時の間隔を2msに加速
        # -----------------------------

        self.setup_data_paths()
        self.setup_gui()
        self.load_data()

    def setup_data_paths(self, test_mode=False):
        current_year = datetime.date.today().year
        self.CSV_PATH = f'./data_{current_year}_utf8.csv'
        self.ENCODING = 'utf-8'

    def load_data(self):
        """CSVファイルを読み込み、GUIの状態を更新する"""
        if not os.path.exists(self.CSV_PATH):
            self.name_var.set("エラー: データファイルが見つかりません。")
            self.button_start["state"] = tk.DISABLED
            return
        
        try:
            self.df = pd.read_csv(self.CSV_PATH, header=None, encoding=self.ENCODING)
            if len(self.df) == 0:
                self.name_var.set("抽選データが空です。")
                self.button_start["state"] = tk.DISABLED
            elif self.button_start["state"] == tk.DISABLED:
                self.button_start["state"] = tk.NORMAL
        except Exception as e:
            self.name_var.set("エラー: データロードに失敗。")
            self.button_start["state"] = tk.DISABLED

    def setup_gui(self):
        """GUI要素のセットアップ"""
        self.master.title('高専くじ ルーレット 虹色フリッカー修正版')
        self.master.configure(bg='white')
        self.master.attributes('-fullscreen', True)

        self.number_var = tk.StringVar(value='99999')
        self.name_var = tk.StringVar(value='Name')
        self.sub_name_var = tk.StringVar(value='')
        
        # ヘッダー
        headline_var = tk.StringVar(value=f'NITYC FES {datetime.date.today().year}')
        self.label_headline = tk.Label(self.master, textvariable=headline_var, font=('Digital-7', 80), bg='white', anchor=tk.CENTER)
        self.label_headline.place(relx=0.5, y=90, anchor=tk.CENTER)

        # 抽選番号表示 (左寄せ)
        self.label_num = tk.Label(self.master, textvariable=self.number_var, font=('Digital-7', 160), anchor=tk.NW, bg='white')
        self.label_num.place(relx=0.1, rely=0.2, anchor=tk.NW)

        # 当選者名表示 (左寄せ)
        self.label_name = tk.Label(self.master, textvariable=self.name_var, font=('Digital-7', 160), anchor=tk.NW, bg='white')
        self.label_name.place(relx=0.1, rely=0.5, anchor=tk.NW)

        # サブネーム表示
        self.label_sub_name = tk.Label(self.master, textvariable=self.sub_name_var, font=('Digital-7', 30), anchor=tk.NW, bg='white')
        self.label_sub_name.place(relx=0.1, rely=0.9, anchor=tk.NW)
        
        # スタートボタン
        self.button_start = tk.Button(self.master, text="START!", font=("", 40), width=16, height=2, command=self.shuffule)
        self.button_start.place(relx=0.5, rely=0.9, anchor=tk.CENTER)

        # 終了ボタン
        tk.Button(self.master, bitmap='error', command=self.master.quit).place(relx=1, y=0, anchor=tk.NE)

        # ロゴ
        try:
            self.logo_image = tk.PhotoImage(file='./nityc_logo.png').subsample(2)
            self.canvas = tk.Canvas(bg='white', width=160, height=160, highlightthickness=0)
            self.canvas.place(relx=0.2, y=100, anchor=tk.CENTER)
            self.canvas.create_image(0, 0, image=self.logo_image, anchor = tk.NW)
        except tk.TclError:
            self.canvas = None

    def _set_bg_color(self, color):
        """背景色をまとめて設定するヘルパー関数"""
        # メインウィンドウ、ラベル、キャンバスの背景色を全て同じ色に設定
        self.master.configure(bg=color)
        self.label_headline.configure(bg=color)
        self.label_num.configure(bg=color)
        self.label_name.configure(bg=color)
        self.label_sub_name.configure(bg=color)
        if self.canvas:
            self.canvas.configure(bg=color)

    def _run_animation_frame(self, mode_list, steps_left, interval_ms, sound_to_play=None):
        """非同期アニメーションの1フレーム処理。`after`で再帰的に呼び出される"""
        
        # --- 虹色フリッカー演出処理 (フリッカー間隔を個別に制御) ---
        if self.flicker_active:
            # 7色を循環
            self.flicker_color_index = (self.flicker_color_index + 1) % len(self.flicker_colors) 
            self._set_bg_color(self.flicker_colors[self.flicker_color_index])
            # フリッカーがアクティブな場合、次の間隔は専用の短いインターバルを使う
            next_interval_ms = self.flicker_interval 
        else:
            # フリッカーがアクティブでない場合、次の間隔はステップに設定されたインターバル (interval_ms) を使う
            next_interval_ms = interval_ms 
        # -----------------------------------------------------

        if steps_left <= 0:
            self.current_sequence_index += 1
            
            # --- シーケンス終了判定と次のアクションの実行 ---
            # 特殊アクションはステップを伴わず即座に次の要素へ進むため while ループで処理する
            while self.current_sequence_index < len(self.animation_sequence):
                next_mode, next_steps, next_interval, next_sound = self.animation_sequence[self.current_sequence_index]
                
                # 特殊アクション判定 (ステップを伴わない即時実行アクション)
                if next_sound == "REGENERATE":
                    self.generate_winner() 
                    print(f"DEBUG: REGENERATE 実行. 当選番号: {self.ABCDE}") 
                    self.current_sequence_index += 1
                    continue # whileループの先頭に戻り、次のシーケンス要素を即座に読み込み
                elif next_sound == "SET_88888":
                    self._set_temp_winner(88888, "再抽選", "アツい!") 
                    print(f"DEBUG: SET_88888 実行.") 
                    self.current_sequence_index += 1
                    continue # whileループの先頭に戻り、次のシーケンス要素を即座に読み込み
                elif next_sound == "FLICKER_ON":
                    self.flicker_active = True
                    self.current_sequence_index += 1
                    continue # 次のシーケンス要素を即座に読み込み
                elif next_sound == "FLICKER_OFF":
                    self.flicker_active = False
                    self._set_bg_color('white') # 背景を白に戻す
                    self.current_sequence_index += 1
                    continue # 次のシーケンス要素を即座に読み込み
                
                # 通常アニメーションの開始: next_soundが特殊アクションでない場合、次のステップを実行
                # ここで再帰呼び出しを行うと while ループを抜ける
                self._run_animation_frame(next_mode, next_steps, next_interval, next_sound)
                return 
            
            # シーケンスが全て終了した場合
            #self.mixer.play_sound("hoge") 
            self.finalize_shuffule()
            return
        
        num_str = self.get_number_at_step(mode_list)
        self.number_var.set(num_str)
        
        # サウンド再生
        # steps_left == 元のステップ数 かつ 特殊アクションでない場合のみ再生
        if steps_left == self.animation_sequence[self.current_sequence_index][1] and sound_to_play and sound_to_play not in ["REGENERATE", "FLICKER_ON", "FLICKER_OFF", "SET_88888"]:
            self.mixer.play_sound(sound_to_play)
        
        steps_left -= 1
        
        # afterで再帰的に呼び出す。フリッカーの有無に応じて次のインターバル時間を決定
        self.master.after(next_interval_ms, lambda: self._run_animation_frame(mode_list, steps_left, interval_ms, sound_to_play))


    def get_number_at_step(self, mode_list):
        """現在のMODEリストに基づき、抽選番号の一部または全部を生成する"""
        n = [int(np.random.rand() * 10 // 1) for _ in range(5)]
        
        for j in range(5):
            if mode_list[j] == 1:
                n[j] = int((self.ABCDE // (10**(4-j))) % 10)
        
        num = sum(n[k] * (10**(4-k)) for k in range(5))
        return str(num).zfill(5)

    def generate_winner(self):
        """当選番号と当選者をCSVデータからランダムに決定する"""
        if len(self.df) == 0:
            return False
            
        law = len(self.df)
        self.law_num = int(law * np.random.rand())
        
        self.ABCDE = int(self.df.iloc[self.law_num, 0])
        self.winner_name = str(self.df.iloc[self.law_num, 1]).replace('　', '')
        self.winner_sub_name = str(self.df.iloc[self.law_num, 2])
        
        return True

    def _set_temp_winner(self, number, name, sub_name):
        """一時的に表示する番号と名前を設定する"""
        self.ABCDE = number
        self.winner_name = name
        self.winner_sub_name = sub_name

    def get_variation_sequence(self):
        """
        抽選演出のパターンを決定し、実行シーケンスを返す。
        
        """
        parameter = int(np.random.rand() * 1000) #1 - 1000
        sequence = []
        global count
        
        INTERVAL = 5 
        
        # ノーマルパターン
        normal_sequence = [
            ([0,0,0,0,0], 80, INTERVAL, None), 
            ([1,0,0,0,0], 80, INTERVAL, "digit"), 
            ([1,1,0,0,0], 80, INTERVAL, "digit"), 
            ([1,1,1,0,0], 80, INTERVAL, "digit"), 
            ([1,1,1,1,0], 80, INTERVAL, "digit"), 
            ([1,1,1,1,1], 120, INTERVAL, "hoge") 
        ]

        # # 確率ロジックの再現とREGENERATE/FLICKERの組み込み
        # if not parameter: # 超絶プレミア級演出 (虹色フリッカー使用) - 1/100
        #     print("超絶プレミア！連続確変演出！")
            
        #     sequence += [([0,0,0,0,0], 80, 2, None)] 
            
        if count == 0: # 激アツ！確変演出 (虹色フリッカー使用) - 1/100
            print("激アツ！確変演出！")
            sequence = [
                ([0,0,0,0,0], 100, INTERVAL, None), ([1,0,0,0,0], 60, INTERVAL, "digit"),
                ([1,1,0,0,0], 100, INTERVAL, "digit"), ([1,1,1,0,0], 60, INTERVAL, "digit"),
                ([1,1,1,1,0], 450, INTERVAL, "digit"),
                ([1,1,1,0,0], 1, 10, "xx"),
                ([1,1,1,0,0], 40, INTERVAL, "digit"),
                ([1,1,0,0,0], 40, INTERVAL, "digit"), ([1,0,0,0,0], 40, INTERVAL, "digit"),
            ]
            
            sequence += [([0,0,0,0,0], 1, 1, "REGENERATE")] 
            
            # 再抽選後の熱い確定演出 (フリッカーON/OFF)
            sequence += [
                ([1,0,0,0,0], 3 , INTERVAL, "yy"), 
                ([1,0,0,0,0], 100, 100, "FLICKER_ON"), # フリッカーON
                ([1,0,0,0,0], 300, INTERVAL, "degit"), # フリッカーON
                ([1,1,0,0,0], 100, INTERVAL, "digit"), # フリッカーON
                ([1,1,1,0,0], 100, INTERVAL, "digit"), 
                ([1,1,1,1,0], 100, INTERVAL, "digit"),
                ([1,1,1,1,1], 1, 1, "FLICKER_OFF") # フリッカーOFF
            ]
            sequence += [([1,1,1,1,1], 200, INTERVAL, "hoge")] # 最終確定
        
        elif count == 1:
            sequence += [
                ([0,0,0,0,0], 80, INTERVAL, None), 
                ([1,0,0,0,0], 80, INTERVAL, "digit"), 
                ([1,1,0,0,0], 300, INTERVAL, "digit"), 
                ([1,1,0,0,1], 80, INTERVAL, "digit"), 
                ([1,1,0,1,1], 200, INTERVAL, "digit"), 
                ([1,1,1,1,1], 120, INTERVAL, "hoge") ,
                ([1,1,1,1,1], 1  , 1        , "hoge"),
            ]
        
        elif  count == 2:
            sequence += [
                ([0,0,0,0,0], 80, INTERVAL, None), 
                ([1,0,0,0,0], 80, INTERVAL, "digit"), 
                ([1,1,0,0,0], 400, INTERVAL, "digit"),
                ([1,1,1,1,1], 1, 10, "dd") 
            ]
        
        elif count == 3:
            sequence += [
                ([0,0,0,0,0], 200, INTERVAL, None), 
                ([0,0,0,0,0], 200, INTERVAL, "jr"), 
                ([1,0,0,0,0], 100, INTERVAL, "jb"), 
                ([1,1,0,0,0], 100, INTERVAL, "jb"),
                ([1,1,1,0,0], 100, INTERVAL, "jb"),
                ([1,1,1,1,0], 100, INTERVAL, "jb"),
                # ([1,1,1,1,0], 200, INTERVAL, "jg"),
                ([1,1,1,1,0], 300, INTERVAL, "jt"),
                ([0,0,0,0,0], 200, INTERVAL, "jr"),
                ([0,0,0,0,0], 1, 1, "REGENERATE"),
                ([1,0,0,0,0], 100, INTERVAL, "jb"),
                ([1,1,0,0,0], 100, INTERVAL, "jb"),
                ([1,1,1,0,0], 100, INTERVAL, "jb"),
                ([1,1,1,1,0], 100, INTERVAL, "jb"),
                ([1,1,1,1,1], 1  ,  INTERVAL, None),
                ([1,1,1,1,1], 1  , 1        , "jg"),
            ]
        
        elif  count == 4 :
            sequence += [
                ([0,0,0,0,0], 80, INTERVAL, None), 
                ([1,0,0,0,0], 80, INTERVAL, "digit"), 
                ([1,1,0,0,0], 100, INTERVAL, "digit"),
                ([1,1,1,0,0], 100, INTERVAL, "digit"),                
                ([1,1,1,0,1], 500, INTERVAL, "digit"),
                ([1,1,1,1,1], 1, 10, "dd") 
            ]
        
        elif  count == 5:
            sequence += [
                ([0,0,0,0,0], 80, INTERVAL, None), 
                ([1,0,0,0,0], 80, INTERVAL, "digit"), 
                ([0,1,0,0,0], 100, INTERVAL, "digit"),
                ([1,0,1,0,0], 100, INTERVAL, "digit"),                
                ([0,1,0,1,0], 200, INTERVAL, "digit"),
                ([1,0,1,0,1], 200, INTERVAL, "digit"),
                ([1,1,1,1,1], 1, 10, "digit") 
            ]
        
        elif  count == 6:
            print("88888表示 再抽選演出（元の番号をスキップ）")
            
            # ① 最初は全桁をランダムに回す
            sequence += [([0,0,0,0,0], 500, INTERVAL, None)] 
            
            # ② 内部で当選番号を88888に設定し直す (特殊アクションで即座に実行)
            sequence += [([1,1,1,1,1], 1, 1, "SET_88888")] 
            
            # ③ 88888を確定させながら演出を挟む（全桁確定モード [1,1,1,1,1] でステップ進行）
            sequence += [
                ([1,0,0,0,0], 120, INTERVAL, "digit"), 
                ([1,1,0,0,0], 120, INTERVAL, "digit"), 
                ([1,1,1,0,0], 120, INTERVAL, "digit"), 
                ([1,1,1,1,0], 120, INTERVAL, "digit"), 
                ([1,1,1,1,1], 120, INTERVAL, "hoge") # 最終確定
            ]
            
            
            # sequence += [([0,0,0,0,0], 100, INTERVAL, "push")] 
            
            sequence += [
                ([0,0,0,0,0], 100, INTERVAL, "push"),
                ([1,0,0,0,0], 100, INTERVAL, "digit"), 
                ([1,1,0,0,0], 100, INTERVAL, "digit"), 
                ([1,1,1,0,0], 100, INTERVAL, "digit"), 
                ([1,1,1,1,0], 150, INTERVAL, "digit"), 
                ([1,1,1,1,1], 100, INTERVAL, "hoge") # 最終確定
            ]
            sequence += [
                ([0,0,0,0,0], 50, INTERVAL, "push"), 
                ([1,0,0,0,0], 80, INTERVAL, "digit"), 
                ([1,1,0,0,0], 100, INTERVAL, "digit"), 
                ([1,1,1,0,0], 100, INTERVAL, "digit"), 
                ([1,1,1,1,0], 200, INTERVAL, "digit"), 
                ([1,1,1,1,1], 200, INTERVAL, "hoge") # 最終確定
            ]
            
            # ④ 全てルーレット状態に戻す
            sequence += [([1,1,1,1,1], 1000, INTERVAL, "8")] 
            
            # ⑤ 本命の再抽選 (当選番号と当選者をCSVから新たに決定)
            sequence += [([0,0,0,0,0], 1, 1, "REGENERATE")] 
            sequence += [([0,0,0,0,0], 500, 1, "push")] 
            
            
            # ⑥ 再抽選後の確定ルーレット演出
            sequence += [
                ([1,0,0,0,0], 100, INTERVAL, "digit"), 
                ([1,1,0,0,0], 100, INTERVAL, "digit"), 
                ([1,1,1,0,0], 100, INTERVAL, "digit"), 
                ([1,1,1,1,0], 120, INTERVAL, "digit"), 
                ([1,1,1,1,1], 100, INTERVAL, "hoge"), # 最終確定
                ([1,1,1,1,1], 1, INTERVAL, "hoge") # 最終確定
            ]
        
        elif  count == 8:
            # ① 最初は全桁をランダムに回す
            sequence += [([0,0,0,0,0], 100, INTERVAL, None)] 
            sequence += [([0,0,0,0,0], 500, 1, "UN_EN")]
            sequence += [
                ([1,0,0,0,0], 100, INTERVAL, "UN_rA"), 
                ([1,0,0,0,1], 100, INTERVAL, "UN_rA"), 
                ([1,0,0,1,1], 100, INTERVAL, "UN_rA"), 
                ([1,0,1,1,1], 300, INTERVAL, "UN_rA"), 
            ]
            sequence += [([1,1,1,1,1], 20, INTERVAL, "UN_rA")]
        
        elif  count == 10:
            # ① 最初は全桁をランダムに回す
            sequence += [([0,0,0,0,0], 100, INTERVAL, None)] 
            sequence += [([0,0,0,0,0], 100, INTERVAL, "UN_pr")] 
            sequence += [([0,0,0,0,0], 500, 1, "UN_EN")]
            sequence += [
                ([1,0,0,0,0], 100, INTERVAL, "UN_rA"), 
                ([1,0,0,0,1], 100, INTERVAL, "UN_rA"), 
                ([1,0,0,1,1], 100, INTERVAL, "UN_rA"), 
                ([1,0,1,1,1], 20, INTERVAL, "UN_rA"), 
            ]
            sequence += [([1,0,1,1,1], 500, INTERVAL, "UN_deth")]
            sequence += [([1,0,1,1,1], 1000, 1, "UN_suns")]
            sequence += [([0,0,0,0,0], 500, 1, "UN_resp")]
            sequence += [([0,0,0,0,0], 1, 1, "REGENERATE")]
            
            sequence += [
                ([1,0,0,0,0], 100, INTERVAL, "UN_hA"), 
                ([1,1,0,0,0], 100, INTERVAL, "UN_hA"), 
                ([1,1,1,0,0], 100, INTERVAL, "UN_hA"), 
                ([1,1,1,1,0], 100, INTERVAL, "UN_hA"), 
                ([1,1,1,1,1], 100, INTERVAL, "UN_hA"),
            ]
            
            
        
        else: # ノーマルパターン (約 97.5% の確率)
            print("ノーマル演出")
            sequence = normal_sequence

        count = count + 1
        return sequence

    def delete_winner(self):
        """当選データをCSVから削除する"""
        if self.law_num != -1:
            self.df = self.df.drop(self.law_num, axis=0)
            self.df.to_csv(self.CSV_PATH, index=False, header=None, encoding=self.ENCODING)
            self.law_num = -1

    def finalize_shuffule(self):
        """抽選アニメーション終了後の処理"""
        self.flicker_active = False
        self._set_bg_color('white') 
        
        self.number_var.set(str(self.ABCDE).zfill(5))
        self.name_var.set(self.winner_name)
        self.sub_name_var.set(self.winner_sub_name)

        # 抽選が再抽選演出 (SET_88888) で一時停止している場合、ここでは削除処理を行わない
        # 最終的な確定後（REGENERATE後）にlaw_numが設定されていれば削除を行う
        if self.ABCDE != 88888:
            self.delete_winner()
            self.load_data() 
    
    def shuffule(self):
        """STARTボタンが押されたときのメイン処理"""
        self.button_start["state"] = tk.DISABLED
        self.name_var.set('')
        self.sub_name_var.set('')
        self.number_var.set('99999')
        
        self.mixer.play_sound("push") 

        if not self.generate_winner():
            self.load_data() 
            return

        self.animation_sequence = self.get_variation_sequence()
        
        if self.animation_sequence:
            self.current_sequence_index = 0
            first_mode, first_steps, first_interval, first_sound = self.animation_sequence[0]
            
            # 初回アクションが特殊な場合も、_run_animation_frame に任せる
            if first_sound in ["REGENERATE", "FLICKER_ON", "FLICKER_OFF", "SET_88888"]:
                # ステップを0として処理を開始することで、即座に while ループに入らせる
                self._run_animation_frame(first_mode, 0, first_interval, first_sound)
                return
            
            # 通常のアニメーション実行を開始
            self._run_animation_frame(first_mode, first_steps, first_interval, first_sound)
        else:
            self.finalize_shuffule()


# -------------------------------------------------------------------------------
# アプリケーションの実行
# -------------------------------------------------------------------------------
if __name__ == '__main__':
    root = tk.Tk()
    app = RouletteApp(root)
    root.mainloop()