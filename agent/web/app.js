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
    tabs.forEach((b) => {
      b.classList.toggle("active", b === btn);
      // aria-current сообщает программам чтения с экрана, какой раздел открыт
      if (b === btn) b.setAttribute("aria-current", "page");
      else b.removeAttribute("aria-current");
    });
    Object.values(panels).forEach((p) => p.classList.remove("active"));
    const panel = panels[btn.dataset.tab];
    panel.classList.add("active");
    document.getElementById("main").scrollTop = 0;
    if (btn.dataset.tab === "overview") loadOverview();
  });
});

// ---------- Моя семья ----------
// Все числа приходят из /api/classify, а туда — из расчётного ядра qamqor/engine.py.
// Здесь только подстановка в готовую разметку и тексты на языке интерфейса.

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
const fmtPct = (v) => Number(v).toLocaleString(LOCALES[currentLang], { maximumFractionDigits: 2 });
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

// ползунки трёх стресс-тестов: id → поле запроса и подпись
const SLIDERS = [
  { id: "s-months", field: "months_without_wage", label: "sc_earner_param", v: "n" },
  { id: "s-col", field: "cost_of_living_pct", label: "sc_col_param", v: "x" },
  { id: "s-rise", field: "housing_rise_pct", label: "sc_housing_param", v: "y" },
];

const CITY_REGIONS = [71, 75, 79]; // Астана, Алматы, Шымкент целиком городские
// приоритет проверки: красный, оранжевый, серый — зелёного нет, «обычный» не значит «всё хорошо»
const PRIO_COLOR = { high: "var(--status-critical)", elevated: "var(--status-serious)", usual: "var(--text-muted)" };

// режим экрана: "income" — доход известен, полный расчёт; "screen" — дохода нет, только оценка
let familyMode = "income";
let riskData = null;
let riskErrorKey = null;
let riskSeq = 0;
let calcSeq = 0;

function familyPayload() {
  const payload = {
    hh_size: Number($("f-hh-size").value),
    n_child: Number($("f-n-child").value),
    n_employed: Number($("f-n-employed").value),
    income_monthly: Number($("f-income").value),
    region: Number($("f-region").value),
    earner_wage: optNum("f-earner-wage"),
    earner_self_employed: $("f-self-employed").checked,
    transfers: optNum("f-transfers"),
    housing_cost: optNum("f-housing"),
    whatif_extra_wage: optNum("w-wage") || 0,
    whatif_child_allowance: optNum("w-allowance") || 0,
  };
  SLIDERS.forEach((s) => (payload[s.field] = Number($(s.id).value)));
  return payload;
}

// оценка без данных о доходе: в запросе нет ни одного поля дохода
function riskPayload() {
  const region = Number($("f-region").value);
  return {
    hh_size: Number($("f-hh-size").value),
    n_child: Number($("f-n-child").value),
    n_child_u7: Number($("f-child-u7").value || 0),
    n_elderly: Number($("f-elderly").value || 0),
    region,
    urban: CITY_REGIONS.includes(region) ? true : $("f-urban").value === "1",
  };
}

// проверка состава до запроса: детей и пожилых не больше, чем людей в семье
function compositionError() {
  const size = Number($("f-hh-size").value);
  const child = Number($("f-n-child").value);
  const u7 = Number($("f-child-u7").value || 0);
  const elderly = Number($("f-elderly").value || 0);
  if (child + elderly > size || u7 > child) return "err_risk_members";
  if (familyMode === "income" && Number($("f-n-employed").value) > size) return "err_members";
  return null;
}

function syncUrbanField() {
  const city = CITY_REGIONS.includes(Number($("f-region").value));
  if (city) $("f-urban").value = "1";
  $("f-urban").disabled = city;
}

function setMode(mode) {
  familyMode = mode;
  // поля дохода в режиме без дохода скрыты и отключены: они не проверяются и никуда не уходят
  familyForm.querySelectorAll(".income-only").forEach((el) => {
    el.classList.toggle("hidden", mode !== "income");
    el.querySelectorAll("input").forEach((input) => (input.disabled = mode !== "income"));
    if (el.matches("fieldset")) el.disabled = mode !== "income";
  });
  $(mode === "screen" ? "risk-slot-screen" : "risk-slot-income").appendChild($("risk-block"));
  // расчёт по доходу сам не запускается: доход должен ввести человек, а не остаться от значения по умолчанию
  if (mode === "screen" ? familyData || riskData || familyErrorKey : familyData) runCalculation();
  else renderAll();
}

// «Есть данные о доходе? Рассчитать точно»: режим меняется, состав семьи и регион остаются
$("to-income").addEventListener("click", () => {
  document.querySelector('input[name="family-mode"][value="income"]').checked = true;
  familyData = null;
  familyErrorKey = null;
  setMode("income");
  $("f-income").focus();
  $("f-income").select();
});

// сводка введённого состава: «Семья из 4 человек, 2 детей (1 до 7 лет), Туркестанская область, город»
function familySummary(r) {
  const i = r.inputs;
  const one = (n) => n % 10 === 1 && n % 100 !== 11;
  let s = t(one(i.size) ? "sum_people_one" : "sum_people", { n: i.size });
  s += ", " + (i.n_child === 0 ? t("sum_children_none") : t(one(i.n_child) ? "sum_children_one" : "sum_children", { n: i.n_child }));
  if (i.n_child_u7 > 0) s += " " + t("sum_u7", { n: i.n_child_u7 });
  if (i.n_elderly > 0) s += ", " + t("sum_elderly", { n: i.n_elderly });
  return `${s}, ${riskRegionName(r)}, ${t(i.urban ? "sum_city" : "sum_village")}`;
}

function riskRegionName(r) {
  const region = regionsList.find((x) => x.name === r.inputs.region);
  return region ? regionName(region.code, region.name) : r.inputs.region;
}

// фактор с выбранным значением: «Город (а не село)», «Детей: 5»
function factorLabel(f, r) {
  const i = r.inputs;
  if (f.key === "urban") return t(i.urban ? "risk_fv_city" : "risk_fv_village");
  if (f.key === "region") return t("risk_fv_region", { r: riskRegionName(r) });
  if (f.key === "children") return t("risk_fv_children", { n: i.n_child });
  if (f.key === "elderly") return t("risk_fv_elderly", { n: i.n_elderly });
  return t("risk_fv_household_size", { s: i.size, w: i.n_working_age });
}

document.querySelectorAll('input[name="family-mode"]').forEach((radio) =>
  radio.addEventListener("change", () => radio.checked && setMode(radio.value))
);

async function calculateRisk() {
  const seq = ++riskSeq;
  try {
    const res = await fetch("/api/risk_screen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(riskPayload()),
    });
    const data = await res.json();
    if (seq !== riskSeq) return;
    if (res.ok) {
      riskData = data;
      riskErrorKey = null;
    } else {
      const code = data.detail && data.detail.code;
      riskData = null;
      riskErrorKey = code && I18N[DEFAULT_LANG][code] ? code : "risk_error";
    }
  } catch (err) {
    if (seq !== riskSeq) return;
    riskData = null;
    riskErrorKey = "risk_error";
  }
}

async function calculate() {
  const seq = ++calcSeq; // ответы на устаревшие запросы (ползунок уже сдвинут дальше) отбрасываются
  let res;
  let data;
  try {
    res = await fetch("/api/classify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(familyPayload()),
    });
    data = await res.json();
  } catch (err) {
    if (seq === calcSeq) setFamilyError(res ? "calc_error" : "no_connection");
    return;
  }
  if (seq !== calcSeq) return;
  if (!res.ok) {
    // сервер присылает код ошибки, текст на нужном языке — из словаря
    const code = data.detail && data.detail.code;
    setFamilyError(code && I18N[DEFAULT_LANG][code] ? code : res.status < 500 ? "calc_invalid" : "calc_error");
    return;
  }
  familyData = data;
  familyErrorKey = null;
}

function setFamilyError(key) {
  familyData = null;
  familyErrorKey = key;
}

async function runCalculation() {
  syncUrbanField();
  const bad = compositionError();
  if (bad) {
    setFamilyError(bad);
    riskData = null;
    renderAll();
    return;
  }
  familyErrorKey = null;
  if (familyMode === "income") await Promise.all([calculate(), calculateRisk()]);
  else {
    await calculateRisk();
    if (riskErrorKey) familyErrorKey = riskErrorKey;
  }
  renderAll();
}

familyForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  // свои сообщения об ошибках вместо всплывающих подсказок браузера: они на языке интерфейса
  familyForm.classList.add("was-submitted");
  const btn = familyForm.querySelector('button[type="submit"]');
  btn.disabled = true;
  btn.setAttribute("aria-busy", "true");
  if (familyForm.checkValidity()) await runCalculation();
  else {
    setFamilyError($("f-region").value ? "calc_invalid" : "err_region");
    renderAll();
  }
  btn.disabled = false;
  btn.removeAttribute("aria-busy");
  if (familyErrorKey) {
    const invalid = familyForm.querySelector(":invalid:not(fieldset)");
    if (invalid) invalid.focus();
  }
});

// после первого расчёта любое изменение пересчитывает результат без кнопки
let recalcTimer = null;
function scheduleRecalc(delay) {
  if (!familyData && !riskData && !familyErrorKey) return;
  clearTimeout(recalcTimer);
  recalcTimer = setTimeout(() => {
    if (familyForm.checkValidity()) runCalculation();
  }, delay);
}
familyForm.addEventListener("change", () => {
  syncUrbanField();
  scheduleRecalc(0);
});
SLIDERS.forEach((s) =>
  $(s.id).addEventListener("input", () => {
    renderSliderLabels();
    scheduleRecalc(40);
  })
);
["w-wage", "w-allowance"].forEach((id) => $(id).addEventListener("input", () => scheduleRecalc(250)));

// используется и при сбое загрузки регионов
function showFamilyError(key) {
  setFamilyError(key);
  renderAll();
}

// что показать: зависит от режима и от того, что уже посчитано
function renderAll() {
  const showIncome = familyMode === "income" && Boolean(familyData);
  const showScreen = familyMode === "screen" && Boolean(riskData);
  familyResult.classList.toggle("hidden", !showIncome);
  $("screen-result").classList.toggle("hidden", !showScreen);
  $("family-empty").classList.toggle("hidden", showIncome || showScreen);
  familyError.classList.toggle("hidden", !familyErrorKey);
  if (familyErrorKey) familyError.textContent = t(familyErrorKey);
  // в режиме с доходом сбой оценки не мешает основному расчёту: сообщение отдельно
  const riskOnly = familyMode === "income" && showIncome && riskErrorKey;
  $("risk-error").classList.toggle("hidden", !riskOnly);
  if (riskOnly) $("risk-error").textContent = t(riskErrorKey);
  if (showIncome) renderFamilyResult();
  renderRisk();
}

function renderSliderLabels() {
  SLIDERS.forEach((s) => ($(`${s.id}-label`).textContent = t(s.label, { [s.v]: fmtPct($(s.id).value) })));
}

function assumptionText(a) {
  if (a.field === "housing_cost") return t("as_housing", { v: fmt(a.value), p: fmtPct(a.share_pct) });
  if (a.basis === "no_workers") return t("as_wage_none");
  if (a.basis === "minus_transfers") return t("as_wage_minus", { v: fmt(a.value), n: a.workers });
  return t("as_wage_share", { v: fmt(a.value), p: fmtPct(a.share_pct), n: a.workers });
}

function setStatus(dotId, labelId, status, level) {
  $(dotId).style.background = STATUS_COLOR[status];
  $(labelId).textContent = t("level_" + level);
}

// буква уровня в цвете уровня; на жёлтом фоне текст тёмный, иначе не читается
function setBadge(el, level, status) {
  el.textContent = level;
  el.style.background = STATUS_COLOR[status];
  el.classList.toggle("dark-ink", status === "warning");
}

// название строки шока с его параметром
function shockName(key, d) {
  const s = d.stress;
  if (key === "fail_earner_loss") return t("shock_earner", { n: fmtPct(s.months) });
  if (key === "fail_cost_of_living") return t("shock_col", { x: fmtPct(s.cost_of_living_pct) });
  return t("shock_housing", { y: fmtPct(s.housing_rise_pct) });
}

// что предполагает тест и как получено число: значения — из ответа ядра
function testDetails(key, d) {
  const I = fmt(d.income_monthly);
  const S = d.hh_size;
  const s = d.stress;
  const r = fmt(d.tests.find((x) => x.key === key).income_pc);
  if (key === "fail_earner_loss") {
    const W = fmt(d.earner_wage);
    const lost = 100 - d.earner_keeps_pct;
    return {
      assume: t("sc_earner_assume", { n: fmtPct(s.months), w: W, k: d.earner_keeps_pct }),
      formula: `(${I} × 12 − ${W} × ${fmtPct(s.months)} × ${lost}%) / 12 / ${S} = ${r}`,
    };
  }
  if (key === "fail_cost_of_living") {
    return {
      assume: t("sc_col_assume", { x: fmtPct(s.cost_of_living_pct) }),
      formula: `${I} / (100% + ${fmtPct(s.cost_of_living_pct)}%) / ${S} = ${r}`,
    };
  }
  const H = d.housing_cost;
  return {
    assume: t("sc_housing_assume", { h: fmt(H), y: fmtPct(s.housing_rise_pct), d: fmt((H * s.housing_rise_pct) / 100) }),
    formula: `(${I} − ${fmt(H)} × ${fmtPct(s.housing_rise_pct)}%) / ${S} = ${r}`,
  };
}

function renderFamilyResult() {
  const d = familyData;
  if (!d) return;
  const o = d.outcome;
  const below = d.level === "D" || d.level === "E";

  // итог: буква, одна строка, запас или дефицит, право на АСП
  setBadge($("r-badge"), d.level, d.status);
  $("r-line").textContent = t("verdict_" + d.level);
  $("r-sub").textContent = t("result_sub", { v: fmt(d.income_pc), p: fmtPct(d.pct_of_sm) });
  $("r-gap-pc-label").textContent = t(below ? "fact_gap_pc" : "fact_margin_pc");
  $("r-gap-fam-label").textContent = t(below ? "fact_gap_fam" : "fact_margin_fam");
  $("r-gap-pc").textContent = t("per_month", { v: kzt(below ? o.gap_pc : o.margin_pc) });
  $("r-gap-fam").textContent = t("per_month", { v: kzt(below ? o.gap_family : o.margin_family) });
  $("r-asp-right").textContent = d.level === "E" ? t("asp_yes", { v: fmt(o.topup_family) }) : t("asp_no");
  $("r-link").classList.toggle("hidden", d.level !== "E");
  $("r-link").firstElementChild.href = `https://egov.kz/cms/${currentLang}/services/pass166_mtszn`;

  // шкала и три числа под ней
  drawMeter(d);
  $("st-income").textContent = kzt(d.income_pc);
  $("st-sm").textContent = kzt(d.sm);
  $("st-asp").textContent = kzt(d.asp);

  // что будет при шоке: строка на тест, подробности внутри
  renderSliderLabels();
  familyResult.querySelectorAll(".shock").forEach((el) => {
    const test = d.tests.find((x) => x.key === el.dataset.scenario);
    const details = testDetails(test.key, d);
    el.querySelector("[data-name]").textContent = shockName(test.key, d);
    el.querySelector("[data-value]").textContent = kzt(test.income_pc);
    const badge = el.querySelector("[data-badge]");
    badge.textContent = t(test.failed ? "shock_below" : "shock_above");
    badge.classList.toggle("bad", test.failed);
    el.querySelector("[data-assume]").textContent = details.assume;
    el.querySelector("[data-formula]").textContent = details.formula;
  });

  // сравнение с фильтром: левая половина — расчёт по доходу
  setBadge($("cmp-badge"), d.level, d.status);
  $("cmp-line").textContent = t("verdict_" + d.level);

  const items = d.assumptions.length ? d.assumptions.map(assumptionText) : [t("as_none")];
  $("r-assumptions").replaceChildren(
    ...items.map((text) => {
      const li = document.createElement("li");
      li.textContent = text;
      return li;
    })
  );
  $("peers-fold").classList.toggle("hidden", !d.peers);
  if (d.peers) {
    $("r-peers").textContent = t("peers", { c: d.peers.n_child, p: fmtPct(d.peers.pct_below_sm), n: fmt(d.peers.households) });
  }

  // а что, если
  const wi = d.what_if;
  $("w-empty").classList.toggle("hidden", Boolean(wi));
  $("w-result").classList.toggle("hidden", !wi);
  if (wi) {
    setStatus("w-before-dot", "w-before-label", d.status, d.level);
    $("w-before-num").textContent = t("wi_line", { v: fmt(d.income_pc) });
    setStatus("w-after-dot", "w-after-label", wi.status, wi.level);
    $("w-after-num").textContent = t("wi_line", { v: fmt(wi.income_pc) });
  }

  $("r-foot").textContent = t("foot", { year: d.year, region: regionName(d.region.code, d.region.name), sm: fmt(d.sm), asp: fmt(d.asp) });
}

// сила фактора словами: вклад в логарифм шансов относительно средней семьи выборки
function factorStrength(c) {
  const a = Math.abs(c);
  return a >= 1 ? "strong" : a >= 0.3 ? "moderate" : "weak";
}

function renderRisk() {
  const block = $("risk-block");
  block.classList.toggle("hidden", !riskData);
  $("filter-fold").classList.toggle("hidden", !riskData);
  if (!riskData) return;
  const r = riskData;
  const color = PRIO_COLOR[r.level];
  $("risk-dot").style.background = color;
  $("risk-label").textContent = t("prio_" + r.level);
  $("risk-summary").textContent = familySummary(r);

  // шкала 0–100%: место семьи среди людей выборки; число — мелко под маркером
  const p = Math.max(0, Math.min(100, r.rank_pct));
  $("risk-marker").style.left = `${p}%`;
  const pin = $("risk-pin");
  pin.style.left = `${p}%`;
  pin.classList.toggle("flip", p > 50);
  const rank = t("prio_rank", { p: fmtPct(r.rank_pct), y: r.test_year });
  $("risk-rank").textContent = rank;
  $("risk-scale").setAttribute("aria-label", `${t("prio_" + r.level)}. ${rank}`);

  const shown = r.factors.filter((f) => f.direction !== "neutral").slice(0, 4);
  $("risk-factors").replaceChildren(
    ...(shown.length ? shown : [null]).map((f) => {
      const li = document.createElement("li");
      li.textContent = f
        ? `${f.direction === "raises" ? "↑" : "↓"} ${factorLabel(f, r)} — ${t("str_" + factorStrength(f.contribution))} ${t("risk_" + f.direction)}`
        : t("risk_f_none");
      return li;
    })
  );
  $("risk-caveat-recall").textContent = t("risk_caveat_recall", { p: fmtPct(Math.round(r.recall_top20_pct)) });

  // сравнение двух результатов: оба рядом и одно предложение
  $("cmp-dot").style.background = color;
  $("cmp-prio").textContent = t("prio_" + r.level);
  if (familyData) {
    const verdict = compareVerdict(familyData.level, r.level); // правило — в compare.js
    $("cmp-verdict").textContent = t(verdict.key);
    $("cmp-verdict").className = `compare-verdict tone-${verdict.tone}`;
  }
}

function drawMeter(d) {
  // шкала от 0; правый край — с запасом над минимумом и над доходом семьи, но не дальше
  // 3,2 минимума: иначе у обеспеченной семьи зоны у нуля сжались бы до нечитаемых
  const max = Math.max(d.sm * 1.6, Math.min(d.income_pc * 1.15, d.sm * 3.2));
  const pct = (v) => Math.max(0, Math.min(100, (v / max) * 100));
  const pAsp = pct(d.asp);
  const pSm = pct(d.sm);

  $("z-a").style.width = `${pAsp}%`;
  $("z-b").style.width = `${pSm - pAsp}%`;

  // подписи границ стоят вплотную к самим границам: черта АСП — слева от своей, минимум — справа
  const bAsp = $("b-asp");
  bAsp.style.right = `${100 - pAsp}%`;
  bAsp.style.maxWidth = `${pAsp}%`;
  const bSm = $("b-sm");
  bSm.style.left = `${pSm}%`;
  bSm.style.maxWidth = `${100 - pSm}%`;

  const p = pct(d.income_pc);
  $("mk-now").style.left = `${p}%`;
  const flag = $("m-now");
  const flip = p > 50; // подпись растёт от маркера внутрь шкалы, чтобы не вылезать за край
  flag.classList.toggle("flip", flip);
  flag.style.marginLeft = flip ? "0" : `${p}%`;
  flag.style.marginRight = flip ? `${100 - p}%` : "0";
  flag.lastElementChild.textContent = t("m_now", { v: fmt(d.income_pc) });
}

loadRegions();
renderSliderLabels();
setMode("income");

// ---------- Обзор по стране ----------
// Данные — инструмент ядра gap_overview с разбивкой по регионам.

let overviewData = null;
let overviewStatus = null; // "calculating" | "overview_error" — пока плиток нет
const LEVELS = ["A", "B", "C", "D", "E"];

function showOverviewStatus(key) {
  overviewStatus = key;
  const cls = key === "overview_error" ? "form-error" : "card-lead";
  $("overview-status").innerHTML = `<p class="${cls}" role="status">${escapeHtml(t(key))}</p>`;
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
    n: fmt(data.persons_in_sample),
    h: fmt(data.households_in_sample),
    lo: fmt(data.sm_min),
    hi: fmt(data.sm_max),
    p: fmtPct(data.pct_below_sm),
    r: fmtPct(data.pct_at_risk),
  });
  $("overview-note").textContent = t("overview_note");
  $("overview-status").replaceChildren();

  // полоса долей; подписи и точные числа — в плитках под ней, они же служат легендой
  $("overview-dist").innerHTML = LEVELS.map(
    (g) => `<div class="dist-seg" style="flex:${data.levels[g].pct} 1 0;background:${STATUS_COLOR[data.levels[g].status]}"></div>`
  ).join("");
  $("overview-dist").setAttribute(
    "aria-label",
    LEVELS.map((g) => `${t("level_" + g)}: ${fmtPct(data.levels[g].pct)}%`).join("; ")
  );
  $("overview-tiles").innerHTML = LEVELS.map((g) => {
    const lvl = data.levels[g];
    return `
        <div class="tile">
          <div class="tile-label">
            <span class="status-dot" style="background:${STATUS_COLOR[lvl.status]}"></span>
            <span>${escapeHtml(t("level_" + g))}</span>
          </div>
          <div class="tile-value">${fmtPct(lvl.pct)}%</div>
          <div class="tile-sub">${escapeHtml(t("ov_people"))}</div>
        </div>`;
  }).join("");
  $("overview-dist-card").classList.remove("hidden");

  // по регионам: у каждого свой минимум
  const head = ["ov_region", "ov_sm", "ov_share", "ov_risk", "ov_below"]
    .map((k) => `<th scope="col">${escapeHtml(t(k))}</th>`)
    .join("");
  const maxPct = Math.max(...data.by_region.map((r) => r.pct_below_sm), 1);
  const rows = [...data.by_region]
    .sort((a, b) => b.pct_below_sm - a.pct_below_sm)
    .map(
      (r) => `<tr>
        <td>${escapeHtml(regionName(r.code, r.name))}</td>
        <td>${fmt(r.sm)}</td>
        <td>${fmtPct(r.persons_pct_of_sample)}</td>
        <td>${fmtPct(r.pct_at_risk)}%</td>
        <td class="bar-cell"><div class="cell-bar"><i style="width:${(70 * r.pct_below_sm) / maxPct}%"></i><span>${fmtPct(
          r.pct_below_sm
        )}%</span></div></td>
      </tr>`
    )
    .join("");
  $("overview-region-table").innerHTML = `<thead><tr>${head}</tr></thead><tbody>${rows}</tbody>`;
  $("overview-regions").classList.remove("hidden");
  renderPrediction(data.prediction);
}

// эксперимент H4: прогноз без данных о доходе; числа — из summary.json эксперимента
function renderPrediction(p) {
  $("overview-pred").classList.toggle("hidden", !p);
  if (!p) return;
  const dec = (v) => Number(v).toLocaleString(LOCALES[currentLang], { minimumFractionDigits: 3, maximumFractionDigits: 3 });
  $("pred-lead").textContent = t("pred_lead", { a: p.train_years[0], b: p.train_years[p.train_years.length - 1], y: p.test_year });
  const tiles = [
    ["pred_auc", dec(p.auc_simple), "pred_auc_sub"],
    ["pred_top20", `${fmtPct(p.recall_top20)}%`, "pred_top20_sub"],
    ["pred_gain", `+${dec(p.auc_diff)}`, "pred_gain_sub"],
  ];
  $("pred-tiles").innerHTML = tiles
    .map(
      ([label, value, sub]) => `
        <div class="tile">
          <div class="tile-label"><span>${escapeHtml(t(label))}</span></div>
          <div class="tile-value">${value}</div>
          <div class="tile-sub">${escapeHtml(t(sub, { lo: dec(p.auc_diff_ci95[0]), hi: dec(p.auc_diff_ci95[1]) }))}</div>
        </div>`
    )
    .join("");
  const head = ["pred_rule", "pred_flagged", "pred_rule_finds", "pred_model_finds"]
    .map((k) => `<th scope="col">${escapeHtml(t(k))}</th>`)
    .join("");
  const rows = p.rules
    .map(
      (r) => `<tr>
        <td>${escapeHtml(t("pred_rule_n", { n: r.min_children }))}</td>
        <td>${fmtPct(r.flagged_pct)}%</td>
        <td>${fmtPct(r.rule_recall_pct)}%</td>
        <td><b>${fmtPct(r.model_recall_pct)}%</b></td>
      </tr>`
    )
    .join("");
  $("pred-table").innerHTML = `<thead><tr>${head}</tr></thead><tbody>${rows}</tbody>`;
  const word = (v) => t("pred_s_" + String(v).replace(/ /g, "_"));
  $("pred-verdict").textContent = t("pred_verdict", { a: word(p.h4a), b: word(p.h4b) });
}

// ---------- Чат (режим "Для анализа") ----------

const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");

let sessionId = sessionStorage.getItem("session_id") || null;

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

// под ответом — какие расчёты ядра были вызваны: числа в ответе берутся только из них
function renderTools(bubble, tools) {
  if (!tools || tools.length === 0) return;
  // раскрывающийся блок: в тексте ответа внутренних имён нет, вызовы видны здесь
  const details = document.createElement("details");
  details.className = "howto";
  const cap = document.createElement("summary");
  cap.dataset.i18n = "how_computed";
  cap.textContent = t("how_computed");
  details.appendChild(cap);
  const box = document.createElement("div");
  box.className = "checklist";
  details.appendChild(box);
  const calls = document.createElement("ul");
  calls.className = "howto-calls";
  tools.forEach((tool) => {
    const li = document.createElement("li");
    li.textContent = `${tool.name}(${JSON.stringify(tool.args)})`;
    calls.appendChild(li);
  });
  details.appendChild(calls);
  // один и тот же расчёт, вызванный несколько раз, показывается один раз со счётчиком
  const counts = new Map();
  tools.forEach((tool) => {
    const key = `${tool.name}|${tool.ok}`;
    counts.set(key, { ...tool, n: (counts.get(key) || { n: 0 }).n + 1 });
  });
  counts.forEach((tool) => {
    const chip = document.createElement("span");
    chip.className = `chip ${tool.ok ? "ok" : "bad"}`;
    chip.dataset.tool = tool.name;
    chip.dataset.n = tool.n;
    chip.dataset.ok = tool.ok ? "1" : "";
    chip.title = tool.name;
    box.appendChild(chip);
  });
  bubble.appendChild(details);
  labelToolChips(box);
}

function labelToolChips(root) {
  root.querySelectorAll(".chip[data-tool]").forEach((chip) => {
    const name = I18N[DEFAULT_LANG]["tool_" + chip.dataset.tool] ? t("tool_" + chip.dataset.tool) : chip.dataset.tool;
    const times = Number(chip.dataset.n) > 1 ? ` ×${chip.dataset.n}` : "";
    chip.textContent = chip.dataset.ok ? `✓ ${name}${times}` : `✗ ${name}${times} — ${t("tool_failed")}`;
  });
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
    renderTools(typingBubble, data.tools);
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
  renderAll();

  if (overviewData) renderOverview();
  else if (overviewStatus) showOverviewStatus(overviewStatus);

  labelToolChips(chat);
});
