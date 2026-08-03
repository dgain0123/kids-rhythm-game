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

# ★ 所有關卡音樂的目標響度（RMS，不是峰值）。
# 量自第一大關卡 level9~18 的實測平均 -16.4 dBFS(RMS 0.152)——那是使用者聽慣的音量。
# **一定要用 RMS 對齊、不能用峰值正規化**：峰值會被節拍器的短促尖峰佔走，
# 動態大的現成曲目就會整首變小聲(2026-08-03 第20關實際小了 7dB 被使用者抓到)。
TARGET_RMS = 0.316       # -10.0 dBFS：對齊「完成提示音」的響度(2026-08-03 使用者要求
                         # 「跟提示音一樣大聲」；原本 -16.4 dB 對齊第一大關卡仍嫌小聲)
LIMIT_CEILING = 0.72     # 限幅天花板：留餘裕給 AAC 編碼過衝
LIMIT_KNEE = 0.60        # 超過這個振幅才開始軟壓，底下完全不動
CLEAN_MASTER = True      # ★全域：母帶一律「只調音量」，**不做任何壓縮/限幅**
                         # (2026-08-03 使用者裁示「全拿掉壓縮，只調音量」——壓縮會吃掉動態
                         #  並把人聲的編碼雜訊抬起來；代價是整體比壓縮版小約 6 dB)
CLEAN_PEAK = 0.97        # clean 模式的目標峰值。零壓縮素材幾乎沒有 AAC 過衝
                         # (實測上限0.99→解碼0.987)，所以可以推到 0.97 榨出最後 0.9dB；
                         # 這是純 gain、不動任何動態。**再上去就削波，不可能更大聲了**
AAC_BITRATE = "160000"   # 實測(真實浮點峰值)：天花板0.72+160k → 0.89 安全；
                         # 0.80+128k 會過衝到 1.02 破音


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

    def noise(self, dur, seed):
        """固定種子的白噪音(每次產生的音檔要一模一樣)。"""
        return np.random.RandomState(seed).randn(int(dur * self.sr))

    def reverb(self, decay=2.0, mix=0.3, seed=7, damp=0.35):
        """整軌加殘響：用「指數衰減噪音」當脈衝響應做 FFT 摺積。
        空間感是氛圍的一大半 —— 乾聲(玩具感) vs 大殘響(空靈) 差很多。"""
        n = int(decay * self.sr)
        t = np.arange(n) / self.sr
        ir = np.random.RandomState(seed).randn(n) * np.exp(-t / (decay / 4.0))
        k = max(1, int(damp * 40))          # 簡易高頻衰減(移動平均)
        ir = np.convolve(ir, np.ones(k) / k, mode="same")
        ir /= max(1e-9, np.max(np.abs(ir)))
        m = len(self.buf) + n - 1
        N = 1 << int(np.ceil(np.log2(m)))
        wet = np.fft.irfft(np.fft.rfft(self.buf, N) * np.fft.rfft(ir, N))[:len(self.buf)]
        wet /= max(1e-9, np.max(np.abs(wet)))
        wet *= max(1e-9, np.max(np.abs(self.buf)))
        self.buf = (1 - mix) * self.buf + mix * wet

    def loudness(self, x=None, skip_head=2.0, skip_tail=1.5):
        """音樂段落的 RMS（跳過開頭緩衝與結尾淡出，才是真正聽到的音量）。"""
        x = self.buf if x is None else x
        a, b = int(skip_head * self.sr), len(x) - int(skip_tail * self.sr)
        core = x[a:b] if b - a > self.sr else x
        return float(np.sqrt(np.mean(core ** 2)))

    def compress(self, thresh=0.10, ratio=3.0, win=0.03, smooth=0.06):
        """溫和的壓縮：把小聲的段落抬起來、大聲的壓下去，整體才推得響又不失真。
        (只靠限幅硬推會把動態大的曲子壓爛；母帶做法是先壓縮再限幅。)
        thresh 以上依 ratio 壓縮；增益曲線再平滑過，避免抽吸感。"""
        n = max(1, int(win * self.sr))
        env = np.sqrt(np.convolve(self.buf ** 2, np.ones(n) / n, mode="same")) + 1e-9
        gain = np.where(env > thresh, (thresh / env) ** (1 - 1.0 / ratio), 1.0)
        m = max(1, int(smooth * self.sr))
        gain = np.convolve(gain, np.ones(m) / m, mode="same")
        self.buf *= gain

    def normalize_loudness(self, target_rms=TARGET_RMS,
                           knee=LIMIT_KNEE, ceiling=LIMIT_CEILING):
        """把整軌拉到目標響度（RMS），超過 knee 的峰值用軟膝限幅壓到 ceiling 以下。
        跟峰值正規化的差別：動態大的曲子不會因為幾個尖峰就整首變小聲。
        ceiling 要留餘裕給 AAC 編碼過衝(不留的話解碼會超過 1.0 破音)。"""
        for _ in range(4):                       # 限幅會吃掉一點響度，補幾次收斂
            cur = self.loudness()
            if cur < 1e-9:
                break
            self.buf *= target_rms / cur
            over = np.abs(self.buf) > knee
            if over.any():                       # 軟膝：門檻以下完全不動
                mag = np.abs(self.buf[over])
                self.buf[over] = np.sign(self.buf[over]) * (
                    knee + (ceiling - knee) * np.tanh((mag - knee) / (ceiling - knee)))
            if abs(20 * np.log10(max(self.loudness(), 1e-9) / target_rms)) < 0.2:
                break
        np.clip(self.buf, -ceiling, ceiling, out=self.buf)
        return self.loudness()

    def finish(self, m4a_path, fade_sec=1.2, target_rms=TARGET_RMS, clean=CLEAN_MASTER):
        """clean=True＝**只調音量**：整軌等比例放大到安全峰值，
        不壓縮、不限幅、不做任何動態處理（2026-08-03 使用者要求：
        「什麼東西都不要動，只要調整音量就好」——壓縮會把人聲的編碼雜訊抬起來）。"""
        fade = int(fade_sec * self.sr)
        if fade > 0:
            self.buf[-fade:] *= np.linspace(1, 0, fade)
        if clean:
            peak = float(np.max(np.abs(self.buf)))
            if peak > 1e-9:
                self.buf *= CLEAN_PEAK / peak
        else:
            self.compress()                  # 先壓縮(抬小聲處)再推響度，才不會壓爛
            self.normalize_loudness(target_rms)
        x = self.buf
        if os.path.dirname(m4a_path):
            os.makedirs(os.path.dirname(m4a_path), exist_ok=True)
        wav_path = m4a_path + ".tmp.wav"
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sr)
            w.writeframes((x * 32767).astype("<i2").tobytes())
        subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", AAC_BITRATE,
                        wav_path, m4a_path], check=True)
        # ★編碼後驗證：AAC 會過衝，不同素材過衝量不同(實測 level14 在上限0.97 時
        # 解碼出 1.05 破表)。破表就等比例降一點重編，直到安全為止。
        for _ in range(4):
            pk = _decoded_peak(m4a_path)
            if pk is None or pk <= 0.99:
                break
            x = x * (0.985 / pk)
            with wave.open(wav_path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(self.sr)
                w.writeframes((x * 32767).astype("<i2").tobytes())
            subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", AAC_BITRATE,
                            wav_path, m4a_path], check=True)
        os.remove(wav_path)
        return len(self.buf) / self.sr


def _decoded_peak(path):
    """解碼回來量真實峰值(要用 float，s16 會被夾在 1.000 看不出過衝)。"""
    try:
        raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1",
                              "-ar", "44100", "-f", "f32le", "-"],
                             capture_output=True, check=True).stdout
        y = np.frombuffer(raw, dtype="<f4")
        return float(np.max(np.abs(y))) if len(y) else None
    except Exception:
        return None


class Style:
    """一個章節的音樂風格。有兩種來源：
    - kind="synth"：程式合成，子類別實作 hit/chord/bass/fill/click，用 prog 當和聲進行
    - kind="track"：**現成 CC0 曲目**，只要填 source/license/credit/source_url，
      合成的部分只剩節拍器 click；做音樂走 tools/track_music.py（變速對齊拍點）

    prog：和聲段清單，每段 {"chord": [和弦音], "bass": 低音, "hits": [拍點音循環]}
          拍點音會依序循環用（三連音關卡＝一段 3 個拍點）。
    """

    kind = "synth"
    name = ""          # 風格名(顯示用)
    key = ""           # 調性
    instruments = ""   # 樂器組(一句話)
    metronome = ""     # 節拍器音色
    prog = []
    # kind="track" 用：素材檔名(放 sounds/music/source/)與授權登記
    source = ""
    license = ""
    credit = ""
    source_url = ""
    # 需要標示的授權(CC BY)：這段文字一定要出現在 index.html 的出處欄
    # (CC BY 要求「想知道音樂來源的人要找得到」)，由測試釘住
    ui_credit = ""

    def needs_attribution(self):
        """這個素材的授權要不要在畫面上標示(CC BY 系列要，CC0/公共領域不用)。"""
        lic = (self.license or "").upper()
        return "BY" in lic and "CC0" not in lic

    def signature(self):
        """風格指紋：任兩個章節不可以一樣(由測試釘住)。"""
        return (self.kind, self.key, self.instruments, self.metronome, self.source,
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


# ── 第二大關卡「第一行第二小節」：現成 CC0 曲目「旋轉木馬風琴」──
# 2026-08-03 使用者裁示：純合成的候選(音樂盒/馬林巴/撥弦)骨架都一樣、氛圍太像第一大關卡，
# 改用現成音樂 → 從 4 首 CC0 候選(旋轉木馬/手風琴波卡/八位元/放克)試聽選定這首。
class CarouselOrganStyle(Style):
    kind = "track"
    name = "旋轉木馬風琴(現成曲目)"
    key = "原曲調性(不變調，只變速)"
    instruments = "遊樂園旋轉木馬管風琴實錄"
    metronome = "高音木塊(1500Hz 極短，切得過風琴)"
    source = "carousel_cc0.mp3"
    license = "CC0 1.0 (公共領域，免標示)"
    credit = "Music of Carousel // Karusellin musiikkia, Linnanmäki — YleArkisto (Freesound)"
    source_url = "https://freesound.org/people/YleArkisto/sounds/524699"

    def click(self, mx, t, vol=0.42):
        n = int(0.09 * mx.sr)
        t2 = np.arange(n) / mx.sr
        s = np.sin(2 * np.pi * 1500 * t2) + 0.4 * np.sin(2 * np.pi * 3400 * t2)
        mx.add(t, s * mx.env_ad(n, 0.002, 0.022) * vol)


# ── 第二大關卡實際採用：Kevin MacLeod「Fluffing a Duck」(CC BY 4.0) ──
# 2026-08-03 使用者聽過旋轉木馬(Freesound CC0)後說「這來源的歌曲都好難聽」——
# Freesound 是使用者上傳的音效庫、不是為聽而做的音樂。改用 incompetech(專業配樂庫)，
# 從 5 首候選試聽選定這首。CC BY 要標示 → ui_credit 必須顯示在 index.html(測試釘住)。
class FluffingDuckStyle(Style):
    kind = "track"
    name = "Fluffing a Duck(現成曲目)"
    key = "原曲調性(不變調，只變速)"
    instruments = "輕快撥弦小品(木琴/撥弦/低音提琴，Kevin MacLeod)"
    metronome = "高音木塊(1500Hz 極短)"
    source = "fluffing_a_duck_ccby.mp3"
    license = "CC BY 4.0 (姓名標示；incompetech 官方 FAQ 版本)"
    credit = ("Fluffing a Duck — Kevin MacLeod (incompetech.com), "
              "Licensed under Creative Commons: By Attribution 4.0")
    source_url = "https://incompetech.com/music/royalty-free/index.html"
    ui_credit = "Fluffing a Duck — Kevin MacLeod (incompetech.com)"

    def click(self, mx, t, vol=0.42):
        n = int(0.09 * mx.sr)
        t2 = np.arange(n) / mx.sr
        s = np.sin(2 * np.pi * 1500 * t2) + 0.4 * np.sin(2 * np.pi * 3400 * t2)
        mx.add(t, s * mx.env_ad(n, 0.002, 0.022) * vol)


# ── 第二大關卡最終採用：布拉姆斯搖籃曲(真正的兒歌) ──
# 2026-08-03 使用者要「兒歌」→ 從 Jamendo(音樂人曲庫，品質遠優於 Freesound 的使用者音效)
# 撈 CC BY 兒歌，通過對齊檢查的三首試聽後選定。**旋律本身是公共領域**(布拉姆斯 1868)，
# 這份錄音是 CC BY 3.0 → 要標示(ui_credit 顯示在 index.html，測試釘住)。
class BrahmsLullabyStyle(Style):
    kind = "track"
    name = "布拉姆斯搖籃曲(現成曲目)"
    key = "原曲調性(不變調，完全不用變速)"
    instruments = "搖籃曲鋼琴／音樂盒編曲(BrunoXe)"
    metronome = "高音木塊(1500Hz 極短)"
    source = "brahms_lullaby_ccby3.mp3"
    license = "CC BY 3.0 (姓名標示)"
    credit = ("Lullaby (Johannes Brahms) — BrunoXe (jamendo.com/track/379363), "
              "Licensed under Creative Commons: By Attribution 3.0")
    source_url = "https://www.jamendo.com/track/379363"
    ui_credit = "Lullaby (Johannes Brahms) — BrunoXe (jamendo.com)"

    def click(self, mx, t, vol=0.42):
        n = int(0.09 * mx.sr)
        t2 = np.arange(n) / mx.sr
        s = np.sin(2 * np.pi * 1500 * t2) + 0.4 * np.sin(2 * np.pi * 3400 * t2)
        mx.add(t, s * mx.env_ad(n, 0.002, 0.022) * vol)


# ── 第二大關卡最終採用：自製兒歌 MIDI ＋ SoundFont render（完全乾聲、零授權風險）──
# 2026-08-03 AI 會議室 5 人一致決議(記錄/會議_20260803_0932.md)：
# 現成錄音都有房間殘響、達不到「跟第一大關一樣乾淨」；土砲正弦合成又音色廉價。
# 解法＝**公共領域兒歌旋律自己寫成 MIDI ＋ 免費專業取樣音源(GeneralUser GS) 離線 render**
# (fluidsynth -R 0 -C 0 關殘響/和聲效果)。旋律是布拉姆斯搖籃曲(1868, 公共領域)，
# 編曲與 MIDI 都是我們自己寫的 → 連第三方編曲權利都沒有。
class LullabyMarimbaStyle(Style):
    kind = "track"
    aligned_render = True      # 自製素材：速度本來就對齊拍點，不必偵測/變速
    name = "布拉姆斯搖籃曲・木琴馬林巴(自製 render)"
    key = "C 大調 3/4 華爾滋(90BPM，一小節＝一個拍點)"
    instruments = "馬林巴取樣音源(GeneralUser GS)：旋律＋分解和弦＋低音"
    metronome = "木魚 1100Hz（與第一大關卡相同，使用者裁示）"
    source = "lullaby_marimba_hit2s.wav"      # 預設(速度10)；各關依拍點間隔取對應 render
    license = "公共領域旋律(布拉姆斯 1868)＋自製編曲；音源 GeneralUser GS 允許自由使用含商用"
    credit = ("Lullaby (Brahms, public domain melody) — 自製 MIDI 編曲，"
              "以 GeneralUser GS SoundFont (S. Christian Collins) 離線 render")
    source_url = "https://github.com/mrbumpy409/GeneralUser-GS"
    ui_credit = "布拉姆斯搖籃曲（公共領域）· 音源 GeneralUser GS"

    def source_for(self, hit_sec):
        """同一首搖籃曲、每個速度各 render 一份（一小節＝一個拍點）。
        由 tools/make_lullaby_render.py 產生，命名 lullaby_marimba_hit<秒>s.wav。"""
        return f"lullaby_marimba_hit{hit_sec:g}s.wav"

    def click(self, mx, t, vol=0.28):
        """**跟第一大關卡用同一個木魚**（1100Hz，衰減 30ms，音量 0.28）——
        2026-08-03 使用者裁示：「提示音跟節拍器都用第一大關原本的就好」。
        （原本我自己調了 900~1500Hz 的版本，聽起來雜。）"""
        n = int(0.12 * mx.sr)
        t2 = np.arange(n) / mx.sr
        s = np.sin(2 * np.pi * 1100 * t2) + 0.3 * np.sin(2 * np.pi * 2640 * t2)
        mx.add(t, s * mx.env_ad(n, 0.002, 0.03) * vol)


# 備用風格(之後開新章節可直接用或當範本)：合成三款 + 用過/試過的現成曲目
CANDIDATES = {"音樂盒": MusicBoxStyle(), "馬林巴": MarimbaStyle(), "撥弦": PluckStyle(),
              "旋轉木馬風琴": CarouselOrganStyle(), "Fluffing a Duck": FluffingDuckStyle(),
              "布拉姆斯搖籃曲(實錄)": BrahmsLullabyStyle()}

# ★ 章節 → 音樂風格。**新增大關卡就一定要在這裡加一組不一樣的**
#   (漏加或跟別章重複 → tests/test_music_style.py 紅 → 守門擋下)
STYLES = {
    1: ChimePadStyle(),         # 第一行第一小節(level9~18)：程式合成
    2: LullabyMarimbaStyle(),   # 第一行第二小節(level20~)：自製兒歌MIDI+SoundFont(乾聲)
}


def style_for_chapter(chapter):
    """取某個大關卡(1 起算)的音樂風格；沒定義就直接爆，不要默默用別章的。"""
    if chapter not in STYLES:
        raise KeyError(f"第 {chapter} 大關卡還沒定義音樂風格 —— "
                       f"請在 tools/music_style.py 的 STYLES 加一組跟其他章節都不同的風格"
                       f"（規矩見 docs/關卡音樂.md）")
    return STYLES[chapter]
