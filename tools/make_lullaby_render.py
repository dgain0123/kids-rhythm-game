#!/usr/bin/env python3
"""第二大關卡的章節音樂素材：自製布拉姆斯搖籃曲 MIDI → SoundFont 離線 render（乾聲）。

規矩見 docs/關卡音樂.md 路線③。要點：
- 旋律＝布拉姆斯搖籃曲（1868，**公共領域**）；編曲與 MIDI 都是本專案自己寫的 → 零第三方權利。
- 寫成 3/4，**一拍 = 該關的一個拍點**（一小節 = 3 個拍點），所以音樂速度＝關卡速度×3：
  速度10→30BPM(一小節6秒)、速度20→60BPM(3秒)、速度30→90BPM(2秒)。
  render 出來本來就對齊拍點，不用偵測也不用變速。
  ★這條是 2026-08-03 使用者裁示（原本是「一小節＝一個拍點」，那樣速度30 會變 270BPM 太趕，
  只改一關又變成「速度10 的音樂比速度30 快」）。規矩見 docs/關卡音樂_做法詳解.md 路線③。
- `fluidsynth -R 0 -C 0` 關掉殘響與和聲效果 → **完全乾聲**（跟第一大關卡一樣乾淨）。

用法（--hit 填**一小節的秒數**＝3 個拍點）：
    python3 tools/make_lullaby_render.py --hit 6 --bars 6      # 速度10 用(30BPM)
    python3 tools/make_lullaby_render.py --hit 3 --bars 11     # 速度20 用(60BPM)
    python3 tools/make_lullaby_render.py --hit 2 --bars 15     # 速度30 用(90BPM)
產出：midi/搖籃曲_第二大關卡_hit<H>s.mid、sounds/music/source/lullaby_marimba_hit<H>s.wav

音色庫（31MB，不進 repo，見 .gitignore）：
    curl -L -o tools/soundfonts/GeneralUser-GS.sf2 \\
      https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/GeneralUser-GS.sf2
"""
import argparse
import os
import re
import subprocess
import sys

import pretty_midi

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SF2 = os.path.join(PROJ, "tools", "soundfonts", "GeneralUser-GS.sf2")
PROGRAM = 12          # GM 12 = Marimba（2026-08-03 使用者從四種音色試聽選定）

# 布拉姆斯搖籃曲（公共領域旋律），3/4，一小節三拍；None＝該拍延續前一音
BARS = [
    ["E4", "E4", "G4"], ["E4", "E4", "G4"], ["E4", "G4", "C5"], ["B4", "A4", "A4"],
    ["G4", None, None], ["D4", "E4", "F4"], ["D4", "E4", "F4"], ["D4", "F4", "B4"],
    ["A4", "G4", "A4"], ["B4", None, None], ["C5", "C5", "A4"], ["F4", "F4", "A4"],
    ["G4", "E4", "C4"], ["F4", "E4", "D4"], ["C5", "A4", "F4"], ["G4", "E4", "C4"],
]
CHORDS = ["C", "C", "C", "G", "C", "G", "G", "G", "G", "G", "F", "F", "C", "G", "F", "C"]
CH = {"C": (["C3", "E3", "G3"], "C2"),
      "G": (["B2", "D3", "G3"], "G2"),
      "F": (["A2", "C3", "F3"], "F2")}


def note_num(name):
    m = re.match(r"([A-G])([#b]?)(\d)", name)
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[m.group(1)]
    acc = {"": 0, "#": 1, "b": -1}[m.group(2)]
    return 12 * (int(m.group(3)) + 1) + base + acc


def build(hit_sec, n_bars, out_mid, out_wav):
    bpm = 3 * 60.0 / hit_sec          # 3/4：一小節 = hit_sec 秒
    spb = 60.0 / bpm
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    mel = pretty_midi.Instrument(program=PROGRAM, name="melody")
    acc = pretty_midi.Instrument(program=PROGRAM, name="accomp")
    for b in range(n_bars):
        bar, ch = BARS[b % len(BARS)], CHORDS[b % len(CHORDS)]
        t0 = b * 3 * spb
        for j, note in enumerate(bar):
            if note is None:
                continue
            long = (j == 0 and bar[1] is None)          # 全小節長音
            dur = spb * (2.8 if long else 0.95)
            mel.notes.append(pretty_midi.Note(velocity=100 if j == 0 else 82,
                                              pitch=note_num(note),
                                              start=t0 + j * spb, end=t0 + j * spb + dur))
        tones, bass = CH[ch]
        acc.notes.append(pretty_midi.Note(velocity=62, pitch=note_num(bass),
                                          start=t0, end=t0 + 3 * spb * 0.98))
        for j, tone in enumerate(tones):                # 三拍分解和弦(圓舞曲感)
            acc.notes.append(pretty_midi.Note(velocity=48, pitch=note_num(tone),
                                              start=t0 + j * spb, end=t0 + j * spb + spb * 0.9))
    pm.instruments += [mel, acc]
    pm.write(out_mid)

    if not os.path.exists(SF2):
        raise SystemExit(f"找不到音色庫 {SF2}——下載指令見本檔開頭說明")
    subprocess.run(["fluidsynth", "-ni", "-R", "0", "-C", "0", "-g", "0.9",
                    "-F", out_wav + ".tmp.wav", SF2, out_mid], check=True,
                   capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-v", "quiet", "-i", out_wav + ".tmp.wav",
                    "-ac", "1", "-ar", "44100", "-codec:a", "pcm_s16le", out_wav], check=True)
    os.remove(out_wav + ".tmp.wav")
    return bpm, n_bars * hit_sec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--hit", type=float, required=True,
                    help="素材一小節的秒數(＝關卡拍點間隔的整數倍)")
    ap.add_argument("--bars", type=int, required=True, help="要幾小節")
    a = ap.parse_args(argv)
    tag = f"{a.hit:g}"
    out_mid = os.path.join(PROJ, "midi", f"搖籃曲_第二大關卡_hit{tag}s.mid")
    out_wav = os.path.join(PROJ, "sounds", "music", "source", f"lullaby_marimba_hit{tag}s.wav")
    bpm, secs = build(a.hit, a.bars, out_mid, out_wav)
    print(f"✅ {os.path.basename(out_wav)}：3/4 {bpm:.0f}BPM（一小節={a.hit:g}秒）× {a.bars} 小節 = {secs:.0f} 秒")
    return 0


if __name__ == "__main__":
    sys.exit(main())
