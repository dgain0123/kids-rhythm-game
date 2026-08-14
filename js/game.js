// game.js — 關卡邏輯，有兩種模式：
//
// 【數下數模式】(舊，chart 沒有 bpm/beat 時)
//   ready   → 顯示音符，開始聽鼓聲
//   hitOnce → 已經打滿，開一個小視窗等看會不會多打
//   pass    → 過關（視窗內沒有多打）
//   fail    → 失敗（超過 maxHits）
//
// 【跟拍模式】(chart 有 bpm 且音符有 beat 時)
//   每個音符有自己的時間點(beat × 60/bpm 秒)；打的那一下依「音樂時間」
//   歸給最近的還沒打到的音符，誤差在 toleranceBeats(預設半拍)以內才算。
//   全部音符都打到 → 過關；最後一顆的容許窗關了還有沒打到的 → 立刻失敗(不等檔尾)。
//   打錯時間點的多餘打擊不懲罰(幼兒友善)，只是不算。

export class Game {
  constructor(chart, { onState, onNote } = {}) {
    this.chart = chart;
    this.maxHits = chart.maxHits ?? 1;
    this.onState = onState || (() => {});
    this.onNote = onNote || (() => {});
    this.hits = 0;
    this.state = "ready";
    this.confirmMs = 1500; // 數下數模式：打完後等這麼久沒有多打，就算過關

    // 跟拍模式：chart 有 bpm、音符有 beat 才啟用
    this.timed = !!(chart.bpm && Array.isArray(chart.notes)
      && chart.notes.length && chart.notes[0].beat != null);
    if (this.timed) {
      const spb = 60 / chart.bpm; // 一拍幾秒
      this.noteTimes = chart.notes.map((n) => n.beat * spb);
      this.tolSec = (chart.toleranceBeats ?? 0.5) * spb;
      this.hitNotes = chart.notes.map(() => false);
    }
    this._confirmTimer = null;
  }

  start() {
    this.hits = 0;
    if (this.timed) this.hitNotes = this.chart.notes.map(() => false);
    this._setState("ready");
  }

  // 由 audio 偵測到一下鼓時呼叫。
  // 跟拍模式要帶 chartTime(音樂時間-預備拍，秒)；數下數模式不用參數。
  registerHit(chartTime) {
    if (this.state === "pass" || this.state === "fail") return;
    if (this.timed) { this._registerTimedHit(chartTime); return; }

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

  // 跟拍模式：把這一下歸給「最近的還沒打到的音符」，在容許誤差內才算
  _registerTimedHit(t) {
    if (typeof t !== "number" || !isFinite(t)) return;
    let best = -1, bestErr = Infinity;
    for (let i = 0; i < this.noteTimes.length; i++) {
      if (this.hitNotes[i]) continue;
      const err = Math.abs(t - this.noteTimes[i]);
      if (err < bestErr) { bestErr = err; best = i; }
    }
    if (best < 0 || bestErr > this.tolSec) return; // 差太多，不算也不懲罰

    this.hitNotes[best] = true;
    this.hits += 1;
    this.onNote(best);
    if (this.hitNotes.every(Boolean)) this._setState("pass");
    else this._setState("progress");
  }

  // 跟拍模式：最後一顆的容許窗關閉(main.js 的 endT)或音樂放完(備援)時呼叫。
  // 還有沒打到的音符 → 失敗
  finishSong() {
    if (!this.timed) return;
    if (this.state === "pass" || this.state === "fail") return;
    this._setState(this.hitNotes.every(Boolean) ? "pass" : "fail");
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
    this.onState(s, {
      hits: this.hits, maxHits: this.maxHits,
      timed: this.timed, hitNotes: this.hitNotes,
    });
  }
}
