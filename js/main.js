// main.js — 串接：載入譜 → 麥克風 → 遊戲邏輯 → 畫面
import { DrumListener } from "./audio.js";
import { Game } from "./game.js";
import { drawNote, confetti } from "./render.js";
import { initCharacters, showCharacter } from "./characters.js";

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

async function loadChart() {
  // 加時間戳避開瀏覽器快取，改譜後重整就能立刻看到
  const res = await fetch("./charts/level1.json?t=" + Date.now(), { cache: "no-store" });
  return res.json();
}

function onState(state, info) {
  // stage 的 class 帶動角色的動畫(過關蹦跳、失敗搖頭等)，角色圖本身不變
  els.stage.className = "stage " + state;
  switch (state) {
    case "ready":
      showCharacter(); // 還原成目前選的角色(皮卡丘)
      els.status.textContent = "準備好了！打1下鼓～";
      break;
    case "hitOnce":
      els.status.textContent = "很好！不要再打囉…";
      break;
    case "pass":
      els.face.innerHTML = '<span class="char-emoji">🎉</span>'; // 過關把角色換成拉炮
      els.status.textContent = "過關！你好棒！";
      confetti(els.fxCanvas);
      celebrateSound();
      stopListening();
      els.retry.hidden = false;
      break;
    case "fail":
      els.status.textContent = "哎呀～打太多下了！再試1次";
      stopListening();
      els.retry.hidden = false;
      break;
  }
}

// 簡單的過關音效（不需外部檔案）
function celebrateSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const notes = [523, 659, 784, 1047];
    notes.forEach((f, i) => {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = f; o.type = "triangle";
      o.connect(g); g.connect(ctx.destination);
      const t = ctx.currentTime + i * 0.12;
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.3, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.25);
      o.start(t); o.stop(t + 0.3);
    });
  } catch (e) { /* 忽略 */ }
}

function stopListening() {
  if (listener) { listener.stop(); listener = null; }
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
    listener = new DrumListener({
      onHit: () => { flashHit(); if (game) game.registerHit(); },
      onLevel: (lv) => {
        els.meterFill.style.width = Math.round(lv * 100) + "%";
        if (lv > _peakMax) _peakMax = lv;
        // 即時把數值秀在診斷面板
        els.debug.textContent =
          `目前音量: ${lv.toFixed(3)}   出現過最大: ${_peakMax.toFixed(3)}\n` +
          `音訊狀態: ${listener.audioCtx ? listener.audioCtx.state : "?"}   ` +
          `取樣率: ${listener.audioCtx ? listener.audioCtx.sampleRate : "?"}\n` +
          `麥克風: ${micInfo(listener)}`;
      }
    });
    const th = sensToThreshold(parseFloat(els.sens.value));
    listener.setThreshold(th);
    updateThreshMark(th);
    _peakMax = 0;
    await listener.start();
    els.debug.textContent = "已取得麥克風，開始偵測…\n" + micInfo(listener);
  } catch (e) {
    els.status.textContent = "拿不到麥克風 😵";
    els.debug.textContent = "❌ 錯誤：" + (e && e.name) + " - " + (e && e.message);
    els.start.disabled = false;
    els.start.textContent = "開始遊戲";
    return;
  }

  els.start.hidden = true;
  els.retry.hidden = true;
  drawNote(els.noteCanvas, chart.notes[0]);
  els.hint.textContent = chart.hint || "";
  game = new Game(chart, { onState });
  game.start();
}

function retry() {
  els.retry.hidden = true;
  drawNote(els.noteCanvas, chart.notes[0]);
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

(async () => {
  chart = await loadChart();
  $("title").textContent = chart.title;
  drawNote(els.noteCanvas, chart.notes[0]);
  await initCharacters({ face: els.face, picker: $("charPicker") });
  updateThreshMark(sensToThreshold(parseFloat(els.sens.value)));
  // 需要除錯麥克風時，用 index.html?debug=1 打開診斷面板
  if (new URLSearchParams(location.search).get("debug")) els.debug.hidden = false;
})();
