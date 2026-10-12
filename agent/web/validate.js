// Правила состава семьи в браузере. Те же правила на сервере — qamqor/household_rules.py.
// Отдельный файл без зависимостей: подключается в index.html и проверяется в test_web.js.
//
//   1. Размер семьи ≥ 1.
//   2. Хотя бы один взрослый: детей ≤ размер − 1.
//   3. Детей + людей 63+ ≤ размер.
//   4. Детей до 7 лет ≤ детей.
//   5. Работающих ≤ размер − детей (работают только взрослые, включая 63+).
//   6. Работающих может быть 0.
//
// f: { size, child, u7, elderly, employed }; employed = null в режиме без дохода.
// Возвращает список { field, key }: id поля формы и ключ текста ошибки.
function validateFamily(f) {
  const errors = [];
  if (!(f.size >= 1)) return [{ field: "f-hh-size", key: "err_size" }];
  if (f.child > f.size - 1) errors.push({ field: "f-n-child", key: "err_no_adult" });
  if (f.child + f.elderly > f.size) errors.push({ field: "f-elderly", key: "err_children_elderly" });
  if (f.u7 > f.child) errors.push({ field: "f-child-u7", key: "err_child_u7" });
  if (f.employed !== null && f.employed !== undefined && f.employed > f.size - f.child) {
    errors.push({ field: "f-n-employed", key: "err_employed" });
  }
  return errors;
}

if (typeof module !== "undefined") module.exports = { validateFamily };
