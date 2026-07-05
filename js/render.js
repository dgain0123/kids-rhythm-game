// render.js — 畫譜面音符 + 過關彩帶動畫

const STEM_DX = 12;   // 符桿相對符頭的水平位移
const STEM_LEN = 60;  // 符桿長度

// 黑色實心符頭
function drawHead(ctx, cx, cy) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(-0.35);
  ctx.fillStyle = "#111";
  ctx.beginPath();
  ctx.ellipse(0, 0, 13, 10, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}
// 符桿
function drawStem(ctx, cx, cy) {
  ctx.strokeStyle = "#111";
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(cx + STEM_DX, cy - 2);
  ctx.lineTo(cx + STEM_DX, cy - STEM_LEN);
  ctx.stroke();
}
// 單個八分音符的旗子(符尾)
function drawFlag(ctx, cx, cy) {
  const x = cx + STEM_DX, y = cy - STEM_LEN;
  ctx.fillStyle = "#111";
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.quadraticCurveTo(x + 18, y + 10, x + 12, y + 28);
  ctx.quadraticCurveTo(x + 15, y + 12, x, y + 14);
  ctx.closePath();
  ctx.fill();
}
// 符樑(把相連的八分音符連起來)
function drawBeam(ctx, x1, x2, yTop) {
  ctx.fillStyle = "#111";
  ctx.fillRect(x1, yTop, x2 - x1, 7);
}

// 在 canvas 上畫五線譜 + 一排音符(quarter=四分、eighth=八分；相連八分自動加符樑)
export function drawNotes(canvas, notes) {
  const list = Array.isArray(notes) ? notes : [notes];
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  // 五線譜五條線
  const lineGap = 18;
  const top = H / 2 - lineGap * 2;
  ctx.strokeStyle = "#5b6b8c";
  ctx.lineWidth = 2;
  for (let i = 0; i < 5; i++) {
    const y = top + i * lineGap;
    ctx.beginPath();
    ctx.moveTo(W * 0.10, y);
    ctx.lineTo(W * 0.90, y);
    ctx.stroke();
  }

  // 小鼓在鼓譜的位置＝五線譜「第三間」(由下往上數)＝top + 1.5 個間距
  const cy = top + lineGap * 1.5;
  const n = list.length;
  const x0 = W * 0.26, x1 = W * 0.74;
  const xs = [];
  for (let i = 0; i < n; i++) xs.push(n === 1 ? W / 2 : x0 + (x1 - x0) * (i / (n - 1)));

  // 先畫所有符頭 + 符桿
  for (let i = 0; i < n; i++) { drawHead(ctx, xs[i], cy); drawStem(ctx, xs[i], cy); }

  // 八分音符：相連的用符樑連起來，落單的畫旗子
  const yTop = cy - STEM_LEN;
  let i = 0;
  while (i < n) {
    if (list[i].type === "eighth") {
      let j = i;
      while (j + 1 < n && list[j + 1].type === "eighth") j++;
      if (j > i) drawBeam(ctx, xs[i] + STEM_DX, xs[j] + STEM_DX, yTop);
      else drawFlag(ctx, xs[i], cy);
      i = j + 1;
    } else i++;
  }
}

// 彩帶動畫（過關用）
export function confetti(canvas, durationMs = 5000) {
  const ctx = canvas.getContext("2d");
  const W = canvas.width = window.innerWidth;
  const H = canvas.height = window.innerHeight;
  const colors = ["#ff5a8a", "#ffd23f", "#3ddc97", "#5b9bff", "#c77dff", "#ff8a3d", "#2ee6c9"];
  const emojis = ["🎉", "🎊", "⭐", "🌟", "🎈", "🥳", "💛", "✨", "🎁"];
  const G = 0.16;
  const MAX = 420;                // 上限，避免太多卡頓拖累音訊
  const emitMs = 2000;            // 這段時間內持續噴發，畫面才會一直滿
  let pieces = [];

  // 把每個 emoji 預先畫到離屏 canvas 當 sprite，之後每幀用 drawImage(便宜很多，不再逐幀 fillText)
  const SS = 72;
  const spriteCache = {};
  function sprite(e) {
    if (spriteCache[e]) return spriteCache[e];
    const c = document.createElement("canvas");
    c.width = c.height = SS;
    const cx = c.getContext("2d");
    cx.font = (SS - 12) + "px serif";
    cx.textAlign = "center"; cx.textBaseline = "middle";
    cx.fillText(e, SS / 2, SS / 2);
    spriteCache[e] = c;
    return c;
  }
  emojis.forEach(sprite); // 開場前先全部畫好，避免播放中才建立

  const rect = (x, y, vx, vy, g) => ({
    kind: "rect", x, y, vx, vy, g,
    r: 5 + Math.random() * 9, c: colors[(Math.random() * colors.length) | 0],
    rot: Math.random() * Math.PI, vr: -0.3 + Math.random() * 0.6
  });
  const emoji = (x, y, vx, vy, g) => ({
    kind: "emoji", x, y, vx, vy, g,
    r: 18 + Math.random() * 26, e: emojis[(Math.random() * emojis.length) | 0],
    rot: Math.random() * Math.PI, vr: -0.3 + Math.random() * 0.6
  });

  // 一發「拉炮」：從某點往某方向錐狀噴出
  function popper(x, y, angle, spread, count, power) {
    for (let i = 0; i < count; i++) {
      const a = angle + (Math.random() - 0.5) * spread;
      const sp = power * (0.5 + Math.random());
      const vx = Math.cos(a) * sp, vy = Math.sin(a) * sp;
      pieces.push(Math.random() < 0.22 ? emoji(x, y, vx, vy, G) : rect(x, y, vx, vy, G));
    }
  }

  // 開場四發：左下、右下往上噴，中央爆開
  popper(0, H, -Math.PI * 0.28, 0.5, 65, 20);         // 左下 → 右上
  popper(W, H, -Math.PI * 0.72, 0.5, 65, 20);         // 右下 → 左上
  popper(W / 2, H * 0.42, -Math.PI / 2, Math.PI * 2, 70, 13); // 中央全向爆
  popper(W / 2, H * 0.42, -Math.PI / 2, Math.PI * 2, 60, 7);

  const start = performance.now();
  function frame(t) {
    const life = t - start;

    // 持續補充：上方灑落 + 兩側再噴，讓整個螢幕維持滿滿
    if (life < emitMs && pieces.length < MAX) {
      for (let i = 0; i < 4; i++)
        pieces.push(rect(Math.random() * W, -20, -1 + Math.random() * 2, 2 + Math.random() * 3, 0.05));
      if (Math.floor(life / 320) !== Math.floor((life - 16) / 320)) {
        popper(0, H, -Math.PI * 0.28, 0.5, 12, 20);
        popper(W, H, -Math.PI * 0.72, 0.5, 12, 20);
      }
    }

    ctx.clearRect(0, 0, W, H);
    const fade = life > durationMs - 700 ? Math.max(0, (durationMs - life) / 700) : 1;
    ctx.globalAlpha = fade;
    for (const p of pieces) {
      p.vy += p.g; p.x += p.vx; p.y += p.vy; p.rot += p.vr;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      if (p.kind === "emoji") {
        const d = p.r * 2;
        ctx.drawImage(sprite(p.e), -d / 2, -d / 2, d, d); // 用 sprite 貼圖，取代昂貴的 fillText
      } else {
        ctx.fillStyle = p.c;
        ctx.fillRect(-p.r / 2, -p.r / 2, p.r, p.r * 1.6);
      }
      ctx.restore();
    }
    ctx.globalAlpha = 1;
    // 清掉掉出畫面的，控制數量
    if (pieces.length > MAX * 0.8) pieces = pieces.filter(p => p.y < H + 40);

    if (life < durationMs) requestAnimationFrame(frame);
    else ctx.clearRect(0, 0, W, H);
  }
  requestAnimationFrame(frame);
}
