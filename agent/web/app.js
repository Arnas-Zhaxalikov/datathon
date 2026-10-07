// ---------- Язык ----------
// Словари и t()/fmt()/setLang() — в i18n.js

const langSelect = document.getElementById("lang-select");
langSelect.value = currentLang;
langSelect.addEventListener("change", () => setLang(langSelect.value));
applyStaticTranslations();

// ---------- Тема ----------
// Начальное значение data-theme ставит скрипт в <head> index.html

document.getElementById("theme-toggle").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem("theme", next);
  } catch (e) {
    // хранилище недоступно — тема просто не запомнится
  }
});

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
// Все числа приходят из /api/classify (agent/backend/engine.py). Здесь только
// подстановка в готовую разметку и тексты на языке интерфейса.

const STATUS_COLOR = {
  good: "var(--status-good)",
  warning: "var(--status-warning)",
  serious: "var(--status-serious)",
  critical: "var(--status-critical)",
};

const $ = (id) => document.getElementById(id);
const familyForm = $("family-form");
const familyResult = $("family-result");
const familyError = $("family-error");

// последний результат/ошибка — чтобы перерисовать при смене языка
let familyData = null;
let familyErrorKey = null;
let regionsList = [];

const kzt = (v) => `${fmt(v)} ${t("kzt")}`;
const fmtPct = (v) => Number(v).toLocaleString(LOCALES[currentLang], { maximumFractionDigits: 1 });
const optNum = (id) => ($(id).value.trim() === "" ? null : Number($(id).value));

async function loadRegions() {
  try {
    const res = await fetch("/api/regions");
    if (!res.ok) throw new Error(String(res.status));
    regionsList = await res.json();
    renderRegions();
  } catch (e) {
    showFamilyError("no_connection");
  }
}

function renderRegions() {
  const select = $("f-region");
  const current = select.value;
  const placeholder = new Option(t("f_region_choose"), "");
  placeholder.disabled = true;
  select.replaceChildren(placeholder, ...regionsList.map((r) => new Option(regionName(r.code, r.name), r.code)));
  select.value = current;
}

function familyPayload() {
  return {
    hh_size: Number($("f-hh-size").value),
    n_child: Number($("f-n-child").value),
    n_employed: Number($("f-n-employed").value),
    income_monthly: Number($("f-income").value),
    region: Number($("f-region").value),
    earner_wage: optNum("f-earner-wage"),
    transfers: optNum("f-transfers"),
    housing_cost: optNum("f-housing"),
    months_without_wage: Number($("s-months").value),
    income_drop_pct: Number($("s-drop").value),
    housing_rise_pct: Number($("s-rise").value),
    whatif_extra_wage: optNum("w-wage") || 0,
    whatif_child_allowance: optNum("w-allowance") || 0,
  };
}

let calcSeq = 0;

async function calculate() {
  const seq = ++calcSeq; // ответы на устаревшие запросы (ползунок уже сдвинут дальше) отбрасываются
  try {
    const res = await fetch("/api/classify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(familyPayload()),
    });
    const data = await res.json();
    if (seq !== calcSeq) return;
    if (!res.ok) {
      // сервер присылает код ошибки, текст на нужном языке — из словаря
      const code = data.detail && data.detail.code;
      showFamilyError(code && I18N[DEFAULT_LANG][code] ? code : res.status < 500 ? "calc_invalid" : "calc_error");
      return;
    }
    familyData = data;
    familyErrorKey = null;
    renderFamilyResult();
  } catch (err) {
    if (seq === calcSeq) showFamilyError("no_connection");
  }
}

familyForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = familyForm.querySelector("button");
  btn.disabled = true;
  btn.textContent = t("calculating");
  await calculate();
  btn.disabled = false;
  btn.textContent = t("calc");
});

// после первого расчёта любое изменение пересчитывает результат без кнопки
let recalcTimer = null;
function scheduleRecalc(delay) {
  if (!familyData && !familyErrorKey) return;
  clearTimeout(recalcTimer);
  recalcTimer = setTimeout(() => {
    if (familyForm.checkValidity()) calculate();
  }, delay);
}
familyForm.addEventListener("change", () => scheduleRecalc(0));
["s-months", "s-drop", "s-rise"].forEach((id) =>
  $(id).addEventListener("input", () => {
    renderSliderLabels();
    scheduleRecalc(40);
  })
);
["w-wage", "w-allowance"].forEach((id) => $(id).addEventListener("input", () => scheduleRecalc(250)));

function showFamilyError(key) {
  familyData = null;
  familyErrorKey = key;
  familyResult.classList.add("hidden");
  familyError.classList.remove("hidden");
  familyError.textContent = t(key);
}

function renderSliderLabels() {
  $("s-months-label").textContent = t("sc_earner_param", { n: $("s-months").value });
  $("s-drop-label").textContent = t("sc_drop_param", { x: $("s-drop").value });
  $("s-rise-label").textContent = t("sc_housing_param", { y: $("s-rise").value });
}

function scenarioShort(key, d) {
  const sc = d.scenarios[key];
  if (key === "earner_gap") return t("sc_earner_short", { n: sc.months });
  if (key === "income_drop") return t("sc_drop_short", { x: fmtPct(sc.pct) });
  return t("sc_housing_short", { y: fmtPct(sc.pct) });
}

function outcomeText(d) {
  const o = d.outcome;
  if (d.group === "A") return t("out_A", { v: fmt(o.topup_family) });
  if (d.group === "B") return t("out_B", { pc: fmt(o.gap_pc), fam: fmt(o.gap_family), asp: fmt(o.above_asp_pc) });
  const margin = { pc: fmt(o.margin_pc), fam: fmt(o.margin_family) };
  if (d.group === "C") return t("out_C", { ...margin, list: o.failing.map((k) => scenarioShort(k, d)).join("; ") });
  return t("out_D", margin);
}

function assumptionText(a) {
  if (a.field === "housing_cost") return t("as_housing", { v: fmt(a.value), p: fmtPct(a.share_pct) });
  if (a.basis === "no_workers") return t("as_wage_none");
  if (a.basis === "minus_transfers") return t("as_wage_minus", { v: fmt(a.value), n: a.workers });
  return t("as_wage_share", { v: fmt(a.value), p: fmtPct(a.share_pct), n: a.workers });
}

function setStatus(dotId, labelId, status, group) {
  $(dotId).style.background = STATUS_COLOR[status];
  $(labelId).textContent = t("group_" + group);
}

function renderFamilyResult() {
  const d = familyData;
  if (!d) return;
  familyError.classList.add("hidden");
  familyResult.classList.remove("hidden");

  // статус и вывод
  setStatus("r-dot", "r-label", d.status, d.group);
  $("r-sub").textContent = t("result_sub", { v: fmt(d.income_pc), p: fmtPct(d.pct_of_sm) });
  drawMeter(d);
  $("r-outcome").textContent = outcomeText(d);
  $("r-link").classList.toggle("hidden", d.group !== "A");
  $("r-link").firstElementChild.href = `https://egov.kz/cms/${currentLang}/services/pass166_mtszn`;

  $("r-peers").classList.toggle("hidden", !d.peers);
  if (d.peers) {
    $("r-peers").textContent = t("peers", { c: d.peers.n_child, p: fmtPct(d.peers.pct_below_sm), n: fmt(d.peers.n) });
  }

  const items = d.assumptions.length ? d.assumptions.map(assumptionText) : [t("as_none")];
  $("r-assumptions").replaceChildren(
    ...items.map((text) => {
      const li = document.createElement("li");
      li.textContent = text;
      return li;
    })
  );

  // сценарии: что предполагается и как получено число
  const I = fmt(d.income_monthly);
  const W = fmt(d.earner_wage);
  const H = fmt(d.housing_cost);
  const S = d.hh_size;
  const { earner_gap: eg, income_drop: dr, housing_rise: hr } = d.scenarios;
  renderSliderLabels();

  $("sc-earner-assume").textContent = t("sc_earner_assume", { n: eg.months, w: W });
  $("sc-earner-avg").textContent = kzt(eg.income_pc);
  $("sc-earner-avg-f").textContent = `(${I} × 12 − ${W} × ${eg.months}) / 12 / ${S} = ${fmt(eg.income_pc)}`;
  $("sc-earner-during").textContent = kzt(eg.during_pc);
  $("sc-earner-during-f").textContent = `(${I} − ${W}) / ${S} = ${fmt(eg.during_pc)}`;

  $("sc-drop-assume").textContent = t("sc_drop_assume", { x: fmtPct(dr.pct) });
  $("sc-drop-v").textContent = kzt(dr.income_pc);
  $("sc-drop-f").textContent = `${I} × (100% − ${fmtPct(dr.pct)}%) / ${S} = ${fmt(dr.income_pc)}`;

  $("sc-housing-assume").textContent = t("sc_housing_assume", { h: H, y: fmtPct(hr.pct), d: fmt(hr.extra_cost) });
  $("sc-housing-v").textContent = kzt(hr.income_pc);
  $("sc-housing-f").textContent = `(${I} − ${H} × ${fmtPct(hr.pct)}%) / ${S} = ${fmt(hr.income_pc)}`;

  // предупреждение — только если сценарий опускает ниже минимума семью, которая была выше
  familyResult.querySelectorAll(".scenario").forEach((el) => {
    el.querySelector(".scenario-flag").classList.toggle("hidden", !d.scenarios[el.dataset.scenario].crosses);
  });

  // а что, если
  const wi = d.what_if;
  $("w-empty").classList.toggle("hidden", Boolean(wi));
  $("w-result").classList.toggle("hidden", !wi);
  if (wi) {
    setStatus("w-before-dot", "w-before-label", d.status, d.group);
    $("w-before-num").textContent = t("wi_line", { v: fmt(d.income_pc) });
    setStatus("w-after-dot", "w-after-label", wi.status, wi.group);
    $("w-after-num").textContent = t("wi_line", { v: fmt(wi.income_pc) });
  }

  $("r-foot").textContent = t("foot", {
    year: d.year,
    region: regionName(d.region.code, d.region.name),
    sm: fmt(d.sm),
    asp: fmt(d.asp),
  });
}

function drawMeter(d) {
  // шкала от 0; правый край — с запасом над минимумом и над доходом семьи, но не дальше
  // 3,2 минимума: иначе у обеспеченной семьи зоны у нуля сжались бы до нечитаемых
  const max = Math.max(d.sm * 1.6, Math.min(Math.max(d.income_pc, d.worst.income_pc) * 1.15, d.sm * 3.2));
  const pct = (v) => Math.max(0, Math.min(100, (v / max) * 100));
  const pAsp = pct(d.asp);
  const pSm = pct(d.sm);

  $("z-a").style.width = `${pAsp}%`;
  $("z-b").style.width = `${pSm - pAsp}%`;

  // подписи границ стоят вплотную к самим границам: черта АСП — слева от своей, минимум — справа
  const bAsp = $("b-asp");
  bAsp.style.right = `${100 - pAsp}%`;
  bAsp.style.maxWidth = `${pAsp}%`;
  bAsp.firstElementChild.textContent = t("tick_asp", { v: fmt(d.asp) });
  const bSm = $("b-sm");
  bSm.style.left = `${pSm}%`;
  bSm.style.maxWidth = `${100 - pSm}%`;
  bSm.firstElementChild.textContent = t("tick_pm", { v: fmt(d.sm) });

  const place = (markerId, flagId, value, text) => {
    const p = pct(value);
    $(markerId).style.left = `${p}%`;
    const flag = $(flagId);
    const flip = p > 50; // подпись растёт от маркера внутрь шкалы, чтобы не вылезать за край
    flag.classList.toggle("flip", flip);
    flag.style.marginLeft = flip ? "0" : `${p}%`;
    flag.style.marginRight = flip ? `${100 - p}%` : "0";
    flag.lastElementChild.textContent = text;
  };
  place("mk-now", "m-now", d.income_pc, t("m_now", { v: fmt(d.income_pc) }));
  place("mk-worst", "m-worst", d.worst.income_pc, t("m_worst", { v: fmt(d.worst.income_pc) }));
}

loadRegions();
renderSliderLabels();

// ---------- Обзор по стране ----------

let overviewData = null;
let overviewStatus = null; // "calculating" | "overview_error" — пока плиток нет

function showOverviewStatus(key) {
  overviewStatus = key;
  const cls = key === "overview_error" ? "error-text" : "hint";
  $("overview-tiles").innerHTML = `<p class="${cls}">${escapeHtml(t(key))}</p>`;
}

async function loadOverview() {
  if (overviewData || overviewStatus === "calculating") return;
  showOverviewStatus("calculating");
  try {
    const res = await fetch("/api/summary");
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
  $("overview-hint").textContent = t("overview_hint", {
    n: fmt(data.total_households),
    lo: fmt(data.sm_min),
    hi: fmt(data.sm_max),
    p: fmtPct(data.pct_below_sm),
  });
  $("overview-note").textContent = t("overview_note", { rel: fmt(data.relative_poverty_line) });

  const order = ["A", "B", "C", "D"]; // по возрастанию дохода
  $("overview-tiles").innerHTML = order
    .map((g) => {
      const grp = data.groups[g];
      return `
        <div class="tile">
          <div class="tile-label">
            <span class="status-dot" style="width:10px;height:10px;background:${STATUS_COLOR[grp.status]}"></span>
            ${escapeHtml(t("group_" + g))}
          </div>
          <div class="tile-value">${fmtPct(grp.pct)}%</div>
          <div class="tile-sub">${fmt(grp.count)} ${escapeHtml(t("households"))}</div>
        </div>`;
    })
    .join("");

  // по регионам: у каждого свой минимум, итог по стране — сумма этих строк
  const head = ["ov_region", "ov_sm", "ov_n", "ov_below"].map((k) => `<th>${escapeHtml(t(k))}</th>`).join("");
  const rows = [...data.by_region]
    .sort((a, b) => b.pct_below_sm - a.pct_below_sm)
    .map(
      (r) =>
        `<tr><td>${escapeHtml(regionName(r.code, r.name))}</td><td>${fmt(r.sm)}</td><td>${fmt(r.n)}</td><td>${fmtPct(
          r.pct_below_sm
        )}%</td></tr>`
    )
    .join("");
  $("overview-region-table").innerHTML = `<tr>${head}</tr>${rows}`;
  $("overview-regions").classList.remove("hidden");
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
  "forecast_caveated",
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

const isTableRow = (line) => line.trim().startsWith("|");
const isTableSeparator = (line) => /^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$/.test(line);
const tableCells = (line) => line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

function renderInline(s) {
  return s.replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function renderTable(lines) {
  const row = (line, tag) => `<tr>${tableCells(line).map((c) => `<${tag}>${renderInline(c)}</${tag}>`).join("")}</tr>`;
  const body = lines.slice(2).map((l) => row(l, "td")).join("");
  return `<div class="table-wrap"><table>${row(lines[0], "th")}${body}</table></div>`;
}

function renderBlock(block) {
  const lines = block.split("\n");
  // таблица может идти сразу за строкой текста, без пустой строки между ними
  const start = lines.findIndex(isTableRow);
  if (start >= 0 && lines.length - start >= 2 && isTableSeparator(lines[start + 1]) && lines.slice(start).every(isTableRow)) {
    const lead = start > 0 ? renderBlock(lines.slice(0, start).join("\n")) : "";
    return lead + renderTable(lines.slice(start));
  }
  const isItem = (l) => /^\s*[-*] /.test(l);
  const firstItem = lines.findIndex(isItem);
  if (firstItem >= 0 && lines.slice(firstItem).every(isItem)) {
    const lead = firstItem > 0 ? renderBlock(lines.slice(0, firstItem).join("\n")) : "";
    const items = lines.slice(firstItem).map((l) => `<li>${renderInline(l.replace(/^\s*[-*] /, ""))}</li>`);
    return `${lead}<ul>${items.join("")}</ul>`;
  }
  if (lines.length === 1 && /^#{1,4} /.test(lines[0])) {
    return `<p><strong>${renderInline(lines[0].replace(/^#{1,4} /, ""))}</strong></p>`;
  }
  return `<p>${renderInline(lines.join("<br>"))}</p>`;
}

// charts — необязательный массив: в него складываются спецификации из блоков ```chart
function renderMarkdownLite(text, charts) {
  // блоки кода вынимаются до разбивки на абзацы — внутри них бывают пустые строки
  const fenced = [];
  const stash = (html) => `\n\n\u0000${fenced.push(html) - 1}\u0000\n\n`;
  const src = String(text).replace(/```([a-zA-Z]*)[ \t]*\n?([\s\S]*?)```/g, (_, lang, code) => {
    if (lang === "chart" && charts) {
      try {
        charts.push(JSON.parse(code));
        return stash(`<div class="chart-host" data-chart="${charts.length - 1}"></div>`);
      } catch (e) {
        // спецификация не разобралась — покажем её как обычный код
      }
    }
    return stash(`<pre><code>${escapeHtml(code)}</code></pre>`);
  });

  return escapeHtml(src)
    .split(/\n{2,}/)
    .map((b) => b.trim())
    .filter(Boolean)
    .map((b) => {
      const m = b.match(/^\u0000(\d+)\u0000$/);
      return m ? fenced[Number(m[1])] : renderBlock(b);
    })
    .join("");
}

function renderReply(bubble, text) {
  const charts = [];
  bubble.innerHTML = renderMarkdownLite(text, charts);
  bubble.querySelectorAll(".chart-host").forEach((host) => {
    const spec = charts[Number(host.dataset.chart)];
    try {
      mountChart(host, spec);
    } catch (e) {
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(spec, null, 2);
      host.replaceChildren(pre);
    }
  });
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
  bubble.innerHTML = `<span class="error-text">${escapeHtml(text)}</span>`;
}

async function send(message) {
  addRow("user", message);
  const typingBubble = addRow("assistant", "");
  // ответ с выполнением кода идёт около минуты — показываем, что работа идёт
  typingBubble.innerHTML = `<span class="typing"><span class="typing-dots"><i></i><i></i><i></i></span><span data-i18n="typing">${escapeHtml(
    t("typing")
  )}</span></span>`;

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
    renderReply(typingBubble, data.reply);
    renderChecklist(typingBubble, data.checklist);
    chat.scrollTop = chat.scrollHeight;
  } catch (e) {
    showChatError(typingBubble, t("no_connection"));
  } finally {
    sendBtn.disabled = false;
  }
}

document.getElementById("suggestions").addEventListener("click", (e) => {
  const btn = e.target.closest(".suggestion");
  if (btn && !sendBtn.disabled) send(btn.textContent);
});

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text || sendBtn.disabled) return;
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
  renderRegions();
  renderSliderLabels();
  if (familyData) renderFamilyResult();
  else if (familyErrorKey) showFamilyError(familyErrorKey);

  if (overviewData) renderOverview();
  else if (overviewStatus) showOverviewStatus(overviewStatus);

  chat.querySelectorAll(".chip[data-key]").forEach((chip) => {
    chip.textContent = `${chip.dataset.mark} ${t("chk_" + chip.dataset.key)}`;
  });
});
