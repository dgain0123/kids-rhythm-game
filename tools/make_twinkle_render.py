#!/usr/bin/env python3
"""第三大關卡的章節音樂素材：自製小星星 MIDI → SoundFont 離線 render（乾聲）。

規矩見 docs/關卡音樂.md 路線③。要點：
- 旋律＝小星星（Twinkle Twinkle Little Star，法國民謠 18 世紀，**公共領域**）；
  編曲與 MIDI 都是本專案自己寫的 → 零第三方權利。
- 寫成 4/4，**一拍 = 該關的一個拍點**（一小節 = 4 個拍點＝第三章十六分音符的一拍×4），
  所以音樂速度＝關卡速度×4：速度10→40BPM(一小節6秒)、速度30→120BPM(2秒)、速度100→400BPM。
  render 出來本來就對齊拍點，不用偵測也不用變速（風格 `aligned_render=True`）。
- 樂器＝尼龍弦吉他(GM 24)旋律＋和弦輕撥、原聲貝斯(GM 32)——
  2026-08-14 使用者從三個候選（吉他/直笛/手風琴）試聽選定吉他。
- `fluidsynth -R 0 -C 0` 關掉殘響與和聲效果 → **完全乾聲**。

用法（--hit 填**一小節的秒數**＝4 個拍點）：
    python3 tools/make_twinkle_render.py --hit 6 --bars 5      # 速度10 用(40BPM)
    python3 tools/make_twinkle_render.py --hit 2 --bars 15     # 速度30 用(120BPM)
產出：midi/小星星_第三大關卡_hit<H>s.mid、sounds/music/source/twinkle_guitar_hit<H>s.wav

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
MEL_PROG = 24         # GM 24 = 尼龍弦吉他（旋律與和弦輕撥）
BASS_PROG = 32        # GM 32 = 原聲貝斯
PAD_PROG = 48         # GM 48 = 弦樂合奏（很小聲的長音墊底）——撥弦音符之間會空掉，
                      # 沒有墊底的話慢速關卡「響段響度」比其他章低 >3dB（守門⑨紅）；
                      # 軟起音也符合「不可被麥克風誤判成鼓聲」的規矩

# 各速度素材的墊底力度（實測調出來的，keys=--hit 的 %g 字串）：
# 墊底愈大響段愈高，**但慢速素材的弦樂 swell 會把峰值頂高**（乾淨母帶頂峰值後
# 整段反而被壓小：hit6s 用 68 量出來 -16.0、用 62 是 -13.2）→ 每個速度各有最佳值，
# 守門⑨（各關響段差 ≤3dB）夾出這張表。改編曲後要重新量。
PAD_VEL = {"6": 62}   # hit6s 用 68 量出來 -16.0、62 才是 -13.2
PAD_VEL_DEFAULT = 68  # hit1.5s 實測 62→-14.0、68→-13.6、70→-13.8 → 68 已是極值

# 小星星（公共領域旋律），F 大調 4/4，一小節四拍；None＝該拍延續前一音
BARS = [
    ["F4", "F4", "C5", "C5"], ["D5", "D5", "C5", None],
    ["Bb4", "Bb4", "A4", "A4"], ["G4", "G4", "F4", None],
    ["C5", "C5", "Bb4", "Bb4"], ["A4", "A4", "G4", None],
    ["C5", "C5", "Bb4", "Bb4"], ["A4", "A4", "G4", None],
]
# 每小節 2 個和弦（半小節一個）
CHORDS = [["F", "F"], ["Bb", "F"], ["Bb", "F"], ["C", "F"],
          ["F", "Bb"], ["F", "C"], ["F", "Bb"], ["F", "C"]]
CH = {"F": (["F3", "A3", "C4"], "F2"),
      "Bb": (["F3", "Bb3", "D4"], "Bb2"),
      "C": (["E3", "G3", "C4"], "C3")}


def note_num(name):
    m = re.match(r"([A-G])([#b]?)(\d)", name)
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[m.group(1)]
    acc = {"": 0, "#": 1, "b": -1}[m.group(2)]
    return 12 * (int(m.group(3)) + 1) + base + acc


def build(hit_sec, n_bars, out_mid, out_wav, pad_vel=62):
    bpm = 4 * 60.0 / hit_sec          # 4/4：一小節 = hit_sec 秒
    spb = 60.0 / bpm
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    mel = pretty_midi.Instrument(program=MEL_PROG, name="melody")
    acc = pretty_midi.Instrument(program=MEL_PROG, name="accomp")
    bass = pretty_midi.Instrument(program=BASS_PROG, name="bass")
    pad = pretty_midi.Instrument(program=PAD_PROG, name="pad")
    for b in range(n_bars):
        bar, ch2 = BARS[b % len(BARS)], CHORDS[b % len(CHORDS)]
        t0 = b * 4 * spb
        for j, note in enumerate(bar):
            if note is None:
                continue
            k = 1                     # 延音：後面接著幾個 None 就撐多長
            while j + k < 4 and bar[j + k] is None:
                k += 1
            mel.notes.append(pretty_midi.Note(
                velocity=92 if j in (0, 2) else 82, pitch=note_num(note),
                start=t0 + j * spb, end=t0 + (j + k) * spb * 0.98))
        # 力度與起音錯開是調出來的：撥弦吉他峰值因子大，母帶不准壓縮（守門⑨⑪），
        # 只能把織體填厚＋讓同拍的起音**錯開幾毫秒**（輕刷 strum）——同時起音會把
        # 峰值疊高、害整首被等比例壓小，錯開後峰值降、響段響度就跟其他章節齊。
        for h in range(2):            # 半小節一個和弦：低音撐半小節、第2/4拍輕刷和弦
            tones, bs = CH[ch2[h]]
            th = t0 + h * 2 * spb
            bass.notes.append(pretty_midi.Note(velocity=88, pitch=note_num(bs),
                                               start=th + 0.008, end=th + 2 * spb * 0.95))
            for g, tone in enumerate(tones):
                acc.notes.append(pretty_midi.Note(velocity=78, pitch=note_num(tone),
                                                  start=th + spb + 0.010 * g,
                                                  end=th + spb * 1.9))
            for tone in tones:        # 弦樂長音墊底(撐滿半小節，填掉撥弦之間的空隙)
                pad.notes.append(pretty_midi.Note(velocity=pad_vel, pitch=note_num(tone),
                                                  start=th, end=th + 2 * spb * 0.98))
    pm.instruments += [mel, acc, bass, pad]
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
                    help="素材一小節的秒數(＝4 × 該關拍點間隔)")
    ap.add_argument("--bars", type=int, required=True, help="要幾小節")
    ap.add_argument("--pad-vel", type=int, default=None,
                    help="弦樂墊底力度(不給就用 PAD_VEL 表的實測值)")
    a = ap.parse_args(argv)
    tag = f"{a.hit:g}"
    pad_vel = a.pad_vel if a.pad_vel is not None else PAD_VEL.get(tag, PAD_VEL_DEFAULT)
    out_mid = os.path.join(PROJ, "midi", f"小星星_第三大關卡_hit{tag}s.mid")
    out_wav = os.path.join(PROJ, "sounds", "music", "source", f"twinkle_guitar_hit{tag}s.wav")
    bpm, secs = build(a.hit, a.bars, out_mid, out_wav, pad_vel=pad_vel)
    print(f"✅ {os.path.basename(out_wav)}：4/4 {bpm:.0f}BPM（一小節={a.hit:g}秒）"
          f"× {a.bars} 小節 = {secs:.0f} 秒（墊底力度 {pad_vel}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
