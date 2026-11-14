"""守門入口：跑 tests/ 底下所有 test_*.py。全域 PostToolUse hook 會呼叫這支；
測試紅就擋下編輯。手動跑：python3 tests/guard_test.py（--no-cache＝全部重跑不看快取）

★快取（2026-11-15）：慢的測試檔（SLOW_DEPS 有列的）只在「它會讀到的檔案」內容有變時才重跑。
  - 指紋＝相依檔案**內容**的 sha1（不是修改時間），存在 tests/.guard_cache.json（不進 git）。
  - 只記「通過」；紅的永遠重跑。相依範圍用**排除法**：預設整個專案都算，
    只排除確定讀不到的（例：示範檢查不讀音樂產生器）→ 漏列只會多跑，不會假綠。
  - 新的測試檔沒列進 SLOW_DEPS＝每次都跑（安全預設）。
  - 環境（python／playwright／ffmpeg 版本）不在指紋裡：換環境後手動 --no-cache 跑一次。
"""
import fnmatch
import glob
import hashlib
import json
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
CACHE = os.path.join(HERE, ".guard_cache.json")

# 任何測試都讀不到的東西
ALWAYS_SKIP = [".git/*", "videos/*", "*/__pycache__/*", "*.DS_Store", "tests/.guard_cache.json",
               "tools/soundfonts/*", "*.pyc"]

_MUSIC_ONLY = ["tools/make_*_music.py", "tools/make_*_render.py", "tools/music_style.py",
               "tools/track_music.py", "tools/voice_count.py", "tools/remaster_*.py",
               "tools/retempo_midi.py", "tools/mid2json.py", "midi/*", "sounds/music/source/*",
               "sounds/voice/*", "關卡/*"]
_DEMO_ONLY = ["tools/demo_rules.py", "tools/make_demo_golden.py", "tools/record_demo.py",
              "tests/golden/*", "docs/示範模式與動物消失.md"]

# 慢的測試檔 → 它**讀不到**的檔案（其餘全部算相依）
SLOW_DEPS = {
    # 無頭瀏覽器跑 40 關×2 條路：讀網頁本體與譜，不讀音樂產生器／素材（m4a 也被換成靜音）
    "test_demo_rules.py": _MUSIC_ONLY + ["tests/test_m*.py", "tests/test_ui_rules.py",
                                         "sounds/music/*.m4a", "README.md"],
    # 音樂守門：讀產生器、音檔、譜、index.html 出處、js/main.js 的章節表；不讀 css/角色圖、示範檢查器
    "test_music_style.py": _DEMO_ONLY + ["css/*", "characters/*", "tests/test_demo_rules.py",
                                         "tests/test_ui_rules.py", "tests/test_mid2json.py",
                                         "README.md"],
}

_SHA = {}


def _sha(path):
    if path not in _SHA:
        h = hashlib.sha1()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _SHA[path] = h.hexdigest()
    return _SHA[path]


def _all_files():
    out = []
    for root, dirs, files in os.walk(PROJ):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), PROJ)
            if not any(fnmatch.fnmatch(rel, pat) for pat in ALWAYS_SKIP):
                out.append(rel)
    return sorted(out)


def fingerprint(test_name, files=None):
    """這支測試的相依指紋；沒列在 SLOW_DEPS 的回傳 None（＝不快取）。"""
    if test_name not in SLOW_DEPS:
        return None
    skip = SLOW_DEPS[test_name]
    h = hashlib.sha1()
    for rel in files if files is not None else _all_files():
        if any(fnmatch.fnmatch(rel, pat) for pat in skip):
            continue
        h.update(rel.encode("utf-8") + b"\0" + _sha(os.path.join(PROJ, rel)).encode() + b"\n")
    return h.hexdigest()


def _load_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    use_cache = "--no-cache" not in argv
    cache = _load_cache() if use_cache else {}
    files = _all_files()
    failed = []
    for path in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
        name = os.path.basename(path)
        fp = fingerprint(name, files)
        if use_cache and fp and cache.get(name) == fp:
            print(f"PASS {name}（相依檔案沒變，沿用上次通過）")
            continue
        try:
            mod = runpy.run_path(path)
            for fn_name, fn in sorted(mod.items()):
                if fn_name.startswith("test_") and callable(fn):
                    fn()
            print(f"PASS {name}")
            if fp:
                cache[name] = fp
        except Exception as e:  # noqa: BLE001
            failed.append((name, e))
            cache.pop(name, None)
            print(f"FAIL {name}: {e}")
    try:                                   # 先組好字串再開檔(開檔會先清空)
        text = json.dumps(cache, ensure_ascii=False, indent=1)
        with open(CACHE, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass
    if failed:
        print(f"\n❌ {len(failed)} 個測試檔失敗")
        return 1
    print("\n✅ 全部測試通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
