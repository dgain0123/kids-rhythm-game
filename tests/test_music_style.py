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
        assert st.kind in ("synth", "track"), f"第{c}章的 kind 只能是 synth 或 track"
        if st.kind == "synth":
            assert len(st.prog) >= 1, f"第{c}章沒有和聲進行"
            for seg in st.prog:
                assert seg["chord"] and seg["bass"] and seg["hits"], f"第{c}章的和聲段缺欄位"
                for note in list(seg["chord"]) + [seg["bass"]] + list(seg["hits"]):
                    music_style.hz(note)  # 音名要能解析成頻率


def test_track_styles_license_ok():
    """用現成曲目的章節（repo 是公開的，曾踩過版權坑 → 這幾條不可以放寬）：
    ① 素材檔要在、來源要登記
    ② 授權只收 **CC0／公共領域／CC BY**
    ③ **NC(禁商用)、ND(禁改作)、SA(相同方式分享) 一律不准**
       ——我們會變速＝改作，ND 直接不相容；SA 會傳染到整個專案
    ④ 需要標示的授權(CC BY)：出處字串一定要**真的顯示在 index.html 上**
       （CC BY 要求「想知道音樂來源的人要找得到」）"""
    doc_path = os.path.join(PROJ, "sounds", "music", "source", "來源與授權.md")
    assert os.path.exists(doc_path), "缺少 sounds/music/source/來源與授權.md"
    doc = open(doc_path, encoding="utf-8").read()
    html = open(os.path.join(PROJ, "index.html"), encoding="utf-8").read()

    for c, st in music_style.STYLES.items():
        if st.kind != "track":
            continue
        assert st.source, f"第{c}章沒填素材檔名"
        path = os.path.join(PROJ, "sounds", "music", "source", st.source)
        assert os.path.exists(path), f"第{c}章的素材不存在：{path}"
        lic = (st.license or "").upper()
        ok = ("CC0" in lic or "PUBLIC DOMAIN" in lic or "公共領域" in st.license
              or "CC BY" in lic)
        assert ok, f"第{c}章素材授權不在白名單(CC0/公共領域/CC BY)：{st.license!r}"
        for bad, why in [("NC", "禁商用"), ("ND", "禁改作(我們會變速=改作)"),
                         ("SA", "相同方式分享(會傳染整個專案)")]:
            assert f"-{bad}" not in lic and f" {bad} " not in lic, \
                f"第{c}章素材授權含 {bad}({why})，不可以用：{st.license!r}"
        assert st.credit and st.source_url, f"第{c}章沒登記來源(credit/source_url)"
        assert st.source in doc, f"{st.source} 沒有登記在 來源與授權.md"
        if st.needs_attribution():
            assert st.ui_credit, f"第{c}章是要標示的授權，必須填 ui_credit"
            assert st.ui_credit in html, \
                f"第{c}章的音樂出處沒有顯示在 index.html：{st.ui_credit!r}"


def test_unknown_chapter_raises():
    """沒定義風格的章節要直接爆，不可以默默沿用別章的音樂。"""
    missing = max(music_style.STYLES) + 99
    try:
        music_style.style_for_chapter(missing)
    except KeyError:
        return
    raise AssertionError("沒定義風格的章節應該要丟 KeyError")


def test_normalize_loudness_hits_target():
    """響度正規化：拉到目標 RMS、且峰值不超過限幅天花板(留給 AAC 過衝的餘裕)。
    用合成訊號測，不碰檔案 → 很快。"""
    import numpy as np
    mx = music_style.Mixer(6.0)
    rng = np.random.RandomState(0)
    mx.buf = rng.randn(len(mx.buf)) * 0.01          # 很小聲
    mx.buf[::5000] = 0.9                             # 幾個大尖峰(模擬節拍器)
    rms = mx.normalize_loudness()
    db = 20 * np.log10(rms / music_style.TARGET_RMS)
    assert abs(db) < 0.4, f"響度沒對齊目標：差 {db:+.2f} dB"
    assert np.max(np.abs(mx.buf)) <= music_style.LIMIT_CEILING + 1e-6, "峰值超過限幅天花板"


def _rms_peak(path, sr=8000, skip_head=3.0, skip_tail=2.0):
    """用 ffmpeg 快速解碼量 RMS 與峰值（比 librosa 快很多，適合守門）。"""
    import subprocess

    import numpy as np
    out = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1",
                          "-ar", str(sr), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    y = np.frombuffer(out, dtype="<i2").astype(float) / 32768
    core = y[int(skip_head * sr): len(y) - int(skip_tail * sr)]
    if len(core) < sr:
        core = y
    return float(np.sqrt(np.mean(core ** 2))), float(np.max(np.abs(y)))


def test_all_level_music_loudness():
    """**每個關卡音樂的音量都要一致**（RMS 對齊 TARGET_RMS ±2.5dB），
    而且解碼後峰值不可以超過 1.0（AAC 過衝會破音）。
    2026-08-03：第20關用峰值正規化，比第一大關卡小 7dB，被使用者抓到 → 改用 RMS 對齊。"""
    import glob
    import shutil

    import numpy as np
    if not shutil.which("ffmpeg"):
        print("（跳過音量檢查：沒有 ffmpeg）")
        return
    files = sorted(glob.glob(os.path.join(PROJ, "sounds", "music", "level*.m4a")))
    assert files, "找不到任何關卡音樂"
    for f in files:
        rms, peak = _rms_peak(f)
        db = 20 * np.log10(max(rms, 1e-9) / music_style.TARGET_RMS)
        name = os.path.basename(f)
        assert abs(db) <= 2.5, f"{name} 音量偏離目標 {db:+.1f} dB（其他關會覺得忽大忽小）"
        assert peak <= 1.0, f"{name} 解碼峰值 {peak:.3f} > 1.0，會破音（限幅天花板要再降）"


def test_generators_use_shared_mastering():
    """所有音樂產生器都要走 music_style 的母帶處理，**不可以自己做峰值正規化**
    （峰值會被節拍器尖峰佔走 → 整首變小聲）。"""
    import glob
    for p in sorted(glob.glob(os.path.join(PROJ, "tools", "make_level*_music.py"))):
        src = open(p, encoding="utf-8").read()
        name = os.path.basename(p)
        assert "np.max(np.abs(buf))" not in src, f"{name} 還在自己做峰值正規化"
        assert "mx.finish(" in src or "render(" in src, f"{name} 沒有走共用的母帶處理/管線"


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
