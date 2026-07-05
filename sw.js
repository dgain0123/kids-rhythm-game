// sw.js — 讓遊戲能離線玩
// 策略：有網路時優先用網路(同時更新快取)，沒網路時用快取 → 線上永遠最新、離線也能玩。
// 快取鍵去掉查詢字串(?t=...)，避免無限累積。

const CACHE = "kids-rhythm-cache";

// 第一次安裝先預抓的核心檔案(之後任何抓過的也會被快取)
const CORE = [
  "./", "./index.html",
  "./css/style.css",
  "./js/main.js", "./js/audio.js", "./js/game.js", "./js/render.js", "./js/characters.js",
  "./charts/level1.json", "./charts/level2.json", "./charts/level3.json", "./charts/level4.json",
  "./charts/level5.json", "./charts/level6.json", "./charts/level7.json", "./charts/level8.json",
  "./characters/index.json", "./characters/cat.png", "./characters/rabbit.png",
  "./sounds/cheer.wav", "./sounds/cheer.mp3", "./sounds/fail.wav",
  "./manifest.webmanifest", "./icon-192.png", "./icon-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) =>
      // 個別加入，某個檔案缺(如公開版沒有角色圖)也不會整包失敗
      Promise.allSettled(CORE.map((u) => c.add(u)))
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return; // 只處理自己的檔案
  const key = url.origin + url.pathname;       // 去掉 ?t=... 查詢字串當快取鍵
  const range = req.headers.get("range");

  e.respondWith((async () => {
    const cache = await caches.open(CACHE);
    try {
      const resp = await fetch(req);
      if (resp && resp.status === 200) cache.put(key, resp.clone()); // 只快取完整檔(不存 206 片段)
      return resp;
    } catch (err) {
      const cached = await cache.match(key);            // 沒網路→用快取
      if (!cached) throw err;
      if (range) {
        // 離線 + 範圍請求(大音檔如歡呼) → 從完整快取切片段回 206，Safari 才播得出來
        const buf = await cached.arrayBuffer();
        const m = /bytes=(\d+)-(\d*)/.exec(range);
        const start = m ? parseInt(m[1], 10) : 0;
        const end = (m && m[2]) ? parseInt(m[2], 10) : buf.byteLength - 1;
        const chunk = buf.slice(start, end + 1);
        return new Response(chunk, {
          status: 206,
          headers: {
            "Content-Range": `bytes ${start}-${end}/${buf.byteLength}`,
            "Accept-Ranges": "bytes",
            "Content-Length": String(chunk.byteLength),
            "Content-Type": cached.headers.get("Content-Type") || "application/octet-stream",
          },
        });
      }
      return cached;
    }
  })());
});
