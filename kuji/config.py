import datetime
import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
EFFECTS_DIR = BASE_DIR / "effects"
SOUNDS_DIR = BASE_DIR / "music"
RESULTS_DIR = BASE_DIR / "results"
SETTINGS_PATH = BASE_DIR / "settings.json"

RANDOM_SLOT = "*random*"

# 前の版の count の分岐と同じ順番
DEFAULT_ORDER = [
    "kakuhen", "tobi", "dd", "slot", "last_dd", "alternate",
    "fake88888", "normal", "un", "normal", "un_revive",
]


@dataclass
class DataSettings:
    csv_path: str = ""
    encoding: str = "auto"
    has_header: bool | None = None
    number_col: int = 0
    name_col: int = 1
    sub_col: int = 2
    strip_name_spaces: bool = True


@dataclass
class EffectSettings:
    order: list[str] = field(default_factory=lambda: list(DEFAULT_ORDER))
    after_order: str = "fallback"
    fallback: str = "normal"
    weights: dict[str, float] = field(default_factory=dict)
    speed: float = 1.0
    flash: bool = True
    start_sound: str = "push.wav"


@dataclass
class DisplaySettings:
    title: str = "NITYC FES {year}"
    digit_font: str = ""
    name_font: str = ""
    fullscreen: bool = True
    volume: float = 0.8
    logo_path: str = "rogo.png"
    show_status: bool = True
    title_screen: bool = True
    opening_video: str = "Credit/supported_CCBYC.mp4"
    credit_logo: str = "Credit/club_logo.png"


@dataclass
class Settings:
    data: DataSettings = field(default_factory=DataSettings)
    effects: EffectSettings = field(default_factory=EffectSettings)
    display: DisplaySettings = field(default_factory=DisplaySettings)


def _fill(cls, raw):
    # 型が合わない値と知らないキーは無視
    obj = cls()
    if not isinstance(raw, dict):
        return obj
    for f in fields(cls):
        if f.name not in raw:
            continue
        value, default = raw[f.name], getattr(obj, f.name)
        if default is None:
            ok = value is None or isinstance(value, bool)
        elif isinstance(default, bool):
            ok = isinstance(value, bool)
        elif isinstance(default, float):
            ok = isinstance(value, (int, float)) and not isinstance(value, bool)
            value = float(value) if ok else value
        else:
            ok = isinstance(value, type(default)) and not isinstance(value, bool)
        if ok:
            setattr(obj, f.name, value)
    return obj


def load(path=None):
    path = path or SETTINGS_PATH
    raw = {}
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = {}
    settings = Settings(
        data=_fill(DataSettings, raw.get("data")),
        effects=_fill(EffectSettings, raw.get("effects")),
        display=_fill(DisplaySettings, raw.get("display")),
    )
    if not settings.data.csv_path:
        default_csv = BASE_DIR / f"data_{datetime.date.today().year}_utf8.csv"
        if default_csv.exists():
            settings.data.csv_path = default_csv.name
    return settings


def save(settings, path=None):
    path = path or SETTINGS_PATH
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def resolve_path(value):
    p = Path(value).expanduser()
    return p if p.is_absolute() else BASE_DIR / p


def relativize(path):
    try:
        return str(path.resolve().relative_to(BASE_DIR))
    except ValueError:
        return str(path)


def format_title(title):
    return title.replace("{year}", str(datetime.date.today().year))
