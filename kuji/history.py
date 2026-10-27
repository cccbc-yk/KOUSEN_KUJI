# 当選履歴。results/ に別ファイルで追記していき、ここに載っている人は抽選から外す。
import csv
import datetime
import os
from collections import Counter
from dataclasses import dataclass

HEADER = ["回", "日時", "番号", "名前", "サブ", "演出", "元データ"]


@dataclass(frozen=True)
class Record:
    draw_no: int
    at: str
    number: str
    name: str
    sub: str
    effect: str
    key: str

    def to_row(self):
        return [str(self.draw_no), self.at, self.number, self.name, self.sub, self.effect, self.key]


def history_path_for(csv_path, results_dir):
    return results_dir / f"{csv_path.stem}_当選履歴.csv"


class History:
    def __init__(self, path):
        self.path = path
        self.records = self._load()

    def _load(self):
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        records = []
        for row in rows[1:]:
            if len(row) < len(HEADER):
                continue
            try:
                records.append(Record(int(row[0]), *row[1:len(HEADER)]))
            except ValueError:
                continue
        return records

    @property
    def next_draw_no(self):
        return len(self.records) + 1

    def drawn_keys(self):
        return Counter(r.key for r in self.records)

    def add(self, entry, effect_name):
        record = Record(
            self.next_draw_no,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            entry.number, entry.name, entry.sub, effect_name, entry.key,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self.path.exists() or self.path.stat().st_size == 0
        # utf-8-sig は新しいファイルの先頭にだけBOMを付ける (Excel対策)
        with self.path.open("a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(HEADER)
            writer.writerow(record.to_row())
            f.flush()
            os.fsync(f.fileno())
        self.records.append(record)
        return record

    def undo_last(self):
        if not self.records:
            return None
        record = self.records.pop()
        tmp = self.path.with_name(self.path.name + ".tmp")
        with tmp.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(HEADER)
            writer.writerows(r.to_row() for r in self.records)
        os.replace(tmp, self.path)
        return record

    def archive(self):
        # 消さずに日時付きの名前にして残す
        self.records = []
        if not self.path.exists():
            return None
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = self.path.with_name(f"{self.path.stem}_{stamp}.bak.csv")
        self.path.rename(dest)
        return dest
