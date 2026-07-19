/**
 * Æther Forge — Frontend
 * Boot animation, websocket comms, UI logic.
 */

// ─── State ───────────────────────────────────────────────────────────────────

const RUNES      = ["ᚠ","ᚢ","ᚦ","ᚨ","ᚱ","ᚷ","ᚹ","ᛁ","ᛃ","ᛇ","ᛚ","ᛟ"];
let   ws         = null;
let   thinking   = false;

// ─── Elements ────────────────────────────────────────────────────────────────

const runeRing   = document.getElementById("rune-ring");
const app        = document.getElementById("app");
const output     = document.getElementById("output");
const input      = document.getElementById("forge-input");
const voiceBtn   = document.getElementById("voice-btn");
const statusDot  = document.getElementById("status-dot");
const runeNodes  = document.querySelectorAll(".rune-ring .rune");

// ─── Boot animation ──────────────────────────────────────────────────────────

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function bootAnimation() {
  // Light up clockwise
  for (let i = 0; i < RUNES.length; i++) {
    runeNodes[i].classList.add("lit");
    await sleep(120);
  }

  await sleep(400);

  // Sweep — 180 degree fade
  for (let i = 0; i < RUNES.length; i++) {
    runeNodes[i].classList.remove("lit");
    runeNodes[i].classList.add("dim");
    await sleep(60);
  }

  await sleep(200);

  // Slide ring to corner + show app
  runeRing.style.transition = "all 0.6s cubic-bezier(0.4, 0, 0.2, 1)";
  runeRing.style.top        = "-30px";
  runeRing.style.left       = "-30px";
  runeRing.style.transform  = "scale(0.18)";
  runeRing.style.opacity    = "0.4";

  await sleep(600);

  app.classList.remove("hidden");
  app.style.opacity = "0";
  app.style.transition = "opacity 0.4s ease";
  requestAnimationFrame(() => {
    app.style.opacity = "1";
  });

  await sleep(400);
  input.focus();
  connectWS();
}

// ─── WebSocket ───────────────────────────────────────────────────────────────

function connectWS() {
  ws = new WebSocket("ws://localhost:7777");

  ws.onopen = () => {
    statusDot.className = "status-dot";
    statusDot.title = "Connected";
    appendForge("⟁ Forge connected. Ready.", "");
  };

  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);

    removeThinking();

    if (data.type === "output") {
      appendForge(data.text, "");
    } else if (data.type === "code") {
      appendForge(data.text, "code");
    } else if (data.type === "error") {
      appendForge(data.text, "error");
    } else if (data.type === "done") {
      setThinking(false);
    }
  };

  ws.onclose = () => {
    statusDot.className = "status-dot offline";
    statusDot.title = "Disconnected";
    setTimeout(connectWS, 3000);
  };

  ws.onerror = () => {
    statusDot.className = "status-dot offline";
  };
}

// ─── Messages ────────────────────────────────────────────────────────────────

function appendUser(text) {
  const msg = document.createElement("div");
  msg.className = "msg msg-user";
  msg.innerHTML = `
    <div class="msg-label">you</div>
    <div class="msg-bubble">${escHtml(text)}</div>
  `;
  output.appendChild(msg);
  scrollDown();
}

function appendForge(text, type = "") {
  const msg = document.createElement("div");
  msg.className = "msg msg-forge";
  msg.innerHTML = `
    <div class="msg-label">æther forge</div>
    <div class="msg-bubble ${type}">${escHtml(text)}</div>
  `;
  output.appendChild(msg);
  scrollDown();
}

function appendThinking() {
  const msg = document.createElement("div");
  msg.className = "msg msg-forge";
  msg.id = "thinking-msg";
  msg.innerHTML = `
    <div class="msg-label">æther forge</div>
    <div class="msg-bubble thinking-dots">
      <span>●</span><span>●</span><span>●</span>
    </div>
  `;
  output.appendChild(msg);
  scrollDown();
}

function removeThinking() {
  const el = document.getElementById("thinking-msg");
  if (el) el.remove();
}

function setThinking(val) {
  thinking = val;
  if (val) {
    statusDot.className = "status-dot thinking";
    appendThinking();
    input.disabled = true;
  } else {
    statusDot.className = "status-dot";
    input.disabled = false;
    input.focus();
  }
}

function scrollDown() {
  output.scrollTop = output.scrollHeight;
}

function escHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ─── Input ───────────────────────────────────────────────────────────────────

function sendCommand(text) {
  if (!text.trim() || thinking) return;
  appendUser(text);
  setThinking(true);

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "command", text }));
  } else {
    removeThinking();
    appendForge("Not connected to forge backend.", "error");
    setThinking(false);
  }
}

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    const val = input.value.trim();
    input.value = "";
    sendCommand(val);
  }
});

// ─── Voice button ────────────────────────────────────────────────────────────

voiceBtn.addEventListener("click", () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    voiceBtn.classList.add("active");
    ws.send(JSON.stringify({ type: "voice_start" }));
    setTimeout(() => {
      voiceBtn.classList.remove("active");
      ws.send(JSON.stringify({ type: "voice_stop" }));
    }, 5000);
  }
});

// ─── Boot ────────────────────────────────────────────────────────────────────

bootAnimation();
