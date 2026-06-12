"use strict";

const $ = (id) => document.getElementById(id);
const statusEl = $("status"), recBtn = $("recBtn"), timerEl = $("timer");
const pauseBtn = $("pauseBtn"), doneBtn = $("doneBtn"), recControls = $("recControls");

let mediaRecorder = null;
let chunks = [];
let mode = "prompt";
let think = "low";
let timerInterval = null;
// Pause-aware elapsed time: accumulated past segments + current segment start.
let elapsedBefore = 0;
let segStart = 0;

// ---- theme ----
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $("themeToggle").textContent = theme === "dark" ? "☀️" : "🌙";
  localStorage.setItem("theme", theme);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = theme === "dark" ? "#262624" : "#FAF9F5";
}
applyTheme(localStorage.getItem("theme") ||
  (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
$("themeToggle").onclick = () =>
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");

// iOS Safari records audio/mp4; Chrome/Android typically audio/webm.
function pickMime() {
  for (const m of ["audio/mp4", "audio/webm;codecs=opus", "audio/webm"]) {
    if (window.MediaRecorder && MediaRecorder.isTypeSupported(m)) return m;
  }
  return "";
}

async function init() {
  try {
    const r = await fetch("/api/status");
    const s = await r.json();
    statusEl.textContent = `${s.whisper_model} (${s.whisper_device}) · ${s.ollama_model || "無 LLM"}`;
    statusEl.classList.add("ok");
    mode = s.mode || "prompt";
    think = s.think_level || "low";
    renderOptions($("modeRow"), s.modes || {}, mode, (k) => { mode = k; });
    renderOptions($("thinkRow"), s.think_levels || {}, think, (k) => { think = k; });
    recBtn.disabled = false;
  } catch {
    statusEl.textContent = "無法連線到伺服器";
    statusEl.classList.add("err");
    setTimeout(init, 3000);
  }
}

function renderOptions(row, options, current, onPick) {
  row.innerHTML = "";
  for (const [key, label] of Object.entries(options)) {
    const b = document.createElement("button");
    b.className = "mode-btn" + (key === current ? " active" : "");
    b.textContent = label;
    b.onclick = () => {
      onPick(key);
      row.querySelectorAll(".mode-btn").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
    };
    row.appendChild(b);
  }
}

function fmtTime(ms) {
  const s = Math.floor(ms / 1000);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function currentElapsed() {
  const paused = mediaRecorder && mediaRecorder.state === "paused";
  return elapsedBefore + (paused ? 0 : Date.now() - segStart);
}

// ---- recording with pause/resume ----
async function startRecording() {
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    timerEl.textContent = "麥克風權限被拒,請到設定開啟";
    return;
  }
  chunks = [];
  const mime = pickMime();
  mediaRecorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
  mediaRecorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  mediaRecorder.onstop = () => {
    stream.getTracks().forEach((t) => t.stop());
    upload(new Blob(chunks, { type: mediaRecorder.mimeType }));
  };
  mediaRecorder.start();
  elapsedBefore = 0;
  segStart = Date.now();
  recBtn.classList.add("recording");
  recControls.classList.remove("hidden");
  pauseBtn.textContent = "⏸ 暫停";
  timerEl.textContent = "00:00";
  timerInterval = setInterval(() => { timerEl.textContent = fmtTime(currentElapsed()); }, 250);
}

function togglePause() {
  if (!mediaRecorder) return;
  if (mediaRecorder.state === "recording") {
    mediaRecorder.pause();
    elapsedBefore += Date.now() - segStart;
    recBtn.classList.add("paused");
    pauseBtn.textContent = "▶ 繼續";
    timerEl.textContent = `${fmtTime(elapsedBefore)} · 已暫停`;
  } else if (mediaRecorder.state === "paused") {
    mediaRecorder.resume();
    segStart = Date.now();
    recBtn.classList.remove("paused");
    pauseBtn.textContent = "⏸ 暫停";
  }
}

function finishRecording() {
  if (!mediaRecorder || mediaRecorder.state === "inactive") return;
  clearInterval(timerInterval);
  recBtn.classList.remove("recording", "paused");
  recControls.classList.add("hidden");
  recBtn.classList.add("busy");
  recBtn.disabled = true;
  timerEl.textContent = "轉錄與優化中...";
  mediaRecorder.stop();  // onstop fires upload()
}

async function upload(blob) {
  const ext = blob.type.includes("mp4") ? "m4a" : "webm";
  const form = new FormData();
  form.append("file", blob, `recording.${ext}`);
  form.append("mode", mode);
  form.append("think", think);
  try {
    const r = await fetch("/api/audio", { method: "POST", body: form });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || r.statusText);
    showResult(data);
    loadHistory();
    timerEl.textContent = `完成 (${data.elapsed}s) · 點擊再次錄音`;
  } catch (e) {
    timerEl.textContent = `失敗: ${e.message}`;
  } finally {
    recBtn.classList.remove("busy");
    recBtn.disabled = false;
    mediaRecorder = null;
  }
}

recBtn.onclick = () => {
  if (!mediaRecorder || mediaRecorder.state === "inactive") startRecording();
  else togglePause();  // tapping the big button while recording = pause/resume
};
pauseBtn.onclick = togglePause;
doneBtn.onclick = finishRecording;

// ---- direct text input ----
$("textSubmit").onclick = async () => {
  const text = $("textInput").value.trim();
  if (!text) return;
  const btn = $("textSubmit");
  btn.disabled = true;
  btn.textContent = "優化中…";
  try {
    const r = await fetch("/api/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, mode, think }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || r.statusText);
    showResult(data);
    loadHistory();
    $("textInput").value = "";
  } catch (e) {
    timerEl.textContent = `失敗: ${e.message}`;
  } finally {
    btn.disabled = false;
    btn.textContent = "✨ 優化";
  }
};

function showResult(data) {
  $("resultArea").classList.remove("hidden");
  $("promptText").textContent = data.prompt;
  $("transcriptText").textContent = data.transcript || "(無內容)";
  $("meta").textContent = data.language === "text"
    ? "· 文字輸入"
    : `· ${data.duration}s · ${data.language}`;
}

// ---- history (notebook) ----
let showArchived = false;

async function loadHistory() {
  try {
    const r = await fetch(`/api/history?archived=${showArchived ? 1 : 0}&limit=50`);
    renderHistory(await r.json());
  } catch { /* server unreachable; init() handles retry */ }
}

function renderHistory(items) {
  const list = $("historyList");
  list.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "history-empty";
    empty.textContent = showArchived ? "封存區是空的" : "還沒有紀錄";
    list.appendChild(empty);
    return;
  }
  for (const item of items) {
    const el = document.createElement("div");
    el.className = "history-item";

    const head = document.createElement("div");
    head.className = "history-item-head";
    const time = document.createElement("span");
    time.textContent = item.timestamp;
    head.appendChild(time);

    const actions = document.createElement("span");
    actions.className = "history-actions";
    actions.append(
      historyBtn("複製", async (btn) => {
        await navigator.clipboard.writeText(item.prompt);
        btn.textContent = "已複製";
        setTimeout(() => { btn.textContent = "複製"; }, 1200);
      }),
      historyBtn(item.archived ? "還原" : "封存", async () => {
        await fetch(`/api/history/${item.id}/archive`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ archived: !item.archived }),
        });
        loadHistory();
      }),
      historyBtn("刪除", async () => {
        if (!confirm("確定刪除這筆紀錄?")) return;
        await fetch(`/api/history/${item.id}`, { method: "DELETE" });
        loadHistory();
      }, "danger"),
    );
    head.appendChild(actions);
    el.appendChild(head);

    const body = document.createElement("div");
    body.className = "history-item-text";
    body.textContent = item.prompt;
    body.onclick = () => body.classList.toggle("expanded");
    el.appendChild(body);

    list.appendChild(el);
  }
}

function historyBtn(label, handler, extra = "") {
  const b = document.createElement("button");
  b.className = "history-btn " + extra;
  b.textContent = label;
  b.onclick = (e) => { e.stopPropagation(); handler(b); };
  return b;
}

$("archiveToggle").onclick = () => {
  showArchived = !showArchived;
  $("archiveToggle").classList.toggle("active", showArchived);
  loadHistory();
};

document.querySelectorAll(".copy-btn").forEach((btn) => {
  btn.onclick = async () => {
    const text = $(btn.dataset.target).textContent;
    try {
      await navigator.clipboard.writeText(text);
      btn.textContent = "已複製";
      btn.classList.add("copied");
      setTimeout(() => { btn.textContent = "複製"; btn.classList.remove("copied"); }, 1500);
    } catch {
      btn.textContent = "複製失敗";
    }
  };
});

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");
init();
loadHistory();
