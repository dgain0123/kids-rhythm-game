#!/usr/bin/env python3
"""示範模式／示範影片／動物消失的「規則檢查器」（正解檔：docs/示範模式與動物消失.md）。

一條規則＝一個 check_* 函式，吃「逐步紀錄(trace)」回傳違規清單（空＝通過）。
trace 由 run_traces() 用虛擬時鐘把關卡從頭跑到結算，每一步都記下中間狀態，
所以檢查的是「整個過程」而不只是最後答案。

    python3 tools/demo_rules.py            # 全部 40 關 × 正常/失敗兩條路跑一遍、印違規
    python3 tools/demo_rules.py 3 18       # 只跑指定關

虛擬時鐘(INIT_JS)也在這裡，tools/record_demo.py 從這裡拿(只有一份)。
"""
import functools
import http.server
import json
import struct
import sys
import tempfile
import threading
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MUSIC_T0 = 0.08     # main.js：musicT0 = 按開始時的 currentTime + 0.08
EPS = 1e-6

# ── 虛擬時鐘：在頁面任何程式執行前注入 ──
INIT_JS = r"""
(() => {
  let vt = 0;                       // 虛擬秒數
  const cbs = new Map(); let nid = 1;
  const desc = (get) => ({ get, configurable: true });
  Object.defineProperty(AudioContext.prototype, 'currentTime', desc(() => vt));
  Object.defineProperty(AudioContext.prototype, 'outputLatency', desc(() => 0));
  Object.defineProperty(BaseAudioContext.prototype, 'currentTime', desc(() => vt));
  Object.defineProperty(AudioContext.prototype, 'baseLatency', desc(() => 0));
  performance.now = () => vt * 1000;
  // 瀏覽器裡不真的播音樂：截圖比實際時間慢，真的播會先放完、觸發「音樂放完＝結算失敗」
  AudioBufferSourceNode.prototype.start = function () {};
  window.requestAnimationFrame = (cb) => { const id = nid++; cbs.set(id, cb); return id; };
  window.cancelAnimationFrame = (id) => { cbs.delete(id); };
  window.__vtStep = (dt) => {
    vt += dt;
    const list = [...cbs.values()]; cbs.clear();
    for (const cb of list) { try { cb(vt * 1000); } catch (e) { console.error(e); } }
  };
  window.__vtNow = () => vt;
})();
"""

# 在頁面裡一路推虛擬時間、每步記狀態(一次 evaluate 跑完，快)
TRACE_JS = r"""
([dt, maxT]) => {
  const D = window.__demo, stage = document.getElementById('stage');
  const stateOf = () => ['pass','fail','hitOnce','progress','ready'].find(s => stage.classList.contains(s));
  const items = () => [...document.querySelectorAll('#face .char-item')];
  const snapItems = () => items().map(e => ({
    gone: e.classList.contains('gone'),
    num: (e.querySelector('.char-num') || {}).textContent || '',
    x: e.offsetLeft, y: e.offsetTop }));        // offset 不受縮小動畫(transform)影響＝排版位置
  const vt0 = __vtNow();
  const steps = [];
  let prevHit = null;
  for (let i = 1; i * dt <= maxT + 1e-9; i++) {
    __vtStep(dt);
    const g = D.game, st = stateOf();
    const s = { e: __vtNow() - vt0, state: st, hits: g.hits };
    if (g.timed) {
      s.newHits = g.hitNotes.map((h, k) => (h && !(prevHit && prevHit[k])) ? k : -1).filter(k => k >= 0);
      prevHit = g.hitNotes.slice();
    } else {
      s.items = snapItems();
    }
    steps.push(s);
    if (st === 'pass' || st === 'fail') break;
  }
  return steps;
}
"""

SNAP_JS = r"""
() => {
  const vis = (sel) => { const e = document.querySelector(sel); return e ? getComputedStyle(e).display !== 'none' : null; };
  const stage = document.getElementById('stage');
  return {
    state: ['pass','fail','hitOnce','progress','ready'].find(s => stage.classList.contains(s)),
    items: [...document.querySelectorAll('#face .char-item')].map(e => ({
      gone: e.classList.contains('gone'),
      num: (e.querySelector('.char-num') || {}).textContent || '',
      x: e.offsetLeft, y: e.offsetTop })),
    controls: { meter: vis('.meter'), sens: vis('.sens-row'), mini: vis('.mini-row'),
                btns: vis('.stage-btns'), credits: vis('#credits') },
  };
}
"""


def load_chart(level):
    return json.loads((ROOT / "charts" / f"level{level}.json").read_text(encoding="utf-8"))


def is_timed(chart):
    return bool(chart.get("bpm") and chart.get("notes") and chart["notes"][0].get("beat") is not None)


def all_levels():
    return sorted(int(p.stem[5:]) for p in (ROOT / "charts").glob("level*.json"))


def timing(chart):
    """跟拍關：每顆音符的譜面秒數、預備拍、結算時刻(同 main.js 的 endT)。"""
    spb = 60 / chart["bpm"]
    times = [n["beat"] * spb for n in chart["notes"]]
    tol = chart.get("toleranceBeats", 0.5) * spb
    return times, chart.get("leadInSec", 0), times[-1] + max(tol, 0.5)


# ── 跑紀錄 ──
class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(root: Path):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def silent_wav():
    """無頭瀏覽器解不了 m4a；檢查只需要遊戲「拿到音訊」，給一段 0.5 秒靜音 wav 就好。"""
    p = Path(tempfile.mkdtemp()) / "silent.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        w.writeframes(struct.pack("<h", 0) * 11025)
    return p


def _run_one(page, port, level, mode):
    chart = load_chart(level)
    timed = is_timed(chart)
    page.goto(f"http://127.0.0.1:{port}/index.html?level={level}&demo={mode}")
    page.wait_for_function("window.__demo && window.__demo.ready && window.__demo.chart"
                           f" && document.getElementById('title').textContent === {json.dumps(chart['title'])}"
                           " && [...document.images].every(im => im.complete)"   # 圖片載完排版才定
                           " && document.fonts.status === 'loaded'",
                           polling=50)
    before = page.evaluate(SNAP_JS)
    page.click("#startBtn")
    # 按開始會重畫角色(新的 <img>)；紀錄在同一段 JS 裡跑完、中間不給圖片載入，所以先等圖片載好
    page.wait_for_function("window.__demo.game && [...document.images].every(im => im.complete)", polling=20)
    if timed:
        times, lead, endT = timing(chart)
        steps = page.evaluate(TRACE_JS, [0.05, MUSIC_T0 + lead + endT + 2])
        after = page.evaluate(SNAP_JS)
    else:
        total = chart["maxHits"] + (1 if mode == "over" else 0)
        steps = page.evaluate(TRACE_JS, [0.25, total + 0.75])
        page.wait_for_timeout(1700)     # 打滿後等 1.5 秒(真實時間 setTimeout)沒多打才過關
        after = page.evaluate(SNAP_JS)
    return {"level": level, "mode": mode, "timed": timed, "before": before, "steps": steps, "after": after}


def run_traces(jobs):
    """jobs = [(level, mode), ...]，mode：跟拍關 '1'/'miss'、數下數關 '1'/'over'。"""
    from playwright.sync_api import sync_playwright
    wav = silent_wav()
    srv = serve(ROOT)
    out = []
    try:
        with sync_playwright() as p:
            br = p.chromium.launch()
            ctx = br.new_context(viewport={"width": 1280, "height": 720}, service_workers="block")
            ctx.add_init_script(INIT_JS)
            ctx.route("**/*.m4a", lambda r: r.fulfill(path=str(wav), content_type="audio/wav"))
            page = ctx.new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            for level, mode in jobs:
                errs.clear()
                tr = _run_one(page, srv.server_address[1], level, mode)
                tr["errors"] = list(errs)
                out.append(tr)
            br.close()
    finally:
        srv.shutdown()
    return out


def run_traces_parallel(jobs, workers=4):
    """分給幾個瀏覽器同時跑(守門用，80 條路從約 50 秒降到十幾秒)；回傳順序同 jobs。"""
    from concurrent.futures import ProcessPoolExecutor
    chunks = [jobs[i::workers] for i in range(workers)]
    with ProcessPoolExecutor(workers) as ex:
        res = list(ex.map(run_traces, chunks))
    by = {(t["level"], t["mode"]): t for r in res for t in r}
    return [by[j] for j in jobs]


def default_jobs(levels=None):
    jobs = []
    for lv in levels or all_levels():
        timed = is_timed(load_chart(lv))
        jobs += [(lv, "1"), (lv, "miss" if timed else "over")]
    return jobs


# ══════════════ 規則（每條一個檢查函式，回傳違規字串清單） ══════════════
def _t(chart, e):
    """紀錄裡的經過秒數 → 譜面時間。"""
    return e - MUSIC_T0 - chart.get("leadInSec", 0)


def check_no_page_errors(tr, chart):
    """[R:demo-no-error] 跑的過程頁面不能有任何 JS 錯誤。"""
    return [f"頁面錯誤：{e}" for e in tr["errors"]]


def check_controls_hidden(tr, chart):
    """[R:demo-hide-controls] 示範模式藏靈敏度條/音量條/小按鈕列/再玩按鈕；音樂出處要留著(CC BY)。"""
    c = tr["before"]["controls"]
    v = [f"{k} 應該藏起來" for k in ("meter", "sens", "mini", "btns") if c[k]]
    if not c["credits"]:
        v.append("音樂出處(credits)不見了")
    return v


def check_timed_hit_on_time(tr, chart):
    """[R:demo-timed-hit-on-time] 跟拍示範：每顆音符正好在「拍點到的那一步」被打中，不早不晚、每顆只打一次。"""
    if not tr["timed"]:
        return []
    times, lead, endT = timing(chart)
    v, seen = [], set()
    prev_t = -1e9
    for s in tr["steps"]:
        t = _t(chart, s["e"])
        for k in s["newHits"]:
            if k in seen:
                v.append(f"第{k + 1}顆被打兩次")
            seen.add(k)
            if not (prev_t + EPS < times[k] <= t + EPS):   # 必須是「第一個到達拍點」的那一步
                v.append(f"第{k + 1}顆在譜面 {t:.3f}s 才算打中，拍點是 {times[k]:.3f}s")
        prev_t = t
    return v


def check_timed_normal_passes(tr, chart):
    """[R:demo-timed-all-pass] 跟拍正常示範：全部打中、在最後一顆拍點那一步過關，過程中不能失敗。"""
    if not tr["timed"] or tr["mode"] != "1":
        return []
    times, lead, endT = timing(chart)
    v = []
    st = [s["state"] for s in tr["steps"]]
    if "fail" in st:
        v.append("正常示範出現失敗")
    if not st or st[-1] != "pass":
        return v + [f"沒有過關(最後狀態 {st[-1] if st else None})"]
    last = tr["steps"][-1]
    if last["hits"] != len(times):
        v.append(f"過關時只打中 {last['hits']}/{len(times)} 顆")
    t = _t(chart, last["e"])
    if not (times[-1] - EPS <= t < times[-1] + 0.05 + EPS):
        v.append(f"過關在譜面 {t:.3f}s，應在最後一顆 {times[-1]:.3f}s 那一步")
    return v


def check_timed_miss_fails_at_window(tr, chart):
    """[R:demo-timed-miss-fail] 漏打最後一顆：最後一顆容許窗一關(endT)那一步立刻失敗，不等檔尾、不會過關。"""
    if not tr["timed"] or tr["mode"] != "miss":
        return []
    times, lead, endT = timing(chart)
    v = []
    st = [s["state"] for s in tr["steps"]]
    if "pass" in st:
        v.append("漏打一顆卻過關")
    if not st or st[-1] != "fail":
        return v + [f"漏打沒有失敗(最後狀態 {st[-1] if st else None})"]
    t = _t(chart, tr["steps"][-1]["e"])
    if not (endT - EPS <= t < endT + 0.05 + EPS):
        v.append(f"失敗在譜面 {t:.3f}s，應在容許窗關閉 {endT:.3f}s 那一步")
    if tr["steps"][-1]["hits"] != len(times) - 1:
        v.append(f"應打中 {len(times) - 1} 顆，實際 {tr['steps'][-1]['hits']}")
    return v


def check_count_initial(tr, chart):
    """[R:count-initial] 打幾下關：開始前動物數＝要打幾下，號碼牌 1..N 依序、都看得到。"""
    if tr["timed"]:
        return []
    its = tr["before"]["items"]
    n = chart["maxHits"]
    v = []
    if len(its) != n:
        v.append(f"開始前有 {len(its)} 隻，應為 {n}")
    if [i["num"] for i in its] != [str(k) for k in range(1, len(its) + 1)]:
        v.append(f"號碼牌順序不對：{[i['num'] for i in its]}")
    if any(i["gone"] for i in its):
        v.append("開始前就有動物消失")
    return v


def check_count_one_gone_per_hit(tr, chart):
    """[R:count-gone-per-hit] 打幾下關：每一步「消失的」正好是第 1～hits 號(依號碼順序、一下一隻)。"""
    if tr["timed"]:
        return []
    v = []
    for s in tr["steps"]:
        if s["state"] in ("pass", "fail"):
            continue
        want = [k < s["hits"] for k in range(len(s["items"]))]
        got = [i["gone"] for i in s["items"]]
        if got != want:
            v.append(f"{s['e']:.2f}s 打了 {s['hits']} 下，消失的是 {[k + 1 for k, g in enumerate(got) if g]}")
    return v


def check_count_positions_kept(tr, chart):
    """[R:count-keep-positions] 打幾下關：動物消失後位置留著，剩下的不跳位(排版座標全程不變)。"""
    if tr["timed"]:
        return []
    base = [(i["x"], i["y"]) for i in tr["before"]["items"]]
    v = []
    for s in tr["steps"]:
        if s["state"] in ("pass", "fail"):
            continue
        cur = [(i["x"], i["y"]) for i in s["items"]]
        if cur != base:
            v.append(f"{s['e']:.2f}s 動物位置變了")
            break
    return v


def check_count_demo_one_per_second(tr, chart):
    """[R:count-demo-1hz] 打幾下關的示範：開始後每 1 秒自動打一下(第 k 下在第 k 秒)。"""
    if tr["timed"]:
        return []
    total = chart["maxHits"] + (1 if tr["mode"] == "over" else 0)
    v = []
    for s in tr["steps"]:
        want = min(total, int(s["e"] + EPS))
        if s["hits"] != want:
            v.append(f"{s['e']:.2f}s 應已打 {want} 下，實際 {s['hits']}")
            break
    return v


def check_count_normal_passes(tr, chart):
    """[R:count-pass] 打幾下關正常示範：打滿後 1.5 秒沒多打 → 過關，過程不能失敗。"""
    if tr["timed"] or tr["mode"] != "1":
        return []
    v = []
    if any(s["state"] == "fail" for s in tr["steps"]):
        v.append("正常示範出現失敗")
    if tr["after"]["state"] != "pass":
        v.append(f"打滿等 1.5 秒後沒過關(狀態 {tr['after']['state']})")
    return v


def check_count_over_restores(tr, chart):
    """[R:count-fail-restore] 打太多下 → 失敗，消失的動物全部回來(數量、號碼、位置都還原)。"""
    if tr["timed"] or tr["mode"] != "over":
        return []
    v = []
    a = tr["after"]
    if a["state"] != "fail":
        return [f"多打一下沒有失敗(狀態 {a['state']})"]
    if [(i["num"], i["x"], i["y"]) for i in a["items"]] != [(i["num"], i["x"], i["y"]) for i in tr["before"]["items"]]:
        v.append("失敗後動物沒有照原樣回來")
    if any(i["gone"] for i in a["items"]):
        v.append("失敗後還有動物是消失的")
    return v


RULES = [
    check_no_page_errors, check_controls_hidden,
    check_timed_hit_on_time, check_timed_normal_passes, check_timed_miss_fails_at_window,
    check_count_initial, check_count_one_gone_per_hit, check_count_positions_kept,
    check_count_demo_one_per_second, check_count_normal_passes, check_count_over_restores,
]


def check_trace(tr):
    chart = load_chart(tr["level"])
    out = []
    for rule in RULES:
        for msg in rule(tr, chart):
            out.append(f"第{tr['level']}關 demo={tr['mode']} {rule.__doc__.split(']')[0]}] {msg}")
    return out


def summarize(tr):
    """golden 用的摘要：每條路的關鍵結果(譜面秒數取到 0.05 秒那一步)。"""
    chart = load_chart(tr["level"])
    if tr["timed"]:
        last = tr["steps"][-1]
        return {"timed": True, "final": last["state"], "hits": last["hits"],
                "notes": len(chart["notes"]), "end_t": round(_t(chart, last["e"]), 3)}
    seq = []
    for s in tr["steps"]:
        n = sum(not i["gone"] for i in s["items"]) if s["state"] not in ("pass", "fail") else None
        if n is not None and (not seq or seq[-1] != n):
            seq.append(n)
    return {"timed": False, "final": tr["after"]["state"], "visible_seq": seq,
            "items_after": len(tr["after"]["items"])}


# ── 示範影片成品檢查(record_demo.py 錄完自動跑) ──
def check_video(path, chart, pass_at, width, height, fps=30):
    """[R:video-sync] 影片解析度對、音軌與畫面一樣長、過關時刻＝預備拍＋最後一顆拍點(差不到一格)。"""
    import subprocess
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,duration",
                        "-of", "json", str(path)], capture_output=True, text=True, check=True)
    st = json.loads(r.stdout)["streams"]
    vs = [s for s in st if s["codec_type"] == "video"]
    au = [s for s in st if s["codec_type"] == "audio"]
    v = []
    if not vs or not au:
        return ["影片缺畫面或聲音"]
    if (vs[0]["width"], vs[0]["height"]) != (width, height):
        v.append(f"解析度 {vs[0]['width']}x{vs[0]['height']}，應為 {width}x{height}")
    vd, ad = float(vs[0]["duration"]), float(au[0]["duration"])
    if abs(vd - ad) > 0.05:
        v.append(f"聲音 {ad:.2f}s 跟畫面 {vd:.2f}s 不一樣長")
    if is_timed(chart):
        times, lead, _ = timing(chart)
        want = lead + times[-1]
        if abs(pass_at - want) > 1 / fps + EPS:
            v.append(f"過關在 {pass_at:.3f}s，應為 {want:.3f}s(預備拍＋最後一顆)")
    return v


if __name__ == "__main__":
    lv = [int(a) for a in sys.argv[1:]] or None
    bad = 0
    for tr in run_traces_parallel(default_jobs(lv)):
        msgs = check_trace(tr)
        bad += len(msgs)
        print(("✅" if not msgs else "❌"), f"第{tr['level']}關 demo={tr['mode']}", summarize(tr))
        for m in msgs:
            print("   ", m)
    print(f"\n違規 {bad} 條")
    sys.exit(1 if bad else 0)
