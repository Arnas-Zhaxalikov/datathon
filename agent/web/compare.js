// Сравнение расчёта по доходу (уровень A–E) с фильтром без дохода (приоритет проверки).
// Отдельный файл без зависимостей: подключается в index.html и проверяется в test_web.js.
//
// «Совпадают» — не только когда оба говорят одно и то же про минимум: семья уровня B или C
// выше минимума, но уязвима, и если фильтр её отметил, он нашёл именно то, что должен.
function compareVerdict(level, priority) {
  const flagged = priority === "high" || priority === "elevated";
  if (level === "D" || level === "E") {
    return flagged ? { key: "cmp_agree_below", tone: "ok" } : { key: "cmp_missed", tone: "bad" };
  }
  if (level === "B" || level === "C") {
    return flagged ? { key: "cmp_agree_vulnerable", tone: "ok" } : { key: "cmp_missed_vulnerable", tone: "warn" };
  }
  return flagged ? { key: "cmp_flag_stable", tone: "neutral" } : { key: "cmp_agree_stable", tone: "ok" };
}

if (typeof module !== "undefined") module.exports = { compareVerdict };
