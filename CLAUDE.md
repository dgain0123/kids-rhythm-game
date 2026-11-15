# 幼兒節奏遊戲 — 路由檔（先讀這頁，再去對應的正解檔）

小朋友對麥克風真的打鼓、畫面顯示鼓譜＋角色的純靜態網頁（HTML/CSS/JS，無後端）。
線上：https://dgain0123.github.io/kids-rhythm-game/ （repo `dgain0123/kids-rhythm-game`，本資料夾就是唯一來源）。

## 要做什麼 → 讀哪個檔
| 工作 | 正解檔 |
|---|---|
| 搞懂檔案結構、資料流、發佈 | `docs/架構總覽.md` |
| 新增／修改關卡、譜格式、目錄兩層制、跟拍模式 | `docs/關卡系統.md`、該關的 `關卡/第N關.md` |
| 關卡音樂（章節風格、速度、音量、收尾、**新增一關的實際步驟**） | `docs/關卡音樂.md`（做法在 `docs/關卡音樂_做法詳解.md`） |
| 示範模式 `?demo=`、打一下消失一隻、示範影片 | `docs/示範模式與動物消失.md` |
| 麥克風偵測、靈敏度 | `docs/打鼓偵測.md` |
| 歡呼／失敗音效、Safari 解鎖 | `docs/音效系統.md` |
| 角色、號碼牌 | `docs/角色與號碼牌.md` |
| 本機伺服器、離線快取、GitHub Pages | `docs/離線與部署.md` |
| 動手前先看有沒有踩過 | `docs/踩過的坑.md` |
| 「歌加節拍器」（給一首真的歌→混節拍器放桌面；他說了才做，**跟關卡音樂裡自己合成的節拍器是兩回事**） | 本體與規則只在鼓譜自動化專案：`~/Downloads/Claude/鼓譜自動化/設計_歌曲加節拍器.md`（入口同專案 `tools/add_click.py`；速度一定先問使用者）。這裡只放指標；有版權的歌與成品不准放進本資料夾 |

## 常用指令
```bash
python3 serve.py                      # 本機玩 http://localhost:8770（麥克風要 localhost；Mac mini 要外接麥克風）
python3 tests/guard_test.py           # 守門（改 .py 會被全域 hook 自動跑）；--no-cache＝全部重跑
python3 tools/mid2json.py X.mid …     # Logic 匯出的 MIDI → charts/levelN.json
python3 tools/make_levelN_music.py    # 做第 N 關音樂 → sounds/music/levelN.m4a
python3 tools/make_demo_golden.py     # 新關卡或示範行為改了 → 重釘示範 golden（有違規會拒釘）
python3 tools/record_demo.py N        # 錄第 N 關示範影片 → videos/（不進 git）
git add -A && git commit && git push  # 發佈（Pages 自動建置，CDN 要等幾分鐘）
```

## 守門快取（2026-11-15）
- 兩支慢測試（示範檢查約 15 秒、音樂約 4 秒）只在**它會讀到的檔案內容有變**時才重跑，
  指紋存 `tests/.guard_cache.json`（不進 git）。規則與相依範圍寫在 `tests/guard_test.py` 開頭。
- **發佈前、換過環境（python／playwright／ffmpeg）後**：跑一次 `--no-cache` 全套。
- 新增測試檔預設每次都跑；要快取才去 `SLOW_DEPS` 用排除法登記「它讀不到的檔」。

## 不能忘的規矩
- repo 是公開的：**有版權的圖／音樂不准 commit**；音樂素材授權登記在 `sounds/music/source/來源與授權.md`。
- 每個 md ≤200 行；每個大關卡的音樂都不一樣；跟拍關卡音樂必含節拍器、到最後一下就結束。
- 新增一關是一條龍：MIDI → 譜 → 音樂 → `js/main.js` 的 GROUPS → `sw.js` 的 CORE → `關卡/第N關.md`
  → 示範 golden → 守門全綠 → push。
