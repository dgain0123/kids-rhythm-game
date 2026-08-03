#!/usr/bin/env python3
"""合成第23關的背景音樂 → sounds/music/level23.m4a

第23關（第二大關卡第5關）：BPM 40、**十六組三連音 + 1 個四分音符**共 49 下，
每 0.5 秒打一下（1/3 拍）。音樂＝第二大關卡的章節風格（自製搖籃曲 MIDI＋SoundFont，乾聲）。

★素材速度：整章統一「**一拍＝一個拍點**」——音樂速度＝關卡速度的 3 倍
  （速度10→30BPM、速度20→60BPM、速度30→90BPM、速度40→**120BPM**）。
  本關 BAR = 3 × HIT = 1.5 秒 = 120BPM，比第22關的 90BPM 快 → 符合
  「同章節內關卡愈快音樂就要愈快」（`tests/test_music_style.py` 釘住）。

★預備拍間隔＝**拍點間隔 0.5 秒**（照「速度50以下＝該關拍點間隔」的既有規矩，
  2026-08-04 使用者裁示照舊）。人聲檔本身 0.72~0.79 秒 → **每個字會被下一個字疊掉
  約 0.26 秒**；使用者知道並選了這個（另外兩個候選是一拍一聲 1.5 秒、兩拍點一聲 1.0 秒）。

結構（總長 31.5 秒，對齊 charts/level23.json）：
    0–1s          開頭靜音緩衝(preRollSec)
    1–3s          預備拍：英文人聲數拍 one/two/three/four
                  （每 0.5 秒一聲＝拍點間隔，純人聲不疊節拍器）
    3–31.5s       音樂進場（19 小節×1.5 秒＝28.5 秒），49 個拍點每 0.5 秒一下，
                  每個拍點一聲木魚；最後一下在 27 秒，之後音樂繼續放到淡出

用法：python3 tools/make_level23_music.py
（素材重做：python3 tools/make_lullaby_render.py --hit 1.5 --bars 19）
"""
import os
import sys

from music_style import style_for_chapter
from track_music import render

CHAPTER = 2
HIT = 0.5           # 拍點間隔 0.5 秒(= BPM 40 的 1/3 拍)
BAR = 3 * HIT       # 素材一小節 1.5 秒 = 120BPM 3/4；一下＝一拍(見 track_music.render 的 source_hit)
PRE = 1.0
LEAD_HITS = 4       # 預備拍 4 聲(間隔＝拍點間隔，速度50以下的規矩)
N_HITS = 49
TAIL = 4.0

STYLE = style_for_chapter(CHAPTER)
LEAD_IN = PRE + LEAD_HITS * HIT      # 3 秒(= chart 的 leadInSec)


def main():
    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(proj, "sounds", "music", "level23.m4a")
    secs, info = render(STYLE, hit_sec=HIT, n_hits=N_HITS, out_path=out,
                        lead_hits=LEAD_HITS, pre=PRE, tail=TAIL, source_hit=BAR)
    print(f"✅ 音樂做好了：{out}（{secs:.1f} 秒，風格＝第{CHAPTER}大關卡「{STYLE.name}」）")
    print(f"   {info}")
    print(f"   預備拍 {LEAD_IN:.3f} 秒，{N_HITS} 個拍點每 {HIT:.3f} 秒一下，"
          f"最後一下在 {LEAD_IN + (N_HITS - 1) * HIT:.2f} 秒")
    print(f"   素材一小節 {BAR:g} 秒（{180 / BAR:.0f}BPM 3/4），一拍＝一個拍點")
    return 0


if __name__ == "__main__":
    sys.exit(main())
