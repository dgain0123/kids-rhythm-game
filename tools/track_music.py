#!/usr/bin/env python3
"""現成音樂 → 關卡音樂：把一首現成曲子**變速對齊關卡拍點**，再疊上預備拍人聲與節拍器。

這是「用現成音樂做關卡音樂」這條路線的唯一正解檔（另一條是純合成，見 music_style.py）。
規矩與步驟見 docs/關卡音樂.md。

★授權：repo 是公開的 → **只收 CC0／公共領域**素材，且來源與授權一定要登記在
  `sounds/music/source/來源與授權.md`（曾踩過版權坑，見 docs/踩過的坑.md）。

做法：
  1. 用 librosa 抓拍點 → **抗漏拍的穩健擬合**算出「每拍幾秒」
     （直接最小平方會被漏拍/多拍拉歪：先用中位數拍距推每個拍點的序號，再擬合）
  2. 選「一個遊戲拍點 = N 拍」：讓變速倍率越接近 1 越好，
     N∈{3,4,6,8}(容易落在小節線上)優先、容許範圍也放寬
  3. time-stretch（保持音高）→ 重新量一次拍距，檢查整首的累積漂移
  4. 從一個「小節起點」切入，鋪到需要的長度（不夠就接續循環）
  5. 疊上 4 拍英文人聲預備拍（**純人聲、底下不疊節拍器**）
     ＋每個拍點一聲節拍器（音色來自章節風格）→ 淡出 → m4a

**同一首曲子可以給同章節不同速度的關卡用**：只要換 hit_sec（＝該關拍點間隔），
本工具會重新選 N 與變速倍率。
"""
import os

import librosa
import numpy as np

from music_style import Mixer
from voice_count import count_voices

SR = 44100
NICE_N = {3, 4, 6, 8}          # 一個拍點＝幾拍：這些比較容易落在小節線上
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_DIR = os.path.join(PROJ, "sounds", "music", "source")


HOP = 512


def onset_env(y, sr, hop=HOP):
    """起音強度包絡(正規化)。`librosa.beat.beat_track` 對管風琴這種
    連續音色會抓錯拍(實測把 99.4BPM 抓成 95.5)，所以本工具不用它，
    改用『自相關求週期 + 梳狀掃相位』——對各種素材都穩。"""
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop, aggregate=np.median)
    return (env - env.mean()) / (env.std() + 1e-9)


def comb_score(env, fps, period, t0=0.0, t1=None):
    """梳狀取樣：回傳 (最佳相位秒, 對比度)。對比度＝網格上的平均能量 ÷ 整段平均，
    >1.3 代表音樂的拍子真的落在這個間隔的網格上。取樣點取 ±1 幀的最大值(抗抖)。"""
    n = len(env)
    a = int(max(0, t0 * fps))
    b = int(min(n, (t1 if t1 is not None else n / fps) * fps))
    seg = env[a:b]
    if len(seg) < 20:
        return 0.0, 0.0
    base = float(np.mean(np.maximum(seg, 0))) + 1e-9
    ticks = np.arange(0, (len(seg) / fps) - period, period)
    best_ph, best_sc = 0.0, -1.0
    for ph in np.linspace(0, period, 96, endpoint=False):
        idx = np.round((ph + ticks) * fps).astype(int)
        idx = idx[(idx >= 1) & (idx < len(seg) - 1)]
        if not len(idx):
            continue
        sc = float(np.mean(np.maximum.reduce([seg[idx - 1], seg[idx], seg[idx + 1]])))
        if sc > best_sc:
            best_sc, best_ph = sc, ph
    return a / fps + best_ph, best_sc / base


def estimate_period(y, sr, lo=0.25, hi=1.6, hop=HOP):
    """量「每拍幾秒」：先用起音包絡自相關抓粗值，再用梳狀能量在 ±7% 內精修。
    精修很重要——長曲子上 0.1% 的誤差就會累積成幾百毫秒的漂移。"""
    env = onset_env(y, sr, hop)
    fps = sr / hop
    ac = librosa.autocorrelate(env, max_size=int(hi * fps) + 2)
    ac[: int(lo * fps)] = 0
    p0 = float(np.argmax(ac)) / fps
    best = (None, -1.0, 0.0)
    for p in np.linspace(p0 * 0.93, p0 * 1.07, 141):
        ph, c = comb_score(env, fps, p)
        if c > best[1]:
            best = (p, c, ph)
    period, contrast, phase = best
    return float(period), float(contrast), float(phase), env, fps


def de_space(y, sr, amount=0.0, thresh=0.18, win=0.015, smooth=0.025):
    """去空間感（向下擴張）：把音符**之間**的殘響尾巴壓掉，聽起來就乾淨、貼近乾聲。

    現成錄音的房間殘響是烤在檔案裡的，去不掉但可以「壓小」——
    門檻以下的訊號（＝尾巴、房間音）依比例衰減，門檻以上（＝音符本身）完全不動。
    amount 0＝不處理、0.5＝中等、1.0＝很乾（比例 1:3）。
    ⚠️ 只能用在音樂本身，別套到人聲/節拍器（那些本來就是乾的）。"""
    if amount <= 0:
        return y
    ratio = 1.0 + 2.0 * min(1.0, amount)          # 1.0~3.0
    n = max(1, int(win * sr))
    env = np.sqrt(np.convolve(y ** 2, np.ones(n) / n, mode="same")) + 1e-9
    gain = np.where(env < thresh, (env / thresh) ** (ratio - 1.0), 1.0)
    m = max(1, int(smooth * sr))
    gain = np.convolve(gain, np.ones(m) / m, mode="same")
    return y * gain


def pick_rate(period, hit_sec):
    """選『一個遊戲拍點 = N 拍』與變速倍率 rate。
    rate = 原拍長 / 目標拍長；>1 = 音樂要加快、<1 = 要放慢。"""
    best = None
    for n in range(1, 13):
        rate = period / (hit_sec / n)
        nice = n in NICE_N
        if not ((0.70 if nice else 0.80) <= rate <= (1.45 if nice else 1.25)):
            continue
        score = abs(np.log(rate)) * (0.45 if nice else 1.0)
        if best is None or score < best[0]:
            best = (score, n, rate)
    if best is None:                                 # 落不進範圍就取最接近的
        n = max(1, int(round(hit_sec / period)))
        best = (0.0, n, period / (hit_sec / n))
    return best[1], best[2]


def render(style, hit_sec, n_hits, out_path, lead_hits=4, pre=1.0, tail=4.0,
           music_gain=0.55, voice_gain=0.30, sr=SR, max_drift=0.08, source_hit=None,
           count_sec=None):
    """做出一關的音樂檔。回傳 (總長秒, 說明字串)。
    style：章節風格(要有 source 檔名與 click 節拍器音色)。
    voice_gain 預設 0.40＝實測讓預備拍音量跟第一大關卡一致(-18.8dB)：**人聲推太大(曾設 0.85)，母帶壓縮會把
    edge-tts 人聲本身的 mp3 編碼雜訊放出來**，使用者聽得出來(2026-08-03)。
    hit_sec：該關的拍點間隔；n_hits：要打幾下。

    count_sec：**預備拍人聲的間隔(秒)**，預設＝hit_sec(＝速度50以下的規矩)。
    速度60起改成「四分音符(一拍)一聲」——三連音關卡的一拍＝3 個拍點，就填 count_sec=3*hit_sec
    （規矩見 docs/關卡系統.md 的預備拍那條；八分/三連音間隔太趕，而且人聲字長 0.72~0.79 秒，
    間隔一短就整片疊在一起）。音樂進場點＝pre + lead_hits × count_sec，節拍器仍然只在拍點上。

    source_hit：**素材的小節長度(秒)**，預設＝hit_sec(一小節＝一個拍點)。
    關卡越快、素材照著變快就會變得又急又吵（速度30 照算是 270BPM，使用者打槍），
    這時改成**一小節＝好幾個拍點**：填 source_hit＝小節長度即可。
    ⚠️ **一定要是 hit_sec 的整數倍**，不然小節線就落不在拍點上、整首會慢慢跑掉
    （由 tests/test_music_style.py 釘住）。

    style.aligned_render=True（**自製 MIDI 用 SoundFont render 出來的素材**）時：
    我們自己決定的速度，本來就精準對齊拍點 → 跳過偵測與變速，直接把音樂放在第一個拍點上。"""
    name = (style.source_for(source_hit or hit_sec)
            if hasattr(style, "source_for") else style.source)
    src = os.path.join(SOURCE_DIR, name)
    y, _ = librosa.load(src, sr=sr, mono=True)

    count = count_sec or hit_sec                # 預備拍人聲間隔(預設＝拍點間隔)
    lead_span = lead_hits * count               # 預備拍總長(音樂進場前)

    if getattr(style, "aligned_render", False):
        span = pre + lead_span + n_hits * hit_sec
        mx = Mixer(span + tail, sr)
        t0 = pre + lead_span                    # 音樂從第一個拍點開始(預備拍只有人聲)
        # ★母帶(壓縮+響度)**只作用在音樂上**：預備拍底下沒音樂，若整軌一起壓，
        # 壓縮器會把人聲連同它的編碼雜訊一起抬起來——使用者聽出來「人聲雜」(2026-08-03)。
        # 音樂先做好母帶，人聲與節拍器最後原封不動疊上去，最後只等比例調音量。
        seg = y[: int((len(mx.buf) / sr - t0) * sr)]
        # ★**完全不壓縮**（2026-08-03 使用者裁示：「壓縮要拿掉」）——
        # 壓縮會吃掉動態(實測把 14.7dB 的 crest factor 壓成 6.7dB)並把雜訊抬起來。
        # 這裡只做「等比例調音量」：在不削波的前提下盡量推大(峰值上限 CLEAN_PEAK)。
        from music_style import CLEAN_PEAK
        gain = CLEAN_PEAK / max(1e-9, float(np.max(np.abs(seg))))
        mx.buf[int(t0 * sr): int(t0 * sr) + len(seg)] += seg * gain
        # 預備拍＝**純人聲、底下不疊節拍器**（跟第一大關卡一模一樣；
        # 之前我在人聲底下加節拍器墊底，使用者聽出來「雜」——2026-08-03 裁示改回）
        for k, (v, on) in enumerate(count_voices(sr)):
            i = max(0, int((pre + k * count - on) * sr))
            mx.buf[i:i + len(v)] += v[: len(mx.buf) - i] * voice_gain
        for k in range(n_hits):                 # 節拍器只在拍點上
            style.click(mx, t0 + k * hit_sec)
        secs = mx.finish(out_path, clean=True)  # ★整軌也不壓縮，只等比例調音量
        return secs, (f"素材 {name}：自製 MIDI＋SoundFont render(乾聲)，"
                      f"速度本來就對齊拍點 → 不偵測、不變速；音樂自 {t0:.0f} 秒進場")

    period, contrast0, _, _, _ = estimate_period(y, sr)
    if contrast0 < 1.20:
        raise ValueError(f"{style.source} 找不到清楚的拍子(對比度 {contrast0:.2f})——"
                         f"這種素材不適合跟拍關卡，換一首")
    n, rate = pick_rate(period, hit_sec)
    ys = librosa.effects.time_stretch(y, rate=rate) if abs(rate - 1) > 1e-3 else y

    # 變速後直接量「音樂的拍子有沒有落在目標網格上」(不重跑 beat_track，避免節拍層級誤判)
    target = hit_sec / n
    span = pre + lead_span + n_hits * hit_sec
    need_sec = span + tail
    env = onset_env(ys, sr)
    fps = sr / HOP
    phase, contrast = comb_score(env, fps, target)
    if contrast < 1.20:
        raise ValueError(f"{style.source} 變速後拍子對不上目標網格(對比度 {contrast:.2f})"
                         f"——換素材或改 N")
    # 前後段各自量相位 → 相位差＝整段用下來的累積漂移
    usable = min(len(ys) / sr, need_sec)
    ph_a, _ = comb_score(env, fps, target, 0, usable / 2)
    ph_b, _ = comb_score(env, fps, target, usable / 2, usable)
    d = (ph_b - ph_a) % target
    drift = min(d, target - d)
    if drift > max_drift:
        raise ValueError(f"{style.source} 對齊漂移過大：{drift*1000:.0f}ms > {max_drift*1000:.0f}ms"
                         f"（前後段相位差）——換素材或改 N")

    # 切入點：對齊到量到的拍子相位(且跳過開頭的底噪/淡入)
    start = phase
    while start < 0.3:
        start += target * n          # 一次跳一個「遊戲拍點」的量，保持相位

    total = span + tail
    mx = Mixer(total, sr)
    seg = ys[int(start * sr):]
    need = len(mx.buf) - int(pre * sr)
    if len(seg) < need:                              # 不夠長就接續循環
        seg = np.tile(seg, int(np.ceil(need / len(seg))))
    mx.buf[int(pre * sr):] += seg[:need] * music_gain

    # 預備拍人聲(騎在音樂上)：不修剪、用起音點對齊拍點
    for k, (v, on) in enumerate(count_voices(sr)):
        i = max(0, int((pre + k * count - on) * sr))
        mx.buf[i:i + len(v)] += v[: len(mx.buf) - i] * voice_gain

    # 節拍器**只在拍點上響**；預備拍＝純人聲（跟第一大關卡一致，2026-08-03 使用者裁示：
    # 我原本把節拍器墊在人聲底下，使用者聽出來「雜」）
    for k in range(n_hits):
        style.click(mx, pre + lead_span + k * hit_sec)

    secs = mx.finish(out_path)
    info = (f"素材 {style.source}：原速 {60/period:.2f}BPM(拍子對比度 {contrast0:.1f}) → "
            f"一個拍點={n}拍，{'加快' if rate > 1 else '放慢'} {abs(rate-1)*100:.1f}% → "
            f"{60/target:.2f}BPM；對齊對比度 {contrast:.1f}、"
            f"整段漂移 {drift*1000:.0f}ms(上限{max_drift*1000:.0f}ms)、切入點 {start:.2f}s")
    return secs, info
