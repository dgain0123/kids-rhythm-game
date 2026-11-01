"""示範模式(?demo=1)行為釘樁：錄示範影片(tools/record_demo.py)靠它。

真的開無頭瀏覽器、用錄影工具同一套虛擬時鐘跑第18關：
  - 不開麥克風也能進跟拍模式
  - 每顆音符都自動打中 → 過關
  - 過程中不能出現失敗(曾因瀏覽器裡真的在播的音樂先放完而判失敗)
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))


def test_demo_mode_auto_hits_all_and_passes():
    import record_demo as R
    from playwright.sync_api import sync_playwright

    wav = Path(tempfile.mkdtemp()) / "m.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i",
                    str(ROOT / "sounds/music/level18.m4a"), str(wav)], check=True)
    srv = R.serve(ROOT)
    try:
        with sync_playwright() as p:
            br = p.chromium.launch()
            ctx = br.new_context(viewport={"width": 1280, "height": 720}, service_workers="block")
            ctx.add_init_script(R.INIT_JS)
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.route("**/*.m4a", lambda r: r.fulfill(path=str(wav), content_type="audio/wav"))
            pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/index.html?level=18&demo=1")
            pg.wait_for_selector("#startBtn:not([hidden])")
            pg.wait_for_timeout(1500)
            pg.click("#startBtn")
            pg.wait_for_timeout(300)
            assert not pg.evaluate("document.getElementById('laneCanvas').hidden"), "示範模式沒進跟拍"
            seen = set()
            for _ in range(20 * 10):          # 推 20 秒虛擬時間，每步 0.1 秒
                pg.evaluate("__vtStep(0.1)")
                cls = pg.evaluate("document.getElementById('stage').className")
                seen.update(c for c in ("pass", "fail") if c in cls.split())
                # 中途讓真實時間也走一點，模擬錄影比實際慢(真的播音樂會在這時放完)
                if len(seen) == 0 and _ % 50 == 0:
                    pg.wait_for_timeout(50)
            br.close()
    finally:
        srv.shutdown()
        os.remove(wav)
    assert "fail" not in seen, "示範模式不該失敗"
    assert "pass" in seen, "示範模式 20 秒內沒過關"
    assert not errs, errs


def _run_count_level(level, title, steps):
    """數下數關卡跑示範：回傳每一步「還看得到幾隻動物」與最後狀態。"""
    import record_demo as R
    from playwright.sync_api import sync_playwright

    srv = R.serve(ROOT)
    try:
        with sync_playwright() as p:
            br = p.chromium.launch()
            ctx = br.new_context(viewport={"width": 1280, "height": 720}, service_workers="block")
            ctx.add_init_script(R.INIT_JS)
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/index.html?level={level}&demo=1")
            pg.wait_for_selector("#startBtn:not([hidden])")
            pg.wait_for_function(f"document.getElementById('title').textContent.includes('{title}')", polling=100)
            pg.wait_for_timeout(300)
            first = pg.evaluate("document.querySelectorAll('#face .char-item').length")
            pg.click("#startBtn")
            pg.wait_for_timeout(200)
            seen = []
            for _ in range(steps):
                pg.evaluate("__vtStep(0.5)")
                seen.append(pg.evaluate(
                    "document.querySelectorAll('#face .char-item:not(.gone)').length"))
            pg.wait_for_timeout(1800)          # 打滿後等 1.5 秒(真實時間)沒多打才過關
            cls = pg.evaluate("document.getElementById('stage').className").split()
            br.close()
    finally:
        srv.shutdown()
    assert not errs, errs
    return first, seen, cls


def test_count_level_each_hit_removes_one_animal():
    # 第3關打3下：每秒自動打一下 → 看得到的動物 3→2→1→0，最後過關
    first, seen, cls = _run_count_level(3, "第3關", 8)
    assert first == 3, first
    # 去掉連續重複，就是消失的順序
    order = [n for i, n in enumerate(seen) if i == 0 or n != seen[i - 1]]
    assert order == [3, 2, 1, 0], seen
    assert seen[-1] == 0, seen
    assert "pass" in cls, cls


def test_count_level_16_hits():
    # 打16下(第30關)：16 隻一隻隻消失到 0、過關
    first, seen, cls = _run_count_level(30, "打16下", 34)
    assert first == 16, first
    order = [n for i, n in enumerate(seen) if i == 0 or n != seen[i - 1]]
    assert order == list(range(16, -1, -1)), seen
    assert "pass" in cls, cls
