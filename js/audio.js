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
    this.threshold = 0.12;      // 觸發門檻(音量)，越小越靈敏
    this.refractoryMs = 200;    // 打一下後多久內不再偵測，避免重複計數
    this._lastHitTime = 0;
    this._armed = true;         // true=目前在安靜狀態、可以再次觸發
    this._releaseRatio = 0.5;   // 音量掉回門檻的一半才重新武裝
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
    // 上升邊緣偵測：峰值衝過門檻，且距上次夠久，且目前是「已武裝」狀態
    if (this._armed && peak > this.threshold && now - this._lastHitTime > this.refractoryMs) {
      this._armed = false;
      this._lastHitTime = now;
      this.onHit(peak);
    }
    // 峰值掉回門檻的一半以下 → 重新武裝，等待下一下
    if (!this._armed && peak < this.threshold * this._releaseRatio) {
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
