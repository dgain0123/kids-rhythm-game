#!/usr/bin/env python3
"""合成第20關的背景音樂 → sounds/music/level20.m4a

第20關（第二大關卡的第2關）：BPM 10、**四個三連音**共 12 下，
小朋友每 2 秒打一下（1/3 拍＝三連音一個間隔）。

結構（總長 37 秒，對齊 charts/level20.json）：
    0–1s     開頭靜音緩衝(preRollSec，躲播放起頭暫態)
    1–9s     預備拍：英文人聲數拍 one/two/three/four
             (每 2 秒一聲＝拍點間隔；速度50以下用拍點間隔數拍的規矩)
    9–33s    伴奏：4 個和聲段 × 6 秒(＝一組三連音 3 個拍點) C G Am F
             每 2 秒＝一個拍點：鐘聲走 根音(亮)→三音→五音，
             **每組三連音的第一顆最亮** → 小朋友聽得出三個一組
             ＋節拍器：三連音(每 2 秒)一聲木魚，預備拍底下也墊著 → 脈動不間斷
             拍點之間(+1 秒)墊一顆很小聲的琶音，慢速也不空
    33–37s   終止 C 和弦餘韻＋淡出(最後一下在 31 秒，留足夠時間給 ±2 秒容許窗)

規矩：預備拍固定 4 拍英文人聲；音樂含節拍器(細分＝chart 的 metronome，本關 triplet)。

用法：python3 tools/make_level20_music.py
"""
import os
import subprocess
import sys
import wave

import numpy as np

from voice_count import count_voices

SR = 44100
HIT = 2.0           # 拍點間隔 2 秒(= BPM 10 的 1/3 拍＝三連音一顆)
PRE = 1.0           # 開頭靜音緩衝(躲播放起頭暫態；= chart 的 preRollSec)
COUNT = HIT         # 數拍間隔＝拍點間隔(速度50以下的規矩，同第9關)
LEAD_IN = PRE + 4 * COUNT   # 預備拍總長 9 秒(= chart 的 leadInSec)
SEG = 3 * HIT       # 一個和聲段 6 秒＝一組三連音(3 個拍點)

F = {
    "C2": 65.41, "G2": 98.00, "A2": 110.00, "F2": 87.31,
    "A3": 220.00, "B3": 246.94, "C4": 261.63, "D4": 293.66,
    "E4": 329.63, "F4": 349.23, "G4": 392.00,
    "C5": 523.25, "E5": 659.26, "G5": 783.99, "A5": 880.00,
    "F5": 698.46, "B4": 493.88, "D5": 587.33,
    "C6": 1046.50,
}

# 4 個和聲段(各 3 個拍點＝一組三連音)：pad 三音、貝斯、三顆鐘聲[根(亮),三,五]、
# 拍點之間墊的小琶音
PROG = [
    {"pad": ["C4", "E4", "G4"], "bass": "C2", "bells": ["C6", "E5", "G5"], "fill": ["G5", "C6"]},
    {"pad": ["B3", "D4", "G4"], "bass": "G2", "bells": ["G5", "B4", "D5"], "fill": ["D5", "G5"]},
    {"pad": ["A3", "C4", "E4"], "bass": "A2", "bells": ["A5", "C5", "E5"], "fill": ["E5", "A5"]},
    {"pad": ["A3", "C4", "F4"], "bass": "F2", "bells": ["F5", "A5", "C5"], "fill": ["C5", "F5"]},
]
SEGS = len(PROG)
END_T = LEAD_IN + SEGS * SEG        # 33 秒：最後一下(第12下)在 31 秒，這裡是收尾和弦
TOTAL = END_T + 4.0

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


def bell(t0, freq, dur=2.0, vol=0.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * freq * t)
         + 0.35 * np.sin(2 * np.pi * freq * 3 * t) * np.exp(-t / 0.25)
         + 0.15 * np.sin(2 * np.pi * freq * 4.2 * t) * np.exp(-t / 0.12))
    add(t0, s * env_ad(n, 0.004, 0.7) * vol)


def pad_note(t0, freq, dur, vol=0.05):
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
    n = int(2.2 * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2 * t)
    add(t0, s * env_ad(n, 0.03, 1.1) * vol)


def click(t0, freq=1100, vol=0.45):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2.4 * t)
    add(t0, s * env_ad(n, 0.002, 0.03) * vol)


def main():
    # 預備拍：英文人聲數拍 one/two/three/four(不修剪，起音點對齊拍點)
    # ＋節拍器同步墊著 → 預備拍到伴奏的 2 秒脈動不間斷
    for k, (v, on) in enumerate(count_voices(SR)):
        add(PRE + k * COUNT - on, v * 0.6)
        click(PRE + k * COUNT, freq=1100, vol=0.20)

    # 4 個和聲段 × 3 個拍點(＝一組三連音)
    for g, seg in enumerate(PROG):
        t0 = LEAD_IN + g * SEG
        for p in seg["pad"]:
            pad_note(t0, F[p], SEG + 0.3)
        bass(t0, F[seg["bass"]])
        for k, b in enumerate(seg["bells"]):
            vol = 0.24 if k == 0 else 0.11   # 三連音的第一顆最亮＝聽得出三個一組
            bell(t0 + k * HIT, F[b], vol=vol)
            click(t0 + k * HIT, freq=1100, vol=0.28)   # 節拍器：每個拍點一聲
            # 拍點之間墊很小聲的琶音(慢速填空，音量遠低於拍點鐘聲不會搶拍)
            if k < len(seg["fill"]):
                bell(t0 + k * HIT + HIT / 2, F[seg["fill"][k]], dur=1.2, vol=0.05)

    # 收尾：終止 C 和弦(最後一下之後 2 秒，不再敲節拍器)
    for p in ["C4", "E4", "G4"]:
        pad_note(END_T, F[p], 3.5)
    bass(END_T, F["C2"])
    bell(END_T, F["C6"], dur=3.0, vol=0.16)

    fade = int(1.2 * SR)
    buf[-fade:] *= np.linspace(1, 0, fade)

    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(proj, "sounds", "music")
    os.makedirs(out_dir, exist_ok=True)
    wav_path = os.path.join(out_dir, "_level20_tmp.wav")
    m4a_path = os.path.join(out_dir, "level20.m4a")

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
    print(f"✅ 音樂做好了：{m4a_path}（{TOTAL:.1f} 秒，預備拍 {LEAD_IN:.0f} 秒，"
          f"12 個拍點每 {HIT:.0f} 秒一下，最後一下在 {LEAD_IN + 11 * HIT:.0f} 秒）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
