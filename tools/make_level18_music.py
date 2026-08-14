#!/usr/bin/env python3
"""合成第18關的背景音樂 → sounds/music/level18.m4a

第18關：BPM 100(第9關十倍速)、小朋友每 0.3 秒打一下、共 33 下。

結構（總長 15.3 秒，對齊 charts/level18.json）：
    0–1s     開頭靜音緩衝(preRollSec，躲播放起頭暫態)
    1–2.2s   預備拍：英文人聲數拍 one/two/three/four(每一拍=四分音符一聲，
             三層鏈:真人錄音>edge-tts Libby>say，見 voice_count.py)
    2.2–11.8s 伴奏：8 個和聲段 × 1.2 秒(C G Am F | C Am F G)＋11.8s 終止 C 和弦
             每 0.3 秒＝一個拍點：鐘聲走 根音(亮)→三音→五音→三音 循環
             ＋節拍器：八分音符(每 0.3 秒)一聲木魚 → 脈動不間斷
    11.8–15.3s 終止和弦短衰減(1.35 秒)後全靜音

規矩：預備拍固定 4 拍英文人聲；音樂含節拍器(細分=chart 的 metronome)。

用法：python3 tools/make_level18_music.py
"""
import os
import subprocess
import sys
import wave

import numpy as np

from voice_count import count_voices

SR = 44100
HIT = 30 / 100      # 小朋友的拍點間隔 0.3 秒(= BPM 100 的半拍)
PRE = 1.0           # 開頭靜音緩衝(躲播放起頭暫態；= chart 的 preRollSec)
COUNT = 2 * HIT     # 數拍間隔=四分音符(一拍)——速度60起八分數拍太趕(2026-07-28規矩)
LEAD_IN = PRE + 4 * COUNT  # 預備拍總長 2.2 秒(= chart 的 leadInSec)
SEG = 4 * HIT       # 一個和聲段 1.2 秒(4 個拍點換一個和弦)

F = {
    "C2": 65.41, "G2": 98.00, "A2": 110.00, "F2": 87.31,
    "A3": 220.00, "B3": 246.94, "C4": 261.63, "D4": 293.66,
    "E4": 329.63, "F4": 349.23, "G4": 392.00,
    "C5": 523.25, "E5": 659.26, "G5": 783.99, "A5": 880.00,
    "F5": 698.46, "B4": 493.88, "D5": 587.33,
    "C6": 1046.50,
}

# 8 個和聲段(各 4 拍點)：pad 三音、貝斯、鐘聲循環[根(亮),三,五,三]
PROG = [
    {"pad": ["C4", "E4", "G4"], "bass": "C2", "bells": ["C6", "E5", "G5", "E5"]},
    {"pad": ["B3", "D4", "G4"], "bass": "G2", "bells": ["G5", "B4", "D5", "B4"]},
    {"pad": ["A3", "C4", "E4"], "bass": "A2", "bells": ["A5", "C5", "E5", "C5"]},
    {"pad": ["A3", "C4", "F4"], "bass": "F2", "bells": ["F5", "A5", "C5", "A5"]},
    {"pad": ["C4", "E4", "G4"], "bass": "C2", "bells": ["C6", "G5", "E5", "G5"]},
    {"pad": ["A3", "C4", "E4"], "bass": "A2", "bells": ["A5", "E5", "C5", "E5"]},
    {"pad": ["A3", "C4", "F4"], "bass": "F2", "bells": ["F5", "C5", "A5", "C5"]},
    {"pad": ["B3", "D4", "G4"], "bass": "G2", "bells": ["G5", "D5", "B4", "D5"]},
]
SEGS = len(PROG)
END_T = LEAD_IN + SEGS * SEG        # 28s = 第 33 下(終止 C)
TOTAL = END_T + 3.5

buf = np.zeros(int(TOTAL * SR))


def add(t0, sig):
    i = int(t0 * SR)
    j = min(len(buf), i + len(sig))
    if i < len(buf):
        buf[i:j] += sig[: j - i]


def env_ad(n, attack, tau):
    t = np.arange(n) / SR
    e = np.exp(-t / tau)
    a = int(attack * SR)
    if a > 0:
        e[:a] *= np.linspace(0, 1, a)
    return e


def bell(t0, freq, dur=1.0, vol=0.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * freq * t)
         + 0.35 * np.sin(2 * np.pi * freq * 3 * t) * np.exp(-t / 0.12)
         + 0.15 * np.sin(2 * np.pi * freq * 4.2 * t) * np.exp(-t / 0.06))
    add(t0, s * env_ad(n, 0.004, 0.3) * vol)


def pad_note(t0, freq, dur, vol=0.05):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + np.sin(2 * np.pi * freq * 1.003 * t)
    e = np.ones(n)
    a = int(0.2 * SR)
    r = int(0.3 * SR)
    e[:a] = np.linspace(0, 1, a)
    e[-r:] *= np.linspace(1, 0, r)
    add(t0, s * e * vol)


def bass(t0, freq, vol=0.16):
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2 * t)
    add(t0, s * env_ad(n, 0.03, 0.7) * vol)


def click(t0, freq=1100, vol=0.45):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2.4 * t)
    add(t0, s * env_ad(n, 0.002, 0.03) * vol)


def main():
    # 預備拍：英文人聲數拍 one/two/three/four(不修剪，起音點對齊拍點)
    for k, (v, on) in enumerate(count_voices(SR)):
        add(PRE + k * COUNT - on, v * 0.6)

    # 8 個和聲段 × 4 拍點
    for g, seg in enumerate(PROG):
        t0 = LEAD_IN + g * SEG
        for p in seg["pad"]:
            pad_note(t0, F[p], SEG + 0.3)
        bass(t0, F[seg["bass"]])
        for k, b in enumerate(seg["bells"]):
            vol = 0.22 if k == 0 else 0.12   # 段頭根音較亮
            bell(t0 + k * HIT, F[b], vol=vol)
            click(t0 + k * HIT, freq=1100, vol=0.28)

    # 第 33 下：終止 C 和弦(亮鐘聲 + pad + 貝斯收尾)
    for p in ["C4", "E4", "G4"]:
        pad_note(END_T, F[p], 3.0)
    bass(END_T, F["C2"])
    bell(END_T, F["C6"], dur=2.5, vol=0.24)
    click(END_T, freq=1100, vol=0.28)

    # ★2026-08-14 使用者裁示：音樂到最後一下就要結束、後面不要再有音樂——
    # 終止那顆留 0.15 秒聲頭，接 1.2 秒餘弦淡出，之後全零(檔尾是靜音緩衝，
    # 容許窗照樣開滿；守門 test_music_ends_at_last_note)
    _i0 = int((END_T + 0.15) * SR)
    _i1 = min(len(buf), int((END_T + 1.35) * SR))
    if _i0 < len(buf):
        buf[_i0:_i1] *= np.cos(np.linspace(0, np.pi / 2, _i1 - _i0)) ** 2
        buf[_i1:] = 0.0

    fade = int(1.0 * SR)
    buf[-fade:] *= np.linspace(1, 0, fade)

    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(proj, "sounds", "music")
    os.makedirs(out_dir, exist_ok=True)
    wav_path = os.path.join(out_dir, "_level18_tmp.wav")
    m4a_path = os.path.join(out_dir, "level18.m4a")

    # 音量交給 music_style 的母帶處理（壓縮→響度對齊→限幅），不要自己做峰值正規化：
    # 峰值會被節拍器的短促尖峰佔走，整首就變小聲（2026-08-03 的教訓，見 docs/關卡音樂.md）
    from music_style import Mixer
    mx = Mixer(TOTAL, SR)
    mx.buf = buf
    mx.finish(m4a_path, fade_sec=0.0)   # 淡出前面已經做過
    print(f"✅ 音樂做好了：{m4a_path}（{TOTAL:.1f} 秒）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
