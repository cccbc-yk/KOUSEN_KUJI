# 高専祭くじ

```sh
uv run kuji
```

Windows で動かすときは `MANUAL.md` を見る (`start_windows.bat` をダブルクリックで起動)。

起動するとタイトル画面が出る。START (Space) で `Credit/` の動画が流れて、そのあと抽選の画面になる。動画は Space で飛ばせる。
タイトル画面を出さないようにするのは、設定の「表示」でできる。

- Space / Enter: スタート
- S: 設定
- F: 全画面
- Esc: 設定を閉じる / 全画面をやめる
- T: 記録モードの試し再生中に、次に進める (音ハメ用。effects/README.md を参照)

CSVは読むだけで書き換えない。当選者は `results/<CSV名>_当選履歴.csv` に書いていき、そこに載っている人は次から抽選に出ない。やり直すときは設定の「履歴」でリセットする。

演出は `effects/` に1つずつ入っている。書き方は `effects/README.md`。
設定の「初期の順番に戻す」は、前の版と同じ順番になる。

テスト: `uv run pytest`
