"""釘住「畫面/互動」這幾條規則（正解檔：docs/關卡系統.md、docs/角色與號碼牌.md）。

這些規則寫在 JS/CSS 裡、專案沒有 JS 測試環境，所以用「檢查原始碼有沒有照規則寫」來守門——
擋的是「改回舊做法」這種回歸，不是語法。每條都對應一次使用者實際打槍過的修正。
"""
import os
import re

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    return open(os.path.join(PROJ, *parts), encoding="utf-8").read()


def test_active_note_switches_exactly_on_beat():
    """**譜面換燈點＝拍點本身，不可以有任何提前量**（2026-08-03 使用者定案）。
    被打槍過三種提前量：容許值×0.6(提前0.6秒)、兩拍中點(提前半拍)、
    進圈提前量(提前0.136秒)。現在必須是 `t >= game.noteTimes[i]`。"""
    src = read("js", "main.js")
    assert "const reached = t >= game.noteTimes[i];" in src, \
        "換燈點必須是拍點本身（t >= noteTimes[i]），見 docs/關卡系統.md"
    for bad, why in [("tolSec * 0.6", "容許值×0.6 會提前 0.6 秒亮"),
                     ("laneEnterLeadSec", "進圈提前量會提前 0.136 秒亮"),
                     ("best = err", "取最近音符＝在兩拍中點就換，會提前半拍")]:
        assert bad not in src, f"js/main.js 又用回 {bad}——{why}"


def test_highlight_never_goes_dark():
    """**燈要一直亮著、不可以閃一下就熄**：沒有音符進入視窗時要退回第一顆未打音符。"""
    src = read("js", "main.js")
    assert "(act === -1 || reached)" in src, \
        "高亮必須在還沒到拍點時也保持亮著（act === -1 時先取第一顆），見 docs/關卡系統.md"


def test_count_in_has_no_metronome():
    """**預備拍＝純人聲，底下不疊節拍器**（跟第一大關卡一致，2026-08-03 使用者裁示）。
    track_music 的節拍器迴圈只能跑 n_hits 次，不能含 lead_hits。"""
    src = read("tools", "track_music.py")
    assert "for k in range(n_hits):" in src, "節拍器應該只在拍點上響"
    assert "lead_hits + n_hits" not in src.replace("span = pre + (lead_hits + n_hits)", ""), \
        "又把節拍器墊到預備拍底下了（使用者聽出來會「雜」）——兩條路徑都不可以"


def test_count_voice_files_are_local():
    """**數拍人聲固定用本地檔**，不要每次重打 TTS（每次合成都不一樣、mp3 雜訊會被母帶抬起來）。
    規矩與換聲步驟見 docs/關卡音樂.md「數拍人聲」。"""
    voice_dir = os.path.join(PROJ, "sounds", "voice")
    missing = [w for w in ("one", "two", "three", "four")
               if not any(os.path.exists(os.path.join(voice_dir, f"{w}.{e}"))
                          for e in ("wav", "mp3", "m4a", "aiff"))]
    assert not missing, (f"缺少數拍人聲本地檔：{missing}——"
                         f"沒有的話產生器會回頭打 TTS，每次聲音都不一樣")


def test_many_characters_wrap():
    """**角色超過 8 隻要換行縮小**（第19關要 12 隻，不然左右會被畫面切掉）。"""
    js = read("js", "characters.js")
    css = read("css", "style.css")
    assert 'classList.toggle("many", charCount > 8)' in js, \
        "characters.js 要在超過 8 隻時掛上 .many"
    assert "#face.many" in css and "flex-wrap: wrap" in css, \
        "css 要有 #face.many 的換行版面"
    assert re.search(r"@media \(max-width: 620px\) \{ #face\.many \{ --per-row: 4", css), \
        "手機(≤620px)一排要改成 4 隻"


def test_triplet_drawing_rules():
    """**三連音：三顆一組連樑＋標「3」、五線譜下移讓出空間、密譜自動加寬**。"""
    src = read("js", "render.js")
    assert "drawTupletNum" in src, "三連音要標「3」"
    assert "triplet: 1 / 3" in src, "render 的時值表要有 triplet(1/3 拍)"
    assert "hasTuplet ? 14 : 0" in src, "有三連音的譜五線譜要下移 14px，否則「3」會被切掉"
    assert "MIN_NOTE_PX = 32" in src, "相鄰音符最小間距規則不見了，密譜符頭會疊在一起"


def test_audio_clock_sync_rules():
    """**畫面與耳朵同步**（2026-08-14 使用者在第二大關聽出「有點沒對到」後定案）：
    ① 音樂要**排準起播**：`start(musicT0)`（不給時刻會晚幾 ms 且不定，時鐘就對不上）
    ② 時鐘要**扣輸出延遲**（outputLatency，Safari 退用 baseLatency）——
       ctx.currentTime 是「正在渲染」，喇叭出聲還要再晚，不扣的話圖示進圈/亮燈
       都比聽到的拍點早幾十 ms。這是「往後補償」，不是被打槍過的提前量。"""
    src = read("js", "main.js")
    assert "musicSrc.start(musicT0)" in src, "音樂要用 start(musicT0) 排準起播"
    assert "outputLatency" in src and "baseLatency" in src, "要有輸出延遲補償(outLatencySec)"
    assert re.search(r"currentTime - musicT0 - outLatencySec\(\)", src), \
        "musicNow() 要扣輸出延遲（耳朵聽到的時刻才是唯一時鐘）"


def test_fail_settles_at_last_note_window():
    """**失敗也要停在最後一下**（2026-08-14 使用者裁示）：最後一顆的容許窗一關
    (至少讓 0.35 秒的「直接停」終止音放完)就立刻 finishSong 結算，不乾等檔尾靜音；
    音檔 onended 只是備援。"""
    src = read("js", "main.js")
    assert "Math.max(game.tolSec, 0.5)" in src, "endT 要至少涵蓋 0.35 秒終止音+餘裕"
    assert re.search(r"t >= endT.*finishSong\(\)", src), "容許窗一關就要立刻結算(endT)"


def test_sixteenth_drawing_rules():
    """**十六分音符：四顆一組雙符樑、落單雙旗、時值 0.25**（第三大關「第一行第三小節」用）。"""
    src = read("js", "render.js")
    assert "sixteenth: 0.25" in src, "render 的時值表要有 sixteenth(1/4 拍)"
    assert 'list[i].type === "sixteenth"' in src, "連樑邏輯要有十六分音符分支(不然會變光桿沒符樑)"
    m = re.search(r'"sixteenth"\)\s*\{(.*?)\}\s*else i\+\+;', src, re.S)
    assert m, "十六分音符分支要在連樑迴圈裡"
    body = m.group(1)
    assert body.count("drawBeam") == 2, "十六分音符成組要畫**兩條**符樑(雙樑)"
    assert body.count("drawFlag") == 2, "十六分音符落單要畫**兩面**旗(雙旗)"
    assert "k < 4" in body, "十六分音符最多四顆一組(一拍)"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL PASS")
