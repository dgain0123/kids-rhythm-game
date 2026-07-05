#!/bin/bash
# 雙擊這個檔案即可啟動遊戲（會開一個本機伺服器，麥克風才能用）
cd "$(dirname "$0")" || exit 1
PORT=8770
echo "🥁 幼兒節奏遊戲啟動中… http://localhost:$PORT"
# 先開瀏覽器，再啟動伺服器(用禁快取的 serve.py，改檔重整就生效)
( sleep 1; open "http://localhost:$PORT/index.html" ) &
python3 serve.py
