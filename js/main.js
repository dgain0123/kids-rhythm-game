// main.js — 串接：載入譜 → 麥克風 → 遊戲邏輯 → 畫面
import { DrumListener } from "./audio.js";
import { Game } from "./game.js";
import { drawNotes, drawLane, confetti, needsScroll } from "./render.js";
import { initCharacters, showCharacter, setCharCount, getCurrentChar } from "./characters.js";

// 大關卡(章節)：把小關卡收在一起。之後加新章節就在這裡加一組
// {title: 章節名, levels: [小關卡...]}；「下一關」只在同章節內接續
const GROUPS = [
  {
    title: "第一行第一小節",
    levels: ["level1", "level2", "level3", "level4", "level5", "level6", "level7", "level8",
             "level9", "level10", "level11", "level12", "level13", "level14", "level15",
             "level16", "level17", "level18"],
  },
  {
    title: "第一行第二小節",
    levels: ["level19", "level20", "level21"],
  },
];
const LEVELS = GROUPS.flatMap((g) => g.levels);
let levelIdx = 0;

// 某個全域關卡索引屬於哪個大關卡 / 大關卡的起始索引
function groupOfIdx(idx) {
  let a = 0;
  for (let i = 0; i < GROUPS.length; i++) { a += GROUPS[i].levels.length; if (idx < a) return i; }
  return GROUPS.length - 1;
}
function groupStart(gi) {
  let a = 0;
  for (let i = 0; i < gi; i++) a += GROUPS[i].levels.length;
  return a;
}

const $ = (id) => document.getElementById(id);

const els = {
  start: $("startBtn"),
  retry: $("retryBtn"),
  stage: $("stage"),
  hint: $("hint"),
  status: $("status"),
  face: $("face"),
  noteCanvas: $("noteCanvas"),
  fxCanvas: $("fxCanvas"),
  meterFill: $("meterFill"),
  threshMark: $("threshMark"),
  sens: $("sensitivity"),
  debug: $("debug"),
  winBanner: $("winBanner"),
  testCheer: $("testCheerBtn"),
  next: $("nextBtn"),
  levelMenu: $("levelMenu"),
  levelList: $("levelList"),
  menuBtn: $("menuBtn"),
  reconnect: $("reconnectBtn"),
  charPicker: $("charPicker"),
  countdown: $("countdown"),
  lane: $("laneCanvas"),
  backBtn: $("backToGroups"),
  controls: document.querySelector(".controls"),
};

let _peakMax = 0; // 記錄出現過的最大峰值，判斷麥克風到底有沒有收到聲音
let _lastMeterT = 0, _lastMeterW = "", _lastDebugT = 0; // 音量條/診斷面板節流

// 靈敏度滑桿(0=不靈敏, 1=很靈敏) → 觸發門檻(0.02=很好觸發, 0.5=很難觸發)
// 往「很靈敏」拉 → 門檻變低 → 更容易被打鼓觸發
const THRESH_MIN = 0.02, THRESH_MAX = 0.5;
function sensToThreshold(s) { return THRESH_MAX - s * (THRESH_MAX - THRESH_MIN); }
function updateThreshMark(th) {
  // 觸發線畫在音量條上(門檻直接對應峰值 0~1 的位置)
  els.threshMark.style.left = Math.round(th * 100) + "%";
}

let listener = null;
let game = null;
let chart = null;

// ── 跟拍關卡(chart 有 bpm/beat/music)的音樂與畫面同步 ──
// 音樂用 Web Audio buffer 播：在獨立音訊執行緒渲染，主執行緒卡頓也不會
// 讓音樂斷斷續續(<audio> 元素在這台 Safari 會被頁面忙碌切到，實測)
let musicBuf = null;  // 解碼好的 AudioBuffer
let musicSrc = null;  // 播放中的 BufferSource(null=沒在播)
let musicT0 = 0;      // 在 AudioContext 時間軸上的開始時刻
let rafId = null;     // 倒數/拍點高亮的 rAF 迴圈
let _activeIdx = -1;  // 目前該打的音符索引(畫橘色高亮用)
let laneSprite = { image: null, emoji: "🥁" }; // 太鼓軌道上跑的圖示(=目前角色)
let laneFx = [];      // 最近打中的時間(譜面秒)，畫爆星特效用

// 太鼓軌道開/關：遊戲中用軌道取代靜態角色列，過關/失敗再把角色換回來
function showLane(on) {
  els.lane.hidden = !on;
  els.face.style.display = on ? "none" : "";
}

// 舞台/太鼓軌道跟著譜面畫布的尺寸走(drawNotes 依螢幕寬算好了)：
// 寬譜舞台變寬；軌道同寬同縮放 → 判定圈跟紅色基準線垂直對齊
function syncStageLane() {
  els.stage.classList.toggle("wide", els.noteCanvas.width > 560);
  els.lane.width = els.noteCanvas.width;
  els.lane.style.width = els.noteCanvas.style.width;
  els.lane.style.maxWidth = els.noteCanvas.style.maxWidth;
}

function isTimedChart(c) {
  return !!(c && c.bpm && Array.isArray(c.notes) && c.notes.length && c.notes[0].beat != null);
}
// 音樂目前播到第幾秒(以 AudioContext 的時鐘為準，唯一時鐘)
function musicNow() {
  return musicSrc && audioCtx ? audioCtx.currentTime - musicT0 : 0;
}
// 譜面時間 = 音樂播放時間 - 預備拍長度(音樂檔前面有預備拍)
function chartTimeNow() {
  return musicSrc ? musicNow() - (chart.leadInSec ?? 0) : undefined;
}
function stopMusic() {
  if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
  els.countdown.hidden = true;
  _activeIdx = -1;
  laneFx = [];
  showLane(false);
  if (musicSrc) {
    musicSrc.onended = null; // 手動停止不要觸發「歌放完」判定
    try { musicSrc.stop(); } catch (e) {}
    musicSrc = null;
  }
}
// 依判定狀態重畫譜面(打到=綠、當前拍點=橘；超過4小節的譜帶目前拍數→往左捲動)
function redrawChart() {
  let state = {};
  if (game && game.timed) {
    const t = chartTimeNow();
    state = {
      hit: game.hitNotes,
      active: _activeIdx,
      curBeat: typeof t === "number" ? t * chart.bpm / 60 : 0,
    };
  }
  drawNotes(els.noteCanvas, chart.notes, state);
}
// 倒數 + 拍點高亮迴圈：全部以音樂播放時間為準(單一時鐘，不會漂移)
function startTimedLoop() {
  if (rafId) cancelAnimationFrame(rafId);
  const lead = chart.leadInSec ?? 0;
  const pre = chart.preRollSec ?? 0; // 音檔開頭的靜音緩衝(躲播放起頭暫態)，還沒開始數
  const step = lead > pre ? (lead - pre) / 4 : 1; // 預備拍 4 聲
  let frame = 0;
  const scrolls = needsScroll(chart.notes); // 超過4小節→譜面每幀跟著捲
  const tick = () => {
    rafId = null;
    if (!game || !game.timed || !musicSrc) return;
    if (game.state === "pass" || game.state === "fail") { els.countdown.hidden = true; return; }
    frame++;
    const ct = musicNow();
    const t = ct - lead;
    if (lead > 0 && ct < lead) {
      if (ct < pre) {
        els.countdown.hidden = true; // 緩衝期還沒開始數
      } else {
        els.countdown.hidden = false;
        const num = String(Math.min(4, Math.floor((ct - pre) / step) + 1));
        if (els.countdown.textContent !== num) els.countdown.textContent = num; // 數字沒變不動 DOM
      }
    } else {
      if (!els.countdown.hidden) {
        els.countdown.hidden = true;
        els.status.textContent = "跟著音樂打！";
      }
      // 找「現在該打」的音符＝**離現在最近的那顆還沒打到的音符**。
      // 不設窗口 → 燈**一直亮著**、直接從這顆跳到下一顆（使用者要求：不要閃一下閃一下消失，
      // 2026-08-03）。切換點剛好是兩個拍點的中間，也就是「上一隻圖示離開圈圈、
      // 下一隻最接近」的時刻，所以跟太鼓軌道還是同步的。
      let act = -1, best = Infinity;
      for (let i = 0; i < game.noteTimes.length; i++) {
        if (game.hitNotes[i]) continue;
        const err = Math.abs(t - game.noteTimes[i]);
        if (err < best) { best = err; act = i; }
      }
      if (act !== _activeIdx) { _activeIdx = act; if (!scrolls) redrawChart(); }
      if (scrolls && frame % 2 === 1) redrawChart(); // 捲動譜面(30fps，跟軌道錯開幀)
    }
    // 太鼓軌道重畫改 30fps(每兩幀畫一次)：減輕主執行緒負擔，
    // 避免 Safari 音樂播放被卡頓切到；角色移動 30fps 視覺上一樣順
    if (frame % 2 === 0) {
      drawLane(els.lane, {
        t,
        noteTimes: game.noteTimes,
        hit: game.hitNotes,
        tolSec: game.tolSec,
        fx: laneFx,
        sprite: laneSprite,
        anchorX: parseFloat(els.noteCanvas.dataset.anchorX || "0"),
      });
    }
    rafId = requestAnimationFrame(tick);
  };
  rafId = requestAnimationFrame(tick);
}

async function loadChart(level) {
  // 加時間戳避開瀏覽器快取，改譜後重整就能立刻看到
  const res = await fetch(`./charts/${level}.json?t=` + Date.now(), { cache: "no-store" });
  return res.json();
}

// 切到第 idx 關：載譜、更新標題/提示/譜面(有音樂就先整包載進記憶體)
async function goToLevel(idx) {
  stopMusic();
  levelIdx = Math.max(0, Math.min(LEVELS.length - 1, idx));
  chart = await loadChart(LEVELS[levelIdx]);
  $("title").textContent = chart.title;
  els.hint.textContent = chart.hint || "";
  drawNotes(els.noteCanvas, chart.notes);
  syncStageLane();
  // 數下數關卡：要打幾下就顯示幾隻角色(掛號碼牌)
  // 跟拍關卡：開始前只放 1 隻、不掛號碼牌(角色會在太鼓軌道上跑)
  if (isTimedChart(chart)) setCharCount(1, { numbers: false });
  else setCharCount(chart.maxHits);
  showCharacter();
  musicBuf = null;
  if (chart.music) {
    // 整包抓下來解碼成 AudioBuffer(離線時由 SW 快取供檔)
    try {
      const res = await fetch(chart.music);
      musicBuf = await getCtx().decodeAudioData(await res.arrayBuffer());
    } catch (e) { musicBuf = null; }
  }
}

// 「下一關」只在同一個大關卡內接續(章節結尾就沒有下一關)
function hasNextLevel() {
  const gi = groupOfIdx(levelIdx);
  return levelIdx < groupStart(gi) + GROUPS[gi].levels.length - 1;
}

// 顯示關卡目錄(暫停偵測、藏遊戲畫面)。view: "groups"=大關卡列表、"levels"=目前章節的小關卡
function showMenu(view = "groups") {
  stopMusic();
  if (listener) listener.pause();
  els.winBanner.hidden = true;
  els.levelMenu.hidden = false;
  els.stage.style.display = "none";
  els.controls.style.display = "none";
  els.charPicker.style.display = "none";
  els.hint.style.display = "none";
  $("title").textContent = "幼兒節奏遊戲";
  if (view === "levels") renderLevelMenu(groupOfIdx(levelIdx));
  else renderGroupMenu();
}
function hideMenu() {
  els.levelMenu.hidden = true;
  els.stage.style.display = "";
  els.controls.style.display = "";
  els.charPicker.style.display = "";
  els.hint.style.display = "";
}

// 目錄資料：開站時先把各關標題抓好(之後選單切換都是即時的)
let levelTitles = [];
async function prefetchTitles() {
  levelTitles = await Promise.all(LEVELS.map(async (lv, i) => {
    try { const c = await loadChart(lv); return c.title || `第${i + 1}關`; }
    catch (e) { return `第${i + 1}關`; }
  }));
}
const menuTitleEl = document.querySelector(".menu-title");

// 大關卡列表(章節)
function renderGroupMenu() {
  menuTitleEl.textContent = "選擇大關卡 🥁";
  els.backBtn.hidden = true;
  els.levelList.innerHTML = "";
  GROUPS.forEach((g, gi) => {
    const btn = document.createElement("button");
    btn.className = "level-card group-card";
    btn.innerHTML = `<span class="lv-num">${gi + 1}</span><span class="lv-name">${g.title}</span>`;
    btn.addEventListener("click", () => renderLevelMenu(gi));
    els.levelList.appendChild(btn);
  });
}

// 某個大關卡底下的小關卡列表
function renderLevelMenu(gi) {
  menuTitleEl.textContent = GROUPS[gi].title + " 🥁";
  els.backBtn.hidden = false;
  els.levelList.innerHTML = "";
  const start = groupStart(gi);
  GROUPS[gi].levels.forEach((lv, k) => {
    const i = start + k;
    const btn = document.createElement("button");
    btn.className = "level-card";
    btn.innerHTML = `<span class="lv-num">${k + 1}</span><span class="lv-name">${levelTitles[i] || `第${i + 1}關`}</span>`;
    btn.addEventListener("click", () => selectLevel(i));
    els.levelList.appendChild(btn);
  });
}

// 選了某一關：進遊戲畫面、顯示「開始遊戲」等使用者按(要有手勢才能開麥克風)
async function selectLevel(idx) {
  hideMenu();
  await goToLevel(idx);
  els.stage.className = "stage" + (els.noteCanvas.width > 560 ? " wide" : "");
  showCharacter();
  els.start.hidden = false;
  els.start.disabled = false;
  els.start.textContent = "開始遊戲";
  els.retry.hidden = true;
  els.next.hidden = true;
  // 跟拍關卡不顯示打幾下(看譜跟音樂就好)；數下數關卡照舊提示
  els.status.textContent = isTimedChart(chart)
    ? "準備好了！跟著音樂打鼓～"
    : `準備好了！打${chart.maxHits}下鼓～`;
}

function onState(state, info) {
  // 只換狀態 class，保留 flash(打擊閃黃)等其他 class 不被覆蓋
  ["ready", "progress", "hitOnce", "pass", "fail"].forEach(s => els.stage.classList.remove(s));
  els.stage.classList.add(state);
  switch (state) {
    case "ready":
      showCharacter(); // 還原成目前選的角色
      els.winBanner.hidden = true;
      els.next.hidden = true;
      els.status.textContent = info.timed
        ? "準備好了！跟著音樂打鼓～"
        : `準備好了！打${info.maxHits}下鼓～`;
      break;
    case "progress":
      els.status.textContent = "";
      break;
    case "hitOnce":
      els.status.textContent = "";
      break;
    case "pass":
      stopMusic();
      celebrateSound();   // 聲音先播，讓音訊管線先建立
      stopListening();
      els.face.innerHTML = '<span class="char-emoji">🎉</span>'.repeat(Math.min(info.maxHits, 8)); // 過關換成拉炮(最多8個,太多會擠出畫面)
      els.winBanner.hidden = false;
      els.status.textContent = "過關！你好棒！";
      els.retry.hidden = false;
      els.next.hidden = !hasNextLevel(); // 有下一關才顯示「下一關」
      (hasNextLevel() ? els.next : els.retry).scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(() => confetti(els.fxCanvas), 120); // 彩帶延後，避開最重的第一幀壓到聲音
      break;
    case "fail":
      stopMusic();
      failSound();
      els.status.textContent = info.timed
        ? "有音符沒打到～再試1次！"
        : "哎呀～打太多下了！再試1次";
      stopListening();
      els.retry.hidden = false;
      els.retry.scrollIntoView({ behavior: "smooth", block: "center" });
      break;
  }
}

// 共用的 AudioContext（要在使用者互動後才會 running）
let audioCtx = null;
function getCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === "suspended") audioCtx.resume();
  return audioCtx;
}

// Safari 解鎖：一定要在使用者點擊時，播一個極短的靜音 buffer，Web Audio 之後才能從任何情境播放
let _audioUnlocked = false;
function unlockAudio() {
  const ctx = getCtx();
  if (ctx.state === "suspended") ctx.resume();
  if (_audioUnlocked) return;
  try {
    const b = ctx.createBuffer(1, 1, 22050);
    const s = ctx.createBufferSource();
    s.buffer = b; s.connect(ctx.destination); s.start(0);
    _audioUnlocked = true;
  } catch (e) { /* 忽略 */ }
}

// 預先載入「真人歡呼」音檔(可有可無)。放 sounds/cheer.mp3 就會優先用真人聲。
// 用 HTMLAudioElement 播放：獨立媒體管線，比 Web Audio buffer 更不怕主執行緒卡頓
let cheerSrc = null;
let cheerEl = null; // 真人歡呼的 <audio> 元素(這台 Safari 能出聲的管線)
let failEl = null;  // 失敗音效的 <audio> 元素
const CHEER_SRCS = ["./sounds/cheer.wav", "./sounds/cheer.mp3"]; // WAV 優先
// 把整個音檔抓進記憶體(blob)再建 <audio>：播放時不再發網路/範圍請求 → 大檔案離線也直接可播
async function loadAudioEl(src) {
  const r = await fetch(src);
  if (!r.ok) throw new Error("not ok");
  const el = new Audio(URL.createObjectURL(await r.blob()));
  el.preload = "auto";
  el.load();
  return el;
}

async function preloadCheer() {
  // 失敗音效(整包載入記憶體)
  try { failEl = await loadAudioEl("./sounds/fail.wav"); } catch (e) {}
  // 過關歡呼(整包載入記憶體，離線也能直接播，不受大檔範圍請求影響)
  for (const src of CHEER_SRCS) {
    try { cheerEl = await loadAudioEl(src); cheerSrc = src; return; }
    catch (e) { /* 試下一個 */ }
  }
}

// 在使用者點擊時「解鎖」<audio> 元素：靜音播一下馬上暫停歸零，之後從非點擊情境也能播
const _primed = new WeakSet();
function primeEl(el) {
  if (!el || _primed.has(el)) return;
  el.muted = true;
  const p = el.play();
  if (p && p.then) {
    p.then(() => { el.pause(); el.currentTime = 0; el.muted = false; _primed.add(el); })
     .catch(() => { el.muted = false; });
  } else { _primed.add(el); }
}
// 每次開始遊戲都試著解鎖(音檔可能還在載，載好後的下一次點擊才解鎖得到)
function primeCheer() {
  primeEl(cheerEl);
  primeEl(failEl);
}

// 播放失敗音效(用已解鎖的 <audio> 元素)
function failSound() {
  if (!failEl) return;
  try { failEl.currentTime = 0; const p = failEl.play(); if (p && p.catch) p.catch(() => {}); } catch (e) {}
}

// 過關音效：優先播真人歡呼(Web Audio buffer)；沒有的話用「人聲合成」的歡呼當後備
function celebrateSound() {
  try {
    const ctx = getCtx();
    const now = ctx.currentTime;

    // 1) 優先：已解鎖的 <audio> 元素(這台 Safari 能出聲的管線)
    if (cheerEl) {
      try {
        cheerEl.currentTime = 0;
        const p = cheerEl.play();
        if (p && p.catch) p.catch(() => {});
        if (els.debug) els.debug.textContent = `歡呼: 播 <audio>(primed=${_cheerPrimed})  ${cheerSrc}`;
        return;
      } catch (e) { /* 落到下面 */ }
    }
    // 2) 備援：Web Audio buffer
    if (cheerBuffer) {
      const s = ctx.createBufferSource();
      s.buffer = cheerBuffer;
      s.connect(ctx.destination);
      s.start();
      if (els.debug) els.debug.textContent = `歡呼: 播 Web Audio buffer  ctx=${ctx.state}`;
      return;
    }
    if (els.debug) els.debug.textContent = "歡呼: 用合成人聲(沒有真人音檔)";
    // 3) 都沒有 → 往下用「合成人聲歡呼」(也走 Web Audio)

    // ↓↓ 以下是沒有真人音檔時的「合成後備」歡呼
    // 主鏈：master → 壓縮器 → 喇叭
    const master = ctx.createGain();
    master.gain.value = 1.0;
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -16; comp.knee.value = 20; comp.ratio.value = 4;
    comp.attack.value = 0.003; comp.release.value = 0.25;
    master.connect(comp); comp.connect(ctx.destination);

    function tone(freq, start, dur, type = "triangle", vol = 0.3) {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.type = type; o.frequency.value = freq;
      o.connect(g); g.connect(master);
      const t = now + start;
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(vol, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      o.start(t); o.stop(t + dur + 0.05);
    }
    function noiseBuffer(dur) {
      const buf = ctx.createBuffer(1, Math.floor(ctx.sampleRate * dur), ctx.sampleRate);
      const d = buf.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
      return buf;
    }
    // 掌聲
    function applause(dur = 2.6, perSec = 45, vol = 0.45) {
      const n = Math.floor(dur * perSec);
      for (let i = 0; i < n; i++) {
        const t = now + Math.random() * dur;
        const b = ctx.createBufferSource(); b.buffer = noiseBuffer(0.03);
        const hp = ctx.createBiquadFilter(); hp.type = "highpass"; hp.frequency.value = 1800;
        const g = ctx.createGain();
        g.gain.setValueAtTime(vol * (0.5 + Math.random()), t);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.05);
        b.connect(hp); hp.connect(g); g.connect(master);
        b.start(t); b.stop(t + 0.06);
      }
    }
    // 母音的共振峰 [F1, F2]
    const VOWEL = {
      oo: [320, 800],   // 嗚
      ah: [720, 1150],  // 啊
      eh: [600, 1700],  // 耶(ㄟ)
      ee: [300, 2300],  // 一
    };
    // 一個音節：鋸齒波(聲帶)→兩個會滑動的共振峰(母音可從一個滑到另一個)
    function syllable(t0, dur, f0a, f0b, vowA, vowB, vol) {
      const o = ctx.createOscillator(); o.type = "sawtooth";
      o.frequency.setValueAtTime(f0a, t0);
      o.frequency.exponentialRampToValueAtTime(f0b, t0 + dur);
      const b1 = ctx.createBiquadFilter(); b1.type = "bandpass"; b1.Q.value = 9;
      const b2 = ctx.createBiquadFilter(); b2.type = "bandpass"; b2.Q.value = 12;
      b1.frequency.setValueAtTime(vowA[0], t0); b1.frequency.linearRampToValueAtTime(vowB[0], t0 + dur);
      b2.frequency.setValueAtTime(vowA[1], t0); b2.frequency.linearRampToValueAtTime(vowB[1], t0 + dur);
      const g = ctx.createGain();
      g.gain.setValueAtTime(0.0001, t0);
      g.gain.exponentialRampToValueAtTime(vol, t0 + 0.05);
      g.gain.setValueAtTime(vol, t0 + dur * 0.6);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
      o.connect(b1); o.connect(b2); b1.connect(g); b2.connect(g); g.connect(master);
      o.start(t0); o.stop(t0 + dur + 0.05);
    }
    // 幾種喊法：ya、yeah、woo-hoo、woo
    function shout(word, t0, f0, vol) {
      const up = 1.14;
      if (word === "ya") {
        syllable(t0, 0.42, f0, f0 * up, VOWEL.ee, VOWEL.ah, vol);        // 一→啊 = 「ya」
      } else if (word === "yeah") {
        syllable(t0, 0.55, f0, f0 * up, VOWEL.eh, VOWEL.ah, vol);        // 耶啊
      } else if (word === "woohoo") {
        syllable(t0, 0.34, f0 * 0.9, f0 * 1.1, VOWEL.oo, VOWEL.oo, vol); // woo
        syllable(t0 + 0.4, 0.4, f0 * 1.05, f0 * 1.2, VOWEL.oo, VOWEL.oo, vol); // hoo(更高)
      } else { // woo
        syllable(t0, 0.6, f0 * 0.9, f0 * 1.25, VOWEL.oo, VOWEL.oo, vol);
      }
    }
    // 一群人亂喊(不同喊法、不同音高大人小孩、錯開時間)＝豐富的歡呼
    function crowdVoices() {
      const words = ["ya", "yeah", "woohoo", "woo"];
      for (let i = 0; i < 18; i++) {
        const word = words[(Math.random() * words.length) | 0];
        const t0 = now + Math.random() * 0.5;
        const f0 = 150 + Math.random() * 240;              // 童聲偏高、成人偏低
        shout(word, t0, f0, 0.12 + Math.random() * 0.06);
      }
      // 第二波，讓歡呼更持久熱鬧
      for (let i = 0; i < 10; i++) {
        const word = words[(Math.random() * words.length) | 0];
        const t0 = now + 0.8 + Math.random() * 0.5;
        const f0 = 160 + Math.random() * 240;
        shout(word, t0, f0, 0.11 + Math.random() * 0.06);
      }
    }

    // 人聲合成歡呼 + 掌聲 + 勝利小號和弦
    crowdVoices();
    applause();
    const run = [523, 659, 784, 1047, 1319, 1568];
    run.forEach((f, i) => tone(f, i * 0.08, 0.2, "square", 0.22));
    const chord = [523, 659, 784, 1047];
    chord.forEach((f) => tone(f, 0.55, 1.0, "triangle", 0.26));
  } catch (e) { /* 忽略 */ }
}

function stopListening() {
  // 只暫停偵測，保持麥克風開著(關麥克風會讓 macOS 重設音訊裝置、害歡呼輸出閃斷)
  if (listener) listener.pause();
}

// 讀出目前用的麥克風裝置名稱與狀態，方便判斷是不是選錯輸入
function micInfo(l) {
  try {
    const t = l.stream && l.stream.getAudioTracks()[0];
    if (!t) return "(沒有音軌)";
    return `${t.label || "未命名"} | enabled=${t.enabled} muted=${t.muted} state=${t.readyState}`;
  } catch (e) { return "(讀不到)"; }
}

async function startGame() {
  els.start.disabled = true;
  els.start.textContent = "開麥克風中…";
  // 診斷用：?nomic=1 完全不開麥克風，只播音樂——用來分辨
  // 「音樂卡頓」是麥克風裝置拖累整個音訊管線、還是播放端本身的問題
  const NOMIC = new URLSearchParams(location.search).get("nomic");
  try {
    unlockAudio(); // 趁「開始遊戲」手勢解鎖 Web Audio
    primeCheer();  // 同一手勢解鎖真人歡呼的 <audio> 元素，過關才播得出
    const th = sensToThreshold(parseFloat(els.sens.value));
    if (NOMIC) throw Object.assign(new Error("nomic"), { nomic: true });
    // 麥克風串流若已死掉(當機/被系統收回)，丟掉重開，避免後面幾關讀到全 0
    if (listener && !listener.isLive()) { listener.stop(); listener = null; }
    if (!listener) {
      // 第一次：開麥克風。之後整場重用同一個，不再每輪開開關關
      listener = new DrumListener({
        ctx: getCtx(), // 跟音樂共用同一個 AudioContext：一條音訊管線，減少裝置抖動/卡頓
        // 跟拍模式要帶「譜面時間」，數下數模式帶 undefined 沒影響
        onHit: () => { if (game) game.registerHit(chartTimeNow()); },
        // 音量回報每幀都來(60fps)，DOM 更新要節流：主執行緒太忙會讓
        // Safari 的音樂播放出現卡頓(這台機器實測過，歡呼斷音同因)
        onLevel: (lv) => {
          if (lv > _peakMax) _peakMax = lv;
          const now = performance.now();
          if (now - _lastMeterT > 100) {
            _lastMeterT = now;
            const w = Math.round(lv * 100) + "%";
            if (w !== _lastMeterW) { _lastMeterW = w; els.meterFill.style.width = w; }
          }
          // 診斷面板隱藏時完全不做(原本每幀組字串+查麥克風狀態，白耗)
          if (!els.debug.hidden && now - _lastDebugT > 300) {
            _lastDebugT = now;
            els.debug.textContent =
              `目前音量: ${lv.toFixed(3)}   出現過最大: ${_peakMax.toFixed(3)}\n` +
              `音訊狀態: ${listener.audioCtx ? listener.audioCtx.state : "?"}   ` +
              `取樣率: ${listener.audioCtx ? listener.audioCtx.sampleRate : "?"}\n` +
              `麥克風: ${micInfo(listener)}`;
          }
        }
      });
      listener.setThreshold(th);
      updateThreshMark(th);
      _peakMax = 0;
      await listener.start();
      els.debug.textContent = "已取得麥克風，開始偵測…\n" + micInfo(listener);
    } else {
      // 之後幾輪：直接恢復偵測(麥克風一直開著；並喚醒可能被 suspend 的 AudioContext)
      listener.setThreshold(th);
      updateThreshMark(th);
      await listener.resume();
    }
  } catch (e) {
    if (!(e && e.nomic)) {
      els.status.textContent = "拿不到麥克風 😵";
      els.debug.textContent = "❌ 錯誤：" + (e && e.name) + " - " + (e && e.message);
      els.start.disabled = false;
      els.start.textContent = "開始遊戲";
      return;
    }
    // nomic 測試模式：跳過麥克風，繼續開始遊戲(只播音樂)
  }

  els.start.hidden = true;
  els.retry.hidden = true;
  els.next.hidden = true;
  drawNotes(els.noteCanvas, chart.notes);
  els.hint.textContent = chart.hint || "";
  game = new Game(chart, {
    onState,
    onNote: () => {
      // 打中：譜面上該音符變綠 + 太鼓判定圈爆星
      const t = chartTimeNow();
      if (typeof t === "number") laneFx.push({ time: t });
      if (laneFx.length > 10) laneFx.shift();
      redrawChart();
    },
  });
  game.start();

  // 跟拍關卡：開始播音樂(內含預備拍) + 倒數/太鼓軌道迴圈
  if (isTimedChart(chart) && musicBuf) {
    _activeIdx = -1;
    laneFx = [];
    // 軌道上跑的圖示＝目前選的角色(圖片先載好；emoji 角色直接畫字)
    const ch = getCurrentChar();
    laneSprite = { image: null, emoji: (ch && ch.emoji) || "🥁" };
    if (ch && ch.img) {
      const im = new Image();
      im.src = "characters/" + ch.img;
      laneSprite.image = im;
    }
    showLane(true);
    // Web Audio buffer 播放：音訊執行緒渲染，不受主執行緒卡頓影響
    const ctx = getCtx();
    musicSrc = ctx.createBufferSource();
    musicSrc.buffer = musicBuf;
    musicSrc.connect(ctx.destination);
    // 音樂放完＝這一輪結束：還有沒打到的音符就算失敗
    musicSrc.onended = () => { musicSrc = null; if (game) game.finishSong(); };
    musicT0 = ctx.currentTime;
    musicSrc.start();
    els.status.textContent = "預備～聽拍子！";
    startTimedLoop();
  }
}

function retry() {
  els.retry.hidden = true;
  els.next.hidden = true;
  drawNotes(els.noteCanvas, chart.notes);
  startGame();
}

// 進入下一關
async function nextLevel() {
  els.next.hidden = true;
  els.retry.hidden = true;
  await goToLevel(levelIdx + 1);
  startGame();
}

// 打到一下時閃一下畫面，給校準用的即時回饋
let _flashT = null;
function flashHit() {
  els.stage.classList.add("flash");
  clearTimeout(_flashT);
  _flashT = setTimeout(() => els.stage.classList.remove("flash"), 120);
}

// 靈敏度滑桿即時調整
els.sens.addEventListener("input", () => {
  const th = sensToThreshold(parseFloat(els.sens.value));
  updateThreshMark(th);
  if (listener) listener.setThreshold(th);
});

els.start.addEventListener("click", startGame);
els.retry.addEventListener("click", retry);
els.next.addEventListener("click", nextLevel);
els.menuBtn.addEventListener("click", () => showMenu("levels")); // 遊戲中☰直接回目前章節的小關卡
els.backBtn.addEventListener("click", renderGroupMenu);

// 螢幕轉向/改變大小：依新寬度重排譜面與軌道(手機直橫切換用)
window.addEventListener("resize", () => {
  if (!chart) return;
  redrawChart();
  syncStageLane();
});

// 註冊 Service Worker → 離線也能玩、可加到主畫面
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  });
}

// 重連麥克風：完全重開麥克風並重新開始本關(麥克風卡住時的救命按鈕)
els.reconnect.addEventListener("click", async () => {
  if (listener) { listener.stop(); listener = null; }
  els.status.textContent = "重新連接麥克風中…";
  await startGame();
});

// 試聽歡呼：單獨播放這段歡呼(不玩遊戲、不放彩帶、不碰麥克風)，用來隔離「斷掉」是檔案還是遊戲負載
els.testCheer.addEventListener("click", () => {
  const a = new Audio(cheerSrc || "./sounds/cheer.wav");
  a.play().catch(() => {});
});

(async () => {
  const params = new URLSearchParams(location.search);
  await initCharacters({ face: els.face, picker: els.charPicker });
  updateThreshMark(sensToThreshold(parseFloat(els.sens.value)));
  preloadCheer(); // 有 sounds/cheer.mp3 就優先用真人歡呼
  await prefetchTitles();
  const lv = parseInt(params.get("level"), 10);
  if (Number.isFinite(lv) && lv >= 1 && lv <= LEVELS.length) {
    await selectLevel(lv - 1); // ?level=2 → 直接進第2關
  } else {
    showMenu();                // 沒指定就先看目錄
  }
  // 需要除錯麥克風時，用 index.html?debug=1 打開診斷面板
  if (params.get("debug")) els.debug.hidden = false;
})();
