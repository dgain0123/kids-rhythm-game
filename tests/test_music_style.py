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
    """每個章節的『調性／樂器／和聲進行』都要跟其他章節不一樣。
    節拍器音色是例外、允許共用（規矩見 docs/關卡音樂.md）。"""
    used = list(music_style.STYLES.items())
    for a in range(len(used)):
        for b in range(a + 1, len(used)):
            (ca, sa), (cb, sb) = used[a], used[b]
            where = f"第{ca}大關卡「{sa.name}」vs 第{cb}大關卡「{sb.name}」"
            assert sa.key != sb.key, f"{where}：調性一樣({sa.key})"
            assert sa.instruments != sb.instruments, f"{where}：樂器一樣"
            # 節拍器音色**允許共用**(2026-08-03 使用者裁示「提示音跟節拍器都用第一大關原本的」)
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


def _rms_peak(path, sr=44100, skip_head=3.0, skip_tail=2.0):
    """用 ffmpeg 快速解碼量 RMS 與峰值（比 librosa 快很多，適合守門）。
    ⚠️ **一定要用原生取樣率 44100 量峰值**：降取樣(8k/22k)的濾波器本身會過衝，
    量出來會假破表(實測 level14 原生 0.977、降到 8k 變 1.097)。"""
    import subprocess

    import numpy as np
    out = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1",
                          "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    y = np.frombuffer(out, dtype="<f4").astype(float)
    core = y[int(skip_head * sr): len(y) - int(skip_tail * sr)]
    if len(core) < sr:
        core = y
    return float(np.sqrt(np.mean(core ** 2))), float(np.max(np.abs(y))), _loud_segment(core, sr)


def _loud_segment(x, sr, frame=0.4):
    """**響段響度**：0.4 秒一格的 RMS，取最響的 1/4 平均（跟 remaster_sfx 同一套量法）。

    比較各關音量要用這個、不能用整段平均 RMS：慢關卡的音樂音符之間本來就有空白
    （第20關 30BPM 一拍 2 秒），整段平均會被空白拉低 5dB，可是**每顆音符一樣響**——
    小朋友聽到的是音符的音量，不是含空白的平均（2026-08-03 實測：整段 RMS 差 5.3dB、
    響段差只有 2.5dB）。"""
    import numpy as np
    n = max(1, int(frame * sr))
    frames = [np.sqrt(np.mean(x[i:i + n] ** 2)) for i in range(0, max(1, len(x) - n), n)]
    frames = np.array(frames) if frames else np.array([np.sqrt(np.mean(x ** 2))])
    return float(np.mean(np.sort(frames)[-max(1, len(frames) // 4):]))


def test_all_level_music_loudness():
    """所有關卡音樂：**只調音量、完全不壓縮**（2026-08-03 使用者裁示）→
    ① 彼此音量要一致（**響段響度**最大差 ≤3dB，不然換關會忽大忽小；
       為什麼不用整段 RMS 見 `_loud_segment`）
    ② 動態要保住（crest factor ≥10dB；壓縮過的會掉到 6~7dB，這條就是防壓縮復辟）
    ③ 解碼峰值 ≤1.0（AAC 過衝會破音）"""
    import glob
    import shutil

    import numpy as np
    if not shutil.which("ffmpeg"):
        print("（跳過音量檢查：沒有 ffmpeg）")
        return
    files = sorted(glob.glob(os.path.join(PROJ, "sounds", "music", "level*.m4a")))
    assert files, "找不到任何關卡音樂"
    levels = []
    for f in files:
        rms, peak, loud = _rms_peak(f)
        name = os.path.basename(f)
        db = 20 * np.log10(max(loud, 1e-9))
        crest = 20 * np.log10(peak / max(rms, 1e-9))
        levels.append((name, round(db, 1)))
        assert peak <= 1.0, f"{name} 解碼峰值 {peak:.3f} > 1.0，會破音"
        assert crest >= 10.0, (f"{name} 動態只剩 {crest:.1f}dB（<10）——"
                               f"八成又被壓縮了，母帶要走 clean 模式")
    spread = max(d for _, d in levels) - min(d for _, d in levels)
    assert spread <= 3.0, f"各關響段音量差 {spread:.1f}dB（>3）：{levels}"


def test_sfx_loudness_matches_music():
    """過關歡呼／失敗音效要跟關卡音樂差不多大聲（用「響段響度」比，短爆發音效才準），
    而且峰值不可以破表。2026-08-03：失敗音效原本比音樂小 8.8dB、歡呼小 3.7dB。
    ⚠️ 量立體聲要用 (L+R)/2，`ffmpeg -ac 1` 的降混會相加、量出來偏大。"""
    import shutil
    import sys

    import numpy as np
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("（跳過音效音量檢查：沒有 ffmpeg）")
        return
    sys.path.insert(0, os.path.join(PROJ, "tools"))
    import remaster_sfx as rs
    for name in rs.FILES:
        path = os.path.join(PROJ, "sounds", name)
        if not os.path.exists(path):
            continue
        sr, ch = rs.probe(path)
        x = rs.decode(path, sr, ch)
        db = 20 * np.log10(max(rs.loud_segment(x, sr), 1e-9) / rs.TARGET_SFX_LOUD)
        assert abs(db) <= 2.5, f"{name} 響度偏離音樂 {db:+.1f} dB（跑 tools/remaster_sfx.py）"
        assert np.max(np.abs(x)) <= 1.0, f"{name} 峰值破表會失真"


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


def test_material_tempo_follows_hit():
    """**音樂素材的速度要跟關卡拍點綁在一起**（產生器的 BAR 與 HIT 的關係）。

    ① 自製 render 的章節（`aligned_render`，目前第2大關卡的搖籃曲）：
       **一拍＝一個拍點**，也就是 `BAR = beats_per_bar × HIT`。
       ——2026-08-03 使用者裁示。原本是「一小節＝一個拍點」，結果音樂速度＝關卡速度×小節拍數，
       速度30 算出來 270BPM「太趕」；只改那一關又變成「速度10 的音樂比速度30 還快」，
       使用者說很奇怪。現在整章統一：音樂速度＝關卡速度×3（30/60/90BPM），
       小朋友每打一下就是馬林巴的一拍，慢的關卡音樂就真的比較慢。
    ② 其他章節（自己合成的）：一小節至少要是拍點間隔的整數倍，
       否則小節線落在拍點之間、整首愈跑愈偏。
    素材檔本身也要真的在（做法見 tools/track_music.py 的 `source_hit`）。
    """
    import glob
    import importlib
    for p in sorted(glob.glob(os.path.join(PROJ, "tools", "make_level*_music.py"))):
        name = os.path.basename(p)
        mod = importlib.import_module(name[:-3])
        hit, bar = getattr(mod, "HIT", None), getattr(mod, "BAR", None)
        if hit is None or bar is None:
            continue                       # 沒有分開兩個概念的關卡＝一小節就是一個拍點
        st = getattr(mod, "STYLE", None)
        if st is not None and getattr(st, "aligned_render", False):
            bpb = getattr(st, "beats_per_bar", None)
            assert bpb, f"{st.name} 是自製 render 風格，要填 beats_per_bar"
            assert abs(bar - bpb * hit) < 1e-6, (
                f"{name}：一小節 {bar:g} 秒 ≠ {bpb} × 拍點間隔 {hit:g} 秒 —— "
                f"本章的規矩是**一拍＝一個拍點**（音樂速度＝關卡速度×{bpb}），"
                f"不照做就會出現「慢的關卡音樂反而比較快」")
            src = os.path.join(PROJ, "sounds", "music", "source", st.source_for(bar))
            assert os.path.exists(src), (
                f"{name} 要的素材不存在：{src}"
                f"（重做：python3 tools/make_lullaby_render.py --hit {bar:g} --bars N）")
        else:
            k = bar / hit
            assert abs(k - round(k)) < 1e-6 and round(k) >= 1, (
                f"{name}：一小節 {bar:g} 秒不是拍點間隔 {hit:g} 秒的整數倍"
                f"（{k:.4f} 倍）——小節線會落在拍點之間，整首愈跑愈偏")


def test_music_outlasts_last_note_window():
    """音樂一定要放完最後一顆音符的**整個容許窗**才結束。

    音樂放完還有沒打到的音符 → 遊戲直接判失敗（見 docs/關卡系統.md 判定），
    所以「音樂長度 ≥ 最後一下 + 容許值」不成立的話，小朋友打在容許窗後半段
    根本來不及被算到。做新關卡最容易漏的就是這條（tail 給太短、lead-in 算錯）。
    """
    import glob
    import shutil
    import subprocess
    if not shutil.which("ffprobe"):
        print("（跳過音樂長度檢查：沒有 ffprobe）")
        return
    margin = 0.5                                  # 再留半秒給收尾淡出
    for path in sorted(glob.glob(os.path.join(PROJ, "charts", "level*.json"))):
        chart = json.load(open(path, encoding="utf-8"))
        if "music" not in chart or "bpm" not in chart:
            continue                              # 數下數關卡不判拍子
        name = os.path.basename(path)
        spb = 60.0 / chart["bpm"]
        last = chart.get("leadInSec", 0) + chart["notes"][-1]["beat"] * spb
        tol = chart.get("toleranceBeats", 0.5) * spb
        music = os.path.join(PROJ, chart["music"].lstrip("./"))
        dur = float(subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", music], capture_output=True, text=True, check=True).stdout)
        assert dur >= last + tol + margin, (
            f"{name} 的音樂只有 {dur:.2f} 秒，最後一下在 {last:.2f} 秒、容許 ±{tol:.2f} 秒"
            f"——音樂放完容許窗還沒關，會誤判失敗（產生器的 tail 要加長）")


if __name__ == "__main__":
    for fn_name, fn in sorted(globals().items()):
        if fn_name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {fn_name}")
    print("ALL PASS")
