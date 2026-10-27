import json
import re
import tomllib
from dataclasses import dataclass

from .config import RANDOM_SLOT

ACTIONS = {"spin", "blank", "wait", "redraw", "fake", "flash", "colors", "message", "sound"}  # と roll
COLOR = re.compile(r"#[0-9a-fA-F]{6}")
ORDER_PREFIX = "order_"


class EffectError(ValueError):
    pass


@dataclass(frozen=True)
class Step:
    action: str = "spin"
    fix: str = ""
    ms: float = 0.0
    sound: str = ""
    number: str = ""
    text: str = ""
    on: bool = True
    wait: bool = False  # 音が鳴り終わるまで次に進まない
    at: float | None = None  # zero のステップから何ms後に始めるか
    zero: bool = False
    bg: str = ""
    fg: str = ""


@dataclass(frozen=True)
class Effect:
    id: str
    name: str
    weight: float
    steps: tuple
    start_sound: str | None = None  # None ならいつもの開始音

    def total_ms(self, sound_length=None):
        t = zero = 0
        for i, s in enumerate(self.steps):
            if s.zero:
                zero = t
            nxt = self.steps[i + 1] if i + 1 < len(self.steps) else None
            if nxt and nxt.at is not None:
                t = max(t, zero + nxt.at)
            else:
                ms = s.ms
                if s.wait and s.sound and sound_length:
                    ms = max(ms, sound_length(s.sound) * 1000)
                t += ms
        return t

    def sounds(self):
        return {s.sound for s in self.steps if s.sound}


def _parse_step(i, raw):
    if not isinstance(raw, dict):
        raise EffectError(f"{i}番目のステップが変です")
    action = raw.get("action", "spin")
    if action not in ACTIONS:
        raise EffectError(f"{i}番目: action = \"{action}\" は使えません")
    fix = str(raw.get("fix", ""))
    if action == "spin" and (not fix or set(fix) - {"0", "1"}):
        raise EffectError(f"{i}番目: fix は 0 と 1 で書く")
    ms = raw.get("ms", 0)
    if isinstance(ms, bool) or not isinstance(ms, (int, float)) or ms < 0:
        raise EffectError(f"{i}番目: ms がおかしい")
    if action == "fake" and not raw.get("number"):
        raise EffectError(f"{i}番目: fake に number がない")
    for key in ("wait", "zero"):
        if not isinstance(raw.get(key, False), bool):
            raise EffectError(f"{i}番目: {key} は true か false")
    at = raw.get("at")
    if at is not None and (isinstance(at, bool) or not isinstance(at, (int, float)) or at < 0):
        raise EffectError(f"{i}番目: at がおかしい")
    bg, fg = str(raw.get("bg", "")), str(raw.get("fg", ""))
    if action == "colors" and (bg or fg) and not (COLOR.fullmatch(bg) and COLOR.fullmatch(fg)):
        raise EffectError(f"{i}番目: bg と fg は \"#000000\" の形で両方書く")
    return Step(action, fix, float(ms), str(raw.get("sound", "")), str(raw.get("number", "")),
                str(raw.get("text", "")), bool(raw.get("on", True)), raw.get("wait", False),
                None if at is None else float(at), raw.get("zero", False), bg, fg)


def _roll(i, raw):
    # 全部回してから order の順に every ms ごとに1桁ずつ止める、をステップに展開する
    order = str(raw.get("order", ""))
    if not order.isdigit() or "0" in order or len(set(order)) != len(order):
        raise EffectError(f"{i}番目: roll の order は \"5432\" のように桁の番号で書く")
    every = raw.get("every", 160)
    if isinstance(every, bool) or not isinstance(every, (int, float)) or every < 0:
        raise EffectError(f"{i}番目: every がおかしい")
    fixed = ["0"] * max(5, *(int(c) for c in order))
    out = [{"fix": "".join(fixed)}]
    for c in order:
        fixed[int(c) - 1] = "1"
        out.append({"fix": "".join(fixed)})
    for step in out:
        step["ms"] = every
        if raw.get("sound"):
            step["sound"] = raw["sound"]
    for key in ("at", "zero"):
        if key in raw:
            out[0][key] = raw[key]
    return [_parse_step(i, step) for step in out]


def parse_effect(effect_id, data):
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise EffectError("steps がない")
    weight = data.get("weight", 1)
    if isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight < 0:
        raise EffectError("weight がおかしい")
    start_sound = data.get("start_sound")
    if start_sound is not None and not isinstance(start_sound, str):
        raise EffectError("start_sound がおかしい")
    parsed = []
    for i, raw in enumerate(steps, 1):
        if isinstance(raw, dict) and raw.get("action") == "roll":
            parsed += _roll(i, raw)
        else:
            parsed.append(_parse_step(i, raw))
    return Effect(effect_id, str(data.get("name", effect_id)), float(weight), tuple(parsed), start_sound)


def load_effects(directory):
    effects, errors = {}, []
    for path in sorted(directory.glob("*.toml")):
        try:
            with path.open("rb") as f:
                effects[path.stem] = parse_effect(path.stem, tomllib.load(f))
        except (tomllib.TOMLDecodeError, EffectError, OSError) as e:
            errors.append(f"{path.name}: {e}")
    return effects, errors


# effects フォルダが空のとき用
BUILTIN_NORMAL = Effect("normal", "ノーマル", 80, (
    Step(fix="00000", ms=600),
    *(Step(fix=f, ms=600, sound="test.wav") for f in ("10000", "11000", "11100", "11110")),
    Step(fix="11111", ms=900, sound="test.wav"),
))


def normalize_mask(fix, digits):
    # 桁数が違うときは最後の文字をのばすか切る
    if len(fix) < digits:
        fix += fix[-1] * (digits - len(fix))
    return tuple(c == "1" for c in fix[:digits])


def planned_slot(draw_no, es):
    i = draw_no - 1
    if i < len(es.order):
        return es.order[i]
    if es.after_order == "repeat" and es.order:
        return es.order[i % len(es.order)]
    if es.after_order == "random":
        return RANDOM_SLOT
    return es.fallback


def pick_weighted(effects, weights, rng):
    pool = [(e, weights.get(e.id, e.weight)) for e in effects.values()]
    pool = [(e, w) for e, w in pool if w > 0]
    if not pool:
        return None
    return rng.choices([e for e, _ in pool], [w for _, w in pool])[0]


def choose_effect(draw_no, es, effects, rng):
    slot = planned_slot(draw_no, es)
    if slot == RANDOM_SLOT:
        picked = pick_weighted(effects, es.weights, rng)
        if picked:
            return picked
    if slot in effects:
        return effects[slot]
    return effects.get("normal") or next(iter(effects.values()), BUILTIN_NORMAL)


# ---- 桁順モード

def order_code(order):
    # order は止める桁の位置 (0始まり) のリスト
    sep = "" if len(order) <= 9 else "-"
    return sep.join(str(p + 1) for p in order)


def order_steps(order, step_ms, first_ms, last_ms, sound, last_sound):
    fixed = ["0"] * len(order)
    steps = [{"fix": "".join(fixed), "ms": first_ms}]
    for i, pos in enumerate(order):
        fixed[pos] = "1"
        last = i == len(order) - 1
        step = {"fix": "".join(fixed), "ms": last_ms if last else step_ms}
        s = last_sound if last else sound
        if s:
            step["sound"] = s
        steps.append(step)
    return steps


def _toml_value(v):
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def write_order_effect(directory, name, order, step_ms=600, first_ms=600, last_ms=900,
                       sound="test.wav", last_sound="test.wav"):
    code = order_code(order)
    lines = [f"name = {_toml_value(name)}", "weight = 0", f"order = \"{code}\"", "", "steps = ["]
    for step in order_steps(order, step_ms, first_ms, last_ms, sound, last_sound):
        lines.append("  { " + ", ".join(f"{k} = {_toml_value(v)}" for k, v in step.items()) + " },")
    lines.append("]")
    path = directory / f"{ORDER_PREFIX}{code}.toml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---- 記録モードで T を押した時刻で at を書き換える

AT_IN_FILE = re.compile(r"(?<=[{,])(\s*at\s*=\s*)(\d+(?:\.\d+)?)")


def rewrite_at(path, effect, new_at):
    # new_at は {ステップの番号: ms}。ファイルの at = の出てくる順とステップの順は同じ
    text = path.read_text(encoding="utf-8")
    matches = list(AT_IN_FILE.finditer(text))
    at_steps = [i for i, s in enumerate(effect.steps) if s.at is not None]
    if len(matches) != len(at_steps):
        raise EffectError("ファイルの at の数が合わないので書き換えられません")
    for k in reversed(range(len(matches))):
        if at_steps[k] in new_at:
            m = matches[k]
            text = text[:m.start(2)] + str(round(new_at[at_steps[k]])) + text[m.end(2):]
    path.write_text(text, encoding="utf-8")
