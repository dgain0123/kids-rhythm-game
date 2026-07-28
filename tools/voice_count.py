#!/usr/bin/env python3
"""英文人聲數拍 one/two/three/four — 給各關音樂產生器的預備拍用。

用 macOS 內建 TTS(`say`, 預設 Samantha 美式人聲)即時合成，去掉頭尾靜音
(讓聲音正好落在拍點上)並正規化。各 make_levelN_music.py 匯入使用：

    from voice_count import count_voices
    voices = count_voices(SR)          # [one, two, three, four] 的 numpy 波形
    add(k * 間隔, voices[k] * 0.6)
"""
import os
import subprocess
import tempfile
import wave

import numpy as np

WORDS = ["one", "two", "three", "four"]


def _load_wav(path):
    with wave.open(path, "rb") as w:
        assert w.getnchannels() == 1, "say 輸出應為單聲道"
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float) / 32767.0
        return x


def _say(text, sr, voice):
    fd, tmp = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        subprocess.run(
            ["say", "-v", voice, "-o", tmp, f"--data-format=LEI16@{sr}", text],
            check=True)
        return _load_wav(tmp)
    finally:
        os.remove(tmp)


def _polish(x, sr):
    """去頭尾靜音(保留緩衝) + 淡入淡出 + 峰值正規化。"""
    loud = np.where(np.abs(x) > 0.005)[0]
    if len(loud):
        a = max(0, loud[0] - int(0.02 * sr))
        b = min(len(x), loud[-1] + 1 + int(0.10 * sr))
        x = x[a:b]
    x = x.copy()
    fi = min(len(x), int(0.008 * sr))
    fo = min(len(x), int(0.08 * sr))
    x[:fi] *= np.linspace(0, 1, fi)
    x[-fo:] *= np.linspace(1, 0, fo)
    return x / max(1e-9, float(np.max(np.abs(x))))


def _split_by_silence(x, sr):
    """依靜音把整句切成字：音量包絡 > 門檻的連續區段(合併小空隙、丟太短的)。"""
    win = int(0.02 * sr)
    env = np.convolve(np.abs(x), np.ones(win) / win, mode="same")
    mask = env > 0.01
    # 找連續 True 區段
    edges = np.flatnonzero(np.diff(mask.astype(int)))
    idx = np.concatenate(([0], edges + 1, [len(x)]))
    runs = [(idx[i], idx[i + 1]) for i in range(len(idx) - 1) if mask[idx[i]]]
    # 合併相距 <90ms 的區段(字內短暫靜音，如 t 的氣音)
    merged = []
    for a, b in runs:
        if merged and a - merged[-1][1] < int(0.09 * sr):
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    # 丟掉 <60ms 的雜訊段
    return [(a, b) for a, b in merged if b - a >= int(0.06 * sr)]


def count_voices(sr=44100, voice="Samantha"):
    """回傳 [one, two, three, four] 四段波形。

    整句合成「one, two, three, four!」(語氣自然、不會一字一頓的死板)，
    再依靜音切成四個字；切不出剛好四段才退回一個字一個字合成。
    """
    x = _say("one, two, three, four!", sr, voice)
    segs = _split_by_silence(x, sr)
    if len(segs) == 4:
        return [_polish(x[a:b], sr) for a, b in segs]
    # 後備：逐字合成
    return [_polish(_say(w, sr, voice), sr) for w in WORDS]
