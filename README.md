# 幼兒節奏遊戲 🥁

一個給幼兒玩的網頁節奏遊戲：畫面上同時顯示**鼓譜**與**吸引小朋友的畫面**，
小朋友對著麥克風**真的打鼓**，程式偵測鼓聲來判定過關 / 失敗。

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

## 譜的格式
譜的來源是 **Logic Pro**。流程規劃：
`Logic → 匯出 MIDI(.mid) → mid→json 轉檔器（待建） → charts/*.json → 遊戲讀取`

目前 `charts/level1.json` 為手寫範例：
```json
{
  "title": "第一關：打一下",
  "maxHits": 1,
  "notes": [ { "type": "quarter", "drum": "snare" } ]
}
```

## 之後可以加
- mid→json 轉檔器（對接 Logic / 鼓譜自動化專案）
- 更多關卡（打兩下、跟拍子、多種鼓件）
- 更華麗的角色動畫（可找 UI / Whimsy agent 加料）
