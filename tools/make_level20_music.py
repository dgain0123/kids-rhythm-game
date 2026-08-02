#!/usr/bin/env python3
"""合成第20關的背景音樂 → sounds/music/level20.m4a

第20關（第二大關卡「第一行第二小節」的第2關）：BPM 10、**四個三連音**共 12 下，
小朋友每 2 秒打一下（1/3 拍＝三連音一個間隔）。

**音樂風格由章節決定**：本關屬第 2 大關卡 → `music_style.style_for_chapter(2)`
（目前＝木琴馬林巴/G 大調/沙鈴節拍器）。規矩「每個大關卡的音樂全都不一樣」
見 docs/關卡音樂.md，違反會被 tests/test_music_style.py 擋下。

結構（總長 37 秒，對齊 charts/level20.json）：
    0–1s     開頭靜音緩衝(preRollSec，躲播放起頭暫態)
    1–9s     預備拍：英文人聲數拍 one/two/three/four
             (每 2 秒一聲＝拍點間隔；速度50以下用拍點間隔數拍的規矩)＋節拍器墊底
    9–33s    伴奏：4 個和聲段 × 6 秒(＝一組三連音 3 個拍點)
             每 2 秒＝一個拍點，**每組三連音的第一顆最亮** → 聽得出三個一組
             ＋節拍器每個拍點一聲 → 脈動不間斷；拍點之間墊很小聲的裝飾音
    33–37s   終止和弦餘韻＋淡出(最後一下在 31 秒，留足夠時間給 ±2 秒容許窗)

用法：python3 tools/make_level20_music.py
"""
import os
import sys

from music_style import Mixer, style_for_chapter
from voice_count import count_voices

CHAPTER = 2         # 這關屬第幾個大關卡(決定音樂風格)
SR = 44100
HIT = 2.0           # 拍點間隔 2 秒(= BPM 10 的 1/3 拍＝三連音一顆)
PRE = 1.0           # 開頭靜音緩衝(= chart 的 preRollSec)
COUNT = HIT         # 數拍間隔＝拍點間隔(速度50以下的規矩)
LEAD_IN = PRE + 4 * COUNT   # 預備拍總長 9 秒(= chart 的 leadInSec)
SEG = 3 * HIT       # 一個和聲段 6 秒＝一組三連音(3 個拍點)

STYLE = style_for_chapter(CHAPTER)
SEGS = len(STYLE.prog)
END_T = LEAD_IN + SEGS * SEG        # 33 秒：最後一下(第12下)在 31 秒，這裡是收尾和弦
TOTAL = END_T + 4.0


def main():
    mx = Mixer(TOTAL, SR)

    # 預備拍：英文人聲數拍(不修剪，起音點對齊拍點)＋節拍器墊底 → 脈動不間斷
    for k, (v, on) in enumerate(count_voices(SR)):
        mx.add(PRE + k * COUNT - on, v * 0.6)
        STYLE.click(mx, PRE + k * COUNT, vol=0.20)

    # 4 個和聲段 × 3 個拍點(＝一組三連音)
    for g, seg in enumerate(STYLE.prog):
        t0 = LEAD_IN + g * SEG
        STYLE.chord(mx, t0, SEG + 0.3, seg)
        STYLE.bass(mx, t0, seg["bass"])
        for k, note in enumerate(seg["hits"]):
            STYLE.hit(mx, t0 + k * HIT, note, accent=(k == 0))  # 三連音第一顆最亮
            STYLE.click(mx, t0 + k * HIT)                       # 節拍器：每個拍點一聲
            if k < len(seg["hits"]) - 1:                        # 拍點之間的小裝飾
                STYLE.fill(mx, t0 + k * HIT + HIT / 2, seg["hits"][k + 1])

    # 收尾：終止和弦(最後一下之後 2 秒，不再敲節拍器)
    STYLE.ending(mx, END_T, STYLE.prog[0])

    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    m4a = os.path.join(proj, "sounds", "music", "level20.m4a")
    secs = mx.finish(m4a)
    print(f"✅ 音樂做好了：{m4a}（{secs:.1f} 秒，風格＝第{CHAPTER}大關卡「{STYLE.name}」"
          f"{STYLE.key}，預備拍 {LEAD_IN:.0f} 秒，12 個拍點每 {HIT:.0f} 秒一下，"
          f"最後一下在 {LEAD_IN + 11 * HIT:.0f} 秒）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
