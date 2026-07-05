// main.js — 串接：載入譜 → 麥克風 → 遊戲邏輯 → 畫面
import { DrumListener } from "./audio.js";
import { Game } from "./game.js";
import { drawNotes, confetti } from "./render.js";
import { initCharacters, showCharacter } from "./characters.js";

// 關卡清單(依順序)。新增關卡就在 charts/ 加 levelN.json 並加進這裡
const LEVELS = ["level1", "level2"];
let levelIdx = 0;

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
};

let _peakMax = 0; // 記錄出現過的最大峰值，判斷麥克風到底有沒有收到聲音

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

async function loadChart(level) {
  // 加時間戳避開瀏覽器快取，改譜後重整就能立刻看到
  const res = await fetch(`./charts/${level}.json?t=` + Date.now(), { cache: "no-store" });
  return res.json();
}

// 切到第 idx 關：載譜、更新標題/提示/譜面
async function goToLevel(idx) {
  levelIdx = Math.max(0, Math.min(LEVELS.length - 1, idx));
  chart = await loadChart(LEVELS[levelIdx]);
  $("title").textContent = chart.title;
  els.hint.textContent = chart.hint || "";
  drawNotes(els.noteCanvas, chart.notes);
}

function hasNextLevel() { return levelIdx < LEVELS.length - 1; }

function onState(state, info) {
  // stage 的 class 帶動角色的動畫(過關蹦跳、失敗搖頭等)，角色圖本身不變
  els.stage.className = "stage " + state;
  switch (state) {
    case "ready":
      showCharacter(); // 還原成目前選的角色
      els.winBanner.hidden = true;
      els.next.hidden = true;
      els.status.textContent = `準備好了！打${info.maxHits}下鼓～`;
      break;
    case "progress":
      els.status.textContent = `很好！再打 ${info.maxHits - info.hits} 下～`;
      break;
    case "hitOnce":
      els.status.textContent = "很好！不要再打囉…";
      break;
    case "pass":
      celebrateSound();   // 聲音先播，讓音訊管線先建立
      stopListening();
      els.face.innerHTML = '<span class="char-emoji">🎉</span>'; // 過關把角色換成拉炮
      els.winBanner.hidden = false;
      els.status.textContent = "過關！你好棒！";
      els.retry.hidden = false;
      els.next.hidden = !hasNextLevel(); // 有下一關才顯示「下一關」
      (hasNextLevel() ? els.next : els.retry).scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(() => confetti(els.fxCanvas), 120); // 彩帶延後，避開最重的第一幀壓到聲音
      break;
    case "fail":
      els.status.textContent = "哎呀～打太多下了！再試1次";
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

// 預先載入「真人歡呼」音檔(可有可無)。放 sounds/cheer.mp3 就會優先用真人聲。
// 用 HTMLAudioElement 播放：獨立媒體管線，比 Web Audio buffer 更不怕主執行緒卡頓
let cheerSrc = null;
const CHEER_SRCS = ["./sounds/cheer.wav", "./sounds/cheer.mp3"]; // WAV 優先(免解碼)
async function preloadCheer() {
  for (const src of CHEER_SRCS) {
    try {
      const r = await fetch(src, { method: "HEAD" });
      if (r.ok) {
        cheerSrc = src;
        new Audio(src).load(); // 先暖機讓瀏覽器快取，正式播放時另開全新 Audio
        return;
      }
    } catch (e) { /* 試下一個 */ }
  }
}

// 過關音效：優先播真人歡呼音檔；沒有的話用「人聲合成」的歡呼當後備
function celebrateSound() {
  try {
    const ctx = getCtx();
    const now = ctx.currentTime;

    // 有真人歡呼音檔 → 每次都開「全新 Audio」播放(跟試聽完全相同路徑，避開 currentTime=0 的 seek)
    if (cheerSrc) {
      const a = new Audio(cheerSrc);
      a.play().catch(() => {});
      return;
    }

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
  try {
    const th = sensToThreshold(parseFloat(els.sens.value));
    if (!listener) {
      // 第一次：開麥克風。之後整場重用同一個，不再每輪開開關關
      listener = new DrumListener({
        onHit: () => { flashHit(); if (game) game.registerHit(); },
        onLevel: (lv) => {
          els.meterFill.style.width = Math.round(lv * 100) + "%";
          if (lv > _peakMax) _peakMax = lv;
          els.debug.textContent =
            `目前音量: ${lv.toFixed(3)}   出現過最大: ${_peakMax.toFixed(3)}\n` +
            `音訊狀態: ${listener.audioCtx ? listener.audioCtx.state : "?"}   ` +
            `取樣率: ${listener.audioCtx ? listener.audioCtx.sampleRate : "?"}\n` +
            `麥克風: ${micInfo(listener)}`;
        }
      });
      listener.setThreshold(th);
      updateThreshMark(th);
      _peakMax = 0;
      await listener.start();
      els.debug.textContent = "已取得麥克風，開始偵測…\n" + micInfo(listener);
    } else {
      // 之後幾輪：直接恢復偵測(麥克風一直開著)
      listener.setThreshold(th);
      updateThreshMark(th);
      listener.resume();
    }
  } catch (e) {
    els.status.textContent = "拿不到麥克風 😵";
    els.debug.textContent = "❌ 錯誤：" + (e && e.name) + " - " + (e && e.message);
    els.start.disabled = false;
    els.start.textContent = "開始遊戲";
    return;
  }

  els.start.hidden = true;
  els.retry.hidden = true;
  els.next.hidden = true;
  drawNotes(els.noteCanvas, chart.notes);
  els.hint.textContent = chart.hint || "";
  game = new Game(chart, { onState });
  game.start();
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

// 試聽歡呼：單獨播放這段歡呼(不玩遊戲、不放彩帶、不碰麥克風)，用來隔離「斷掉」是檔案還是遊戲負載
els.testCheer.addEventListener("click", () => {
  const a = new Audio(cheerSrc || "./sounds/cheer.wav");
  a.play().catch(() => {});
});

(async () => {
  const params = new URLSearchParams(location.search);
  const lv = parseInt(params.get("level"), 10);
  await goToLevel(Number.isFinite(lv) ? lv - 1 : 0); // ?level=2 → 第2關
  await initCharacters({ face: els.face, picker: $("charPicker") });
  updateThreshMark(sensToThreshold(parseFloat(els.sens.value)));
  preloadCheer(); // 有 sounds/cheer.mp3 就優先用真人歡呼
  // 需要除錯麥克風時，用 index.html?debug=1 打開診斷面板
  if (params.get("debug")) els.debug.hidden = false;
})();
