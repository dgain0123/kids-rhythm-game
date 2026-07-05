// render.js — 畫譜面音符 + 過關彩帶動畫

// 在 canvas 上畫一個簡單的五線譜片段 + 一個四分音符
export function drawNote(canvas, note) {
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
    ctx.moveTo(W * 0.15, y);
    ctx.lineTo(W * 0.85, y);
    ctx.stroke();
  }

  // 四分音符（實心符頭 + 符桿）
  // 小鼓在鼓譜的位置＝五線譜「第三間」(由下往上數)＝top + 1.5 個間距
  const cx = W / 2;
  const cy = top + lineGap * 1.5;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(-0.35);
  ctx.fillStyle = "#111";
  ctx.beginPath();
  ctx.ellipse(0, 0, 13, 10, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
  // 符桿
  ctx.strokeStyle = "#111";
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(cx + 12, cy - 2);
  ctx.lineTo(cx + 12, cy - 60);
  ctx.stroke();
}

// 彩帶動畫（過關用）
export function confetti(canvas, durationMs = 5000) {
  const ctx = canvas.getContext("2d");
  const W = canvas.width = window.innerWidth;
  const H = canvas.height = window.innerHeight;
  const colors = ["#ff5a8a", "#ffd23f", "#3ddc97", "#5b9bff", "#c77dff", "#ff8a3d", "#2ee6c9"];
  const emojis = ["🎉", "🎊", "⭐", "🌟", "🎈", "🥳", "💛", "✨", "🎁"];
  const G = 0.16;
  const MAX = 900;                // 上限，避免太多卡頓
  const emitMs = 2200;            // 這段時間內持續噴發，畫面才會一直滿
  let pieces = [];

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
      pieces.push(Math.random() < 0.45 ? emoji(x, y, vx, vy, G) : rect(x, y, vx, vy, G));
    }
  }

  // 開場四發：左下、右下往上噴，中央爆開
  popper(0, H, -Math.PI * 0.28, 0.5, 120, 20);        // 左下 → 右上
  popper(W, H, -Math.PI * 0.72, 0.5, 120, 20);        // 右下 → 左上
  popper(W / 2, H * 0.42, -Math.PI / 2, Math.PI * 2, 120, 13); // 中央全向爆
  popper(W / 2, H * 0.42, -Math.PI / 2, Math.PI * 2, 120, 7);

  const start = performance.now();
  function frame(t) {
    const life = t - start;

    // 持續補充：上方灑落 + 兩側再噴，讓整個螢幕維持滿滿
    if (life < emitMs && pieces.length < MAX) {
      for (let i = 0; i < 8; i++)
        pieces.push(rect(Math.random() * W, -20, -1 + Math.random() * 2, 2 + Math.random() * 3, 0.05));
      if (Math.floor(life / 260) !== Math.floor((life - 16) / 260)) {
        popper(0, H, -Math.PI * 0.28, 0.5, 25, 20);
        popper(W, H, -Math.PI * 0.72, 0.5, 25, 20);
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
        ctx.font = p.r * 2 + "px serif";
        ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(p.e, 0, 0);
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
