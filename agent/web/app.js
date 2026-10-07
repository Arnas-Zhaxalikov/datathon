// ---------- Язык ----------
// Словари и t()/fmt()/setLang() — в i18n.js

const langSelect = document.getElementById("lang-select");
langSelect.value = currentLang;
langSelect.addEventListener("change", () => setLang(langSelect.value));
applyStaticTranslations();

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

const familyForm = document.getElementById("family-form");
const familyResult = document.getElementById("family-result");

// последний результат/ошибка — чтобы перерисовать при смене языка
let familyData = null;
let familyErrorKey = null;

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
  btn.textContent = t("calculating");
  try {
    const res = await fetch("/api/classify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      // тексты ошибок бэкенда — на русском, поэтому показываем свой перевод по коду ответа
      showFamilyError(res.status === 400 || res.status === 422 ? "calc_invalid" : "calc_error");
      return;
    }
    familyData = data;
    familyErrorKey = null;
    renderFamilyResult(data);
  } catch (err) {
    showFamilyError("no_connection");
  } finally {
    btn.disabled = false;
    btn.textContent = t("calc");
  }
});

function showFamilyError(key) {
  familyData = null;
  familyErrorKey = key;
  familyResult.classList.remove("hidden");
  familyResult.innerHTML = `<p class="error-text">${escapeHtml(t(key))}</p>`;
}

function renderFamilyResult(data) {
  familyResult.classList.remove("hidden");
  familyResult.innerHTML = `
    <div class="result-badge">
      <span class="status-dot" style="background:${STATUS_COLOR[data.status]}"></span>
      <div>
        <div class="result-label">${escapeHtml(t("group_" + data.group))}</div>
        <div class="result-sub">${t("result_sub", { p: data.pct_of_poverty_line })}</div>
      </div>
    </div>

    <div class="meter-wrap">
      <div class="meter-track" id="meter-track"></div>
      <div class="meter-ticks">
        <span>0</span>
        <span>${t("tick_asp", { v: fmt(data.asp_threshold) })}</span>
        <span>${t("tick_pm", { v: fmt(data.poverty_line) })}</span>
      </div>
      <div class="meter-legend">
        <span><i class="dot dot-now"></i>${t("legend_now", { v: fmt(data.income_pc) })}</span>
        <span><i class="dot dot-stress"></i>${t("legend_stress", { v: fmt(data.worst_stress_income_pc) })}</span>
      </div>
    </div>

    <div class="stress-table">
      ${Object.entries(data.stress_scenarios)
        .map(
          ([k, v]) =>
            `<div class="stress-row"><span>${escapeHtml(t("stress_" + k))}</span><b>${fmt(v)} ${t("per_month")}${
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
    <div class="meter-marker marker-stress" style="left:${stressPct}%" title="${escapeHtml(
      t("title_stress", { v: fmt(data.worst_stress_income_pc) })
    )}"></div>
    <div class="meter-marker marker-now" style="left:${nowPct}%" title="${escapeHtml(
      t("title_now", { v: fmt(data.income_pc) })
    )}"></div>
  `;
}

// ---------- Обзор по стране ----------

let overviewData = null;
let overviewStatus = null; // "calculating" | "overview_error" — пока плиток нет

function showOverviewStatus(key) {
  overviewStatus = key;
  const cls = key === "overview_error" ? "error-text" : "hint";
  document.getElementById("overview-tiles").innerHTML = `<p class="${cls}">${escapeHtml(t(key))}</p>`;
}

async function loadOverview() {
  if (overviewData || overviewStatus === "calculating") return;
  showOverviewStatus("calculating");
  try {
    const res = await fetch("/api/summary?year=2024");
    if (!res.ok) throw new Error(String(res.status));
    overviewData = await res.json();
    overviewStatus = null;
    renderOverview();
  } catch (e) {
    showOverviewStatus("overview_error");
  }
}

function renderOverview() {
  const data = overviewData;
  document.getElementById("overview-hint").textContent = t("overview_hint", {
    n: fmt(data.total_households),
    pm: fmt(data.poverty_line),
    asp: fmt(data.asp_threshold),
  });

  const order = ["B", "C", "A", "D"]; // от самой "невидимой" проблемы к устойчивым
  document.getElementById("overview-tiles").innerHTML = order
    .map((g) => {
      const grp = data.groups[g];
      return `
        <div class="tile">
          <div class="tile-label">
            <span class="status-dot" style="width:10px;height:10px;background:${STATUS_COLOR[grp.status]}"></span>
            ${escapeHtml(t("group_" + g))}
          </div>
          <div class="tile-value">${grp.pct}%</div>
          <div class="tile-sub">${fmt(grp.count)} ${escapeHtml(t("households"))}</div>
        </div>`;
    })
    .join("");
}

// ---------- Чат (режим "Для анализа") ----------

const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");

let sessionId = sessionStorage.getItem("session_id") || null;

const CHECKLIST_KEYS = [
  "reported_n_and_missingness",
  "checked_schema_drift",
  "checked_correlation_reliability",
  "flagged_small_sample",
  "cross_checked_against_priors",
];

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
  avatar.dataset.i18n = role === "user" ? "avatar_user" : "avatar_ai";
  avatar.textContent = t(avatar.dataset.i18n);
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
  for (const key of CHECKLIST_KEYS) {
    if (!applicable.has(key)) continue;
    const chip = document.createElement("span");
    chip.className = `chip ${checklist[key] ? "ok" : "bad"}`;
    chip.dataset.mark = checklist[key] ? "✓" : "✗";
    chip.dataset.key = key;
    chip.textContent = `${chip.dataset.mark} ${t("chk_" + key)}`;
    box.appendChild(chip);
  }
  if (box.childElementCount > 0) bubble.appendChild(box);
}

function showChatError(bubble, text) {
  bubble.innerHTML = `<span style="color:#b42318">${escapeHtml(text)}</span>`;
}

async function send(message) {
  addRow("user", message);
  const typingBubble = addRow("assistant", "");
  typingBubble.innerHTML = `<span class="typing">${escapeHtml(t("typing"))}</span>`;

  sendBtn.disabled = true;
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message, lang: currentLang }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      // 503 — нет ключа API: показываем перевод; остальное — как пришло от сервера
      showChatError(typingBubble, res.status === 503 ? t("chat_no_key") : err.detail || t("error"));
      return;
    }
    const data = await res.json();
    sessionId = data.session_id;
    sessionStorage.setItem("session_id", sessionId);
    typingBubble.innerHTML = renderMarkdownLite(data.reply);
    renderChecklist(typingBubble, data.checklist);
    chat.scrollTop = chat.scrollHeight;
  } catch (e) {
    showChatError(typingBubble, t("no_connection"));
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

// ---------- Смена языка: перерисовать всё, что собрано в JS ----------

document.addEventListener("langchange", () => {
  if (familyData) renderFamilyResult(familyData);
  else if (familyErrorKey) showFamilyError(familyErrorKey);

  if (overviewData) renderOverview();
  else if (overviewStatus) showOverviewStatus(overviewStatus);

  chat.querySelectorAll(".chip[data-key]").forEach((chip) => {
    chip.textContent = `${chip.dataset.mark} ${t("chk_" + chip.dataset.key)}`;
  });
});
