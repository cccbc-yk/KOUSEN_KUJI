from pydub import AudioSegment

def mp3_to_wav(mp3_filepath, wav_filepath):
    """
    MP3ファイルをWAVファイルに変換する関数だ.

    :param mp3_filepath: 変換したいMP3ファイルのパス (str)
    :param wav_filepath: 出力するWAVファイルのパス (str)
    """
    try:
        # MP3ファイルを読み込む
        audio = AudioSegment.from_mp3(mp3_filepath)

        # WAVファイルとしてエクスポート（保存）する
        audio.export(wav_filepath, format="wav")

        print(f"変換が完了した. '{mp3_filepath}' -> '{wav_filepath}'")

    except FileNotFoundError:
        print("エラー: FFmpeg/Libavが見つからない. システムにインストールし、PATHを設定しているか確認してくれ.")
    except Exception as e:
        print(f"エラーが発生した: {e}")

# --- 使用例 ---
# 変換したいMP3ファイルのパスと出力したいWAVファイルのパスを指定する
input_file = "pr.mp3"
output_file = "pr.wav"

mp3_to_wav(input_file, output_file)