import hashlib
import random
import tomllib
from collections import Counter

import pytest

from kuji import config
from kuji.config import DEFAULT_ORDER, RANDOM_SLOT, DataSettings, EffectSettings
from kuji.effects import (
    EffectError, choose_effect, load_effects, normalize_mask, parse_effect, planned_slot, rewrite_at,
    write_order_effect,
)
from kuji.history import History, history_path_for
from kuji.performance import Performance
from kuji.roster import Entry, build_entries, guess_header, read_table, remaining

CSV_TEXT = "学籍番号,氏名,カナ氏名\n26001,山田　太郎,ﾔﾏﾀﾞ ﾀﾛｳ\n26002,佐藤　花子,ｻﾄｳ ﾊﾅｺ\n26003,鈴木　一郎,ｽｽﾞｷ ｲﾁﾛｳ\n"
POOL = [Entry(str(26000 + i), f"名前{i}", "", f"k{i}") for i in range(50)]


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")
    return path


@pytest.fixture
def effects():
    return load_effects(config.EFFECTS_DIR)[0]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_read_utf8_with_header(csv_file):
    table = read_table(csv_file)
    assert guess_header(table.rows)
    entries = build_entries(table, DataSettings())
    assert [e.number for e in entries] == ["26001", "26002", "26003"]
    assert entries[0].name == "山田太郎"
    assert entries[0].sub == "ﾔﾏﾀﾞ ﾀﾛｳ"


def test_read_shift_jis(tmp_path):
    path = tmp_path / "sjis.csv"
    path.write_bytes(CSV_TEXT.replace("ﾔﾏﾀﾞ ﾀﾛｳ", "ヤマダ").encode("cp932"))
    table = read_table(path)
    assert table.encoding == "cp932"
    assert build_entries(table, DataSettings(strip_name_spaces=False))[0].name == "山田　太郎"


def test_no_header(tmp_path):
    path = tmp_path / "plain.csv"
    path.write_text("26001,山田\n26002,佐藤\n", encoding="utf-8")
    table = read_table(path)
    assert not guess_header(table.rows)
    assert len(build_entries(table, DataSettings())) == 2


def test_remaining_with_duplicates():
    a = Entry("1", "A", "", "k1")
    entries = [a, a, Entry("2", "B", "", "k2")]
    assert remaining(entries, Counter({"k1": 1})) == [a, entries[2]]


def test_history_does_not_touch_csv(csv_file, tmp_path):
    before = sha(csv_file)
    entries = build_entries(read_table(csv_file), DataSettings())
    history = History(history_path_for(csv_file, tmp_path / "results"))
    history.add(entries[1], "ノーマル")
    history.add(entries[0], "確変")
    assert sha(csv_file) == before

    reloaded = History(history.path)
    assert reloaded.next_draw_no == 3
    assert remaining(entries, reloaded.drawn_keys()) == [entries[2]]
    assert history.path.read_bytes().count(b"\xef\xbb\xbf") == 1

    assert reloaded.undo_last().name == "山田太郎"
    assert remaining(entries, History(history.path).drawn_keys()) == [entries[0], entries[2]]

    backup = reloaded.archive()
    assert backup.exists() and not history.path.exists()
    assert History(history.path).next_draw_no == 1
    assert sha(csv_file) == before


def test_bundled_effects(effects):
    assert load_effects(config.EFFECTS_DIR)[1] == []
    assert all(eid in effects for eid in DEFAULT_ORDER)
    sounds = {s for e in effects.values() for s in e.sounds()}
    assert all((config.SOUNDS_DIR / s).exists() for s in sounds)


def test_choose_effect(effects):
    rng = random.Random(0)
    es = EffectSettings(order=["kakuhen", "dd"], fallback="normal")
    assert [choose_effect(n, es, effects, rng).id for n in (1, 2, 3, 4)] == ["kakuhen", "dd", "normal", "normal"]
    es.after_order = "repeat"
    assert [planned_slot(n, es) for n in (3, 4, 5)] == ["kakuhen", "dd", "kakuhen"]
    es.after_order = "random"
    es.weights = {eid: 0 for eid in effects} | {"tobi": 1}
    assert planned_slot(3, es) == RANDOM_SLOT
    assert choose_effect(3, es, effects, rng).id == "tobi"


def test_parse_errors():
    with pytest.raises(EffectError):
        parse_effect("x", {"steps": [{"fix": "12000", "ms": 10}]})
    with pytest.raises(EffectError):
        parse_effect("x", {"steps": [{"action": "explode"}]})
    with pytest.raises(EffectError):
        parse_effect("x", {"steps": []})


def test_normalize_mask():
    assert normalize_mask("11000", 5) == (True, True, False, False, False)
    assert normalize_mask("11111", 6) == (True,) * 6
    assert normalize_mask("11110", 4) == (True,) * 4


def test_order_effect(tmp_path):
    path = write_order_effect(tmp_path, "桁順 31524", [2, 0, 4, 1, 3], step_ms=500, sound="test.wav", last_sound="")
    assert path.name == "order_31524.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    effect = parse_effect(path.stem, data)
    assert effect.name == "桁順 31524"
    assert [s.fix for s in effect.steps] == ["00000", "00100", "10100", "10101", "11101", "11111"]
    assert effect.steps[1].sound == "test.wav" and effect.steps[-1].sound == ""
    assert effect.steps[2].ms == 500 and effect.steps[-1].ms == 900

    seen = []
    perf = Performance(effect, 5, lambda: POOL[7])
    perf.start(0.0)
    for t in range(0, 4000, 50):
        perf.update(t / 1000)
        seen.append(tuple(i for i, fixed in enumerate(perf.mask) if fixed))
    order = []
    for fixed in seen:
        order += [i for i in fixed if i not in order]
    assert order == [2, 0, 4, 1, 3]


def run(effect, **kw):
    rng = random.Random(1)
    picks, played, flashes = [], [], []

    def pick():
        picks.append(rng.choice(POOL))
        return picks[-1]

    perf = Performance(effect, 5, pick, play=lambda n, v: played.append(n), rng=rng, **kw)
    t = 0.0
    perf.start(t)
    while not perf.done:
        t += 0.016
        perf.update(t)
        flashes.append(perf.flash)
    return perf, picks, played, flashes, t


def test_kakuhen(effects):
    perf, picks, played, flashes, t = run(effects["kakuhen"])
    assert len(picks) == 2
    assert perf.winner is picks[-1]
    assert perf.target == perf.winner.number
    assert all(fixed for _, fixed in perf.frame_digits())
    assert any(flashes) and not perf.flash
    assert "XX.wav" in played and "YY.wav" in played
    assert t == pytest.approx(effects["kakuhen"].total_ms() / 1000, abs=0.05)


def test_no_flash_and_speed(effects):
    _, _, _, flashes, t = run(effects["kakuhen"], flash_enabled=False, speed=2.0)
    assert not any(flashes)
    assert t == pytest.approx(effects["kakuhen"].total_ms() / 2000, abs=0.05)


def test_fake_then_real(effects):
    perf = Performance(effects["fake88888"], 5, lambda: POOL[3], rng=random.Random(0))
    perf.start(0.0)
    perf.update(4.0)
    assert perf.target == "88888"
    perf.update(1000.0)
    assert perf.done and perf.target == "26003"


def test_skip(effects):
    perf = Performance(effects["normal"], 5, lambda: POOL[0])
    perf.start(0.0)
    perf.skip()
    assert perf.done and perf.target == "26000"


def test_yokai(effects):
    effect = effects["yokai"]
    assert effect.start_sound == ""
    lengths = {"yokai/OH.wav": 2.4, "yokai/HYAKURETU.wav": 2.89, "yokai/HIT.wav": 2.69, "yokai/PREKAKUTEI.wav": 1.13}
    rng = random.Random(3)
    picks, played = [], []

    def pick():
        picks.append(rng.choice(POOL))
        return picks[-1]

    perf = Performance(effect, 5, pick, speed=2.0, play=lambda n, v: played.append((n, t)),
                       sound_length=lambda n: lengths.get(n, 0), rng=rng)
    t = 0.0
    perf.start(t)
    frames = []
    while not perf.done:
        frames.append((t, perf.blank, perf.mask, perf.target))
        t = round(t + 0.01, 2)
        perf.update(t)

    # OH の途中 (1.2秒、速さ2倍なので0.6秒) から回る
    spin_at = 0.6
    assert spin_at < 2.4
    assert all(blank for at, blank, _, _ in frames if at < spin_at - 0.01)
    assert not any(blank for at, blank, _, _ in frames if at >= spin_at + 0.01)
    start = {name: at for name, at in reversed(played)}
    assert start["yokai/TMPROCK.wav"] > spin_at
    assert start["yokai/HIT.wav"] >= start["yokai/HYAKURETU.wav"] + 2.89 - 0.01
    last_tmprock = max(at for name, at in played if name == "yokai/TMPROCK.wav")
    assert start["yokai/HYAKURETU.wav"] - last_tmprock == pytest.approx((400 + 2000) / 2 / 1000, abs=0.02)

    # 1,2,3,5桁目の順に止まり、ここは最初の当選者の数字のまま。選び直しは HIT で全部回り出すとき
    order = []
    for _, _, mask, _ in frames:
        order += [i for i, fixed in enumerate(mask) if fixed and i not in order]
        if mask == (True,) * 5:
            break
    assert order[:4] == [0, 1, 2, 4]
    assert len(picks) == 2
    hit_at = start["yokai/HIT.wav"]
    before_hit = [f for f in frames if f[2] == (True, True, True, False, True) and f[0] < hit_at]
    assert before_hit and all(f[3] == pad(picks[0].number) for f in before_hit)
    assert all(f[2] == (False,) * 5 for f in frames if hit_at <= f[0] < hit_at + 2.68)

    # 全桁そろってから PREKAKUTEI、鳴り終わったら名前と同時に KAKUTEI
    assert start["yokai/PREKAKUTEI.wav"] + 1.13 == pytest.approx(start["yokai/KAKUTEI.wav"], abs=0.02)
    assert perf.target == picks[-1].number
    assert played[-1][0] == "yokai/KAKUTEI.wav"
    assert all(s in {n for n, _ in played} for s in effect.sounds())


def pad(number):
    return number.zfill(5)


# 本物の vivant.toml は手で音ハメするので、テストではこの見本を使う
VIVANT_SAMPLE = """
name = "VIVANT"
start_sound = ""
steps = [
  { action = "blank", sound = "vivant/PRE.wav", zero = true },
  { action = "colors", bg = "#000000", fg = "#d7000f", at = 7680 },
  { action = "sound", sound = "push.wav", at = 12710 },
  { fix = "00000", sound = "vivant/START.wav", wait = true, at = 13210 },
  { fix = "00000", sound = "vivant/MUSIC.wav", zero = true },
  { fix = "10000", sound = "test.wav", at = 3170 },
  { fix = "11000", sound = "test.wav", at = 4150 },
  { fix = "11100", sound = "test.wav", at = 6070 },
  { fix = "11110", sound = "test.wav", at = 7910 },
  { fix = "11111", sound = "test.wav", at = 9770 },
  { fix = "11111", at = 10710 },
]
"""


@pytest.fixture
def vivant():
    return parse_effect("vivant", tomllib.loads(VIVANT_SAMPLE))


def test_vivant(vivant):
    effect = vivant
    lengths = {"vivant/PRE.wav": 12.71, "vivant/START.wav": 2.25, "vivant/MUSIC.wav": 16.26}
    played = []
    perf = Performance(effect, 5, lambda: POOL[5], speed=2.0, play=lambda n, v: played.append((n, t)),
                       sound_length=lambda n: lengths.get(n, 0), rng=random.Random(0))
    t = 0.0
    perf.start(t)
    frames = []
    while not perf.done:
        frames.append((t, perf.blank, perf.colors, perf.mask))
        t = round(t + 0.01, 2)
        perf.update(t)
    start = dict((n, at) for n, at in played)

    # PRE の 7.68 秒で赤と黒になる。at は速さ2倍でも変わらない
    assert all(c is None for at, _, c, _ in frames if at < 7.67)
    assert all(c == ("#000000", "#d7000f") for at, _, c, _ in frames if at >= 7.69)
    assert all(blank for at, blank, _, _ in frames if at < 13.20)
    assert start["push.wav"] == pytest.approx(12.71, abs=0.011)
    assert start["vivant/START.wav"] == pytest.approx(13.21, abs=0.011)
    assert start["vivant/MUSIC.wav"] == pytest.approx(13.21 + 2.25, abs=0.011)

    # MUSIC の頭から決めた時刻に1桁ずつ止まる
    music = start["vivant/MUSIC.wav"]
    for k, at in enumerate([3.17, 4.15, 6.07, 7.91, 9.77]):
        fixed = next(f for f in frames if sum(f[3]) == k + 1)
        assert fixed[0] - music == pytest.approx(at, abs=0.011)
    assert t - music == pytest.approx(10.71, abs=0.011)
    assert perf.colors == ("#000000", "#d7000f")
    assert effect.total_ms(lambda n: lengths.get(n, 0)) == pytest.approx((13.21 + 2.25 + 10.71) * 1000)
    assert [n for n, _ in played].count("test.wav") == 5


def test_rewrite_at(vivant, tmp_path):
    path = tmp_path / "vivant.toml"
    path.write_text(VIVANT_SAMPLE, encoding="utf-8")
    effect = vivant
    rewrite_at(path, effect, {5: 3000.4, 10: 11000})
    new = parse_effect("vivant", tomllib.loads(path.read_text(encoding="utf-8")))
    assert [s.at for s in new.steps if s.at is not None] == [7680, 12710, 13210, 3000, 4150, 6070, 7910, 9770, 11000]
    assert new.steps[4].sound == "vivant/MUSIC.wav" and new.name == "VIVANT"


def test_colors_must_be_pairs():
    with pytest.raises(EffectError):
        parse_effect("x", {"steps": [{"action": "colors", "bg": "#000000"}]})
    with pytest.raises(EffectError):
        parse_effect("x", {"steps": [{"action": "colors", "bg": "black", "fg": "red"}]})
    assert parse_effect("x", {"steps": [{"action": "colors"}]}).steps[0].bg == ""


def test_record_mode(vivant):
    effect = vivant
    lengths = {"vivant/PRE.wav": 12.71, "vivant/START.wav": 2.25}
    perf = Performance(effect, 5, lambda: POOL[5], sound_length=lambda n: lengths.get(n, 0), record=True)
    perf.start(0.0)
    perf.update(30.0)
    assert perf.waiting_tap and perf.colors is None   # at のステップは押すまで始まらない
    assert perf.tap(31.0) == (1, 31000.0)
    assert perf.colors == ("#000000", "#d7000f")
    assert perf.tap(32.0) == (2, 32000.0)
    assert perf.tap(32.5) == (3, 32500.0)
    perf.update(34.75)                                # START が鳴り終わって MUSIC (zero)
    assert perf.zero_index == 4 and perf.waiting_tap
    taps = [perf.tap(34.75 + t) for t in (1.0, 2.0, 3.0, 4.0, 5.0, 6.5)]
    assert [i for i, _ in taps] == [5, 6, 7, 8, 9, 10]
    assert [round(ms) for _, ms in taps] == [1000, 2000, 3000, 4000, 5000, 6500]
    assert perf.done and perf.tap(50.0) is None


def test_many_redraws():
    effect = parse_effect("x", tomllib.loads("""
steps = [
  { fix = "00000", ms = 300 },
  { fix = "11100", ms = 2000 },
  { action = "redraw" },
  { fix = "00000", ms = 500, zero = true },
  { action = "redraw", at = 500 }, { fix = "00000" }, { fix = "11111", at = 800 },
  { action = "redraw", at = 1100 }, { fix = "00000" }, { fix = "11111", at = 1400 },
  { action = "redraw", at = 1700 }, { fix = "00000" },
  { fix = "11111", sound = "end.wav", at = 2000 },
]
"""))
    rng = random.Random(5)
    picks = []

    def pick():
        picks.append(rng.choice(POOL))
        return picks[-1]

    played = []
    perf = Performance(effect, 5, pick, play=lambda n, v: played.append(n), rng=random.Random(1))
    perf.start(0.0)
    for t in (0.31, 1.0, 2.29):                      # 3桁止まったまま2秒
        perf.update(t)
        assert [f for _, f in perf.frame_digits()] == [True, True, True, False, False]
    perf.update(2.31)
    assert not any(f for _, f in perf.frame_digits())
    perf.update(2.3 + 0.85)
    assert perf.target == pad(picks[2].number) and all(f for _, f in perf.frame_digits())
    perf.update(10.0)
    assert perf.done and played == ["end.wav"]
    assert len(picks) == 5 and perf.winner is picks[-1]


def test_roll():
    effect = parse_effect("x", {"steps": [{"action": "roll", "order": "5432", "every": 160, "sound": "a.wav", "at": 200}]})
    assert [s.fix for s in effect.steps] == ["00000", "00001", "00011", "00111", "01111"]
    assert all(s.ms == 160 and s.sound == "a.wav" for s in effect.steps)
    assert effect.steps[0].at == 200 and all(s.at is None for s in effect.steps[1:])
    with pytest.raises(EffectError):
        parse_effect("x", {"steps": [{"action": "roll", "order": "5502"}]})


def test_naoya_never_shows_a_loser(effects):
    # 外れた人の下4桁 (学籍番号が特定できる) がそろって見えることがないか。時刻を手で変えても守られているか
    effect = effects["naoya"]
    lengths = {"naoya/WAIT.wav": 1.73, "naoya/HIDOI.wav": 5.0, "naoya/BUTI.wav": 2.97, "naoya/AIZO.wav": 20.88}
    rng = random.Random(2)
    picks, played = [], []

    def pick():
        picks.append(rng.choice(POOL))
        return picks[-1]

    perf = Performance(effect, 5, pick, play=lambda n, v: played.append((n, t)), sound_length=lambda n: lengths.get(n, 0),
                       rng=random.Random(0))
    t = 0.0
    perf.start(t)
    full = []
    while not perf.done:
        if all(perf.mask[1:]):
            full.append((t, perf.target, len(picks)))
        t = round(t + 0.01, 2)
        perf.update(t)
    assert len(picks) > 20
    assert full and all(n == len(picks) and target == pad(picks[-1].number) for _, target, n in full)
    oreya = next(at for n, at in played if n == "naoya/OREYA.wav")
    assert full[0][0] > oreya and t > full[0][0]   # OREYA のあとで全部そろい、さらにあとで名前


def test_opening_video_audio():
    from kuji.video import decode_audio
    pcm = decode_audio(config.BASE_DIR / "Credit/supported_CCBYC.mp4", 44100, 2)
    assert pcm.dtype.name == "int16"
    assert pcm.size / 2 / 44100 == pytest.approx(7.87, abs=0.05)


def test_draq(effects):
    effect = effects["draq"]
    assert effect.start_sound == ""
    events, t = [], 0.0
    perf = Performance(effect, 5, lambda: POOL[9], play=lambda n, v: events.append((round(t, 2), "play", n)),
                       stop=lambda n: events.append((round(t, 2), "stop", n)),
                       sound_length=lambda n: {"draq/END.wav": 1.43}.get(n, 0))
    perf.start(t)
    order, colors = [], set()
    while not perf.done:
        order += [i for i, f in enumerate(perf.mask) if f and i not in order]
        colors.add(perf.colors)
        t = round(t + 0.01, 2)
        perf.update(t)
    assert order == [0, 1, 3, 4, 2]                    # 3桁目は後回し
    assert colors == {("#000000", "#ffffff")} and perf.font == "DotGothic16"
    names = [n for _, kind, n in events if kind == "play"]
    assert names.count("draq/DAMEGE.wav") == 4 and names.count("draq/MISS.wav") == 1
    assert names.count("draq/KAISIN.wav") == 1 and names[-1] == "draq/LEVEL.wav"
    stop_at = next(at for at, kind, n in events if kind == "stop" and n == "draq/BGM.wav")
    end_at = next(at for at, kind, n in events if n == "draq/END.wav")
    level_at = next(at for at, kind, n in events if n == "draq/LEVEL.wav")
    assert stop_at == end_at and level_at == pytest.approx(end_at + 1.43, abs=0.02) and t == level_at
    assert ("draq/BGM.wav" not in names[names.index("draq/END.wav"):])


def test_step_volume(effects):
    played = []
    perf = Performance(effects["draq"], 5, lambda: POOL[0], play=lambda n, v: played.append((n, v)))
    perf.start(0.0)
    perf.update(100.0)
    volumes = dict(played)
    assert volumes["draq/BGM.wav"] == 0.5 and volumes["draq/DAMEGE.wav"] == 1.0
    with pytest.raises(EffectError):
        parse_effect("x", {"steps": [{"fix": "11111", "sound": "a.wav", "volume": 1.5}]})


def test_milk(effects):
    effect = effects["milk"]
    colors = ["#ffffff", "#7fd3f7", "#ff8fc8", "#ffe600", "#e60012"]
    played, t = [], 0.0
    perf = Performance(effect, 5, lambda: POOL[4], play=lambda n, v: played.append((round(t, 2), n, v)))
    perf.start(t)
    order, confetti_from, bursts = [], None, []
    while not perf.done:
        order += [i for i, f in enumerate(perf.mask) if f and i not in order]
        if perf.confetti and confetti_from is None:
            confetti_from = t
        while perf.bursts:
            bursts.append((t, perf.bursts.pop(0)))
        t = round(t + 0.01, 2)
        perf.update(t)
    bursts += [(t, b) for b in perf.bursts]
    assert order == [0, 1, 2, 3, 4]
    assert perf.cards == tuple(colors) and perf.colors == ("#141414", "#ffffff")
    assert confetti_from == pytest.approx(6.02, abs=0.011) and perf.confetti
    assert [b for _, b in bursts] == [200, 200] and t == pytest.approx(14.07, abs=0.011)
    assert ("milk/METSU.wav", 0.5) in [(n, v) for _, n, v in played]


def test_cards_and_confetti_parse():
    step = parse_effect("x", {"steps": [{"action": "confetti", "burst": 50}]}).steps[0]
    assert step.burst == 50 and step.on is None          # burst だけなら降らせ続けるかは変えない
    with pytest.raises(EffectError):
        parse_effect("x", {"steps": [{"action": "cards", "fill": ["white"]}]})
