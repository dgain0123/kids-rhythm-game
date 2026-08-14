#!/usr/bin/env python3
"""合成第21關的背景音樂 → sounds/music/level21.m4a

第21關（第二大關卡第3關）：BPM 20、**八組三連音 + 1 個四分音符**共 25 下，
每 1 秒打一下（1/3 拍）。音樂＝第二大關卡的章節風格（自製搖籃曲 MIDI＋SoundFont，乾聲）。

★素材速度（2026-08-03 使用者裁示）：整章統一成 **「一拍＝一個拍點」**——
  音樂速度＝關卡速度的 3 倍（速度10→30BPM、速度20→**60BPM**、速度30→90BPM）。
  本關 BAR = 3 × HIT = 3 秒 = 60BPM。原本照「一小節＝一個拍點」是 180BPM，太趕；
  使用者聽過 180/120/60 三個候選後選 60BPM。
  （1 秒的拍點只跟 60/120/180BPM 對得齊——90BPM 的一拍是 0.667 秒，會變跨拍。）

結構（總長 34 秒，對齊 charts/level21.json）：
    0–1s     開頭靜音緩衝(preRollSec)
    1–5s     預備拍：英文人聲數拍 one/two/three/four（每 1 秒一聲＝拍點間隔，純人聲不疊節拍器）
    5–30s    音樂進場（10 小節×3 秒＝30 秒），25 個拍點每 1 秒一下，每個拍點一聲木魚
    30–34s   終止衰減後全靜音(2026-08-14 裁示)

用法：python3 tools/make_level21_music.py
（素材重做：python3 tools/make_lullaby_render.py --hit 3 --bars 10）
"""
import os
import sys

from music_style import style_for_chapter
from track_music import render

CHAPTER = 2
HIT = 1.0           # 拍點間隔 1 秒(= BPM 20 的 1/3 拍)
BAR = 3.0           # 素材一小節 3 秒 = 60BPM 3/4；一下＝一拍(見 track_music.render 的 source_hit)
PRE = 1.0
LEAD_HITS = 4       # 預備拍 4 聲(間隔＝拍點間隔，速度50以下的規矩)
N_HITS = 25
TAIL = 4.0

STYLE = style_for_chapter(CHAPTER)
LEAD_IN = PRE + LEAD_HITS * HIT      # 5 秒(= chart 的 leadInSec)


def main():
    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(proj, "sounds", "music", "level21.m4a")
    secs, info = render(STYLE, hit_sec=HIT, n_hits=N_HITS, out_path=out,
                        lead_hits=LEAD_HITS, pre=PRE, tail=TAIL, source_hit=BAR)
    print(f"✅ 音樂做好了：{out}（{secs:.1f} 秒，風格＝第{CHAPTER}大關卡「{STYLE.name}」）")
    print(f"   {info}")
    print(f"   預備拍 {LEAD_IN:.0f} 秒，{N_HITS} 個拍點每 {HIT:.0f} 秒一下，"
          f"最後一下在 {LEAD_IN + (N_HITS - 1) * HIT:.0f} 秒")
    return 0


if __name__ == "__main__":
    sys.exit(main())
