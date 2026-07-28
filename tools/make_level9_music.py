#!/usr/bin/env python3
"""合成第9關的背景音樂 → sounds/music/level9.m4a

結構（總長約 40 秒，對齊 charts/level9.json，9 個音符）：
    0–12s   預備拍：4 聲木魚聲(每 3 秒一聲，第 4 聲較高=「要開始了」)
    12–39s  伴奏：9 小節 × 3 秒(和弦 C G Am F | C Am F G | C 結尾)
            每小節第一拍有較亮的鐘聲＝小朋友要打鼓的拍點
            ＋節拍器：八分音符(BPM 10 的半拍=每 3 秒)一聲木魚，
              跟預備拍同款、稍小聲 → 整首 3 秒脈動不間斷
    39–40s  收尾淡出

規矩：每個跟拍關卡的音樂都要含節拍器聲，細分每關可不同
(第9關=eighth，記錄在 chart 的 metronome 欄位)。

設計重點：伴奏樂器用「軟起音」(pad/貝斯/鐘琴)，避免被麥克風的
打鼓偵測誤判成鼓聲；節拍器是短促高頻小聲，若仍誤觸就把靈敏度調低。

用法：python3 tools/make_level9_music.py
需要 numpy(pretty_midi 已附帶)；轉 m4a 用 macOS 內建 afconvert。
"""
import os
import subprocess
import sys
import wave

import numpy as np

SR = 44100
LEAD_IN = 12.0      # 預備拍長度(秒)，= chart 的 leadInSec
BAR = 3.0           # 一小節 3 秒(= BPM 10 的半拍，小朋友每小節打一下)

# 音高(Hz)
F = {
    "C2": 65.41, "G2": 98.00, "A2": 110.00, "F2": 87.31,
    "A3": 220.00, "B3": 246.94, "C4": 261.63, "D4": 293.66,
    "E4": 329.63, "F4": 349.23, "G4": 392.00,
    "C5": 523.25, "E5": 659.26, "G5": 783.99, "A5": 880.00,
    "F5": 698.46, "B4": 493.88, "D5": 587.33,
    "C6": 1046.50,
}

# 9 小節(=9 個音符)：和弦(pad 三音)、貝斯、拍點鐘聲、琶音(在 0.75/1.5/2.25 秒)
# 和聲：C G Am F | C Am F G | C(終止式收尾)
PROG = [
    {"pad": ["C4", "E4", "G4"], "bass": "C2", "bell": "C6", "arp": ["E5", "G5", "E5"]},
    {"pad": ["B3", "D4", "G4"], "bass": "G2", "bell": "G5", "arp": ["D5", "B4", "D5"]},
    {"pad": ["A3", "C4", "E4"], "bass": "A2", "bell": "A5", "arp": ["C5", "E5", "C5"]},
    {"pad": ["A3", "C4", "F4"], "bass": "F2", "bell": "F5", "arp": ["C5", "A5", "C5"]},
    {"pad": ["C4", "E4", "G4"], "bass": "C2", "bell": "C6", "arp": ["G5", "E5", "G5"]},
    {"pad": ["A3", "C4", "E4"], "bass": "A2", "bell": "A5", "arp": ["E5", "C5", "E5"]},
    {"pad": ["A3", "C4", "F4"], "bass": "F2", "bell": "F5", "arp": ["A5", "C5", "A5"]},
    {"pad": ["B3", "D4", "G4"], "bass": "G2", "bell": "G5", "arp": ["B4", "D5", "B4"]},
    {"pad": ["C4", "E4", "G4"], "bass": "C2", "bell": "C6", "arp": ["E5", "G5", "C6"]},
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
    """attack(線性) + 指數衰減 envelope，長度 n samples。"""
    t = np.arange(n) / SR
    e = np.exp(-t / tau)
    a = int(attack * SR)
    if a > 0:
        e[:a] *= np.linspace(0, 1, a)
    return e


def bell(t0, freq, dur=2.0, vol=0.2):
    """鐘琴：基音 + 泛音，起音快但音色圓潤。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * freq * t)
         + 0.35 * np.sin(2 * np.pi * freq * 3 * t) * np.exp(-t / 0.25)
         + 0.15 * np.sin(2 * np.pi * freq * 4.2 * t) * np.exp(-t / 0.12))
    add(t0, s * env_ad(n, 0.004, 0.7) * vol)


def pad_note(t0, freq, dur, vol=0.05):
    """和弦墊底：慢起音、雙振盪器微失諧。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + np.sin(2 * np.pi * freq * 1.003 * t)
    e = np.ones(n)
    a = int(0.4 * SR)
    r = int(0.5 * SR)
    e[:a] = np.linspace(0, 1, a)
    e[-r:] *= np.linspace(1, 0, r)
    add(t0, s * e * vol)


def bass(t0, freq, vol=0.16):
    """貝斯：軟起音正弦 + 一點第二泛音。"""
    n = int(2.2 * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2 * t)
    add(t0, s * env_ad(n, 0.03, 1.1) * vol)


def click(t0, freq=1100, vol=0.45):
    """預備拍木魚聲：短促圓潤。"""
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2.4 * t)
    add(t0, s * env_ad(n, 0.002, 0.03) * vol)


def main():
    # 預備拍：1、2、3 同音，4 較高(提示要開始了)
    for k in range(4):
        click(k * BAR, freq=1400 if k == 3 else 1100)

    # 8 小節伴奏
    for b, bar in enumerate(PROG):
        t0 = LEAD_IN + b * BAR
        for p in bar["pad"]:
            pad_note(t0, F[p], BAR + 0.3)
        bass(t0, F[bar["bass"]])
        bell(t0, F[bar["bell"]], vol=0.22)          # 拍點(小朋友打這裡)
        click(t0, freq=1100, vol=0.28)              # 節拍器:八分音符(每3秒)一聲
        for k, a in enumerate(bar["arp"]):
            bell(t0 + 0.75 * (k + 1), F[a], vol=0.10)

    # 收尾淡出
    fade = int(1.0 * SR)
    buf[-fade:] *= np.linspace(1, 0, fade)

    # 正規化 → 16-bit wav → afconvert 轉 m4a
    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(proj, "sounds", "music")
    os.makedirs(out_dir, exist_ok=True)
    wav_path = os.path.join(out_dir, "_level9_tmp.wav")
    m4a_path = os.path.join(out_dir, "level9.m4a")

    x = buf / max(1e-9, np.max(np.abs(buf))) * 0.85
    pcm = (x * 32767).astype("<i2")
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())

    subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "96000",
                    wav_path, m4a_path], check=True)
    os.remove(wav_path)
    print(f"✅ 音樂做好了：{m4a_path}（{TOTAL:.1f} 秒）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
