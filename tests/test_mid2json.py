"""釘住 mid→json 轉檔器的行為。用合成 MIDI 測試，不依賴外部檔案。"""
import os
import sys

import pretty_midi

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import mid2json  # noqa: E402


def _make_midi(events, bpm=120):
    """events: [(beat, pitch)]，回傳寫好的暫存 MIDI 路徑。"""
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    drum = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")
    sec_per_beat = 60.0 / bpm
    for beat, pitch in events:
        t = beat * sec_per_beat
        drum.notes.append(pretty_midi.Note(velocity=100, pitch=pitch, start=t, end=t + 0.05))
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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL PASS")
