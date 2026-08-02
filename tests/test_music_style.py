"""釘住「每個大關卡的音樂全都不一樣」這條規矩（規則正解檔：docs/關卡音樂.md）。

守門邏輯：js/main.js 新增一個大關卡，卻沒在 tools/music_style.py 的 STYLES
加一組**跟其他章節都不同**的風格 → 這裡就紅 → PostToolUse hook 擋下編輯。
"""
import json
import os
import re
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJ, "tools"))
import music_style  # noqa: E402


def chapters_in_game():
    """從 js/main.js 的 GROUPS 讀出目前有幾個大關卡（唯一真相在那支）。"""
    src = open(os.path.join(PROJ, "js", "main.js"), encoding="utf-8").read()
    block = re.search(r"const GROUPS = \[(.*?)\n\];", src, re.S)
    assert block, "js/main.js 找不到 GROUPS 定義"
    return re.findall(r'title:\s*"([^"]+)"', block.group(1))


def test_every_chapter_has_its_own_style():
    titles = chapters_in_game()
    assert titles, "至少要有一個大關卡"
    for i, title in enumerate(titles, start=1):
        assert i in music_style.STYLES, (
            f"第 {i} 大關卡「{title}」還沒定義音樂風格 —— "
            f"請在 tools/music_style.py 的 STYLES 加一組（規矩見 docs/關卡音樂.md）")
        music_style.style_for_chapter(i)  # 不可以爆


def test_styles_are_all_different():
    """每個章節的『調性／樂器／節拍器／和聲進行』都要跟其他章節不一樣。"""
    used = list(music_style.STYLES.items())
    for a in range(len(used)):
        for b in range(a + 1, len(used)):
            (ca, sa), (cb, sb) = used[a], used[b]
            where = f"第{ca}大關卡「{sa.name}」vs 第{cb}大關卡「{sb.name}」"
            assert sa.key != sb.key, f"{where}：調性一樣({sa.key})"
            assert sa.instruments != sb.instruments, f"{where}：樂器一樣"
            assert sa.metronome != sb.metronome, f"{where}：節拍器音色一樣"
            assert sa.signature() != sb.signature(), f"{where}：風格完全一樣"
            prog_a = [tuple(s["chord"]) for s in sa.prog]
            prog_b = [tuple(s["chord"]) for s in sb.prog]
            assert prog_a != prog_b, f"{where}：和聲進行一樣"


def test_style_has_required_parts():
    for c, st in music_style.STYLES.items():
        assert st.name and st.key and st.instruments and st.metronome, f"第{c}章風格欄位沒填齊"
        assert len(st.prog) >= 1, f"第{c}章沒有和聲進行"
        for seg in st.prog:
            assert seg["chord"] and seg["bass"] and seg["hits"], f"第{c}章的和聲段缺欄位"
            for note in list(seg["chord"]) + [seg["bass"]] + list(seg["hits"]):
                music_style.hz(note)  # 音名要能解析成頻率


def test_unknown_chapter_raises():
    """沒定義風格的章節要直接爆，不可以默默沿用別章的音樂。"""
    missing = max(music_style.STYLES) + 99
    try:
        music_style.style_for_chapter(missing)
    except KeyError:
        return
    raise AssertionError("沒定義風格的章節應該要丟 KeyError")


def test_level20_generator_uses_chapter2_style():
    import make_level20_music as m
    assert m.CHAPTER == 2
    assert m.STYLE is music_style.STYLES[2]


def test_timed_charts_have_existing_music():
    """每個跟拍關卡 json 指到的音樂檔都要真的在（缺檔＝那關直接不能玩）。"""
    charts_dir = os.path.join(PROJ, "charts")
    for name in sorted(os.listdir(charts_dir)):
        if not name.endswith(".json"):
            continue
        chart = json.load(open(os.path.join(charts_dir, name), encoding="utf-8"))
        if "music" not in chart:
            continue
        path = os.path.join(PROJ, chart["music"].lstrip("./"))
        assert os.path.exists(path), f"{name} 的音樂檔不存在：{chart['music']}"


if __name__ == "__main__":
    for fn_name, fn in sorted(globals().items()):
        if fn_name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {fn_name}")
    print("ALL PASS")
