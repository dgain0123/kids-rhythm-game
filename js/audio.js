// audio.js — 麥克風輸入 + 打鼓聲偵測（onset detection）
// 原理：持續量測麥克風音量(RMS)，當音量從安靜「突然」衝高過門檻時，
//       視為打了一下鼓。用不反應期(refractory)避免一下被算成很多下。

export class DrumListener {
  constructor({ onHit, onLevel } = {}) {
    this.onHit = onHit || (() => {});        // 偵測到一下鼓時呼叫
    this.onLevel = onLevel || (() => {});    // 每一幀回報目前音量(0~1)，給音量條用
    this.audioCtx = null;
    this.analyser = null;
    this.data = null;
    this.running = false;

    // 可調參數
    this.threshold = 0.12;      // 使用者設的「絕對最低門檻」，越小越靈敏
    this.refractoryMs = 400;    // 打一下後多久內不再偵測(蓋掉餘音/回音，避免一下算成多下)
    this.riseFactor = 3.0;      // 要比背景底噪大這麼多倍才算一下
    this.margin = 0.03;         // 額外緩衝，避免貼著底噪誤觸
    this._ambient = 0.02;       // 自動追蹤的背景底噪
    this._lastHitTime = 0;
    this._armed = true;         // true=目前安靜、可以再次觸發
  }

  async start() {
    if (this.running) return;
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false
      }
    });
    this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = this.audioCtx.createMediaStreamSource(stream);
    this.analyser = this.audioCtx.createAnalyser();
    this.analyser.fftSize = 1024;
    source.connect(this.analyser);
    this.data = new Float32Array(this.analyser.fftSize);
    this.stream = stream;
    this.running = true;
    if (this.audioCtx.state === "suspended") await this.audioCtx.resume();
    this._loop();
  }

  setThreshold(v) { this.threshold = v; }

  _loop = () => {
    if (!this.running) return;
    this.analyser.getFloatTimeDomainData(this.data);

    // 用「峰值」偵測打鼓的爆音(比 RMS 更抓得到瞬間的敲擊)
    let peak = 0;
    for (let i = 0; i < this.data.length; i++) {
      const a = Math.abs(this.data[i]);
      if (a > peak) peak = a;
    }
    this.onLevel(Math.min(1, peak)); // 直接用峰值給音量條(和門檻同一把尺)

    const now = performance.now();
    // 有效門檻 = max(使用者設的絕對門檻, 背景底噪×倍率+緩衝)
    // → 房間吵時門檻自動抬高，安靜時維持使用者設定，兩邊都穩
    const trigger = Math.max(this.threshold, this._ambient * this.riseFactor + this.margin);

    // 相對安靜時，緩慢跟隨背景底噪(打擊當下不更新，避免把打擊算進底噪)
    if (peak < trigger * 0.8) this._ambient = this._ambient * 0.99 + peak * 0.01;

    // 打擊：明顯高過門檻、距上次夠久、且已武裝
    if (this._armed && peak > trigger && now - this._lastHitTime > this.refractoryMs) {
      this._armed = false;
      this._lastHitTime = now;
      this.onHit(peak);
    }
    // 要等音量真的掉回接近底噪，才重新武裝(遲滯，避免餘音抖動重複觸發)
    if (!this._armed && peak < Math.max(this.threshold * 0.5, this._ambient * 1.6)) {
      this._armed = true;
    }

    requestAnimationFrame(this._loop);
  };

  stop() {
    this.running = false;
    if (this.stream) this.stream.getTracks().forEach(t => t.stop());
    if (this.audioCtx) this.audioCtx.close();
    this.audioCtx = null;
    this.analyser = null;
    this.stream = null;
  }
}
