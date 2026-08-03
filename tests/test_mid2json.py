"""釘住 mid→json 轉檔器的行為。用合成 MIDI 測試，不依賴外部檔案。"""
import os
import sys

import pretty_midi

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import mid2json  # noqa: E402


def _make_midi(events, bpm=120, is_drum=True):
    """events: [(beat, pitch)] 或 [(beat, pitch, dur_beats)]，回傳寫好的暫存 MIDI 路徑。"""
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    drum = pretty_midi.Instrument(program=0, is_drum=is_drum, name="Drums")
    sec_per_beat = 60.0 / bpm
    for ev in events:
        beat, pitch = ev[0], ev[1]
        dur = ev[2] * sec_per_beat if len(ev) > 2 else 0.05
        t = beat * sec_per_beat
        drum.notes.append(pretty_midi.Note(velocity=100, pitch=pitch, start=t, end=t + dur))
    pm.instruments.append(drum)
    path = os.path.join(os.path.dirname(__file__), "_tmp_test.mid")
    pm.write(path)
    return path


def test_snap_note_type():
    assert mid2json.snap_note_type(1.0) == "quarter"
    assert mid2json.snap_note_type(0.5) == "eighth"
    assert mid2json.snap_note_type(2.0) == "half"
    assert mid2json.snap_note_type(0.25) == "sixteenth"
    assert mid2json.snap_note_type(4.0) == "whole"
    # 三連音(1/3 拍)：加進來之後，八分/十六分不可以被搶走
    assert mid2json.snap_note_type(1.0 / 3.0) == "triplet"
    assert mid2json.snap_note_type(0.334) == "triplet"  # beat 四捨五入到小數三位的實際值
    assert mid2json.snap_note_type(0.325) == "triplet"  # 斷奏輸入的最後一顆(音長 0.325 拍)


def test_gm_mapping():
    assert mid2json.GM_TO_DRUM[36] == "kick"
    assert mid2json.GM_TO_DRUM[38] == "snare"
    assert mid2json.GM_TO_DRUM[42] == "hihat"


def test_basic_convert():
    path = _make_midi([(0, 36), (1, 38), (2, 36), (3, 38)])
    try:
        chart = mid2json.convert(path)
        assert chart["maxHits"] == 4
        beats = [n["beat"] for n in chart["notes"]]
        assert beats == [0.0, 1.0, 2.0, 3.0]
        drums = [n["drum"] for n in chart["notes"]]
        assert drums == ["kick", "snare", "kick", "snare"]
        assert all(n["type"] == "quarter" for n in chart["notes"])
    finally:
        os.remove(path)


def test_only_filter_and_type():
    path = _make_midi([(0, 36), (1, 38), (2, 36), (3, 38)])
    try:
        chart = mid2json.convert(path, only={"snare"})
        assert len(chart["notes"]) == 2
        assert all(n["drum"] == "snare" for n in chart["notes"])
        # 小鼓相隔 2 拍 → half（最後一下預設 quarter）
        assert chart["notes"][0]["type"] == "half"
    finally:
        os.remove(path)


def test_max_hits_override_and_bars():
    path = _make_midi([(0, 36), (1, 38), (2, 36), (3, 38)])
    try:
        chart = mid2json.convert(path, max_hits=1, bars=1)
        assert chart["maxHits"] == 1
        # 前 1 小節(4 拍) → beat < 4 全中，共 4 個
        assert len(chart["notes"]) == 4
    finally:
        os.remove(path)


def test_non_drum_track_fallback():
    """Logic 匯出常沒標 is_drum：整份沒有鼓軌時，改收所有音軌。"""
    path = _make_midi([(0, 38), (0.5, 38), (1, 38)], is_drum=False)
    try:
        chart = mid2json.convert(path)
        assert len(chart["notes"]) == 3
        assert all(n["drum"] == "snare" for n in chart["notes"])
    finally:
        os.remove(path)


def test_tolerance_music_leadin_fields():
    """跟拍關卡的三個新欄位：toleranceBeats / music / leadInSec。"""
    path = _make_midi([(0, 38), (1, 38)])
    try:
        chart = mid2json.convert(path, tolerance=0.5,
                                 music="sounds/music/level9.m4a", lead_in=12,
                                 pre_roll=1)
        assert chart["toleranceBeats"] == 0.5
        assert chart["music"] == "sounds/music/level9.m4a"
        assert chart["leadInSec"] == 12
        assert chart["preRollSec"] == 1
        # 節拍器細分(每關可不同；聲音烤在音樂檔，這欄位是規格記錄)
        with_met = mid2json.convert(path, metronome="eighth")
        assert with_met["metronome"] == "eighth"
        # 沒給就不該出現這些欄位(舊關卡 json 不受影響)
        plain = mid2json.convert(path)
        assert "toleranceBeats" not in plain
        assert "music" not in plain
        assert "leadInSec" not in plain
        assert "metronome" not in plain
        assert "preRollSec" not in plain
    finally:
        os.remove(path)


def test_last_note_type_from_duration():
    """最後一顆音符：有實際長度就用長度判時值(第9關=8個八分+結尾1個四分)；
    長度太短(斷奏輸入)才沿用前一個間隔。"""
    # 8 個八分(每 0.5 拍) + 最後一顆在 beat 4.0、長度 1 拍 → quarter
    events = [(i * 0.5, 38, 0.49) for i in range(8)] + [(4.0, 38, 1.0)]
    path = _make_midi(events, bpm=10, is_drum=False)
    try:
        chart = mid2json.convert(path)
        types = [n["type"] for n in chart["notes"]]
        assert types == ["eighth"] * 8 + ["quarter"]
    finally:
        os.remove(path)


def test_slow_bpm10_eighths():
    """BPM 10、每 3 秒一下(半拍) → beat 0,0.5,1…、type=eighth、bpm=10。"""
    path = _make_midi([(i * 0.5, 38) for i in range(8)], bpm=10, is_drum=False)
    try:
        chart = mid2json.convert(path)
        assert chart["bpm"] == 10.0
        assert [n["beat"] for n in chart["notes"]] == [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
        assert all(n["type"] == "eighth" for n in chart["notes"])
    finally:
        os.remove(path)


def test_triplets_one_bar():
    """第19關：BPM10、每 2 秒一下(1/3 拍)、共 12 下＝4 個三連音(1 小節)。
    最後一顆用 MIDI 音長(1.95 秒=0.325 拍)判，也要是 triplet。"""
    events = [(i / 3.0, 38, 0.325) for i in range(12)]
    path = _make_midi(events, bpm=10, is_drum=False)
    try:
        chart = mid2json.convert(path)
        assert len(chart["notes"]) == 12
        assert all(n["type"] == "triplet" for n in chart["notes"]), \
            [n["type"] for n in chart["notes"]]
        assert all(n["drum"] == "snare" for n in chart["notes"])
        # 12 顆三連音 = 4 拍 = 剛好一小節(最後一顆在第 11/3 拍)
        assert abs(chart["notes"][-1]["beat"] - 11 / 3.0) < 0.01
    finally:
        os.remove(path)


def test_count_mode_no_timing():
    """數下數關卡(不配速度)：輸出不能有 bpm，音符不能有 beat
    (有的話遊戲會誤判成跟拍模式)。"""
    path = _make_midi([(i / 3.0, 38, 0.325) for i in range(12)], bpm=10, is_drum=False)
    try:
        chart = mid2json.convert(path, count_mode=True, title="打12下", max_hits=12)
        assert "bpm" not in chart
        assert all("beat" not in n for n in chart["notes"])
        assert chart["title"] == "打12下"
        assert chart["maxHits"] == 12
        assert len(chart["notes"]) == 12
        # 沒開 count_mode 就照舊有 bpm/beat(舊關卡不受影響)
        timed = mid2json.convert(path)
        assert timed["bpm"] == 10.0
        assert timed["notes"][0]["beat"] == 0.0
    finally:
        os.remove(path)


def test_triplet_timed_level():
    """第20關(三連音跟拍關卡)：12 個三連音 + 第2小節開頭 1 個四分音符收尾＝13 下。
    不開 count_mode → 要有 bpm/beat；拍點每 2 秒一下(BPM10 的 1/3 拍)，容許 1/3 拍＝±2 秒。
    最後那顆用 MIDI 實際音長(約 1 拍)判成 quarter，不可以被貼成 triplet。"""
    events = [(i / 3.0, 38, 0.325) for i in range(12)] + [(4.0, 38, 0.992)]
    path = _make_midi(events, bpm=10, is_drum=False)
    try:
        chart = mid2json.convert(path, tolerance=0.3333, metronome="triplet",
                                 music="./sounds/music/level20.m4a",
                                 lead_in=9, pre_roll=1)
        assert chart["bpm"] == 10.0
        assert chart["metronome"] == "triplet"
        assert chart["leadInSec"] == 9
        assert chart["maxHits"] == 13
        types = [n["type"] for n in chart["notes"]]
        assert types == ["triplet"] * 12 + ["quarter"], types
        spb = 60.0 / chart["bpm"]
        times = [n["beat"] * spb for n in chart["notes"]]
        assert all(abs(t - 2.0 * i) < 0.01 for i, t in enumerate(times)), times
        assert abs(chart["toleranceBeats"] * spb - 2.0) < 0.01  # 1/3 拍 = 2 秒
    finally:
        os.remove(path)


SAME_CONTENT_LEVELS = list(range(23, 30))   # 第23~29關＝速度40~100，內容完全一樣


def test_same_content_levels_share_grid():
    """**同內容不同速度的關卡，譜面音符必須逐顆一樣**（只有 bpm/title/容許秒數不同）。

    第23~29關（速度40~100）是同一份內容：MIDI 由 `tools/retempo_midi.py` 從
    `midi/第23關.mid` 只換 tempo 產生（音符 tick 逐一相同）。這條測試就是防止
    以後只重出其中一關、悄悄變成「內容不一樣了」——那會讓小朋友練同一段的手感斷掉。
    要故意讓某關內容不同，就把它從 SAME_CONTENT_LEVELS 移掉並在該關 md 寫清楚。
    """
    import json
    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base_notes = None
    for lv in SAME_CONTENT_LEVELS:
        path = os.path.join(proj, "charts", f"level{lv}.json")
        assert os.path.exists(path), f"缺 charts/level{lv}.json（同內容關卡表裡有它）"
        chart = json.load(open(path, encoding="utf-8"))
        notes = [(n["type"], n["drum"], n["beat"]) for n in chart["notes"]]
        assert chart["toleranceBeats"] == 0.3333, (
            f"level{lv} 的容許值不是 1/3 拍（使用者 2026-08-04 指定這幾關全部 1/3 拍）")
        if base_notes is None:
            base_notes, base_lv = notes, lv
            continue
        assert notes == base_notes, (
            f"level{lv} 的譜面跟 level{base_lv} 不一樣了（{len(notes)} vs {len(base_notes)} 顆）——"
            f"這幾關應該只差速度；重出請用 "
            f"python3 tools/retempo_midi.py --src midi/第{base_lv}關.mid --bpm <速度> "
            f"-o midi/第{lv}關.mid")


def test_midi_tempo_matches_chart_bpm():
    """每關 chart 的 bpm 要等於它來源 MIDI 的 tempo（轉檔器直接讀 MIDI，
    所以這條在抓「換了 MIDI 卻沒重轉譜」或「retempo 打錯速度」）。"""
    import json
    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for lv in SAME_CONTENT_LEVELS:
        mid = os.path.join(proj, "midi", f"第{lv}關.mid")
        chart = json.load(open(os.path.join(proj, "charts", f"level{lv}.json"), encoding="utf-8"))
        if not os.path.exists(mid):
            continue
        bpm = pretty_midi.PrettyMIDI(mid).get_tempo_changes()[1][0]
        # MIDI 的 tempo 存的是「每拍幾微秒」的整數 → 70BPM 實際是 70.0000047，
        # 轉檔器會取整到 70.0；所以比對留 0.01 的餘裕，不是浮點等值。
        assert abs(bpm - chart["bpm"]) < 0.01, (
            f"midi/第{lv}關.mid 的 tempo {bpm:g} ≠ charts/level{lv}.json 的 bpm "
            f"{chart['bpm']:g}——譜沒有跟著 MIDI 重轉")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL PASS")
