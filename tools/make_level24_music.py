#!/usr/bin/env python3
"""合成第24關的背景音樂 → sounds/music/level24.m4a

第24關（第二大關卡第6關）：BPM 50、**十六組三連音 + 1 個四分音符**共 49 下，
每 0.4 秒打一下（1/3 拍）。**內容跟第23關（速度40）一模一樣、只有速度不同**——
MIDI 由 `tools/retempo_midi.py` 從 `midi/第23關.mid` 換 tempo 產生（音符 tick 逐一相同）。

★素材速度：整章統一「**一拍＝一個拍點**」→ 音樂速度＝關卡速度×3＝**150BPM**
  （BAR = 3 × HIT = 1.2 秒）。比前一關（速度40 的 120BPM）快 →
  符合「同章節內關卡愈快音樂就要愈快」（`tests/test_music_style.py` 釘住）。

★預備拍間隔＝**拍點間隔 0.4 秒**（速度50以下的規矩）。
  ⚠️ 人聲字長 0.72~0.79 秒 > 間隔 → 每個字被下一個字疊掉約 0.38 秒，**本章最擠的一關**；
  速度60起改成「一拍一聲」就不再相疊（規矩見 docs/關卡系統.md）。

結構（總長 26.2 秒，對齊 charts/level24.json）：
- 0~1 秒：開頭靜音緩衝(preRollSec)
- 1~2.6 秒：預備拍英文人聲 one/two/three/four（每 0.4 秒一聲，純人聲不疊節拍器）
- 2.6~26.2 秒：音樂進場（20 小節 × 1.2 秒），49 個拍點每 0.4 秒一下、
  每個拍點一聲木魚；最後一下在 21.8 秒，之後音樂繼續放到淡出

用法：python3 tools/make_level24_music.py
（素材重做：python3 tools/make_lullaby_render.py --hit 1.2 --bars 20）
"""
import os
import sys

from music_style import style_for_chapter
from track_music import render

CHAPTER = 2
HIT = 60 / 50 / 3      # 拍點間隔 0.4 秒(= BPM 50 的 1/3 拍)
BAR = 3 * HIT           # 素材一小節 1.2 秒 = 150BPM 3/4；一拍＝一個拍點(見 render 的 source_hit)
COUNT = HIT       # 預備拍人聲間隔 0.4 秒（速度50以下＝該關拍點間隔）
PRE = 1.0
LEAD_HITS = 4           # 預備拍 4 聲
N_HITS = 49
TAIL = 4.0

STYLE = style_for_chapter(CHAPTER)
LEAD_IN = PRE + LEAD_HITS * COUNT    # 2.6 秒(= chart 的 leadInSec)


def main():
    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(proj, "sounds", "music", "level24.m4a")
    secs, info = render(STYLE, hit_sec=HIT, n_hits=N_HITS, out_path=out,
                        lead_hits=LEAD_HITS, pre=PRE, tail=TAIL, source_hit=BAR,
                        count_sec=COUNT)
    print(f"✅ 音樂做好了：{out}（{secs:.1f} 秒，風格＝第{CHAPTER}大關卡「{STYLE.name}」）")
    print(f"   {info}")
    print(f"   預備拍 {LEAD_IN:.3f} 秒（每 {COUNT:.3f} 秒一聲），"
          f"{N_HITS} 個拍點每 {HIT:.3f} 秒一下，最後一下在 {LEAD_IN + (N_HITS - 1) * HIT:.2f} 秒")
    print(f"   素材一小節 {BAR:g} 秒（{180 / BAR:.0f}BPM 3/4），一拍＝一個拍點")
    return 0


if __name__ == "__main__":
    sys.exit(main())
