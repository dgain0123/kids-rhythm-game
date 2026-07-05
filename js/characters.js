// characters.js — 角色系統：讀 characters/index.json、畫角色選單、把選中的角色放進畫面
// 一個角色一張圖(或一個 emoji)；換角色只要改 index.json，不動這支程式。

const STORE_KEY = "kids_char_id";
let list = [];
let currentId = null;
let els = null;

// 把一個角色渲染成 HTML(圖片或 emoji)
function mediaHTML(ch, cls) {
  if (ch.img) {
    return `<img class="${cls}" src="characters/${ch.img}" alt="${ch.name}">`;
  }
  return `<span class="${cls} char-emoji">${ch.emoji || "❓"}</span>`;
}

let charCount = 1; // 要顯示幾隻(＝該關要打幾下)

// 設定角色數量(第2關打2下就顯示2隻)
export function setCharCount(n) { charCount = Math.max(1, n | 0); }

function renderCurrent() {
  const ch = list.find(c => c.id === currentId) || list[0];
  if (!ch) { els.face.textContent = "🙂"; return; }
  els.face.innerHTML = mediaHTML(ch, "char-media").repeat(charCount);
  // 選單高亮
  [...els.picker.querySelectorAll(".char-btn")].forEach(b =>
    b.classList.toggle("active", b.dataset.id === ch.id));
}

function renderPicker(onChange) {
  els.picker.innerHTML = "";
  for (const ch of list) {
    const btn = document.createElement("button");
    btn.className = "char-btn";
    btn.dataset.id = ch.id;
    btn.title = ch.name;
    btn.innerHTML = mediaHTML(ch, "char-thumb") + `<span class="char-name">${ch.name}</span>`;
    btn.addEventListener("click", () => {
      currentId = ch.id;
      try { localStorage.setItem(STORE_KEY, ch.id); } catch (e) {}
      renderCurrent();
      if (onChange) onChange(ch);
    });
    els.picker.appendChild(btn);
  }
}

// 重新把目前選的角色畫回角色框(過關顯示拉炮後要還原時用)
export function showCharacter() { renderCurrent(); }

export async function initCharacters({ face, picker, onChange } = {}) {
  els = { face, picker };
  const res = await fetch("./characters/index.json?t=" + Date.now(), { cache: "no-store" });
  const data = await res.json();
  list = data.characters || [];

  // 預設角色：網址 ?char= > 上次選的 > 第一個
  const urlChar = new URLSearchParams(location.search).get("char");
  let saved = null;
  try { saved = localStorage.getItem(STORE_KEY); } catch (e) {}
  currentId = (urlChar && list.some(c => c.id === urlChar)) ? urlChar
            : (saved && list.some(c => c.id === saved)) ? saved
            : (list[0] && list[0].id);

  renderPicker(onChange);
  renderCurrent();
}
