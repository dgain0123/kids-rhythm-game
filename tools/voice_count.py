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


def count_voices(sr=44100, voice="Samantha"):
    """回傳 [one, two, three, four] 四段波形(已去頭尾靜音、峰值正規化)。"""
    out = []
    for word in WORDS:
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            subprocess.run(
                ["say", "-v", voice, "-o", tmp, f"--data-format=LEI16@{sr}", word],
                check=True)
            x = _load_wav(tmp)
        finally:
            os.remove(tmp)
        loud = np.where(np.abs(x) > 0.01)[0]
        if len(loud):
            x = x[loud[0]: loud[-1] + 1]
        x = x / max(1e-9, float(np.max(np.abs(x))))
        out.append(x)
    return out
