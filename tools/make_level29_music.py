#!/usr/bin/env python3
"""合成第29關的背景音樂 → sounds/music/level29.m4a

第29關（第二大關卡第11關）：BPM 100、**十六組三連音 + 1 個四分音符**共 49 下，
每 0.2 秒打一下（1/3 拍）。**內容跟第23關（速度40）一模一樣、只有速度不同**——
MIDI 由 `tools/retempo_midi.py` 從 `midi/第23關.mid` 換 tempo 產生（音符 tick 逐一相同）。

★素材速度：整章統一「**一拍＝一個拍點**」→ 音樂速度＝關卡速度×3＝**300BPM**
  （BAR = 3 × HIT = 0.6 秒）。比前一關（速度90 的 270BPM）快 →
  符合「同章節內關卡愈快音樂就要愈快」（`tests/test_music_style.py` 釘住）。

★預備拍間隔＝**一拍一聲＝3 個拍點＝0.6 秒**（速度60起的規矩）。
  拍點間隔只有 0.2 秒、比人聲字長（0.72~0.79 秒）短很多，照拍點數會整片疊在一起 →
  改成四分音符一聲（跟第一大關卡第14~18關同一條規矩，leadInSec 也剛好一樣）。

結構（總長 17.2 秒，對齊 charts/level29.json）：
- 0~1 秒：開頭靜音緩衝(preRollSec)
- 1~3.4 秒：預備拍英文人聲 one/two/three/four（每 0.6 秒一聲，純人聲不疊節拍器）
- 3.4~17.2 秒：音樂進場（24 小節 × 0.6 秒），49 個拍點每 0.2 秒一下、
  每個拍點一聲木魚；最後一下在 13 秒，之後音樂繼續放到淡出

用法：python3 tools/make_level29_music.py
（素材重做：python3 tools/make_lullaby_render.py --hit 0.6 --bars 24）
"""
import os
import sys

from music_style import style_for_chapter
from track_music import render

CHAPTER = 2
HIT = 60 / 100 / 3      # 拍點間隔 0.2 秒(= BPM 100 的 1/3 拍)
BAR = 3 * HIT           # 素材一小節 0.6 秒 = 300BPM 3/4；一拍＝一個拍點(見 render 的 source_hit)
COUNT = 3 * HIT   # 預備拍人聲間隔 0.6 秒（速度60起＝四分音符(一拍)一聲）
PRE = 1.0
LEAD_HITS = 4           # 預備拍 4 聲
N_HITS = 49
TAIL = 4.0

STYLE = style_for_chapter(CHAPTER)
LEAD_IN = PRE + LEAD_HITS * COUNT    # 3.4 秒(= chart 的 leadInSec)


def main():
    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(proj, "sounds", "music", "level29.m4a")
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
