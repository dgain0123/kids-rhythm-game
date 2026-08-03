#!/usr/bin/env python3
"""把一份鼓 MIDI 原封不動換速度 → 產生「同內容、不同速度」的下一關 MIDI。

**為什麼有這支**（2026-08-04 使用者問「每個速度都要再給你 MIDI 嗎」）：
同一個章節裡連續好幾關常常是**內容一樣、只有速度不同**（第一大關卡的第14~18關就是
同一組 33 顆音符、tempo 60/70/80/90/100；第二大關卡的速度40~100 是同一組 49 顆）。
這種關卡**不用再去 Logic 匯出一份**——音符的 tick 完全不動、只改 tempo 事件就好，
這樣新關卡的節拍網格跟原始匯出檔**逐 tick 相同**，不會有捨入誤差。

⚠️ 內容要變（多一小節、換節奏型、加別的鼓件）就**不能**用這支，要重新匯出 MIDI。

用法：
    python3 tools/retempo_midi.py --src midi/第23關.mid --bpm 50 -o midi/第24關.mid
    python3 tools/retempo_midi.py --src midi/第23關.mid --bpm 50 60 70   # 一次幾關(-o 用樣板)
        -o 'midi/第{i}關.mid' --start-index 24

驗證：改完會自己比對「音符 tick 與原檔完全相同」，不同就直接爆。
"""
import argparse
import os
import sys

import mido


def note_ticks(path):
    """每個 note_on 的絕對 tick（tempo 無關），用來證明格子沒被動到。"""
    mid = mido.MidiFile(path)
    out = []
    for track in mid.tracks:
        t = 0
        for msg in track:
            t += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                out.append((t, msg.note))
    return sorted(out), mid.ticks_per_beat


def retempo(src, bpm, out):
    mid = mido.MidiFile(src)
    tempo = mido.bpm2tempo(bpm)
    found = False
    for track in mid.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                msg.tempo = tempo
                found = True
    if not found:                                   # 原檔沒寫 tempo：補在第一軌開頭
        mid.tracks[0].insert(0, mido.MetaMessage("set_tempo", tempo=tempo, time=0))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    mid.save(out)

    a, tpb_a = note_ticks(src)
    b, tpb_b = note_ticks(out)
    if a != b or tpb_a != tpb_b:
        raise SystemExit(f"❌ {out} 的音符格子跟 {src} 不一樣了（不該發生，請檢查 mido 版本）")
    return len(b), tpb_b


def main(argv=None):
    ap = argparse.ArgumentParser(description="同內容不同速度：只換 MIDI 的 tempo")
    ap.add_argument("--src", required=True, help="來源 MIDI（音符格子照抄這份）")
    ap.add_argument("--bpm", required=True, type=float, nargs="+", help="要產生的速度，可給多個")
    ap.add_argument("-o", "--out", required=True,
                    help="輸出路徑；給多個 --bpm 時用含 {i} 的樣板（i＝關號）")
    ap.add_argument("--start-index", type=int, default=None, help="{i} 的起始關號")
    a = ap.parse_args(argv)

    if len(a.bpm) > 1 and "{i}" not in a.out:
        ap.error("一次產生多關要用含 {i} 的 -o 樣板，並給 --start-index")
    for k, bpm in enumerate(a.bpm):
        out = a.out.format(i=(a.start_index or 0) + k) if "{i}" in a.out else a.out
        n, tpb = retempo(a.src, bpm, out)
        print(f"✅ {out}：tempo {bpm:g}、{n} 顆音符（tick 與 {os.path.basename(a.src)} 逐一相同，"
              f"ticks_per_beat {tpb}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
