// main.js — 串接：載入譜 → 麥克風 → 遊戲邏輯 → 畫面
import { DrumListener } from "./audio.js";
import { Game } from "./game.js";
import { drawNote, confetti } from "./render.js";

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
};

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
  const res = await fetch("./charts/level1.json");
  return res.json();
}

function setFace(emoji) { els.face.textContent = emoji; }

function onState(state, info) {
  els.stage.className = "stage " + state;
  switch (state) {
    case "ready":
      setFace("🥁");
      els.status.textContent = "準備好了！打一下鼓～";
      break;
    case "hitOnce":
      setFace("👀");
      els.status.textContent = "很好！不要再打囉…";
      break;
    case "pass":
      setFace("🎉");
      els.status.textContent = "過關！你好棒！";
      confetti(els.fxCanvas);
      celebrateSound();
      stopListening();
      els.retry.hidden = false;
      break;
    case "fail":
      setFace("😢");
      els.status.textContent = "哎呀～打太多下了！再試一次";
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

async function startGame() {
  els.start.disabled = true;
  els.start.textContent = "開麥克風中…";
  try {
    listener = new DrumListener({
      onHit: () => { flashHit(); if (game) game.registerHit(); },
      onLevel: (lv) => { els.meterFill.style.width = Math.round(lv * 100) + "%"; }
    });
    const th = sensToThreshold(parseFloat(els.sens.value));
    listener.setThreshold(th);
    updateThreshMark(th);
    await listener.start();
  } catch (e) {
    els.status.textContent = "拿不到麥克風權限 😵 請允許麥克風、並用 localhost 開啟";
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
  updateThreshMark(sensToThreshold(parseFloat(els.sens.value)));
})();
