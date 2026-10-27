# 名簿CSVの読み込み。CSVには書き込まない。
import csv
import io
import json
from collections import Counter
from dataclasses import dataclass

ENCODINGS = {
    "auto": ("utf-8-sig", "cp932"),
    "utf-8": ("utf-8-sig",),
    "cp932": ("cp932",),
}


class RosterError(Exception):
    pass


@dataclass(frozen=True)
class Entry:
    number: str
    name: str
    sub: str
    key: str  # 元の行をJSONにしたもの。履歴との照合用


@dataclass
class Table:
    rows: list
    encoding: str

    @property
    def width(self):
        return max((len(r) for r in self.rows), default=0)


def read_table(path, encoding="auto"):
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise RosterError(f"ファイルがありません: {path.name}") from None
    except OSError as e:
        raise RosterError(f"ファイルを開けません: {e}") from None

    for enc in ENCODINGS.get(encoding, ENCODINGS["auto"]):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise RosterError("文字コードが読めません (UTF-8かShift_JISで保存してください)")

    rows = [[cell.strip() for cell in row] for row in csv.reader(io.StringIO(text))]
    rows = [row for row in rows if any(row)]
    return Table(rows, "utf-8" if enc == "utf-8-sig" else enc)


def guess_header(rows):
    # 2行目以降が数字だけの列で、1行目が数字でなければ見出し
    if len(rows) < 2:
        return False
    first, rest = rows[0], rows[1:51]
    for c, cell in enumerate(first):
        column = [r[c] for r in rest if c < len(r)]
        if column and all(v.isdigit() for v in column) and not cell.isdigit():
            return True
    return False


def _cell(row, i):
    return row[i] if 0 <= i < len(row) else ""


def column_labels(table, has_header):
    labels = []
    for c in range(table.width):
        letter = chr(ord("A") + c) if c < 26 else f"#{c + 1}"
        first = _cell(table.rows[0], c) if table.rows else ""
        labels.append(f"{letter}列 {first}" if has_header else f"{letter}列 (例: {first})")
    return labels


def build_entries(table, ds):
    has_header = guess_header(table.rows) if ds.has_header is None else ds.has_header
    if ds.number_col >= table.width:
        raise RosterError("番号の列がありません")
    entries = []
    for row in table.rows[1:] if has_header else table.rows:
        number = _cell(row, ds.number_col)
        if not number:
            continue
        name = _cell(row, ds.name_col)
        if ds.strip_name_spaces:
            name = name.replace("　", "")
        sub = _cell(row, ds.sub_col) if ds.sub_col >= 0 else ""
        entries.append(Entry(number, name, sub, json.dumps(row, ensure_ascii=False)))
    return entries


def remaining(entries, drawn):
    # 同じ行が何個かあっても、当たった数だけ外す
    left = Counter(drawn)
    out = []
    for e in entries:
        if left[e.key] > 0:
            left[e.key] -= 1
        else:
            out.append(e)
    return out


def digit_count(entries, default=5):
    return max((len(e.number) for e in entries), default=default)


def pad_number(number, digits):
    return number.zfill(digits) if number.isdigit() else number.rjust(digits)
