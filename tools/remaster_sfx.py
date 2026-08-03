#!/usr/bin/env python3
"""音效母帶重製：把過關歡呼／失敗音效拉到跟關卡音樂同一個「聽感音量」。

為什麼跟音樂用不同指標：音效是 2~4 秒的短爆發，整檔 RMS 會被前後靜音拉低，
所以改用 **響段響度**＝把音檔切 0.4 秒一格、取最響的 1/4 格平均（近似人耳對「這聲多大」的印象）。
目標值 `TARGET_SFX_LOUD` 就是關卡音樂的響段響度。

處理鏈：**只調音量**（拉到目標響段；只有會削波時才等比例壓回來）→ 寫回原格式。
⚠️ **不做壓縮**（2026-08-03 使用者裁示「全拿掉壓縮」）——壓縮會吃掉動態、抬起雜訊。

⚠️ 量立體聲檔要用 **(L+R)/2** 自己混，不要用 `ffmpeg -ac 1`：
   它的降混會把兩聲道相加，量出來會比實際大（實測歡呼被算成峰值 1.39）。

用法：
    python3 tools/remaster_sfx.py            # 檢查全部，偏離才處理
    python3 tools/remaster_sfx.py cheer      # 只處理指定檔案
"""
import os
import subprocess
import sys

import numpy as np

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOUNDS = os.path.join(PROJ, "sounds")
TARGET_SFX_LOUD = 0.226     # -12.9 dBFS：關卡音樂(零壓縮版)的響段響度
                            # (2026-08-03 全面拿掉壓縮後，音樂降了約 6dB，音效跟著降)
TOLERANCE_DB = 1.5          # 差這麼多以內就不動(避免每次重壓越壓越扁)
FILES = ["cheer.wav", "cheer.mp3", "fail.wav"]


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=sample_rate,channels", "-of", "csv=p=0:nk=1", path],
                         capture_output=True, text=True, check=True).stdout
    sr, ch = out.replace("\n", ",").strip(",").split(",")[:2]
    return int(sr), int(ch)


def decode(path, sr, ch):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-ac", str(ch),
                          "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    y = np.frombuffer(raw, dtype="<f4").astype(float)
    return y.reshape(-1, ch) if ch > 1 else y.reshape(-1, 1)


def loud_segment(x, sr, frame=0.4):
    """響段響度：0.4 秒一格的 RMS，取最響的 1/4 平均。"""
    mono = x.mean(axis=1)
    n = max(1, int(frame * sr))
    frames = [np.sqrt(np.mean(mono[i:i + n] ** 2)) for i in range(0, max(1, len(mono) - n), n)]
    frames = np.array(frames) if frames else np.array([np.sqrt(np.mean(mono ** 2))])
    return float(np.mean(np.sort(frames)[-max(1, len(frames) // 4):]))


def compress(x, sr, thresh=0.12, ratio=2.5, win=0.03, smooth=0.06):
    mono = np.abs(x).max(axis=1)
    n = max(1, int(win * sr))
    env = np.sqrt(np.convolve(mono ** 2, np.ones(n) / n, mode="same")) + 1e-9
    gain = np.where(env > thresh, (thresh / env) ** (1 - 1.0 / ratio), 1.0)
    m = max(1, int(smooth * sr))
    gain = np.convolve(gain, np.ones(m) / m, mode="same")
    return x * gain[:, None]


def soft_limit(x, knee=0.80, ceiling=0.95):
    over = np.abs(x) > knee
    if over.any():
        mag = np.abs(x[over])
        x[over] = np.sign(x[over]) * (knee + (ceiling - knee)
                                      * np.tanh((mag - knee) / (ceiling - knee)))
    return np.clip(x, -ceiling, ceiling)


def write(path, x, sr, ch):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
    if path.lower().endswith(".mp3"):
        subprocess.run(["ffmpeg", "-y", "-v", "quiet", "-f", "s16le", "-ar", str(sr),
                        "-ac", str(ch), "-i", "-", "-codec:a", "libmp3lame",
                        "-b:a", "256k", path], input=pcm, check=True)
    else:
        subprocess.run(["ffmpeg", "-y", "-v", "quiet", "-f", "s16le", "-ar", str(sr),
                        "-ac", str(ch), "-i", "-", "-codec:a", "pcm_s16le", path],
                       input=pcm, check=True)


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    targets = [f for f in FILES if not args or any(a in f for a in args)]
    for name in targets:
        path = os.path.join(SOUNDS, name)
        if not os.path.exists(path):
            print(f"  {name:12s} 檔案不存在，跳過")
            continue
        sr, ch = probe(path)
        x = decode(path, sr, ch)
        before = loud_segment(x, sr)
        db = 20 * np.log10(max(before, 1e-9) / TARGET_SFX_LOUD)
        if abs(db) <= TOLERANCE_DB:
            print(f"  {name:12s} 響段 {20*np.log10(before):6.1f} dB ({db:+.1f}) → 已達標，跳過")
            continue
        y = x * (TARGET_SFX_LOUD / max(before, 1e-9))    # ★只調音量，不壓縮
        pk = float(np.max(np.abs(y)))
        if pk > 0.95:                                     # 只有會削波才等比例壓回來
            y = y * (0.95 / pk)
        write(path, y, sr, ch)
        z = decode(path, sr, ch)
        print(f"  {name:12s} 響段 {20*np.log10(before):6.1f} → "
              f"{20*np.log10(loud_segment(z, sr)):6.1f} dB，峰值 {np.max(np.abs(z)):.3f} "
              f"{'✅' if np.max(np.abs(z)) <= 1.0 else '⚠️'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
