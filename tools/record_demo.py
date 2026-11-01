#!/usr/bin/env python3
"""錄跟拍關卡的「示範影片」mp4（自動打中每一下，配原本的關卡音樂＋過關歡呼）。

用法：
    python3 tools/record_demo.py 18                 # → videos/第18關_示範.mp4
    python3 tools/record_demo.py 18 --width 1280 --height 720 --scale 1.5

做法（畫面和聲音一格不差）：
  1. 開本機伺服器，用無頭 Chromium 開 index.html?level=N&demo=1
     （demo=1＝不開麥克風、每顆音符一到拍點自動打中，見 js/main.js 的 DEMO）。
  2. 換掉瀏覽器的時鐘：AudioContext.currentTime／performance.now／requestAnimationFrame
     全部改成「虛擬時鐘」，每一格手動往前推 1/60 秒、每兩步截一張 → 30fps，
     不管截圖多慢，畫面時間都精準。
  3. 無頭瀏覽器解不了 m4a(AAC)，錄影時把音樂請求換成同內容的 wav（只是讓遊戲拿到音訊，
     影片的聲音不是從瀏覽器錄的）。
  4. ffmpeg 合成：音樂從第 0 秒起（=遊戲裡音樂起播那一刻）＋在過關那一格疊上歡呼 cheer.mp3。
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FPS = 30
SUB = 2            # 每格推兩次 1/60 秒(遊戲的軌道/捲動是「每兩幀畫一次」，彩帶物理以 60fps 為單位)
TAIL_SEC = 5.6     # 過關後再錄多久(彩帶 5 秒＋一點收尾)

# 虛擬時鐘、本機伺服器、成品檢查都在 demo_rules.py(唯一一份)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo_rules import INIT_JS, MUSIC_T0, serve, check_video  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("level", type=int)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--scale", type=float, default=1.5, help="裝置像素比(1.5 → 1920×1080)")
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    chart = json.loads((ROOT / "charts" / f"level{args.level}.json").read_text(encoding="utf-8"))
    if not chart.get("bpm") or not chart.get("music"):
        sys.exit("這關不是跟拍關卡(沒有 bpm/music)，示範影片只做跟拍關")
    music = (ROOT / chart["music"]).resolve()
    out = Path(args.out) if args.out else ROOT / "videos" / f"第{args.level}關_示範.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)

    work = Path(tempfile.mkdtemp(prefix="demo_rec_"))
    frames = work / "frames"
    frames.mkdir()
    wav = work / "music.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(music), str(wav)], check=True)

    srv = serve(ROOT)
    port = srv.server_address[1]
    pass_at = None
    try:
        with sync_playwright() as p:
            br = p.chromium.launch()
            ctx = br.new_context(viewport={"width": args.width, "height": args.height},
                                 device_scale_factor=args.scale, service_workers="block")
            ctx.add_init_script(INIT_JS)
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            # m4a → wav(同內容)；無頭瀏覽器沒有 AAC 解碼器
            page.route("**/*.m4a", lambda r: r.fulfill(path=str(wav), content_type="audio/wav"))
            page.goto(f"http://127.0.0.1:{port}/index.html?level={args.level}&demo=1")
            page.wait_for_selector("#startBtn:not([hidden])")
            # 等關卡＋音樂載好、圖片載完才按開始(沒解完就按會變成不跟拍)
            page.wait_for_function("window.__demo && window.__demo.ready"
                                   " && [...document.images].every(im => im.complete)", polling=50)
            page.click("#startBtn")
            page.wait_for_timeout(300)
            if page.evaluate("document.getElementById('laneCanvas').hidden"):
                sys.exit("按了開始但沒進跟拍模式(音樂沒載到？)")
            # 第 0 格＝音樂起播那一刻(虛擬時間 MUSIC_T0)
            page.evaluate(f"window.__vtStep({MUSIC_T0})")
            k = 0
            end_vt = None
            while True:
                page.screenshot(path=str(frames / f"f{k:05d}.jpg"), type="jpeg", quality=95)
                k += 1
                for _ in range(SUB):
                    page.evaluate(f"window.__vtStep({1 / (FPS * SUB)})")
                st = page.evaluate("[__vtNow(), document.getElementById('stage').classList.contains('pass')"
                                   " ? __vtNow() : null]")
                if st[1] is not None and pass_at is None:
                    pass_at = st[1] - MUSIC_T0
                    end_vt = st[0] + TAIL_SEC
                    page.wait_for_timeout(300)   # 彩帶是 setTimeout 120ms 後才開始(真實時間)
                if end_vt is not None and st[0] >= end_vt:
                    break
                if k > FPS * 120:
                    sys.exit(f"錄了 2 分鐘還沒過關，示範模式可能壞了；頁面錯誤：{errors[:3]}")
                if k % 90 == 0:
                    print(k, page.evaluate("[__vtNow(), document.getElementById('stage').className]"), flush=True)
            if errors:
                print("頁面錯誤：", *errors, sep="\n  ")
            br.close()
    finally:
        srv.shutdown()

    dur = k / FPS
    cheer = ROOT / "sounds" / "cheer.mp3"
    ms = int(round(pass_at * 1000))
    print(f"共 {k} 格({dur:.2f} 秒)，過關在第 {pass_at:.3f} 秒")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-framerate", str(FPS), "-i", str(frames / "f%05d.jpg"),
        "-i", str(music), "-i", str(cheer),
        "-filter_complex",
        f"[2:a]adelay={ms}|{ms}[c];[1:a][c]amix=inputs=2:duration=longest:normalize=0,"
        f"apad=pad_dur=10,atrim=0:{dur:.3f}[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}", "-movflags", "+faststart", str(out),
    ], check=True)
    shutil.rmtree(work, ignore_errors=True)
    bad = check_video(out, chart, pass_at, round(args.width * args.scale), round(args.height * args.scale), FPS)
    if bad:
        sys.exit("影片沒通過規則檢查：\n  " + "\n  ".join(bad))
    print("完成(規則檢查通過)：", out)


if __name__ == "__main__":
    main()
