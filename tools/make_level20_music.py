#!/usr/bin/env python3
"""合成第20關的背景音樂 → sounds/music/level20.m4a

第20關（第二大關卡「第一行第二小節」的第2關）：BPM 10、**四個三連音**共 12 下，
小朋友每 2 秒打一下（1/3 拍＝三連音一個間隔）。

**音樂風格由章節決定**：本關屬第 2 大關卡 → `music_style.style_for_chapter(2)`
＝現成 CC0 曲目「旋轉木馬風琴」，用 `tools/track_music.py` 變速對齊到本關拍點。
規矩「每個大關卡的音樂全都不一樣」與「現成素材只收 CC0」見 docs/關卡音樂.md。

結構（總長 37 秒，對齊 charts/level20.json）：
    0–1s     開頭靜音緩衝(preRollSec，躲播放起頭暫態)
    1–9s     音樂進來＋預備拍：英文人聲數拍 one/two/three/four 騎在音樂上
             (每 2 秒一聲＝拍點間隔)＋節拍器同步
    9–33s    12 個拍點(每 2 秒一下)，每個拍點一聲節拍器 → 脈動不間斷
    33–37s   收尾＋淡出(最後一下在 31 秒，留足夠時間給 ±2 秒容許窗)

用法：python3 tools/make_level20_music.py
"""
import os
import sys

from music_style import style_for_chapter
from track_music import render

CHAPTER = 2         # 這關屬第幾個大關卡(決定音樂風格)
HIT = 2.0           # 拍點間隔 2 秒(= BPM 10 的 1/3 拍＝三連音一顆)
PRE = 1.0           # 開頭靜音緩衝(= chart 的 preRollSec)
LEAD_HITS = 4       # 預備拍 4 聲(間隔＝拍點間隔，速度50以下的規矩)
N_HITS = 12         # 這關要打 12 下
TAIL = 4.0

STYLE = style_for_chapter(CHAPTER)
LEAD_IN = PRE + LEAD_HITS * HIT      # 9 秒(= chart 的 leadInSec)


def main():
    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(proj, "sounds", "music", "level20.m4a")
    secs, info = render(STYLE, hit_sec=HIT, n_hits=N_HITS, out_path=out,
                        lead_hits=LEAD_HITS, pre=PRE, tail=TAIL)
    print(f"✅ 音樂做好了：{out}（{secs:.1f} 秒，風格＝第{CHAPTER}大關卡「{STYLE.name}」）")
    print(f"   {info}")
    print(f"   預備拍 {LEAD_IN:.0f} 秒，{N_HITS} 個拍點每 {HIT:.0f} 秒一下，"
          f"最後一下在 {LEAD_IN + (N_HITS - 1) * HIT:.0f} 秒")
    return 0


if __name__ == "__main__":
    sys.exit(main())
