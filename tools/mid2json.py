#!/usr/bin/env python3
"""mid→json 轉檔器：把 Logic 匯出的鼓 MIDI 轉成遊戲讀的關卡 JSON。

用法：
    python3 tools/mid2json.py <輸入.mid> [選項]

選項：
    -o, --out PATH       輸出檔（預設 charts/<midi檔名>.json）
    --title T            關卡標題
    --hint H             提示文字
    --only DRUM[,DRUM]   只保留某些鼓件(如 snare 或 snare,kick)
    --bars N             只取前 N 小節(預設 4/4)
    --max-hits N         覆寫 maxHits(預設=音符數)
    --dedup MS           同一時間點(毫秒內)的多鼓件只留一個(預設 30)

這是「mid→json 轉檔」這條規則的唯一正解檔。行為由 tests/test_mid2json.py 釘住。
"""
import argparse
import json
import os
import sys

import pretty_midi

# GM 鼓件 → 遊戲用簡化分類（給幼兒，只分大類）
GM_TO_DRUM = {
    35: "kick", 36: "kick",
    37: "snare", 38: "snare", 40: "snare",
    42: "hihat", 44: "hihat", 46: "hihat",
    41: "tom", 43: "tom", 45: "tom", 47: "tom", 48: "tom", 50: "tom",
    49: "cymbal", 51: "cymbal", 52: "cymbal", 55: "cymbal", 57: "cymbal", 59: "cymbal",
}

# 音符時值(以拍為單位) → 名稱；轉檔時把「到下一下的間隔」貼到最近的標準時值
NOTE_VALUES = {
    "whole": 4.0,
    "half": 2.0,
    "quarter": 1.0,
    "eighth": 0.5,
    "sixteenth": 0.25,
}


def snap_note_type(beats: float) -> str:
    """把一個以拍為單位的長度，貼到最接近的音符時值名稱。"""
    if beats <= 0:
        return "quarter"
    best, best_err = "quarter", float("inf")
    import math
    for name, val in NOTE_VALUES.items():
        err = abs(math.log2(beats / val))
        if err < best_err:
            best, best_err = name, err
    return best


def collect_hits(pm: pretty_midi.PrettyMIDI):
    """把所有鼓件音符收集成 (time, tick, pitch) 並依時間排序。"""
    hits = []
    for inst in pm.instruments:
        if not inst.is_drum:
            continue
        for n in inst.notes:
            hits.append((float(n.start), pm.time_to_tick(n.start), int(n.pitch)))
    hits.sort(key=lambda h: h[0])
    return hits


def convert(midi_path, title=None, hint=None, only=None, bars=None,
            max_hits=None, dedup_ms=30):
    pm = pretty_midi.PrettyMIDI(midi_path)
    resolution = pm.resolution or 480

    tempi = pm.get_tempo_changes()[1]
    bpm = float(tempi[0]) if len(tempi) else 120.0

    hits = collect_hits(pm)
    if not hits:
        raise ValueError("這個 MIDI 找不到任何鼓件音符(is_drum 音軌)。")

    # 起點對齊到第一下，讓 beat 從 0 開始
    t0 = hits[0][0]
    tick0 = hits[0][1]

    notes = []
    for time_s, tick, pitch in hits:
        drum = GM_TO_DRUM.get(pitch, "other")
        if only and drum not in only:
            continue
        beat = (tick - tick0) / resolution
        notes.append({"drum": drum, "beat": round(beat, 3),
                      "time": round(time_s - t0, 3), "pitch": pitch})

    # 同一時間點多鼓件(和音)只留第一個，避免幼兒版重複
    if dedup_ms and dedup_ms > 0:
        deduped = []
        last_t = -1e9
        for n in notes:
            if n["time"] * 1000 - last_t >= dedup_ms:
                deduped.append(n)
                last_t = n["time"] * 1000
        notes = deduped

    # 只取前 N 小節(預設 4/4 → 每小節 4 拍)
    if bars is not None:
        beats_per_bar = 4.0
        limit = bars * beats_per_bar
        notes = [n for n in notes if n["beat"] < limit]

    # 依「到下一下的間隔」決定每個音符的時值(quarter/eighth…)
    for i, n in enumerate(notes):
        if i + 1 < len(notes):
            ioi = notes[i + 1]["beat"] - n["beat"]
        else:
            ioi = 1.0  # 最後一下預設四分音符
        n["type"] = snap_note_type(ioi)

    if not notes:
        raise ValueError("過濾後沒有剩下任何音符(檢查 --only / --bars 條件)。")

    chart = {
        "title": title or os.path.splitext(os.path.basename(midi_path))[0],
        "bpm": round(bpm, 2),
        "maxHits": max_hits if max_hits is not None else len(notes),
        "notes": [{"type": n["type"], "drum": n["drum"], "beat": n["beat"]} for n in notes],
    }
    if hint:
        chart["hint"] = hint
    return chart


def main(argv=None):
    ap = argparse.ArgumentParser(description="鼓 MIDI → 遊戲關卡 JSON")
    ap.add_argument("midi")
    ap.add_argument("-o", "--out")
    ap.add_argument("--title")
    ap.add_argument("--hint")
    ap.add_argument("--only")
    ap.add_argument("--bars", type=int)
    ap.add_argument("--max-hits", type=int)
    ap.add_argument("--dedup", type=float, default=30)
    args = ap.parse_args(argv)

    only = set(s.strip() for s in args.only.split(",")) if args.only else None
    chart = convert(args.midi, title=args.title, hint=args.hint, only=only,
                    bars=args.bars, max_hits=args.max_hits, dedup_ms=args.dedup)

    out = args.out
    if not out:
        base = os.path.splitext(os.path.basename(args.midi))[0]
        proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out = os.path.join(proj, "charts", base + ".json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(chart, f, ensure_ascii=False, indent=2)
    print(f"✅ 轉好了：{out}（{len(chart['notes'])} 個音符, bpm={chart['bpm']}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
