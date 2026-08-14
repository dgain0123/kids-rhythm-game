#!/usr/bin/env python3
"""合成第20關的背景音樂 → sounds/music/level20.m4a

第20關（第二大關卡「第一行第二小節」的第2關）：BPM 10、**四個三連音 + 1 個四分音符**共 13 下，
小朋友每 2 秒打一下（1/3 拍＝三連音一個間隔）。

**音樂風格由章節決定**：本關屬第 2 大關卡 → `music_style.style_for_chapter(2)`
＝自製布拉姆斯搖籃曲 MIDI ＋ GeneralUser GS 取樣音源離線 render（乾聲）。

★素材速度（2026-08-03 使用者裁示）：整章統一成 **「一拍＝一個拍點」**——
  音樂速度＝關卡速度的 3 倍（速度10→**30BPM**、速度20→60BPM、速度30→90BPM），
  慢的關卡音樂就真的比較慢。本關 BAR = 3 × HIT = 6 秒 = 30BPM。
  （原本是「一小節＝一個拍點」＝90BPM，結果速度10 的音樂跟速度30 一樣快、
   比速度20 還快，使用者說很奇怪 → 改成現在這條。）

結構（總長 39 秒，對齊 charts/level20.json）：
    0–1s     開頭靜音緩衝(preRollSec，躲播放起頭暫態)
    1–9s     預備拍：英文人聲數拍 one/two/three/four(每 2 秒一聲＝拍點間隔，純人聲不疊節拍器)
    9–39s    音樂進場，13 個拍點(每 2 秒一下)，每個拍點一聲木魚
    35–39s   終止衰減後全靜音(2026-08-14 裁示)(最後一下在 33 秒，留足夠時間給 ±2 秒容許窗)

用法：python3 tools/make_level20_music.py
（素材重做：python3 tools/make_lullaby_render.py --hit 6 --bars 6）
"""
import os
import sys

from music_style import style_for_chapter
from track_music import render

CHAPTER = 2         # 這關屬第幾個大關卡(決定音樂風格)
HIT = 2.0           # 拍點間隔 2 秒(= BPM 10 的 1/3 拍＝三連音一顆)
BAR = 3 * HIT       # 素材一小節 6 秒 = 30BPM 3/4；一下＝一拍(見 track_music.render 的 source_hit)
PRE = 1.0           # 開頭靜音緩衝(= chart 的 preRollSec)
LEAD_HITS = 4       # 預備拍 4 聲(間隔＝拍點間隔，速度50以下的規矩)
N_HITS = 13         # 這關要打 13 下(12 個三連音 + 第2小節開頭 1 個四分音符收尾)
TAIL = 4.0

STYLE = style_for_chapter(CHAPTER)
LEAD_IN = PRE + LEAD_HITS * HIT      # 9 秒(= chart 的 leadInSec)


def main():
    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(proj, "sounds", "music", "level20.m4a")
    secs, info = render(STYLE, hit_sec=HIT, n_hits=N_HITS, out_path=out,
                        lead_hits=LEAD_HITS, pre=PRE, tail=TAIL, source_hit=BAR)
    print(f"✅ 音樂做好了：{out}（{secs:.1f} 秒，風格＝第{CHAPTER}大關卡「{STYLE.name}」）")
    print(f"   {info}")
    print(f"   預備拍 {LEAD_IN:.0f} 秒，{N_HITS} 個拍點每 {HIT:.0f} 秒一下，"
          f"最後一下在 {LEAD_IN + (N_HITS - 1) * HIT:.0f} 秒")
    return 0


if __name__ == "__main__":
    sys.exit(main())
