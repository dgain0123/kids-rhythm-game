#!/usr/bin/env python3
"""章節(大關卡)音樂風格 —— 「每個大關卡的音樂全都不一樣」這條規則的唯一正解檔。

規矩（2026-08-02 使用者定案）：
    **每一個大關卡(章節)的背景音樂都要跟其他大關卡明顯不同**——
    樂器音色、和聲進行、調性、節拍器音色 全部都要換，小朋友一聽就知道換章節了。
    新增大關卡 → 一定要在 STYLES 加一組新風格，否則 tests/test_music_style.py 會紅、
    守門(PostToolUse hook)直接擋下。

不變的部分（跟章節無關，所有跟拍關卡都一樣）：
    - 軟起音樂器：避免喇叭聲被麥克風的打鼓偵測誤判成鼓聲
    - 拍點音最亮：小朋友要打的那一下一定是當下最明顯的聲音
    - 節拍器每個拍點一聲(音色隨章節換)，預備拍底下也墊著 → 脈動不間斷
    - 預備拍：4 拍英文人聲 one/two/three/four(見 voice_count.py)

用法（各關的 make_levelN_music.py）：
    from music_style import Mixer, style_for_chapter
    st = style_for_chapter(2)
    mx = Mixer(total_sec)
    st.chord(mx, t0, dur, seg); st.hit(mx, t, name, accent=True); st.click(mx, t)
    mx.finish("sounds/music/level20.m4a")

第一大關卡(level9~18)的音樂是這套系統之前做的，產生器 make_level9~18_music.py
內建同款合成函式、音檔已出貨，就不回頭改寫；STYLES[1] 忠實記錄它們的風格，
確保之後往第一大關卡加關卡時聲音仍一致。
"""
import os
import subprocess
import wave

import numpy as np

SR = 44100
SEMI = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def hz(name):
    """音名 → 頻率（A4=440）。例：'C4'、'Bb3'、'F#5'。"""
    step = SEMI[name[0]]
    i = 1
    while i < len(name) and name[i] in "#b":
        step += 1 if name[i] == "#" else -1
        i += 1
    octave = int(name[i:])
    return 440.0 * 2 ** ((step - 9) / 12.0 + (octave - 4))


class Mixer:
    """音訊緩衝區：加訊號、正規化、淡出、寫成 m4a。"""

    def __init__(self, total_sec, sr=SR):
        self.sr = sr
        self.buf = np.zeros(int(total_sec * sr))

    def add(self, t0, sig):
        i = int(t0 * self.sr)
        j = min(len(self.buf), i + len(sig))
        if i < len(self.buf):
            self.buf[i:j] += sig[: j - i]

    def env_ad(self, n, attack, tau):
        t = np.arange(n) / self.sr
        e = np.exp(-t / tau)
        a = int(attack * self.sr)
        if a > 0:
            e[:a] *= np.linspace(0, 1, a)
        return e

    def finish(self, m4a_path, fade_sec=1.2, peak=0.85):
        fade = int(fade_sec * self.sr)
        self.buf[-fade:] *= np.linspace(1, 0, fade)
        x = self.buf / max(1e-9, np.max(np.abs(self.buf))) * peak
        os.makedirs(os.path.dirname(m4a_path), exist_ok=True)
        wav_path = m4a_path + ".tmp.wav"
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sr)
            w.writeframes((x * 32767).astype("<i2").tobytes())
        subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "96000",
                        wav_path, m4a_path], check=True)
        os.remove(wav_path)
        return len(self.buf) / self.sr


class Style:
    """一個章節的音樂風格。子類別實作 hit/chord/bass/fill/click。

    prog：和聲段清單，每段 {"chord": [和弦音], "bass": 低音, "hits": [拍點音循環]}
          拍點音會依序循環用（三連音關卡＝一段 3 個拍點）。
    """

    name = ""          # 風格名(顯示用)
    key = ""           # 調性
    instruments = ""   # 樂器組(一句話)
    metronome = ""     # 節拍器音色
    prog = []

    def signature(self):
        """風格指紋：任兩個章節不可以一樣(由測試釘住)。"""
        return (self.key, self.instruments, self.metronome,
                tuple(tuple(s["chord"]) + (s["bass"],) for s in self.prog))

    # 以下由子類別實作
    def hit(self, mx, t, note, accent=False):
        raise NotImplementedError

    def chord(self, mx, t, dur, seg):
        raise NotImplementedError

    def bass(self, mx, t, note):
        raise NotImplementedError

    def fill(self, mx, t, note):
        """拍點之間的小裝飾（很小聲，不可以搶拍點）。"""

    def click(self, mx, t, vol=0.28):
        raise NotImplementedError

    def ending(self, mx, t, seg):
        """收尾終止和弦（最後一下之後）。"""
        self.chord(mx, t, 3.5, seg)
        self.bass(mx, t, seg["bass"])
        self.hit(mx, t, seg["hits"][0], accent=False)


# ── 第一大關卡「第一行第一小節」：鐘琴＋pad＋貝斯，C 大調，木魚節拍器 ──
class ChimePadStyle(Style):
    name = "鐘琴音樂盒＋暖 pad"
    key = "C 大調"
    instruments = "鐘琴(拍點)＋雙振盪暖 pad＋正弦貝斯"
    metronome = "木魚(1100Hz 短促)"
    prog = [
        {"chord": ["C4", "E4", "G4"], "bass": "C2", "hits": ["C6", "E5", "G5"]},
        {"chord": ["B3", "D4", "G4"], "bass": "G2", "hits": ["G5", "B4", "D5"]},
        {"chord": ["A3", "C4", "E4"], "bass": "A2", "hits": ["A5", "C5", "E5"]},
        {"chord": ["A3", "C4", "F4"], "bass": "F2", "hits": ["F5", "A5", "C5"]},
    ]

    def hit(self, mx, t, note, accent=False):
        f = hz(note)
        n = int(2.0 * mx.sr)
        tt = np.arange(n) / mx.sr
        s = (np.sin(2 * np.pi * f * tt)
             + 0.35 * np.sin(2 * np.pi * f * 3 * tt) * np.exp(-tt / 0.25)
             + 0.15 * np.sin(2 * np.pi * f * 4.2 * tt) * np.exp(-tt / 0.12))
        mx.add(t, s * mx.env_ad(n, 0.004, 0.7) * (0.24 if accent else 0.11))

    def chord(self, mx, t, dur, seg):
        for note in seg["chord"]:
            f = hz(note)
            n = int(dur * mx.sr)
            tt = np.arange(n) / mx.sr
            s = np.sin(2 * np.pi * f * tt) + np.sin(2 * np.pi * f * 1.003 * tt)
            e = np.ones(n)
            a, r = int(0.4 * mx.sr), int(0.5 * mx.sr)
            e[:a] = np.linspace(0, 1, a)
            e[-r:] *= np.linspace(1, 0, r)
            mx.add(t, s * e * 0.05)

    def bass(self, mx, t, note):
        f = hz(note)
        n = int(2.2 * mx.sr)
        tt = np.arange(n) / mx.sr
        s = np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2 * tt)
        mx.add(t, s * mx.env_ad(n, 0.03, 1.1) * 0.16)

    def fill(self, mx, t, note):
        f = hz(note)
        n = int(1.2 * mx.sr)
        tt = np.arange(n) / mx.sr
        s = np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 3 * tt) * np.exp(-tt / 0.15)
        mx.add(t, s * mx.env_ad(n, 0.004, 0.4) * 0.05)

    def click(self, mx, t, vol=0.28):
        n = int(0.12 * mx.sr)
        tt = np.arange(n) / mx.sr
        s = np.sin(2 * np.pi * 1100 * tt) + 0.3 * np.sin(2 * np.pi * 2640 * tt)
        mx.add(t, s * mx.env_ad(n, 0.002, 0.03) * vol)


# ── 候選 A：音樂盒 ── F 大調、玻璃感高音樂盒＋豎琴琶音、三角鐵節拍器
class MusicBoxStyle(Style):
    name = "音樂盒"
    key = "F 大調"
    instruments = "玻璃音樂盒高音(長餘韻)＋低音撥弦＋氣音弦樂墊"
    metronome = "三角鐵(4200Hz 輕鈴)"
    prog = [
        {"chord": ["F4", "A4", "C5"], "bass": "F2", "hits": ["F6", "A5", "C6"]},
        {"chord": ["D4", "F4", "A4"], "bass": "D2", "hits": ["D6", "F5", "A5"]},
        {"chord": ["Bb3", "D4", "F4"], "bass": "Bb1", "hits": ["Bb5", "D6", "F5"]},
        {"chord": ["C4", "E4", "G4"], "bass": "C2", "hits": ["C6", "G5", "E5"]},
    ]

    def hit(self, mx, t, note, accent=False):
        f = hz(note)
        n = int(2.6 * mx.sr)
        tt = np.arange(n) / mx.sr
        # 音樂盒＝金屬齒片：非諧和高泛音 + 很長的餘韻
        s = (np.sin(2 * np.pi * f * tt)
             + 0.5 * np.sin(2 * np.pi * f * 2.76 * tt) * np.exp(-tt / 0.5)
             + 0.25 * np.sin(2 * np.pi * f * 5.4 * tt) * np.exp(-tt / 0.2)
             + 0.12 * np.sin(2 * np.pi * f * 8.9 * tt) * np.exp(-tt / 0.08))
        mx.add(t, s * mx.env_ad(n, 0.006, 1.1) * (0.26 if accent else 0.10))

    def chord(self, mx, t, dur, seg):
        for note in seg["chord"]:
            f = hz(note)
            n = int(dur * mx.sr)
            tt = np.arange(n) / mx.sr
            # 氣音弦樂：微顫音 + 一點呼吸感噪音
            vib = 1 + 0.004 * np.sin(2 * np.pi * 4.5 * tt)
            s = np.sin(2 * np.pi * f * tt * vib) + 0.5 * np.sin(2 * np.pi * f * 2 * tt)
            e = np.ones(n)
            a, r = int(0.7 * mx.sr), int(0.7 * mx.sr)
            e[:a] = np.linspace(0, 1, a) ** 2
            e[-r:] *= np.linspace(1, 0, r)
            mx.add(t, s * e * 0.035)

    def bass(self, mx, t, note):
        f = hz(note)
        n = int(2.6 * mx.sr)
        tt = np.arange(n) / mx.sr
        s = np.sin(2 * np.pi * f * tt) + 0.2 * np.sin(2 * np.pi * f * 3 * tt) * np.exp(-tt / 0.3)
        mx.add(t, s * mx.env_ad(n, 0.05, 1.3) * 0.15)

    def fill(self, mx, t, note):
        # 豎琴式往上的小琶音(三顆，很輕)
        for k, mul in enumerate([1.0, 1.5, 2.0]):
            f = hz(note) * mul
            n = int(0.9 * mx.sr)
            tt = np.arange(n) / mx.sr
            s = np.sin(2 * np.pi * f * tt) + 0.2 * np.sin(2 * np.pi * f * 2.76 * tt) * np.exp(-tt / 0.1)
            mx.add(t + k * 0.11, s * mx.env_ad(n, 0.005, 0.45) * 0.035)

    def click(self, mx, t, vol=0.28):
        n = int(0.35 * mx.sr)
        tt = np.arange(n) / mx.sr
        s = (np.sin(2 * np.pi * 4200 * tt) + 0.6 * np.sin(2 * np.pi * 6300 * tt)
             + 0.3 * np.sin(2 * np.pi * 9100 * tt))
        mx.add(t, s * mx.env_ad(n, 0.001, 0.09) * vol * 0.5)


# ── 候選 B：木琴馬林巴 ── G 大調、木質馬林巴＋沙鈴節拍器
class MarimbaStyle(Style):
    name = "木琴馬林巴"
    key = "G 大調"
    instruments = "馬林巴(木質共鳴)＋低音馬林巴＋木管長音"
    metronome = "沙鈴(柔和噪音)"
    prog = [
        {"chord": ["G3", "B3", "D4"], "bass": "G2", "hits": ["G5", "B4", "D5"]},
        {"chord": ["E3", "G3", "B3"], "bass": "E2", "hits": ["E5", "G4", "B4"]},
        {"chord": ["C4", "E4", "G4"], "bass": "C2", "hits": ["C5", "E5", "G5"]},
        {"chord": ["D4", "F#4", "A4"], "bass": "D2", "hits": ["D5", "F#5", "A5"]},
    ]

    def hit(self, mx, t, note, accent=False):
        f = hz(note)
        n = int(1.4 * mx.sr)
        tt = np.arange(n) / mx.sr
        # 馬林巴：基音 + 第 4 泛音(木質特徵)，衰減快、圓潤
        s = (np.sin(2 * np.pi * f * tt)
             + 0.4 * np.sin(2 * np.pi * f * 4 * tt) * np.exp(-tt / 0.06)
             + 0.2 * np.sin(2 * np.pi * f * 9.2 * tt) * np.exp(-tt / 0.03))
        mx.add(t, s * mx.env_ad(n, 0.006, 0.34) * (0.30 if accent else 0.13))

    def chord(self, mx, t, dur, seg):
        for note in seg["chord"]:
            f = hz(note)
            n = int(dur * mx.sr)
            tt = np.arange(n) / mx.sr
            # 木管長音：基音強、偶次泛音少
            s = (np.sin(2 * np.pi * f * tt)
                 + 0.25 * np.sin(2 * np.pi * f * 3 * tt)
                 + 0.08 * np.sin(2 * np.pi * f * 5 * tt))
            e = np.ones(n)
            a, r = int(0.35 * mx.sr), int(0.45 * mx.sr)
            e[:a] = np.linspace(0, 1, a)
            e[-r:] *= np.linspace(1, 0, r)
            mx.add(t, s * e * 0.04)

    def bass(self, mx, t, note):
        f = hz(note)
        n = int(1.8 * mx.sr)
        tt = np.arange(n) / mx.sr
        s = np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * f * 4 * tt) * np.exp(-tt / 0.1)
        mx.add(t, s * mx.env_ad(n, 0.02, 0.6) * 0.18)

    def fill(self, mx, t, note):
        f = hz(note)
        n = int(0.7 * mx.sr)
        tt = np.arange(n) / mx.sr
        s = np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 4 * tt) * np.exp(-tt / 0.05)
        mx.add(t, s * mx.env_ad(n, 0.006, 0.22) * 0.06)

    def click(self, mx, t, vol=0.28):
        rng = np.random.RandomState(int(t * 1000) % 9973)  # 固定種子→每次產生一樣的音檔
        n = int(0.14 * mx.sr)
        noise = rng.randn(n)
        # 簡易帶通：一階差分拉高頻 + 指數包絡
        s = np.diff(np.concatenate([[0.0], noise]))
        mx.add(t, s * mx.env_ad(n, 0.004, 0.045) * vol * 0.55)


# ── 候選 C：撥弦(烏克麗麗/豎琴) ── D 大調、Karplus-Strong 撥弦＋木塊節拍器
class PluckStyle(Style):
    name = "撥弦(烏克麗麗)"
    key = "D 大調"
    instruments = "尼龍弦撥弦(Karplus-Strong)＋撥弦低音＋輕柔弦墊"
    metronome = "高音木塊(1800Hz 極短)"
    prog = [
        {"chord": ["D4", "F#4", "A4"], "bass": "D2", "hits": ["D5", "F#5", "A5"]},
        {"chord": ["A3", "C#4", "E4"], "bass": "A2", "hits": ["A5", "C#5", "E5"]},
        {"chord": ["B3", "D4", "F#4"], "bass": "B1", "hits": ["B4", "D5", "F#5"]},
        {"chord": ["G3", "B3", "D4"], "bass": "G2", "hits": ["G5", "B4", "D5"]},
    ]

    @staticmethod
    def _pluck(sr, f, dur, decay=0.996, seed=0):
        """Karplus-Strong：噪音激發 → 延遲線平均 → 撥弦音。"""
        n = int(dur * sr)
        L = max(2, int(sr / f))
        rng = np.random.RandomState(seed)
        buf = rng.uniform(-1, 1, L)
        buf *= np.linspace(0, 1, L) ** 0.5      # 軟化激發(起音不要太尖)
        out = np.empty(n)
        idx = 0
        for i in range(n):
            out[i] = buf[idx]
            buf[idx] = decay * 0.5 * (buf[idx] + buf[(idx + 1) % L])
            idx = (idx + 1) % L
        return out

    def hit(self, mx, t, note, accent=False):
        f = hz(note)
        s = self._pluck(mx.sr, f, 1.8, 0.9965, seed=int(f) % 997)
        n = len(s)
        e = mx.env_ad(n, 0.012, 1.2)            # 12ms 起音：不像鼓的尖銳瞬態
        mx.add(t, s * e * (0.32 if accent else 0.13))

    def chord(self, mx, t, dur, seg):
        for note in seg["chord"]:
            f = hz(note)
            n = int(dur * mx.sr)
            tt = np.arange(n) / mx.sr
            s = np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 2 * tt * 1.002)
            e = np.ones(n)
            a, r = int(0.6 * mx.sr), int(0.6 * mx.sr)
            e[:a] = np.linspace(0, 1, a) ** 1.5
            e[-r:] *= np.linspace(1, 0, r)
            mx.add(t, s * e * 0.03)

    def bass(self, mx, t, note):
        f = hz(note)
        s = self._pluck(mx.sr, f, 2.2, 0.998, seed=int(f) % 991)
        mx.add(t, s * mx.env_ad(len(s), 0.02, 1.5) * 0.22)

    def fill(self, mx, t, note):
        f = hz(note)
        s = self._pluck(mx.sr, f, 0.9, 0.994, seed=int(f) % 983)
        mx.add(t, s * mx.env_ad(len(s), 0.015, 0.5) * 0.055)

    def click(self, mx, t, vol=0.28):
        n = int(0.07 * mx.sr)
        tt = np.arange(n) / mx.sr
        s = np.sin(2 * np.pi * 1800 * tt) + 0.4 * np.sin(2 * np.pi * 3300 * tt)
        mx.add(t, s * mx.env_ad(n, 0.001, 0.016) * vol)


# 第二大關卡的候選(試聽用；選定的那個放進 STYLES)
CANDIDATES = {"A": MusicBoxStyle(), "B": MarimbaStyle(), "C": PluckStyle()}

# ★ 章節 → 音樂風格。**新增大關卡就一定要在這裡加一組不一樣的**
#   (漏加或跟別章重複 → tests/test_music_style.py 紅 → 守門擋下)
STYLES = {
    1: ChimePadStyle(),     # 第一行第一小節(level9~18)
    2: MarimbaStyle(),      # 第一行第二小節(level20~)：2026-08-02 使用者從 A/B/C 試聽選定 B
}


def style_for_chapter(chapter):
    """取某個大關卡(1 起算)的音樂風格；沒定義就直接爆，不要默默用別章的。"""
    if chapter not in STYLES:
        raise KeyError(f"第 {chapter} 大關卡還沒定義音樂風格 —— "
                       f"請在 tools/music_style.py 的 STYLES 加一組跟其他章節都不同的風格"
                       f"（規矩見 docs/關卡音樂.md）")
    return STYLES[chapter]
