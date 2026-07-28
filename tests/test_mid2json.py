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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL PASS")
