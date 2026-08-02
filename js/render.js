// render.js — 畫譜面音符 + 過關彩帶動畫

const STEM_DX = 12;   // 符桿相對符頭的水平位移
const STEM_LEN = 60;  // 符桿長度

// 音符時值(拍)：跟轉檔器 tools/mid2json.py 的 NOTE_VALUES 對齊。
// triplet＝一拍三連音的一顆(1/3 拍)，三顆一組剛好一拍(連樑並標「3」)
const DUR = { whole: 4, half: 2, quarter: 1, eighth: 0.5, triplet: 1 / 3, sixteenth: 0.25 };
const durOf = (t) => DUR[t] ?? 1;

// 實心符頭(color: 一般黑、打到綠、當前拍點橘；s=縮放，音符多時整體縮小)
function drawHead(ctx, cx, cy, color = "#111", s = 1) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(-0.35);
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.ellipse(0, 0, 13 * s, 10 * s, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}
// 符桿
function drawStem(ctx, cx, cy, color = "#111", s = 1) {
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(2.5, 4 * s);
  ctx.beginPath();
  ctx.moveTo(cx + STEM_DX * s, cy - 2);
  ctx.lineTo(cx + STEM_DX * s, cy - STEM_LEN * s);
  ctx.stroke();
}
// 單個八分音符的旗子(符尾)
function drawFlag(ctx, cx, cy, s = 1) {
  const x = cx + STEM_DX * s, y = cy - STEM_LEN * s;
  ctx.fillStyle = "#111";
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.quadraticCurveTo(x + 18 * s, y + 10 * s, x + 12 * s, y + 28 * s);
  ctx.quadraticCurveTo(x + 15 * s, y + 12 * s, x, y + 14 * s);
  ctx.closePath();
  ctx.fill();
}
// 符樑(把相連的八分音符連起來)
function drawBeam(ctx, x1, x2, yTop, s = 1) {
  ctx.fillStyle = "#111";
  ctx.fillRect(x1, yTop, x2 - x1, Math.max(4, 7 * s));
}
// 三連音記號：符樑正上方的斜體「3」(告訴大家這三顆＝一拍)
function drawTupletNum(ctx, cx, yTop, s = 1) {
  ctx.save();
  ctx.fillStyle = "#111";
  ctx.font = `italic bold ${Math.round(17 * s)}px Georgia, serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "bottom";
  ctx.fillText("3", cx, yTop - 4 * s);
  ctx.restore();
}

// 螢幕能用的寬度(扣掉舞台內距)——手機窄、桌機寬
function availWidth() {
  const vw = (typeof window !== "undefined" && window.innerWidth) ? window.innerWidth : 1280;
  return Math.max(300, vw - 44);
}

// 依螢幕寬決定譜面可視窗有幾小節(上限4)：桌機=4小節、手機=1~2小節。
// 回傳可視窗的「位置單位」長度(拍+小節空隙)
function visibleUnits() {
  const avail = availWidth();
  for (let k = 4; k >= 1; k--) {
    const units = k * 4 + (k - 1) * 0.9;
    if (units * 64 + 80 <= avail || k === 1) return units;
  }
  return 4;
}

// 這份譜是否超出可視窗(超過的話遊戲迴圈要每幀重畫，讓譜面跟著進度往左捲)
export function needsScroll(notes) {
  const list = Array.isArray(notes) ? notes : [notes];
  let acc = 0;
  for (const nn of list) acc += durOf(nn.type);
  const lastStart = acc - durOf(list[list.length - 1].type);
  const barOf = (b) => Math.floor(b / 4 + 1e-6);
  return lastStart + barOf(lastStart) * 0.9 > visibleUnits() + 1e-6;
}

// 在 canvas 上畫五線譜 + 一排音符(quarter=四分、eighth=八分；相連八分自動加符樑)
// state(選填)：{ hit: [true,false,...], active: 索引 }
//   hit=true 的音符畫綠色(已打到)；active 的音符畫橘色+光圈(現在該打這個)
export function drawNotes(canvas, notes, state = {}) {
  const list = Array.isArray(notes) ? notes : [notes];
  const hit = state.hit || [];
  const active = state.active ?? -1;
  const colorOf = (i) => (hit[i] ? "#1fa96b" : i === active ? "#ff8a3d" : "#111");
  const n = list.length;

  // 依「拍」定位：四分=1拍、八分=半拍、三連音=1/3拍 → 每拍等寬
  const starts = []; let acc = 0;
  for (let i = 0; i < n; i++) { starts.push(acc); acc += durOf(list[i].type); }
  // 超過一小節(4/4)就畫小節線隔開：跨小節處左右多留空間
  const BPB = 4, BAR_GAP = 0.9;
  const barOf = (b) => Math.floor(b / BPB + 1e-6);
  const posOf = (b) => b + barOf(b) * BAR_GAP;
  const pos = starts.map(posOf);
  const total = Math.max(0.0001, pos[n - 1]);

  // 可視窗依螢幕寬自動決定(桌機4小節、手機1~2小節)；超出的譜像太鼓軌道一樣
  // 捲動(state.curBeat=目前拍)：左邊有一條固定「基準粗線」(貫穿整個五線譜，
  // 任何音高都碰得到)，目前該打的音符釘在線上、整片譜一路往左滑到最後一下。
  const visible = visibleUnits();
  const scrolling = total > visible + 1e-6;
  const anchor = visible * 0.16; // 基準線位置(對齊下方太鼓判定圈)
  // 游標的「平滑位置」：音符定位用的小節空隙是階梯狀(跨小節瞬間+0.9)，
  // 游標若直接用它會在換小節時跳一下 → 改在小節最後半拍內漸進滑過空隙
  const posSmooth = (b) => {
    const barF = Math.floor(b / BPB);
    const rem = b - barF * BPB;
    const ramp = Math.max(0, rem - (BPB - 0.5)) / 0.5; // 小節最後半拍 0→1
    return b + (barF + ramp) * BAR_GAP;
  };
  let offset = 0;
  if (scrolling) {
    offset = posSmooth(Math.max(0, state.curBeat ?? 0)) - anchor; // 一路滑到最後一下停在線上
  }
  const denom = Math.min(total, visible);

  // 音符大小固定(跟第9關一樣大)。放不下就：桌機加寬畫布(上限=可視窗寬)、
  // 手機縮小左右邊界；再塞不下由 CSS maxWidth 均勻微縮(不會被截掉)
  const BASE_W = 560, PPB = 64;      // PPB=每拍畫幾px(第9關的密度)
  const MIN_NOTE_PX = 32;            // 相鄰音符至少隔這麼多px(符頭寬約25px，不能疊在一起)
  // 音符很密的譜(三連音=1/3拍、十六分=1/4拍)每拍要畫寬一點，符頭才不會擠成一團。
  // 八分(0.5拍)以上算出來剛好＝PPB，舊關卡的版面完全不變。
  let minGap = Infinity;
  for (let i = 1; i < n; i++) minGap = Math.min(minGap, starts[i] - starts[i - 1]);
  const ppb = minGap > 0 && isFinite(minGap) ? Math.max(PPB, MIN_NOTE_PX / minGap) : PPB;
  let margin = 75;
  let needW = Math.round(denom * ppb + margin * 2);
  if (needW > availWidth()) { margin = 40; needW = Math.round(denom * ppb + margin * 2); }
  // 短譜維持置中舊版面(1~9關不變)；但舊版面的密度(置中 22%~78%)不夠寬時要改用加寬版面
  const legacyPPB = (BASE_W * 0.56) / denom;
  const legacy = !scrolling && needW < BASE_W && legacyPPB >= ppb - 0.5;
  const W = legacy ? BASE_W : needW;
  if (canvas.width !== W) canvas.width = W;
  if (!legacy) {
    canvas.style.width = W + "px";
    canvas.style.maxWidth = "100%"; // 極窄螢幕最後保險:均勻縮小而不是被截掉
  } else {
    canvas.style.width = "";
    canvas.style.maxWidth = "";
  }
  const H = canvas.height;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, W, H);

  // 五線譜五條線（有三連音的譜整個下移一點，把符樑上方的「3」空間讓出來）
  const lineGap = 18;
  const hasTuplet = list.some((nn) => nn.type === "triplet");
  const top = H / 2 - lineGap * 2 + (hasTuplet ? 14 : 0);
  ctx.strokeStyle = "#5b6b8c";
  ctx.lineWidth = 2;
  const edge = legacy ? W * 0.10 : margin * 0.4;
  for (let i = 0; i < 5; i++) {
    const y = top + i * lineGap;
    ctx.beginPath();
    ctx.moveTo(edge, y);
    ctx.lineTo(W - edge, y);
    ctx.stroke();
  }

  // 小鼓在鼓譜的位置＝五線譜「第三間」(由下往上數)＝top + 1.5 個間距
  const cy = top + lineGap * 1.5;
  const xa = legacy ? W * 0.22 : margin;
  const xb = legacy ? W * 0.78 : W - margin;
  // 基準線的像素位置存到 dataset，讓下方太鼓判定圈對齊(一上一下)
  canvas.dataset.anchorX = String(scrolling ? xa + (xb - xa) * (anchor / denom) : W * 0.16);
  const xs = pos.map((p) => (n === 1 ? W / 2 : xa + (xb - xa) * ((p - offset) / denom)));

  // 捲動譜的固定基準線(跟太鼓判定圈同角色)：一條貫穿五線譜的粗線，
  // 任何音高位置的音符滑到線上＝現在該打
  if (scrolling) {
    const ax = xa + (xb - xa) * (anchor / denom);
    ctx.fillStyle = "rgba(255,90,138,0.45)";
    ctx.fillRect(ax - 6, top - 18, 12, lineGap * 4 + 36);
  }

  // 小節線(畫在跨小節的空隙正中間，貫穿五條線；捲動時跟著位移)
  ctx.strokeStyle = "#5b6b8c";
  ctx.lineWidth = 3;
  for (let b = 1; b <= barOf(starts[n - 1]); b++) {
    const lx = xa + (xb - xa) * ((b * BPB + (b - 1) * BAR_GAP + BAR_GAP / 2 - offset) / denom);
    if (lx < -10 || lx > W + 10) continue;
    ctx.beginPath();
    ctx.moveTo(lx, top);
    ctx.lineTo(lx, top + lineGap * 4);
    ctx.stroke();
  }

  // 先畫所有符頭 + 符桿(當前拍點加一圈光暈)
  for (let i = 0; i < n; i++) {
    if (i === active && !hit[i]) {
      ctx.fillStyle = "rgba(255,138,61,0.25)";
      ctx.beginPath();
      ctx.arc(xs[i], cy, 24, 0, Math.PI * 2);
      ctx.fill();
    }
    drawHead(ctx, xs[i], cy, colorOf(i));
    drawStem(ctx, xs[i], cy, colorOf(i));
  }

  // 八分音符：每「兩個一組」(一拍)打符樑，組跟組分開；落單的畫旗子(不跨小節連樑)
  // 三連音：每「三個一組」(一拍)打符樑，符樑上方標「3」
  const yTop = cy - STEM_LEN;
  let i = 0;
  while (i < n) {
    if (list[i].type === "eighth") {
      if (i + 1 < n && list[i + 1].type === "eighth"
          && barOf(starts[i]) === barOf(starts[i + 1])) {
        drawBeam(ctx, xs[i] + STEM_DX, xs[i + 1] + STEM_DX, yTop); // 兩個一組
        i += 2;
      } else { drawFlag(ctx, xs[i], cy); i += 1; }
    } else if (list[i].type === "triplet") {
      let k = 1; // 同一小節內最多連三顆＝一拍
      while (k < 3 && i + k < n && list[i + k].type === "triplet"
             && barOf(starts[i]) === barOf(starts[i + k])) k++;
      if (k >= 2) drawBeam(ctx, xs[i] + STEM_DX, xs[i + k - 1] + STEM_DX, yTop);
      else drawFlag(ctx, xs[i], cy);
      drawTupletNum(ctx, (xs[i] + xs[i + k - 1]) / 2 + STEM_DX, yTop);
      i += k;
    } else i++;
  }
}

// ── 太鼓達人式軌道（跟拍關卡用）──
// 角色圖示從右往左跑，跑進左邊的判定圈時打鼓。
// 參數：t=譜面時間(秒)、noteTimes=各音符時間、hit=各音符是否已打到、
//       tolSec=容許誤差(秒)、fx=[{time}]最近打中的時間(爆星特效)、
//       sprite={image, emoji}=跑動圖示(優先用角色圖，沒有就 emoji)
export function drawLane(canvas, { t, noteTimes, hit = [], tolSec = 0, fx = [], sprite = {}, anchorX = 0 }) {
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  const cy = H * 0.56;
  // 判定圈位置：由譜面算好傳進來(anchorX) → 跟上面的紅色基準線垂直對齊
  const hitX = anchorX || W * 0.16;
  const R = 36;

  // 軌道底
  ctx.fillStyle = "#eef1fa";
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(4, cy - 34, W - 8, 68, 34);
  else ctx.rect(4, cy - 34, W - 8, 68);
  ctx.fill();

  // 音符間隔(用前兩個音符的距離；只有一個就當 1 秒)
  const ioi = noteTimes.length > 1 ? noteTimes[1] - noteTimes[0] : 1;
  // 捲動速度：一個間隔 = 0.45 個畫面寬
  const pps = (W * 0.45) / ioi;

  // 判定圈：跟著拍子脈動
  const phase = (((t % ioi) + ioi) % ioi) / ioi;
  const pulse = 1 + 0.10 * Math.max(0, 1 - phase * 3);
  ctx.lineWidth = 6;
  ctx.strokeStyle = "#ff5a8a";
  ctx.beginPath();
  ctx.arc(hitX, cy, R * pulse, 0, Math.PI * 2);
  ctx.stroke();
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = "rgba(255,90,138,.45)";
  ctx.beginPath();
  ctx.arc(hitX, cy, (R - 9) * pulse, 0, Math.PI * 2);
  ctx.stroke();

  // 跑動的角色圖示(還沒打到的音符)
  const img = sprite.image;
  const imgOk = img && img.complete && img.naturalWidth > 0;
  for (let i = 0; i < noteTimes.length; i++) {
    if (hit[i]) continue; // 打到的由 fx 爆星處理，圖示消失
    const x = hitX + (noteTimes[i] - t) * pps;
    if (x < -70 || x > W + 70) continue;
    const missed = t > noteTimes[i] + tolSec; // 錯過：變淡繼續往左飄走
    ctx.save();
    ctx.globalAlpha = missed ? 0.35 : 1;
    // 蹦蹦跳的跑步感
    const hop = Math.abs(Math.sin((noteTimes[i] - t) * Math.PI / (ioi / 2))) * 8;
    const y = cy - hop;
    if (imgOk) {
      const S = 62;
      ctx.drawImage(img, x - S / 2, y - S / 2 - 4, S, S);
    } else {
      ctx.font = "48px serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(sprite.emoji || "🥁", x, y - 2);
    }
    ctx.restore();
  }

  // 打中特效：判定圈爆開的圈圈 + 星星往上飄(0.5 秒)
  for (const f of fx) {
    const age = t - f.time;
    if (age < 0 || age > 0.5) continue;
    const k = age / 0.5;
    ctx.save();
    ctx.globalAlpha = 1 - k;
    ctx.lineWidth = 5;
    ctx.strokeStyle = "#ffd23f";
    ctx.beginPath();
    ctx.arc(hitX, cy, R + k * 70, 0, Math.PI * 2);
    ctx.stroke();
    ctx.font = "34px serif";
    ctx.textAlign = "center";
    ctx.fillText("⭐", hitX - 20, cy - 30 - k * 40);
    ctx.fillText("✨", hitX + 24, cy - 20 - k * 55);
    ctx.restore();
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
