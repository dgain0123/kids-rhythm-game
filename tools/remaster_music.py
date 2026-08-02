#!/usr/bin/env python3
"""母帶重製：把既有的關卡音樂拉到統一響度（TARGET_RMS）。

用途：音量標準改變時，不必重新合成（重新合成會重抓 TTS 人聲、內容可能微變），
直接對現成的 m4a 做「解碼→壓縮→響度對齊→限幅→重編碼」，**音樂內容完全不變、只動音量**。

規矩見 docs/關卡音樂.md：所有關卡音樂對齊同一響度，不可以用峰值正規化。

用法：
    python3 tools/remaster_music.py            # 全部檢查，偏離才處理
    python3 tools/remaster_music.py level9     # 只處理某幾關
"""
import glob
import os
import subprocess
import sys

import numpy as np

from music_style import AAC_BITRATE, TARGET_RMS, Mixer

SR = 44100
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSIC_DIR = os.path.join(PROJ, "sounds", "music")
TOLERANCE_DB = 0.7          # 已經夠接近就不重壓(避免重複壓縮越壓越扁)


def decode(path, sr=SR):
    out = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1",
                          "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype="<f4").astype(float)


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    files = sorted(glob.glob(os.path.join(MUSIC_DIR, "level*.m4a")))
    if args:
        files = [f for f in files if any(a in os.path.basename(f) for a in args)]
    for f in files:
        y = decode(f)
        mx = Mixer(len(y) / SR, SR)
        mx.buf = y.copy()
        before = mx.loudness()
        db = 20 * np.log10(max(before, 1e-9) / TARGET_RMS)
        name = os.path.basename(f)
        if abs(db) <= TOLERANCE_DB:
            print(f"  {name:14s} {db:+5.1f} dB → 已達標，跳過")
            continue
        mx.finish(f, fade_sec=0.0)          # 淡出原本就有了，這裡只做母帶處理
        after = decode(f)
        core = after[int(3 * SR):len(after) - int(2 * SR)]
        rms = float(np.sqrt(np.mean(core ** 2)))
        print(f"  {name:14s} {db:+5.1f} dB → {20*np.log10(rms/TARGET_RMS):+5.1f} dB "
              f"(RMS {20*np.log10(rms):.1f} dBFS, 峰值 {np.max(np.abs(after)):.3f}) "
              f"{'✅' if np.max(np.abs(after)) <= 0.999 else '⚠️破表'} [{AAC_BITRATE[:3]}k]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
