#!/usr/bin/env python3
"""重釘示範模式 golden：tests/golden/demo_golden.json（每關 × 正常/失敗兩條路的關鍵結果）。

只有「確定要改規則／改譜」時才重釘，並先在 docs/示範模式與動物消失.md 改規則。
重釘前規則檢查器(tools/demo_rules.py)必須全綠，不然拒絕寫檔(不准把違規結果釘成答案)。
    python3 tools/make_demo_golden.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import demo_rules as D  # noqa: E402

OUT = D.ROOT / "tests" / "golden" / "demo_golden.json"

if __name__ == "__main__":
    traces = D.run_traces_parallel(D.default_jobs())
    bad = [m for t in traces for m in D.check_trace(t)]
    if bad:
        print("規則檢查有違規，不釘 golden：", *bad, sep="\n  ")
        sys.exit(1)
    gold = {}
    for t in traces:
        gold.setdefault(str(t["level"]), {})[t["mode"]] = D.summarize(t)
    OUT.write_text(json.dumps(gold, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"已寫 {OUT}（{len(traces)} 條路）")
