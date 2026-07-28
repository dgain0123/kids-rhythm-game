#!/usr/bin/env python3
"""英文人聲數拍 one/two/three/four — 給各關音樂產生器的預備拍用。

三層產生鏈(2026-07-28 AI會議室會議定案，記錄/會議_20260728_1221.md)：
    1) 真人錄音(最優先)：<專案>/sounds/voice/count.(wav|mp3|m4a|aiff) 整句自動切 4 字，
       或 one/two/three/four.(wav|mp3|m4a|aiff) 逐字檔——放了檔案重跑產生器即自動採用
    2) edge-tts 神經語音(en-US-AnaNeural 兒童女聲)：品質高；只在「產音檔時」上網，
       遊戲本身仍離線
    3) macOS say(Samantha) 後備：離線一定可用

驗收標準(會議共識)：四個字等長、重音一致、可精準對齊拍點，而非單純擬真度。

各 make_levelN_music.py 匯入使用：
    from voice_count import count_voices
    voices = count_voices(SR)          # [one, two, three, four] 的 numpy 波形
    add(k * 間隔, voices[k] * 0.6)
"""
import glob
import os
import subprocess
import tempfile
import wave

import numpy as np

WORDS = ["one", "two", "three", "four"]
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOICE_DIR = os.path.join(PROJ, "sounds", "voice")
EDGE_VOICE = "en-GB-LibbyNeural"  # 英國年輕女聲(2026-07-28 使用者從4候選中選定)
EXTS = ("wav", "mp3", "m4a", "aiff")


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


def _prep(x, sr):
    """不修剪、不淡入：保留字的完整頭尾(one 的 /w/ 滑音、four 的 /f/ 氣音與 /r/ 尾音
    都是軟邊緣，修剪會把它們切出「卡」感——2026-07-28 教訓)。
    只去掉編碼器 padding 的「純零」頭尾＋尾端 30ms 保險淡出，
    並回傳「起音點」(包絡首次達峰值 10% 處)讓字能對齊拍點。"""
    nz = np.where(np.abs(x) > 1e-4)[0]
    if len(nz):
        x = x[nz[0]: nz[-1] + 1]
    x = x.copy()
    fo = min(len(x), int(0.03 * sr))
    x[-fo:] *= np.linspace(1, 0, fo)
    win = int(0.01 * sr)
    env = np.convolve(np.abs(x), np.ones(win) / win, mode="same")
    onset = int(np.argmax(env > float(env.max()) * 0.1))
    return x, onset / sr


def _finalize(voices):
    """四個字整組響度對齊：每個字的 RMS 拉到一致(中位數)，再整組把峰值調到 1。
    voices = [(波形, 起音秒), ...]；避免各字各自拉滿造成音量落差。"""
    rms = [max(1e-9, float(np.sqrt(np.mean(v ** 2)))) for v, _ in voices]
    target = float(np.median(rms))
    voices = [(v * (target / r), on) for (v, on), r in zip(voices, rms)]
    peak = max(1e-9, max(float(np.max(np.abs(v))) for v, _ in voices))
    return [(v / peak, on) for v, on in voices]


def _split_by_silence(x, sr):
    """依靜音把整句切成字：音量包絡 > 門檻的連續區段(合併小空隙、丟太短的)。"""
    win = int(0.02 * sr)
    env = np.convolve(np.abs(x), np.ones(win) / win, mode="same")
    mask = env > 0.006
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


def _decode(path, sr):
    """任意音檔 → 單聲道 numpy(用 afconvert 轉 wav)。"""
    fd, tmp = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        subprocess.run(["afconvert", "-f", "WAVE", "-d", f"LEI16@{sr}", "-c", "1",
                        path, tmp], check=True, capture_output=True)
        return _load_wav(tmp)
    finally:
        os.remove(tmp)


def _find(basename):
    for ext in EXTS:
        hits = glob.glob(os.path.join(VOICE_DIR, f"{basename}.{ext}"))
        if hits:
            return hits[0]
    return None


def _from_recording(sr):
    """第1層：使用者真人錄音。逐字檔優先，其次整句檔自動切4字。"""
    words = [_find(w) for w in WORDS]
    if all(words):
        print("🎙 數拍人聲：使用真人錄音(逐字檔)")
        return _finalize([_prep(_decode(p, sr), sr) for p in words])
    phrase = _find("count")
    if phrase:
        x = _decode(phrase, sr)
        segs = _split_by_silence(x, sr)
        if len(segs) == 4:
            print("🎙 數拍人聲：使用真人錄音(整句自動切4字)")
            return _finalize([_prep(x[a:b], sr) for a, b in segs])
        raise ValueError(f"count 錄音切出 {len(segs)} 段(需要4段，字間留點空隙再錄)")
    return None


def _from_edge_tts(sr):
    """第2層：edge-tts 神經語音(僅產檔時上網)。
    一個字一個字合成——每個字同樣語氣，不會有整句切字的音高/音量落差。"""
    import asyncio

    import edge_tts

    async def gen_word(word, path):
        await edge_tts.Communicate(word + "!", voice=EDGE_VOICE).save(path)

    voices = []
    for word in WORDS:
        fd, tmp = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            asyncio.run(gen_word(word, tmp))
            voices.append(_prep(_decode(tmp, sr), sr))
        finally:
            os.remove(tmp)
    print(f"🗣 數拍人聲：edge-tts {EDGE_VOICE}(逐字合成+不修剪+起音對齊)")
    return _finalize(voices)


def _from_say_phrase(sr, voice="Samantha"):
    """第3層：macOS say 後備(整句合成再切字，離線一定可用)。"""
    x = _say("[[slnc 400]] one, two, three, four! [[slnc 500]]", sr, voice)
    segs = _split_by_silence(x, sr)
    if len(segs) == 4:
        print("🔈 數拍人聲：macOS say 後備")
        return _finalize([_prep(x[a:b], sr) for a, b in segs])
    return _finalize([_prep(_say(w, sr, voice), sr) for w in WORDS])


def count_voices(sr=44100, voice="Samantha"):
    """回傳 [(波形, 起音秒), ...] 共 4 個字(三層產生鏈，見檔頭)。
    產生器把「起音點」對齊拍點：add(拍點時間 - 起音秒, 波形)。"""
    try:
        rec = _from_recording(sr)
        if rec:
            return rec
    except Exception as e:
        print(f"⚠️ 真人錄音層失敗({e})，往下一層")
    try:
        return _from_edge_tts(sr)
    except Exception as e:
        print(f"⚠️ edge-tts 層失敗({e})，退回 say")
    return _from_say_phrase(sr, voice)
