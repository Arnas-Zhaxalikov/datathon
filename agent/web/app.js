const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");

let sessionId = sessionStorage.getItem("session_id") || null;

const CHECKLIST_LABELS = {
  reported_n_and_missingness: "n и заполненность",
  checked_schema_drift: "дрейф схемы",
  checked_correlation_reliability: "надёжность связи",
  flagged_small_sample: "малая выборка",
  cross_checked_against_priors: "сверка с ориентирами",
};

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

function renderMarkdownLite(text) {
  let safe = escapeHtml(text);
  safe = safe.replace(/```([\s\S]*?)```/g, (_, code) => `<pre><code>${code}</code></pre>`);
  safe = safe.replace(/`([^`]+)`/g, "<code>$1</code>");
  safe = safe.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  safe = safe
    .split(/\n{2,}/)
    .map((p) => `<p>${p.replace(/\n/g, "<br>")}</p>`)
    .join("");
  return safe;
}

function addRow(role, text) {
  const row = document.createElement("div");
  row.className = `row ${role}`;
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "Вы" : "ИИ";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = renderMarkdownLite(text);
  row.append(avatar, bubble);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
  return bubble;
}

function renderChecklist(bubble, checklist) {
  if (!checklist || !checklist.applicable || checklist.applicable.length === 0) return;
  const box = document.createElement("div");
  box.className = "checklist";
  const applicable = new Set(checklist.applicable);
  for (const [key, label] of Object.entries(CHECKLIST_LABELS)) {
    if (!applicable.has(key)) continue;
    const chip = document.createElement("span");
    chip.className = `chip ${checklist[key] ? "ok" : "bad"}`;
    chip.textContent = `${checklist[key] ? "✓" : "✗"} ${label}`;
    box.appendChild(chip);
  }
  if (box.childElementCount > 0) bubble.appendChild(box);
}

async function send(message) {
  addRow("user", message);
  const typingBubble = addRow("assistant", "");
  typingBubble.innerHTML = '<span class="typing">печатает…</span>';

  sendBtn.disabled = true;
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message }),
    });
    if (!res.ok) {
      const err = await res.text();
      typingBubble.innerHTML = `<span style="color:#b42318">Ошибка: ${escapeHtml(err)}</span>`;
      return;
    }
    const data = await res.json();
    sessionId = data.session_id;
    sessionStorage.setItem("session_id", sessionId);
    typingBubble.innerHTML = renderMarkdownLite(data.reply);
    renderChecklist(typingBubble, data.checklist);
    chat.scrollTop = chat.scrollHeight;
  } catch (e) {
    typingBubble.innerHTML = '<span style="color:#b42318">Нет связи с сервером</span>';
  } finally {
    sendBtn.disabled = false;
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  input.style.height = "auto";
  send(text);
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
});
