// ---------- Языки интерфейса: en (по умолчанию), kk, ru ----------

const I18N = {
  en: {
    tab_family: "My family",
    tab_overview: "Country overview",
    tab_analyst: "Analysis (AI)",
    lang_label: "Language",
    family_title: "Your family profile",
    family_hint: "Nothing is saved — the calculation runs right here, on STAT.DATATHON-2026 synthetic data.",
    f_hh_size: "Family size",
    f_n_child: "Children",
    f_n_employed: "Working family members",
    f_income: "Family income per month, KZT",
    f_settlement: "Where you live",
    city: "City",
    village: "Village",
    calc: "Calculate",
    calculating: "Calculating…",
    calc_error: "Calculation failed",
    calc_invalid: "Please check the values you entered",
    group_A: "Receives / is eligible for TSA",
    group_B: "Poor but invisible to the system",
    group_C: "Hidden vulnerable",
    group_D: "Resilient",
    result_sub: "Income per person is {p}% of the subsistence minimum",
    tick_asp: "TSA: {v}",
    tick_pm: "Subsistence min.: {v}",
    legend_now: "Now: <b>{v}</b> KZT/month per person",
    legend_stress: "In the worst of 3 scenarios: <b>{v}</b> KZT/month",
    title_now: "Now: {v} KZT",
    title_stress: "Worst scenario: {v} KZT",
    per_month: "KZT/month",
    stress_earner_loss: "Breadwinner loses income",
    stress_income_drop15: "Income −15%",
    stress_utility_up30: "Utilities +30%",
    overview_title: "Who official poverty statistics do not see",
    overview_hint:
      "{n} households, 2024. Subsistence minimum ≈ {pm} KZT/month per person (relative line), TSA line ≈ {asp} KZT/month.",
    overview_note:
      "The subsistence-minimum line and the TSA (targeted social assistance) line are relative — 50% and 35% of the year's median per-capita income — not official BNS figures. Methodology: <code>agent/backend/segmentation.py</code>.",
    overview_error: "Failed to load the overview",
    households: "households",
    chat_intro:
      "Ask about employment, income, households or regions in 2021–2024. Before every substantive answer I check it against the data audit — the checks that passed are shown under the answer.",
    chat_placeholder: "For example: how did employment change in Almaty Region?",
    send: "Send",
    avatar_user: "You",
    avatar_ai: "AI",
    typing: "typing…",
    error: "Error",
    no_connection: "No connection to the server",
    chat_no_key:
      "ANTHROPIC_API_KEY is not set — chat mode is unavailable. The family calculator and the country overview work without a key.",
    chk_reported_n_and_missingness: "n and completeness",
    chk_checked_schema_drift: "schema drift",
    chk_checked_correlation_reliability: "correlation reliability",
    chk_flagged_small_sample: "small sample",
    chk_cross_checked_against_priors: "checked against benchmarks",
  },
  kk: {
    tab_family: "Менің отбасым",
    tab_overview: "Ел бойынша шолу",
    tab_analyst: "Талдау (ЖИ)",
    lang_label: "Тіл",
    family_title: "Отбасыңыздың профилі",
    family_hint:
      "Деректер сақталмайды — есеп осы жерде, STAT.DATATHON-2026 синтетикалық деректері бойынша жүргізіледі.",
    f_hh_size: "Отбасы мүшелерінің саны",
    f_n_child: "Балалар саны",
    f_n_employed: "Жұмыс істейтін отбасы мүшелері",
    f_income: "Отбасының айлық табысы, тг",
    f_settlement: "Тұратын жеріңіз",
    city: "Қала",
    village: "Ауыл",
    calc: "Есептеу",
    calculating: "Есептелуде…",
    calc_error: "Есептеу қатесі",
    calc_invalid: "Енгізілген мәндерді тексеріңіз",
    group_A: "АӘК алады / алуға құқылы",
    group_B: "Кедей, бірақ жүйеге көрінбейді",
    group_C: "Жасырын осал",
    group_D: "Орнықты",
    result_sub: "Адам басына шаққандағы табыс — ең төменгі күнкөріс деңгейінің {p}%-ы",
    tick_asp: "АӘК: {v}",
    tick_pm: "Күнкөріс деңгейі: {v}",
    legend_now: "Қазір: адам басына айына <b>{v}</b> тг",
    legend_stress: "3 сценарийдің ең нашарында: айына <b>{v}</b> тг",
    title_now: "Қазір: {v} тг",
    title_stress: "Ең нашар сценарийде: {v} тг",
    per_month: "тг/ай",
    stress_earner_loss: "Асыраушы табысынан айырылады",
    stress_income_drop15: "Табыс −15%",
    stress_utility_up30: "Коммуналдық төлемдер +30%",
    overview_title: "Ресми кедейлік статистикасы кімді көрмейді",
    overview_hint:
      "{n} үй шаруашылығы, 2024 жыл. Ең төменгі күнкөріс деңгейі ≈ адам басына айына {pm} тг (салыстырмалы шек), АӘК шегі ≈ айына {asp} тг.",
    overview_note:
      "Ең төменгі күнкөріс деңгейінің шегі мен АӘК (атаулы әлеуметтік көмек) шегі салыстырмалы — жылдық жан басына шаққандағы медианалық табыстың 50%-ы және 35%-ы; бұл ҰСБ-ның ресми көрсеткіштері емес. Әдіснама: <code>agent/backend/segmentation.py</code>.",
    overview_error: "Шолуды жүктеу мүмкін болмады",
    households: "үй шаруашылығы",
    chat_intro:
      "2021–2024 жылдардағы жұмыспен қамту, табыс, үй шаруашылықтары немесе өңірлер туралы сұраңыз. Әрбір мазмұнды жауаптың алдында мен оны деректер аудитімен салыстырамын — қандай тексерулерден өткені жауаптың астында көрсетіледі.",
    chat_placeholder: "Мысалы: Алматы облысында жұмыспен қамту қалай өзгерді?",
    send: "Жіберу",
    avatar_user: "Сіз",
    avatar_ai: "ЖИ",
    typing: "жазып жатыр…",
    error: "Қате",
    no_connection: "Сервермен байланыс жоқ",
    chat_no_key:
      "ANTHROPIC_API_KEY берілмеген — чат режимі қолжетімсіз. Отбасы калькуляторы мен ел бойынша шолу кілтсіз жұмыс істейді.",
    chk_reported_n_and_missingness: "n және толтырылуы",
    chk_checked_schema_drift: "схема дрейфі",
    chk_checked_correlation_reliability: "байланыс сенімділігі",
    chk_flagged_small_sample: "шағын іріктеме",
    chk_cross_checked_against_priors: "бағдарлармен салыстыру",
  },
  ru: {
    tab_family: "Моя семья",
    tab_overview: "Обзор по стране",
    tab_analyst: "Для анализа (ИИ)",
    lang_label: "Язык",
    family_title: "Профиль вашей семьи",
    family_hint:
      "Данные не сохраняются — расчёт происходит здесь же, на синтетических данных STAT.DATATHON-2026.",
    f_hh_size: "Размер семьи",
    f_n_child: "Детей",
    f_n_employed: "Работающих членов семьи",
    f_income: "Доход семьи в месяц, тг",
    f_settlement: "Где живёте",
    city: "Город",
    village: "Село",
    calc: "Рассчитать",
    calculating: "Считаю…",
    calc_error: "Ошибка расчёта",
    calc_invalid: "Проверьте введённые значения",
    group_A: "Получает/имеет право на АСП",
    group_B: "Бедны, но не видны системе",
    group_C: "Скрыто уязвимы",
    group_D: "Устойчивы",
    result_sub: "Доход на человека — {p}% от прожиточного минимума",
    tick_asp: "АСП: {v}",
    tick_pm: "ПМ: {v}",
    legend_now: "Сейчас: <b>{v}</b> тг/мес на человека",
    legend_stress: "В худшем из 3 сценариев: <b>{v}</b> тг/мес",
    title_now: "Сейчас: {v} тг",
    title_stress: "В худшем сценарии: {v} тг",
    per_month: "тг/мес",
    stress_earner_loss: "Кормилец теряет доход",
    stress_income_drop15: "Доход −15%",
    stress_utility_up30: "Коммунальные +30%",
    overview_title: "Кого не видит официальная статистика бедности",
    overview_hint:
      "{n} домохозяйств, 2024 год. Прожиточный минимум ≈ {pm} тг/мес на человека (относительная черта), черта АСП ≈ {asp} тг/мес.",
    overview_note:
      "Черта прожиточного минимума и черта АСП — относительные (50% и 35% медианного дохода на душу за год), не официальные показатели БНС. Методология: <code>agent/backend/segmentation.py</code>.",
    overview_error: "Не удалось загрузить обзор",
    households: "домохозяйств",
    chat_intro:
      "Спросите про занятость, доходы, домохозяйства или регионы за 2021–2024. Перед каждым содержательным ответом я сверяюсь с аудитом данных — под ответом будет видно, какие проверки прошли.",
    chat_placeholder: "Например: как менялась занятость в Алматинской области?",
    send: "Отправить",
    avatar_user: "Вы",
    avatar_ai: "ИИ",
    typing: "печатает…",
    error: "Ошибка",
    no_connection: "Нет связи с сервером",
    chat_no_key:
      "ANTHROPIC_API_KEY не задан — чат-режим недоступен. Калькулятор семьи и обзор по стране работают без ключа.",
    chk_reported_n_and_missingness: "n и заполненность",
    chk_checked_schema_drift: "дрейф схемы",
    chk_checked_correlation_reliability: "надёжность связи",
    chk_flagged_small_sample: "малая выборка",
    chk_cross_checked_against_priors: "сверка с ориентирами",
  },
};

const LOCALES = { en: "en-US", kk: "kk-KZ", ru: "ru-RU" };
const DEFAULT_LANG = "en";

function readSavedLang() {
  try {
    const saved = localStorage.getItem("lang");
    return saved in I18N ? saved : DEFAULT_LANG;
  } catch (e) {
    return DEFAULT_LANG;
  }
}

let currentLang = readSavedLang();

function t(key, vars) {
  let s = I18N[currentLang][key];
  if (s === undefined) s = I18N[DEFAULT_LANG][key];
  if (s === undefined) return key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, v);
  return s;
}

function fmt(n) {
  return Math.round(n).toLocaleString(LOCALES[currentLang]);
}

function applyStaticTranslations() {
  document.documentElement.lang = currentLang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-html]").forEach((el) => {
    el.innerHTML = t(el.dataset.i18nHtml);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
    el.setAttribute("aria-label", t(el.dataset.i18nAria));
  });
}

function setLang(lang) {
  if (!(lang in I18N)) return;
  currentLang = lang;
  try {
    localStorage.setItem("lang", lang);
  } catch (e) {
    // хранилище недоступно — язык просто не запомнится
  }
  applyStaticTranslations();
  document.dispatchEvent(new CustomEvent("langchange"));
}
