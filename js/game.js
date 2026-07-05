// game.js — 關卡邏輯：打一下過關、打兩下失敗
// 狀態流程：
//   ready   → 顯示音符，開始聽鼓聲
//   hitOnce → 已經打了第一下，開一個小視窗等看會不會有第二下
//   pass    → 過關（在小視窗內沒有第二下）
//   fail    → 失敗（打了第二下 / 超過 maxHits）

export class Game {
  constructor(chart, { onState } = {}) {
    this.chart = chart;
    this.maxHits = chart.maxHits ?? 1;
    this.onState = onState || (() => {});
    this.hits = 0;
    this.state = "ready";
    this.confirmMs = 1500; // 打完後等這麼久沒有多打，就算過關
    this._confirmTimer = null;
  }

  start() {
    this.hits = 0;
    this._setState("ready");
  }

  // 由 audio 偵測到一下鼓時呼叫
  registerHit() {
    if (this.state === "pass" || this.state === "fail") return;

    this.hits += 1;
    this._clearTimer();

    if (this.hits > this.maxHits) {
      // 打太多下 → 失敗
      this._setState("fail");
      return;
    }

    if (this.hits < this.maxHits) {
      // 還沒打夠 → 鼓勵繼續打，不開過關視窗、也不會失敗
      this._setState("progress");
      return;
    }

    // 剛好打到 maxHits 下：開視窗等看會不會再多打(多打就失敗，沒多打就過關)
    this._setState("hitOnce");
    this._confirmTimer = setTimeout(() => this._setState("pass"), this.confirmMs);
  }

  reset() {
    this._clearTimer();
    this.start();
  }

  _clearTimer() {
    if (this._confirmTimer) { clearTimeout(this._confirmTimer); this._confirmTimer = null; }
  }

  _setState(s) {
    this.state = s;
    this.onState(s, { hits: this.hits, maxHits: this.maxHits });
  }
}
