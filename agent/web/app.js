// ---------- Tabs ----------

const tabs = document.querySelectorAll(".tab");
const panels = {
  family: document.getElementById("panel-family"),
  overview: document.getElementById("panel-overview"),
  analyst: document.getElementById("panel-analyst"),
};

tabs.forEach((btn) => {
  btn.addEventListener("click", () => {
    tabs.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    Object.values(panels).forEach((p) => p.classList.remove("active"));
    const panel = panels[btn.dataset.tab];
    panel.classList.add("active");
    if (btn.dataset.tab === "overview") loadOverview();
  });
});

// ---------- Моя семья ----------

const STATUS_COLOR = {
  good: "var(--status-good)",
  warning: "var(--status-warning)",
  serious: "var(--status-serious)",
  critical: "var(--status-critical)",
};

const STRESS_LABELS = {
  earner_loss: "Кормилец теряет доход",
  income_drop15: "Доход −15%",
  utility_up30: "Коммунальные +30%",
};

const familyForm = document.getElementById("family-form");
const familyResult = document.getElementById("family-result");

familyForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    hh_size: Number(document.getElementById("f-hh-size").value),
    n_child: Number(document.getElementById("f-n-child").value),
    n_employed: Number(document.getElementById("f-n-employed").value),
    income_monthly: Number(document.getElementById("f-income").value),
    settlement: document.getElementById("f-settlement").value,
  };

  const btn = familyForm.querySelector("button");
  btn.disabled = true;
  btn.textContent = "Считаю…";
  try {
    const res = await fetch("/api/classify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Ошибка расчёта");
    renderFamilyResult(data);
  } catch (err) {
    familyResult.classList.remove("hidden");
    familyResult.innerHTML = `<p class="error-text">${escapeHtml(err.message)}</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Рассчитать";
  }
});

function renderFamilyResult(data) {
  familyResult.classList.remove("hidden");
  familyResult.innerHTML = `
    <div class="result-badge">
      <span class="status-dot" style="background:${STATUS_COLOR[data.status]}"></span>
      <div>
        <div class="result-label">${escapeHtml(data.label)}</div>
        <div class="result-sub">Доход на человека — ${data.pct_of_poverty_line}% от прожиточного минимума</div>
      </div>
    </div>

    <div class="meter-wrap">
      <div class="meter-track" id="meter-track"></div>
      <div class="meter-ticks">
        <span>0</span>
        <span>АСП: ${fmt(data.asp_threshold)}</span>
        <span>ПМ: ${fmt(data.poverty_line)}</span>
      </div>
      <div class="meter-legend">
        <span><i class="dot dot-now"></i>Сейчас: <b>${fmt(data.income_pc)}</b> тг/мес на человека</span>
        <span><i class="dot dot-stress"></i>В худшем из 3 сценариев: <b>${fmt(data.worst_stress_income_pc)}</b> тг/мес</span>
      </div>
    </div>

    <div class="stress-table">
      ${Object.entries(data.stress_scenarios)
        .map(
          ([k, v]) =>
            `<div class="stress-row"><span>${STRESS_LABELS[k] || k}</span><b>${fmt(v)} тг/мес${
              v < data.poverty_line ? " ⚠" : ""
            }</b></div>`
        )
        .join("")}
    </div>
  `;
  drawMeter(data);
}

function drawMeter(data) {
  const track = document.getElementById("meter-track");
  // шкала — от 0 до максимума из (доход сейчас * 1.15, ПМ * 1.6), чтобы метки не вылезали за край
  const max = Math.max(data.income_pc * 1.15, data.poverty_line * 1.6);
  const pct = (v) => Math.max(0, Math.min(100, (v / max) * 100));

  const ascPct = pct(data.asp_threshold);
  const pmPct = pct(data.poverty_line);
  const nowPct = pct(data.income_pc);
  const stressPct = pct(data.worst_stress_income_pc);

  track.innerHTML = `
    <div class="meter-zone zone-a" style="width:${ascPct}%"></div>
    <div class="meter-zone zone-b" style="width:${pmPct - ascPct}%"></div>
    <div class="meter-zone zone-cd" style="width:${100 - pmPct}%"></div>
    <div class="meter-marker marker-stress" style="left:${stressPct}%" title="В худшем сценарии: ${fmt(data.worst_stress_income_pc)} тг"></div>
    <div class="meter-marker marker-now" style="left:${nowPct}%" title="Сейчас: ${fmt(data.income_pc)} тг"></div>
  `;
}

function fmt(n) {
  return Math.round(n).toLocaleString("ru-RU");
}

// ---------- Обзор по стране ----------

let overviewLoaded = false;

async function loadOverview() {
  if (overviewLoaded) return;
  const tiles = document.getElementById("overview-tiles");
  const hint = document.getElementById("overview-hint");
  tiles.innerHTML = '<p class="hint">Считаю…</p>';
  try {
    const res = await fetch("/api/summary?year=2024");
    const data = await res.json();
    overviewLoaded = true;
    hint.textContent = `${data.total_households.toLocaleString("ru-RU")} домохозяйств, 2024 год. Прожиточный минимум ≈ ${fmt(
      data.poverty_line
    )} тг/мес на человека (относительная черта), черта АСП ≈ ${fmt(data.asp_threshold)} тг/мес.`;

    const order = ["B", "C", "A", "D"]; // от самой "невидимой" проблемы к устойчивым
    tiles.innerHTML = order
      .map((g) => {
        const grp = data.groups[g];
        return `
        <div class="tile">
          <div class="tile-label">
            <span class="status-dot" style="width:10px;height:10px;background:${STATUS_COLOR[grp.status]}"></span>
            ${escapeHtml(grp.label)}
          </div>
          <div class="tile-value">${grp.pct}%</div>
          <div class="tile-sub">${grp.count.toLocaleString("ru-RU")} домохозяйств</div>
        </div>`;
      })
      .join("");
  } catch (e) {
    tiles.innerHTML = '<p class="error-text">Не удалось загрузить обзор</p>';
  }
}

// ---------- Чат (режим "Для анализа") ----------

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
  return String(s).replace(/[&<>"']/g, (c) => ({
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
      const err = await res.json().catch(() => ({ detail: "Ошибка" }));
      typingBubble.innerHTML = `<span style="color:#b42318">${escapeHtml(err.detail || "Ошибка")}</span>`;
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
