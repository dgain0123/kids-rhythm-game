#!/usr/bin/env python3
"""合成第10關的背景音樂 → sounds/music/level10.m4a

第10關：BPM 20(第9關兩倍速)、小朋友每 1.5 秒打一下、共 17 下。

結構（總長 34 秒，對齊 charts/level10.json）：
    0–6s    預備拍：英文人聲數拍 one/two/three/four(每 1.5 秒一聲，
            三層鏈:真人錄音>edge-tts Libby>say，見 voice_count.py)，人聲單獨乾淨不疊其他聲
    6–33s   伴奏：9 個和聲小節 × 3 秒(C G Am F | C Am F G | C 終止式)
            每 1.5 秒＝一個拍點：小節頭放亮鐘聲(根音)、小節中放次亮鐘聲(五音)
            ＋節拍器：八分音符(每 1.5 秒)一聲木魚 → 整首 1.5 秒脈動不間斷
            最後一小節只留第 1 拍(第 17 下)，之後讓和弦收尾
    33–34s  終止音只響正拍那一聲就停(2026-08-14 裁示)

規矩：每個跟拍關卡的音樂都要含節拍器聲，細分每關可不同
(第10關=eighth，記錄在 chart 的 metronome 欄位)。

用法：python3 tools/make_level10_music.py
"""
import os
import subprocess
import sys
import wave

import numpy as np

from voice_count import count_voices

SR = 44100
HIT = 1.5           # 小朋友的拍點間隔(= BPM 20 的半拍)
PRE = 1.0           # 開頭靜音緩衝(躲播放起頭暫態；= chart 的 preRollSec)
LEAD_IN = PRE + 4 * HIT  # 預備拍總長 7 秒(= chart 的 leadInSec)
BAR = 2 * HIT       # 一個和聲小節 3 秒(兩個拍點換一個和弦)

F = {
    "C2": 65.41, "G2": 98.00, "A2": 110.00, "F2": 87.31,
    "A3": 220.00, "B3": 246.94, "C4": 261.63, "D4": 293.66,
    "E4": 329.63, "F4": 349.23, "G4": 392.00,
    "C5": 523.25, "E5": 659.26, "G5": 783.99, "A5": 880.00,
    "F5": 698.46, "B4": 493.88, "D5": 587.33,
    "C6": 1046.50,
}

# 9 個和聲小節：pad 三音、貝斯、拍點鐘聲(小節頭=根音較亮、小節中=五音次亮)、輕琶音
PROG = [
    {"pad": ["C4", "E4", "G4"], "bass": "C2", "bell": "C6", "mid": "G5", "arp": ["E5", "G5"]},
    {"pad": ["B3", "D4", "G4"], "bass": "G2", "bell": "G5", "mid": "D5", "arp": ["B4", "D5"]},
    {"pad": ["A3", "C4", "E4"], "bass": "A2", "bell": "A5", "mid": "E5", "arp": ["C5", "E5"]},
    {"pad": ["A3", "C4", "F4"], "bass": "F2", "bell": "F5", "mid": "C5", "arp": ["A5", "C5"]},
    {"pad": ["C4", "E4", "G4"], "bass": "C2", "bell": "C6", "mid": "G5", "arp": ["G5", "E5"]},
    {"pad": ["A3", "C4", "E4"], "bass": "A2", "bell": "A5", "mid": "E5", "arp": ["E5", "C5"]},
    {"pad": ["A3", "C4", "F4"], "bass": "F2", "bell": "F5", "mid": "C5", "arp": ["A5", "C5"]},
    {"pad": ["B3", "D4", "G4"], "bass": "G2", "bell": "G5", "mid": "D5", "arp": ["B4", "D5"]},
    {"pad": ["C4", "E4", "G4"], "bass": "C2", "bell": "C6", "mid": None, "arp": []},  # 終止
]
BARS = len(PROG)
TOTAL = LEAD_IN + BARS * BAR + 1.0

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


def bell(t0, freq, dur=1.6, vol=0.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * freq * t)
         + 0.35 * np.sin(2 * np.pi * freq * 3 * t) * np.exp(-t / 0.2)
         + 0.15 * np.sin(2 * np.pi * freq * 4.2 * t) * np.exp(-t / 0.1))
    add(t0, s * env_ad(n, 0.004, 0.5) * vol)


def pad_note(t0, freq, dur, vol=0.05):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + np.sin(2 * np.pi * freq * 1.003 * t)
    e = np.ones(n)
    a = int(0.3 * SR)
    r = int(0.4 * SR)
    e[:a] = np.linspace(0, 1, a)
    e[-r:] *= np.linspace(1, 0, r)
    add(t0, s * e * vol)


def bass(t0, freq, vol=0.16):
    n = int(1.8 * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2 * t)
    add(t0, s * env_ad(n, 0.03, 0.9) * vol)


def click(t0, freq=1100, vol=0.45):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2.4 * t)
    add(t0, s * env_ad(n, 0.002, 0.03) * vol)


def main():
    # 預備拍：英文人聲數拍 one/two/three/four(不疊其他聲音，人聲乾淨)
    # 波形不修剪(頭尾完整)，用「起音點」對齊拍點
    for k, (v, on) in enumerate(count_voices(SR)):
        add(PRE + k * HIT - on, v * 0.6)

    for b, bar in enumerate(PROG):
        t0 = LEAD_IN + b * BAR
        last = b == BARS - 1
        for p in bar["pad"]:
            pad_note(t0, F[p], (BAR if not last else BAR + 0.6) + 0.3)
        bass(t0, F[bar["bass"]])
        bell(t0, F[bar["bell"]], vol=0.22)          # 拍點1(小節頭)
        click(t0, freq=1100, vol=0.28)              # 節拍器
        if bar["mid"]:
            bell(t0 + HIT, F[bar["mid"]], vol=0.18)  # 拍點2(小節中)
            click(t0 + HIT, freq=1100, vol=0.28)
        for k, a in enumerate(bar["arp"]):
            bell(t0 + 0.75 + k * HIT, F[a], vol=0.08)

    # ★2026-08-14 使用者裁示：音樂到最後一下就要結束、後面不要再有音樂——
    # 終止音只響正拍那一聲(0.12 秒斷音+0.03 秒去喀聲)，之後全零(檔尾是靜音緩衝，
    # 容許窗照樣開滿；守門 test_music_ends_at_last_note)
    _i0 = int(((LEAD_IN + (BARS - 1) * BAR) + 0.12) * SR)
    _i1 = min(len(buf), int(((LEAD_IN + (BARS - 1) * BAR) + 0.15) * SR))
    if _i0 < len(buf):
        buf[_i0:_i1] *= np.cos(np.linspace(0, np.pi / 2, _i1 - _i0)) ** 2
        buf[_i1:] = 0.0

    fade = int(1.0 * SR)
    buf[-fade:] *= np.linspace(1, 0, fade)

    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(proj, "sounds", "music")
    os.makedirs(out_dir, exist_ok=True)
    wav_path = os.path.join(out_dir, "_level10_tmp.wav")
    m4a_path = os.path.join(out_dir, "level10.m4a")

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
