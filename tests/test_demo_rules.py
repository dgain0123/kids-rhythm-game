"""示範模式／動物消失／示範影片：規則檢查器 × 全部關卡 × 每條路 × 每一步 + golden。

正解檔：docs/示範模式與動物消失.md；檢查器：tools/demo_rules.py。
  1. 全 40 關 × (正常, 失敗) 兩條路真的跑一遍，每一步中間狀態都過所有規則
  2. 每條路的關鍵結果 == tests/golden/demo_golden.json；新關卡沒釘 golden → 紅
  3. 每條規則都要「咬得到」：餵故意做壞的紀錄，該規則一定要報違規(防假綠)
  4. 影片檢查(check_video)：好影片過、聲音短/解析度錯/過關時刻錯都要抓到
"""
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import demo_rules as D  # noqa: E402

GOLD = json.loads((ROOT / "tests/golden/demo_golden.json").read_text(encoding="utf-8"))
_CACHE = {}


def _traces():
    if "t" not in _CACHE:
        _CACHE["t"] = D.run_traces_parallel(D.default_jobs())
    return _CACHE["t"]


def test_every_level_every_path_obeys_all_rules():
    bad = [m for t in _traces() for m in D.check_trace(t)]
    assert not bad, "\n".join(bad[:20])


def test_matches_golden_and_golden_covers_all_levels():
    assert sorted(GOLD, key=int) == [str(l) for l in D.all_levels()], "有關卡沒釘 golden(跑 tools/make_demo_golden.py)"
    diff = []
    for t in _traces():
        want = GOLD[str(t["level"])][t["mode"]]
        got = D.summarize(t)
        if got != want:
            diff.append(f"第{t['level']}關 demo={t['mode']}：{got} ≠ golden {want}")
    assert not diff, "\n".join(diff)


def test_every_rule_has_id_and_doc_is_listed():
    ids = [r.__doc__.split("]")[0] + "]" for r in D.RULES]
    assert all(i.startswith("[R:") for i in ids), ids
    assert len(set(ids)) == len(ids), "規則代號重複"
    doc = (ROOT / "docs/示範模式與動物消失.md").read_text(encoding="utf-8")
    missing = [i for i in ids + ["[R:video-sync]"] if i not in doc]
    assert not missing, f"正解檔沒寫到這些規則：{missing}"


# ── 每條規則都要咬得到(拿真的紀錄改壞) ──
def _pick(level, mode):
    return copy.deepcopy(next(t for t in _traces() if t["level"] == level and t["mode"] == mode))


def _bites(rule, tr):
    return rule(tr, D.load_chart(tr["level"]))


def test_rules_bite():
    R = D
    # 頁面錯誤
    t = _pick(18, "1"); t["errors"] = ["boom"]
    assert _bites(R.check_no_page_errors, t)
    # 控制列沒藏 / 出處不見
    t = _pick(18, "1"); t["before"]["controls"]["sens"] = True
    assert _bites(R.check_controls_hidden, t)
    t = _pick(18, "1"); t["before"]["controls"]["credits"] = False
    assert _bites(R.check_controls_hidden, t)
    # 跟拍：晚一步才打中 / 打兩次
    t = _pick(18, "1")
    k = next(i for i, s in enumerate(t["steps"]) if s["newHits"])
    t["steps"][k + 1]["newHits"] = t["steps"][k]["newHits"]; t["steps"][k]["newHits"] = []
    assert _bites(R.check_timed_hit_on_time, t)
    t = _pick(18, "1"); t["steps"][-1]["newHits"] = [0]
    assert _bites(R.check_timed_hit_on_time, t)
    # 跟拍正常：中途失敗 / 太晚過關 / 少打
    t = _pick(18, "1"); t["steps"][5]["state"] = "fail"
    assert _bites(R.check_timed_normal_passes, t)
    t = _pick(18, "1"); t["steps"][-1]["e"] += 0.3
    assert _bites(R.check_timed_normal_passes, t)
    t = _pick(18, "1"); t["steps"][-1]["hits"] -= 1
    assert _bites(R.check_timed_normal_passes, t)
    # 漏打：過關了 / 失敗太晚(等檔尾)
    t = _pick(18, "miss"); t["steps"][-1]["state"] = "pass"
    assert _bites(R.check_timed_miss_fails_at_window, t)
    t = _pick(18, "miss"); t["steps"][-1]["e"] += 1.0
    assert _bites(R.check_timed_miss_fails_at_window, t)
    # 打幾下：開始前數量/號碼錯
    t = _pick(3, "1"); t["before"]["items"].pop()
    assert _bites(R.check_count_initial, t)
    t = _pick(3, "1"); t["before"]["items"][0]["num"] = "2"
    assert _bites(R.check_count_initial, t)
    # 消失順序錯(從最後一號消失) / 一下消失兩隻
    t = _pick(3, "1")
    s = next(s for s in t["steps"] if s["hits"] == 1)
    s["items"][0]["gone"], s["items"][-1]["gone"] = False, True
    assert _bites(R.check_count_one_gone_per_hit, t)
    t = _pick(3, "1")
    s = next(s for s in t["steps"] if s["hits"] == 1)
    s["items"][1]["gone"] = True
    assert _bites(R.check_count_one_gone_per_hit, t)
    # 剩下的動物跳位
    t = _pick(3, "1")
    s = next(s for s in t["steps"] if s["hits"] == 1)
    s["items"][2]["x"] -= 50
    assert _bites(R.check_count_positions_kept, t)
    # 示範不是每秒一下
    t = _pick(3, "1"); t["steps"][0]["hits"] = 1
    assert _bites(R.check_count_demo_one_per_second, t)
    # 正常沒過關 / 中途失敗
    t = _pick(3, "1"); t["after"]["state"] = "hitOnce"
    assert _bites(R.check_count_normal_passes, t)
    t = _pick(3, "1"); t["steps"][1]["state"] = "fail"
    assert _bites(R.check_count_normal_passes, t)
    # 多打：沒失敗 / 動物沒回來
    t = _pick(3, "over"); t["after"]["state"] = "pass"
    assert _bites(R.check_count_over_restores, t)
    t = _pick(3, "over"); t["after"]["items"][0]["gone"] = True
    assert _bites(R.check_count_over_restores, t)
    t = _pick(3, "over"); t["after"]["items"].pop()
    assert _bites(R.check_count_over_restores, t)


def test_check_video_catches_bad_files():
    chart = D.load_chart(18)
    times, lead, _ = D.timing(chart)
    good_pass = lead + times[-1]
    d = Path(tempfile.mkdtemp())

    def mk(name, vdur, adur, size="64x36"):
        p = d / name
        subprocess.run(["ffmpeg", "-y", "-v", "error",
                        "-f", "lavfi", "-i", f"color=c=white:s={size}:r=30:d={vdur}",
                        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={adur}",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-t", str(max(vdur, adur)), str(p)],
                       check=True)
        return p

    ok = mk("ok.mp4", 2, 2)
    assert D.check_video(ok, chart, good_pass, 64, 36) == []
    assert D.check_video(mk("short.mp4", 2, 1), chart, good_pass, 64, 36), "聲音比畫面短沒抓到"
    assert D.check_video(ok, chart, good_pass, 1920, 1080), "解析度錯沒抓到"
    assert D.check_video(ok, chart, good_pass + 0.2, 64, 36), "過關時刻錯沒抓到"
