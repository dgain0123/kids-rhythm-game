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
  ctx.fillStyle = "#ff5a8a";
  ctx.beginPath();
  ctx.ellipse(0, 0, 13, 10, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
  // 符桿
  ctx.strokeStyle = "#ff5a8a";
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(cx + 12, cy - 2);
  ctx.lineTo(cx + 12, cy - 60);
  ctx.stroke();
}

// 彩帶動畫（過關用）
export function confetti(canvas, durationMs = 2500) {
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const colors = ["#ff5a8a", "#ffd23f", "#3ddc97", "#5b9bff", "#c77dff"];
  const pieces = Array.from({ length: 140 }, () => ({
    x: Math.random() * W,
    y: -20 - Math.random() * H,
    r: 4 + Math.random() * 7,
    c: colors[(Math.random() * colors.length) | 0],
    vy: 2 + Math.random() * 4,
    vx: -1.5 + Math.random() * 3,
    rot: Math.random() * Math.PI,
    vr: -0.2 + Math.random() * 0.4
  }));
  const start = performance.now();
  function frame(t) {
    ctx.clearRect(0, 0, W, H);
    for (const p of pieces) {
      p.x += p.vx; p.y += p.vy; p.rot += p.vr;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.fillStyle = p.c;
      ctx.fillRect(-p.r / 2, -p.r / 2, p.r, p.r * 1.6);
      ctx.restore();
    }
    if (t - start < durationMs) requestAnimationFrame(frame);
    else ctx.clearRect(0, 0, W, H);
  }
  requestAnimationFrame(frame);
}
