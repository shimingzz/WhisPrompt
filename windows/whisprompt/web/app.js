"use strict";

const $ = (id) => document.getElementById(id);
const statusEl = $("status"), recBtn = $("recBtn"), timerEl = $("timer");

let mediaRecorder = null;
let chunks = [];
let mode = "prompt";
let timerInterval = null;
let startTime = 0;

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
    renderModes(s.modes || {});
    recBtn.disabled = false;
  } catch {
    statusEl.textContent = "無法連線到伺服器";
    statusEl.classList.add("err");
    setTimeout(init, 3000);
  }
}

function renderModes(modes) {
  const row = $("modeRow");
  row.innerHTML = "";
  for (const [key, label] of Object.entries(modes)) {
    const b = document.createElement("button");
    b.className = "mode-btn" + (key === mode ? " active" : "");
    b.textContent = label;
    b.onclick = () => {
      mode = key;
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
  startTime = Date.now();
  recBtn.classList.add("recording");
  timerEl.textContent = "00:00";
  timerInterval = setInterval(() => { timerEl.textContent = fmtTime(Date.now() - startTime); }, 250);
}

function stopRecording() {
  clearInterval(timerInterval);
  recBtn.classList.remove("recording");
  recBtn.classList.add("busy");
  recBtn.disabled = true;
  timerEl.textContent = "轉錄與優化中...";
  mediaRecorder.stop();
}

async function upload(blob) {
  const ext = blob.type.includes("mp4") ? "m4a" : "webm";
  const form = new FormData();
  form.append("file", blob, `recording.${ext}`);
  form.append("mode", mode);
  try {
    const r = await fetch("/api/audio", { method: "POST", body: form });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || r.statusText);
    showResult(data);
    timerEl.textContent = `完成 (${data.elapsed}s) · 點擊再次錄音`;
  } catch (e) {
    timerEl.textContent = `失敗: ${e.message}`;
  } finally {
    recBtn.classList.remove("busy");
    recBtn.disabled = false;
  }
}

function showResult(data) {
  $("resultArea").classList.remove("hidden");
  $("promptText").textContent = data.prompt;
  $("transcriptText").textContent = data.transcript || "(無語音內容)";
  $("meta").textContent = `· ${data.duration}s · ${data.language}`;
}

recBtn.onclick = () => {
  if (mediaRecorder && mediaRecorder.state === "recording") stopRecording();
  else startRecording();
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
