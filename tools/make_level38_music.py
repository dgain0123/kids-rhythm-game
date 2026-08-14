#!/usr/bin/env python3
"""合成第38關的背景音樂 → sounds/music/level38.m4a

第38關（第三大關卡第9關）：BPM 80、**十六分音符 64 顆 + 1 個四分音符收尾**共 65 下，
每 0.1875 秒打一下（1/4 拍）。音樂＝第三大關卡的章節風格
（自製小星星 MIDI＋SoundFont，乾聲，尼龍吉他，2026-08-14 使用者試聽選定）。

★素材速度：整章統一「**一拍＝一個拍點**」——音樂速度＝關卡速度的 4 倍
  （速度10→40BPM…速度100→400BPM）。本關 BAR = 4 × HIT = 0.75 秒 = 320BPM 4/4。
  「同章節內關卡愈快音樂就要愈快」由 tests/test_music_style.py 釘住。

★預備拍間隔＝**四分音符(一拍)一聲＝0.75 秒**（速度60起的規矩；十六分音符關卡的一拍＝4 個拍點）。

用法：python3 tools/make_level38_music.py
（素材重做：python3 tools/make_twinkle_render.py --hit 0.75 --bars 22）
"""
import os
import sys

from music_style import style_for_chapter
from track_music import render

CHAPTER = 3
HIT = 60 / 80 / 4  # 拍點間隔 0.1875 秒(= BPM 80 的 1/4 拍)
BAR = 4 * HIT       # 素材一小節 0.75 秒 = 320BPM 4/4；一下＝一拍(track_music.render 的 source_hit)
PRE = 1.0
LEAD_HITS = 4       # 預備拍 4 聲
COUNT = 4 * HIT  # 人聲間隔：一拍一聲(速度60起規矩)
N_HITS = 65
TAIL = 4.0

STYLE = style_for_chapter(CHAPTER)
LEAD_IN = PRE + LEAD_HITS * COUNT    # 4 秒(= chart 的 leadInSec)


def main():
    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(proj, "sounds", "music", "level38.m4a")
    secs, info = render(STYLE, hit_sec=HIT, n_hits=N_HITS, out_path=out,
                        lead_hits=LEAD_HITS, pre=PRE, tail=TAIL, source_hit=BAR,
                        count_sec=COUNT)
    print(f"✅ 音樂做好了：{out}（{secs:.1f} 秒，風格＝第{CHAPTER}大關卡「{STYLE.name}」）")
    print(f"   {info}")
    print(f"   預備拍 {LEAD_IN:.4f} 秒，{N_HITS} 個拍點每 {HIT:.4f} 秒一下，"
          f"最後一下在 {LEAD_IN + (N_HITS - 1) * HIT:.2f} 秒")
    return 0


if __name__ == "__main__":
    sys.exit(main())
