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
export function confetti(canvas, durationMs = 3800) {
  const ctx = canvas.getContext("2d");
  // 讓畫布跟整個視窗一樣大(高解析、鋪滿全螢幕)
  const W = canvas.width = window.innerWidth;
  const H = canvas.height = window.innerHeight;
  const colors = ["#ff5a8a", "#ffd23f", "#3ddc97", "#5b9bff", "#c77dff", "#ff8a3d"];
  const emojis = ["🎉", "🎊", "⭐", "🌟", "🎈", "🥳", "💛"];
  const G = 0.14; // 重力

  const pieces = [];
  // 1) 從上方一直落下的紙屑
  for (let i = 0; i < 170; i++) {
    pieces.push({
      kind: "rect", x: Math.random() * W, y: -20 - Math.random() * H,
      r: 5 + Math.random() * 8, c: colors[(Math.random() * colors.length) | 0],
      vy: 2 + Math.random() * 4, vx: -1.5 + Math.random() * 3,
      rot: Math.random() * Math.PI, vr: -0.25 + Math.random() * 0.5, g: 0
    });
  }
  // 2) 從中央往外噴發的紙屑 + emoji
  const cx = W / 2, cy = H * 0.42;
  for (let i = 0; i < 90; i++) {
    const ang = Math.random() * Math.PI * 2;
    const sp = 6 + Math.random() * 12;
    const isEmoji = Math.random() < 0.4;
    pieces.push({
      kind: isEmoji ? "emoji" : "rect",
      x: cx, y: cy,
      r: isEmoji ? 20 + Math.random() * 16 : 5 + Math.random() * 8,
      c: colors[(Math.random() * colors.length) | 0],
      e: emojis[(Math.random() * emojis.length) | 0],
      vx: Math.cos(ang) * sp, vy: Math.sin(ang) * sp - 3,
      rot: Math.random() * Math.PI, vr: -0.3 + Math.random() * 0.6, g: G
    });
  }

  const start = performance.now();
  function frame(t) {
    ctx.clearRect(0, 0, W, H);
    const life = t - start;
    const fade = life > durationMs - 600 ? Math.max(0, (durationMs - life) / 600) : 1;
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
    if (life < durationMs) requestAnimationFrame(frame);
    else ctx.clearRect(0, 0, W, H);
  }
  requestAnimationFrame(frame);
}
