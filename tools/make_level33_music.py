#!/usr/bin/env python3
"""合成第33關的背景音樂 → sounds/music/level33.m4a

第33關（第三大關卡第4關）：BPM 30、**十六分音符 48 顆 + 1 個四分音符收尾**共 49 下，
每 0.5 秒打一下（1/4 拍）。音樂＝第三大關卡的章節風格
（自製小星星 MIDI＋SoundFont，乾聲，尼龍吉他，2026-08-14 使用者試聽選定）。

★素材速度：整章統一「**一拍＝一個拍點**」——音樂速度＝關卡速度的 4 倍
  （速度10→40BPM…速度100→400BPM）。本關 BAR = 4 × HIT = 2 秒 = 120BPM 4/4。
  「同章節內關卡愈快音樂就要愈快」由 tests/test_music_style.py 釘住。

★預備拍間隔＝**拍點間隔 0.5 秒**（速度50以下的規矩）。人聲字長 0.72~0.79 秒 → 間隔比字短、字會相疊（規矩照舊不改，2026-08-04 使用者裁示）。

用法：python3 tools/make_level33_music.py
（素材重做：python3 tools/make_twinkle_render.py --hit 2 --bars 15）
"""
import os
import sys

from music_style import style_for_chapter
from track_music import render

CHAPTER = 3
HIT = 60 / 30 / 4  # 拍點間隔 0.5 秒(= BPM 30 的 1/4 拍)
BAR = 4 * HIT       # 素材一小節 2 秒 = 120BPM 4/4；一下＝一拍(track_music.render 的 source_hit)
PRE = 1.0
LEAD_HITS = 4       # 預備拍 4 聲
COUNT = HIT  # 人聲間隔：拍點間隔(速度50以下規矩)
N_HITS = 49
TAIL = 4.0

STYLE = style_for_chapter(CHAPTER)
LEAD_IN = PRE + LEAD_HITS * COUNT    # 3 秒(= chart 的 leadInSec)


def main():
    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(proj, "sounds", "music", "level33.m4a")
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
