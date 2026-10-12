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
