// Проверки интерфейса без браузера. Запуск: node test_web.js
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { compareVerdict } = require("./compare.js");

const read = (name) => fs.readFileSync(path.join(__dirname, name), "utf8");
const ctx = { localStorage: { getItem: () => null, setItem: () => {} }, document: { documentElement: {}, querySelectorAll: () => [] }, navigator: {} };
vm.createContext(ctx);
vm.runInContext(read("i18n.js") + "\nthis.I18N = I18N;", ctx);
const I18N = ctx.I18N;
const LANGS = ["en", "kk", "ru"];
const tests = [];
const test = (name, fn) => tests.push([name, fn]);

test("сравнение с фильтром: шесть случаев", () => {
  const cases = [
    // уровень по доходу, приоритет фильтра → текст и тон
    [["D", "E"], ["high", "elevated"], "cmp_agree_below", "ok"],
    [["D", "E"], ["usual"], "cmp_missed", "bad"],
    [["B", "C"], ["high", "elevated"], "cmp_agree_vulnerable", "ok"],
    [["B", "C"], ["usual"], "cmp_missed_vulnerable", "warn"],
    [["A"], ["high", "elevated"], "cmp_flag_stable", "neutral"],
    [["A"], ["usual"], "cmp_agree_stable", "ok"],
  ];
  let n = 0;
  for (const [levels, priorities, key, tone] of cases) {
    for (const level of levels) for (const priority of priorities) {
      assert.deepStrictEqual(compareVerdict(level, priority), { key, tone }, `${level} + ${priority}`);
      n += 1;
    }
  }
  assert.strictEqual(n, 15); // 5 уровней × 3 приоритета: ни одна пара не пропущена
});

test("тексты сравнения есть на трёх языках и различаются", () => {
  const keys = ["cmp_agree_below", "cmp_missed", "cmp_agree_vulnerable", "cmp_missed_vulnerable", "cmp_flag_stable", "cmp_agree_stable"];
  for (const lang of LANGS) {
    const texts = keys.map((k) => I18N[lang][k]);
    assert.ok(texts.every((x) => typeof x === "string" && x.length > 10), lang);
    assert.strictEqual(new Set(texts).size, keys.length, lang);
  }
});

test("у всех языков один и тот же набор ключей", () => {
  const base = Object.keys(I18N.en).sort();
  for (const lang of LANGS) assert.deepStrictEqual(Object.keys(I18N[lang]).sort(), base, lang);
});

test("все ключи data-i18n из разметки есть в словаре", () => {
  const html = read("index.html");
  const keys = [...html.matchAll(/data-i18n(?:-placeholder)?="([^"]+)"/g)].map((m) => m[1]);
  assert.ok(keys.length > 50);
  for (const key of keys) assert.ok(key in I18N.en, key);
});

// контраст по WCAG: (L1 + 0.05) / (L2 + 0.05)
function luminance(hex) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
const contrast = (a, b) => (Math.max(luminance(a), luminance(b)) + 0.05) / (Math.min(luminance(a), luminance(b)) + 0.05);

test("тёмная тема: серый текст не ниже 4,5:1 на всех фонах", () => {
  const dark = read("style.css").split(':root[data-theme="dark"] {')[1].split("}")[0];
  const v = (name) => dark.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`))[1];
  for (const text of ["text-muted", "text-secondary"]) {
    for (const bg of ["surface", "bg", "bg-alt"]) {
      const ratio = contrast(v(text), v(bg));
      assert.ok(ratio >= 4.5, `${text} on ${bg}: ${ratio.toFixed(2)}`);
    }
  }
  assert.ok(contrast(v("text-muted"), v("surface")) >= 7, "мелкий серый текст на карточке — с запасом");
});

// ---- правила состава семьи (validate.js; те же на сервере — qamqor/household_rules.py) ----
const { validateFamily } = require("./validate.js");
const OK = { size: 4, child: 2, u7: 1, elderly: 1, employed: 1 };
const keys = (f) => validateFamily({ ...OK, ...f }).map((e) => e.key);
const fields = (f) => validateFamily({ ...OK, ...f }).map((e) => e.field);

test("состав: обычная семья проходит", () => {
  assert.deepStrictEqual(validateFamily(OK), []);
});
test("правило 1: размер семьи не меньше 1", () => {
  assert.deepStrictEqual(keys({ size: 0, child: 0, u7: 0, elderly: 0, employed: 0 }), ["err_size"]);
  assert.deepStrictEqual(fields({ size: 0, child: 0, u7: 0, elderly: 0, employed: 0 }), ["f-hh-size"]);
  assert.deepStrictEqual(keys({ size: NaN }), ["err_size"]); // пустое поле
});
test("правило 2: хотя бы один взрослый", () => {
  assert.deepStrictEqual(keys({ size: 2, child: 2, u7: 0, elderly: 0, employed: 0 }), ["err_no_adult"]);
  assert.deepStrictEqual(fields({ size: 2, child: 2, u7: 0, elderly: 0, employed: 0 }), ["f-n-child"]);
  assert.deepStrictEqual(keys({ size: 2, child: 1, u7: 0, elderly: 0, employed: 1 }), []);
});
test("правило 3: детей и людей 63+ вместе не больше размера семьи", () => {
  assert.deepStrictEqual(keys({ size: 4, child: 2, elderly: 3 }), ["err_children_elderly"]);
  assert.deepStrictEqual(fields({ size: 4, child: 2, elderly: 3 }), ["f-elderly"]);
  assert.deepStrictEqual(keys({ size: 4, child: 2, elderly: 2 }), []);
});
test("правило 4: детей до 7 лет не больше, чем детей", () => {
  assert.deepStrictEqual(keys({ u7: 3 }), ["err_child_u7"]);
  assert.deepStrictEqual(fields({ u7: 3 }), ["f-child-u7"]);
  assert.deepStrictEqual(keys({ u7: 2 }), []);
});
test("правило 5: работающих не больше, чем взрослых", () => {
  assert.deepStrictEqual(keys({ employed: 3 }), ["err_employed"]);
  assert.deepStrictEqual(fields({ employed: 3 }), ["f-n-employed"]);
  assert.deepStrictEqual(keys({ employed: 2 }), []);
  assert.deepStrictEqual(keys({ size: 3, child: 0, u7: 0, elderly: 3, employed: 3 }), []); // работающие 63+ считаются
  assert.deepStrictEqual(keys({ employed: null, child: 3, u7: 0, elderly: 0 }), []); // режим без дохода: поле не проверяется
});
test("правило 6: работающих может не быть", () => {
  assert.deepStrictEqual(keys({ size: 2, child: 0, u7: 0, elderly: 2, employed: 0 }), []); // семья пенсионеров
});
test("3 человека, 3 ребёнка, 1 работающий — отклоняется", () => {
  assert.deepStrictEqual(keys({ size: 3, child: 3, u7: 0, elderly: 0, employed: 1 }), ["err_no_adult", "err_employed"]);
});
test("2 человека, 1 ребёнок, 2 работающих — отклоняется", () => {
  assert.deepStrictEqual(keys({ size: 2, child: 1, u7: 0, elderly: 0, employed: 2 }), ["err_employed"]);
});
test("тексты ошибок состава есть на трёх языках", () => {
  for (const lang of LANGS) {
    for (const key of ["err_size", "err_no_adult", "err_children_elderly", "err_child_u7", "err_employed"]) {
      assert.ok(typeof I18N[lang][key] === "string" && I18N[lang][key].length > 10, `${lang} ${key}`);
    }
  }
});

let failed = 0;
for (const [name, fn] of tests) {
  try {
    fn();
    console.log("ok   " + name);
  } catch (e) {
    failed += 1;
    console.log("FAIL " + name + ": " + e.message);
  }
}
console.log(failed ? `${failed} failed` : `${tests.length} passed`);
process.exit(failed ? 1 : 0);
