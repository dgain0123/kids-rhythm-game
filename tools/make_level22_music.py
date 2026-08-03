#!/usr/bin/env python3
"""合成第22關的背景音樂 → sounds/music/level22.m4a

第22關（第二大關卡第4關）：BPM 30、**十二組三連音 + 1 個四分音符**共 37 下，
每 2/3 秒打一下（1/3 拍）。音樂＝第二大關卡的章節風格（自製搖籃曲 MIDI＋SoundFont，乾聲）。

★素材選擇（2026-08-03 使用者裁示）：照原規矩「一小節＝一個拍點」算出來是 **270BPM**，
  使用者聽過說**太趕**→ 這關改成 **一小節＝3 個拍點**（BAR = 3 × HIT = 2 秒 = **90BPM**，
  跟速度10 同一個速度感），拍點就落在馬林巴的每一拍上、對齊照樣精準。
  所以素材直接沿用速度10 的 `lullaby_marimba_hit2s.wav`（3/4 90BPM、一小節 2 秒）。

結構（總長 32.3 秒，對齊 charts/level22.json）：
    0–1s          開頭靜音緩衝(preRollSec)
    1–3.67s       預備拍：英文人聲數拍 one/two/three/four
                  （每 2/3 秒一聲＝拍點間隔，純人聲不疊節拍器）
    3.67–29.67s   音樂進場（13 小節×2 秒＝26 秒），37 個拍點每 2/3 秒一下，
                  每個拍點一聲木魚
    29.67–32.3s   收尾（素材放完，跟第20/21關一樣淡出）

用法：python3 tools/make_level22_music.py
（素材已存在；要重做：python3 tools/make_lullaby_render.py --hit 2 --bars 13）
"""
import os
import sys

from music_style import style_for_chapter
from track_music import render

CHAPTER = 2
HIT = 2 / 3         # 拍點間隔 2/3 秒(= BPM 30 的 1/3 拍)
BAR = 2.0           # 素材一小節的秒數 = 3 個拍點(必須是 HIT 的整數倍，見 track_music.render)
PRE = 1.0
LEAD_HITS = 4       # 預備拍 4 聲(間隔＝拍點間隔，速度50以下的規矩)
N_HITS = 37
TAIL = 4.0

STYLE = style_for_chapter(CHAPTER)
LEAD_IN = PRE + LEAD_HITS * HIT      # 3.667 秒(= chart 的 leadInSec)


def main():
    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(proj, "sounds", "music", "level22.m4a")
    secs, info = render(STYLE, hit_sec=HIT, n_hits=N_HITS, out_path=out,
                        lead_hits=LEAD_HITS, pre=PRE, tail=TAIL, source_hit=BAR)
    print(f"✅ 音樂做好了：{out}（{secs:.1f} 秒，風格＝第{CHAPTER}大關卡「{STYLE.name}」）")
    print(f"   {info}")
    print(f"   預備拍 {LEAD_IN:.3f} 秒，{N_HITS} 個拍點每 {HIT:.3f} 秒一下，"
          f"最後一下在 {LEAD_IN + (N_HITS - 1) * HIT:.2f} 秒")
    print(f"   素材一小節 {BAR:g} 秒 = {round(BAR / HIT)} 個拍點（90BPM，270BPM 太趕）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
