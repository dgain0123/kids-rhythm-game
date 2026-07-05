# 幼兒節奏遊戲 🥁

一個給幼兒玩的網頁節奏遊戲：畫面上同時顯示**鼓譜**與**吸引小朋友的畫面**，
小朋友對著麥克風**真的打鼓**，程式偵測鼓聲來判定過關 / 失敗。

## 文件（docs/）
- [架構總覽](docs/架構總覽.md) — 檔案結構、資料流、本機vs線上、關鍵決策
- [打鼓偵測](docs/打鼓偵測.md) — 麥克風偵測、門檻、暖機、生命週期
- [音效系統](docs/音效系統.md) — 歡呼/失敗音、Safari 解鎖、blob 離線播放
- [角色與號碼牌](docs/角色與號碼牌.md) — 角色清單、數量、號碼牌、個別定位
- [關卡系統](docs/關卡系統.md) — 譜格式、音符繪製、判定、目錄導覽
- [離線與部署](docs/離線與部署.md) — serve.py、PWA/SW、GitHub Pages、同步流程
- [踩過的坑](docs/踩過的坑.md) — 除錯筆記
- 各關規格：`關卡/第N關.md`

## 怎麼玩（第一關）
- 畫面顯示：一個四分音符 + 大表情
- 規則：**打一下鼓 → 過關 🎉**；**打第二下 → 失敗 😢**（不判拍子）

## 怎麼啟動
> ⚠️ 瀏覽器要用麥克風，必須透過 `localhost`，不能直接雙擊 index.html。

**方法 A（最簡單）**：雙擊 `start.command`，會自動開伺服器並打開瀏覽器。
（第一次可能被 macOS 擋，右鍵 →「打開」一次即可。）

**方法 B（手動）**：
```bash
cd ~/Downloads/Claude/幼兒節奏遊戲
python3 -m http.server 8770
# 瀏覽器開 http://localhost:8770
```
第一次會問麥克風權限，請按「允許」。用滑桿調整靈敏度（真的鼓比較大聲、可調低靈敏；用手拍桌可調高）。

## 關卡規格
每一關都有獨立的規格正解檔，放在 `關卡/`（例：`關卡/第1關.md`）。要改某關規則先改它的 md，程式/資料以該檔為準。**每個 md 保持在 200 行以內**。

## 專案結構
```
index.html          遊戲畫面
css/style.css        幼兒風格樣式
js/audio.js          麥克風 + 打鼓聲偵測(onset detection)
js/game.js           關卡邏輯(打一下過關 / 打兩下失敗)
js/render.js         畫譜面音符 + 過關彩帶
js/main.js           串接以上
charts/level1.json   第一關的「譜」
start.command        一鍵啟動
```

## 譜的格式 & 轉檔
譜的來源是 **Logic Pro**。流程：
`Logic → 匯出 MIDI(.mid) → tools/mid2json.py → charts/*.json → 遊戲讀取`

**在 Logic 匯出**：File → Export → Selection/Tracks as MIDI File（鼓軌用 GM 鼓對照，小鼓=38、大鼓=36…）。

**轉檔**（需要 `pretty_midi`，缺的話 `pip3 install pretty_midi`）：
```bash
# 全鼓件、前 4 小節
python3 tools/mid2json.py 你的鼓.mid --bars 4 --title "第二關"
# 只留小鼓當簡單關
python3 tools/mid2json.py 你的鼓.mid --only snare --bars 4 -o charts/level2.json
```
選項：`--only kick,snare,hihat,tom,cymbal`、`--bars N`、`--max-hits N`、`--title`、`--hint`。
轉檔行為由 `tests/test_mid2json.py` 釘住，`tests/guard_test.py` 為守門入口（改 .py 會自動跑）。

目前 `charts/level1.json` 為手寫範例：
```json
{
  "title": "第一關：打一下",
  "maxHits": 1,
  "notes": [ { "type": "quarter", "drum": "snare" } ]
}
```

## 換角色（每個小朋友喜歡的不一樣）
畫面上方有**角色選單**，點一下就換，選擇會記住。**一份網頁、多個角色**，不用複製整個網站。

**加一個新角色（約 30 秒）：**
1. 把圖片放進 `characters/` 資料夾（建議**透明背景 PNG、正方形**，例如 `characters/pikachu.png`）
2. 打開 `characters/index.json`，在 `characters` 陣列加一筆：
   ```json
   { "id": "pikachu", "name": "皮卡丘", "img": "pikachu.png" }
   ```
   （想用 emoji 當角色就寫 `"emoji": "🐱"`、不用放圖）
3. 重整網頁 → 選單就多一個

- 過關時角色會自己蹦蹦跳（`css/style.css` 的 `@keyframes celebrate`）
- 也能用網址指定預設角色：`index.html?char=pikachu`
- 角色系統程式在 `js/characters.js`

## 之後可以加
- mid→json 轉檔器（對接 Logic / 鼓譜自動化專案）
- 更多關卡（打兩下、跟拍子、多種鼓件）
- 更華麗的角色動畫（可找 UI / Whimsy agent 加料）
