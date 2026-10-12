"""
Qamqor AI — итоговые таблицы и график / final tables and chart (v0.3).

RU: Читает только results/results.json (его пишет run_baseline.py) и собирает один файл
    results/final_tables.md и график results/three_lines.svg. Сам ничего не считает, кроме
    разностей уже готовых чисел, поэтому числа для слайдов всегда совпадают с ядром.
EN: Reads only results/results.json (written by run_baseline.py) and builds one file,
    results/final_tables.md, plus the chart results/three_lines.svg. It computes nothing itself
    apart from differences of ready numbers, so slide numbers always match the engine.

Запуск / Run:
    python make_tables.py results
"""
import json
import sys
from pathlib import Path

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results")
R = json.loads((out / "results.json").read_text(encoding="utf-8"))
L = []  # строки итогового файла / lines of the final file


def num(v, d=None):
    """RU: число с запятой и пробелом между тысячами; точность — как в results.json (1 или 2 знака).
       EN: a number with a decimal comma and thousands spaces; precision as in results.json (1 or 2 places)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, int):
        s = f"{v:,}"
    else:
        s = f"{v:,.{d if d is not None else (1 if round(v, 1) == v else 2)}f}"
    return s.replace(",", " ").replace(".", ",")


def table(head, rows):
    L.append("| " + " | ".join(head) + " |")
    L.append("|" + "|".join("---" for _ in head) + "|")
    for r in rows:
        L.append("| " + " | ".join(num(c) for c in r) + " |")
    L.append("")


def h(text):
    L.extend(["## " + text, ""])


def p(text):
    L.extend([text, ""])


TIER_RU = {"A_resilient": "A — проходит все тесты", "B_fails_one_test": "B — не проходит один тест",
           "C_fails_two_or_more": "C — не проходит два и более", "D_below_sm": "D — ниже ПМ, выше черты АСП",
           "E_below_tsa_line": "E — ниже черты АСП"}
TIERS = list(TIER_RU)
TEST_RU = {"fail_earner_loss": "Кормилец без заработка", "fail_cost_of_living": "Стоимость жизни",
           "fail_utilities": "Жильё и ЖКУ"}
VERSION_RU = {"weak": "слабая", "base": "базовая", "strong": "сильная"}

L.extend(["# Qamqor AI — итоговые таблицы, v" + R["version"], ""])
p("Единственный источник чисел для слайдов и приложения. Файл собран из `results/results.json` "
  "скриптом `make_tables.py`; `verify.py` проверяет, что те же числа возвращают инструменты ассистента.")
p("**Как читать.** Данные синтетические и без весов: все доли — это доли людей в выборке. Допустимы только "
  "относительные и методологические выводы, оценок численности или сумм по стране здесь нет. Доверительные "
  "интервалы занижены (README организаторов, п. 6). Сравнение лет — иллюстрация: панели нет.")

# ---- 1. Три черты -------------------------------------------------------------------------
h("1. Три черты по годам (доля людей, %)")
table(["Год", "Ниже черты АСП (70% регионального ПМ)", "Ниже бюджетного ПМ", "Ниже регионального ПМ",
       "Непокрытая полоса", "Доля людей ниже ПМ без права на АСП по доходу"],
      [[str(r["year"]), r["below_tsa_line_pct"], r["below_budget_sm_pct"], r["below_regional_sm_pct"],
        r["uncovered_band_pct"], r["share_of_poor_not_eligible_pct"]] for r in R["three_lines_by_year"]])
p("Непокрытая полоса — разница между первой и третьей чертой: люди ниже ПМ своего региона, которым АСП по "
  "доходу не положена. График: `three_lines.svg`.")
table(["Год", "Черта АСП, тг (среднее по людям)", "Бюджетный ПМ, тг", "Региональный ПМ, тг (среднее по людям)"],
      [[str(r["year"]), r["tsa_line_tenge"], r["budget_sm_tenge"], r["regional_sm_tenge"]] for r in R["three_lines_by_year"]])

# ---- 2. Карта доходов A–E -----------------------------------------------------------------
h("2. Карта доходов A–E по годам (доля людей, %, базовые стресс-тесты)")
table(["Год"] + [TIER_RU[t] for t in TIERS] + ["B и C вместе", "Ниже ПМ (D и E)"],
      [[str(r["year"])] + [r["tiers_pct"][t] for t in TIERS] + [r["at_risk_pct"], r["poverty_rate_sm_pct"]]
       for r in R["gap_by_year_regional_line"]])
u = R["uncertainty_2024"]
p("95% доверительные интервалы за 2024 год (перевыборка семей, 200 повторов):")
table(["Показатель", "Значение, %", "95% ДИ"],
      [[name, u[k]["value"], f"{num(u[k]['ci95'][0])}–{num(u[k]['ci95'][1])}"] for k, name in [
          ("poverty_rate_sm_pct", "Ниже регионального ПМ (D и E)"), ("E_below_tsa_line_pct", "E — ниже черты АСП"),
          ("D_below_sm_pct", "D — ниже ПМ, выше черты АСП"), ("C_fails_two_or_more_pct", "C — не проходит два и более"),
          ("B_fails_one_test_pct", "B — не проходит один тест"), ("at_risk_b_and_c_pct", "B и C вместе")]])
p("**Буквы поменялись.** До v0.3 A означало «ниже черты АСП», D — «устойчивые». Теперь A — самые устойчивые, "
  "E — ниже черты АСП. Старые подписи с буквами A–D использовать нельзя.")

# ---- 3. Стресс-тесты ----------------------------------------------------------------------
h("3. Три стресс-теста: три версии (2024)")
st = R["stress_tests"]
table(["Тест", "Слабая", "Базовая", "Сильная"], [
    ["Главный кормилец без заработка, мес. (наёмный сохраняет 45%, самозанятый — ничего)"]
    + [num(st[v]["main_earner_months_lost"], 0) for v in ("weak", "base", "strong")],
    ["Стоимость жизни, рост"] + [f"+{st[v]['cost_of_living_rise']:.0%}" for v in ("weak", "base", "strong")],
    ["Жильё и ЖКУ, рост"] + [f"+{st[v]['utilities_rise']:.0%}" for v in ("weak", "base", "strong")]])
p("Доля людей выше ПМ, не проходящих тест (% всех людей), и уровни при каждой версии:")
table(["Версия"] + [TEST_RU[t] for t in TEST_RU] + ["A", "B", "C", "B и C"],
      [[VERSION_RU[r["version"]]] + [r["above_sm_and_failing_pct"][t] for t in TEST_RU]
       + [r["tiers_pct"]["A_resilient"], r["tiers_pct"]["B_fails_one_test"], r["tiers_pct"]["C_fails_two_or_more"],
          r["at_risk_pct"]] for r in R["levels_by_stress_version_2024"]])
p("Тест «ещё один иждивенец» убран в v0.3.4: он был строже остальных почти для всех семей и один определял "
  "уровень B. Допущение: тип занятости главного кормильца в таблице "
  "«семья-год» неизвестен, 45% применяется к доле зарплаты в трудовом доходе семьи.")

# ---- 4. Региональные ПМ и доля ниже ПМ ------------------------------------------------------
h("4. Регионы: ПМ и доля людей ниже ПМ своего региона")
sm = R["regional_sm_by_year"]
by_year = {r["region"]: r for r in R["below_sm_by_region_by_year"]}
table(["Регион", "ПМ 2022, тг", "ПМ 2023, тг", "ПМ 2024, тг", "Ниже ПМ 2022, %", "Ниже ПМ 2023, %", "Ниже ПМ 2024, %"],
      [[r["region"], sm["2022"][r["region"]], sm["2023"][r["region"]], sm["2024"][r["region"]],
        by_year[r["region"]]["2022"], by_year[r["region"]]["2023"], by_year[r["region"]]["2024"]]
       for r in R["gap_by_region_2024"]])
p("По отдельным регионам доля скачет от года к году, динамику по регионам использовать нельзя.")
table(["Регион, 2024"] + ["A", "B", "C", "D", "E"],
      [[r["region"]] + [r[t] for t in TIERS] for r in R["gap_by_region_2024"]])
table(["Город/село, 2024", "Доля выборки, %"] + ["A", "B", "C", "D", "E"],
      [[{"urban": "город", "rural": "село"}[r["area"]], r["persons_pct_of_sample"]] + [r[t] for t in TIERS]
       for r in R["gap_urban_rural_2024"]])
table(["Число детей, 2024", "Доля выборки, %"] + ["A", "B", "C", "D", "E"],
      [[r["n_child"], r["persons_pct_of_sample"]] + [r[t] for t in TIERS] for r in R["gap_by_children_2024"]])

# ---- 5. Шкала эквивалентности -------------------------------------------------------------
h("5. Шкала эквивалентности БНС (1 + 0,8 за каждого следующего члена семьи)")
table(["Год", "Ниже ПМ, доход на человека, %", "Ниже ПМ, доход на эквивалентного члена, та же черта, %",
       "Были бы переклассифицированы по шкале БНС, % всех людей", "…как доля людей ниже ПМ, %"],
      [[str(r["year"]), r["below_sm_per_capita_pct"], r["below_sm_equivalised_same_line_pct"],
        r["reclassified_out_of_poverty_pct_of_people"], r["reclassified_share_of_the_poor_pct"]]
       for r in R["equivalence_by_year"]])
e = R["equivalence_2024"]
sh = e["same_headcount"]
p(f"Второе чтение, 2024: если поднять черту так, чтобы доля людей ниже неё осталась прежней (множитель "
  f"{num(sh['line_multiplier'], 3)}), местами меняются {num(sh['enter_poverty_pct_of_people'], 2)}% людей в каждую сторону.")
p("Формулировка для выводов: эти люди «были бы переклассифицированы по шкале БНС». АСП по закону считает доход "
  "на человека, поэтому это не ошибка АСП. БНС применяет шкалу к доходам, использованным на потребление, "
  "здесь — к денежному доходу.")
cols = ["Доля выборки, %", "На человека, %", "На эквивалентного члена, та же черта, %", "Та же общая доля, %"]
keys = ["persons_pct_of_sample", "below_sm_per_capita_pct", "below_sm_equivalised_same_line_pct", "below_line_same_headcount_pct"]
for title, block, key in [("Число детей", "by_children", "n_child_group"), ("Число пожилых", "by_elderly", "n_elderly_group"),
                          ("Город/село", "by_urban", "area"), ("Регион", "by_region", "region")]:
    rows = e[block]
    if block == "by_region":
        rows = sorted(rows, key=lambda r: -r["below_sm_per_capita_pct"])
    name = {"urban": "город", "rural": "село"}
    table([title + ", 2024"] + cols, [[name.get(r[key], r[key])] + [r[k] for k in keys] for r in rows])

# ---- 6. Профиль уровней B и C --------------------------------------------------------------
h("6. Уровни B и C: кто это (2024, базовые стресс-тесты)")
G = R["levels_b_c_profile_2024"]["groups"]
order = [("B", "B"), ("C", "C"), ("B_and_C", "B и C"), ("A", "A"), ("all", "Все")]
table(["Показатель"] + [n for _, n in order], [
    ["Доля выборки, % людей"] + [G[k]["persons_pct_of_sample"] for k, _ in order],
    ["Медианный доход на человека, тг в месяц"] + [G[k]["median_income_per_capita"] for k, _ in order],
    ["Медианный запас над ПМ, %"] + [G[k]["median_margin_above_sm_pct"] for k, _ in order],
    ["В городе, %"] + [G[k]["urban_pct"] for k, _ in order],
    ["Один работающий, %"] + [G[k]["one_earner_pct"] for k, _ in order]]
    + [[f"Детей: {c}, %"] + [G[k]["by_children_pct"].get(c, 0.0) for k, _ in order] for c in ("0", "1", "2", "3", "4+")]
    + [[f"Работающих: {c}, %"] + [G[k]["by_earners_pct"].get(c, 0.0) for k, _ in order] for c in ("0", "1", "2+")])
tests = list(G["B_and_C"]["tests_failed_pct"])
p("Какой стресс-тест не проходит (% людей уровня):")
table(["Тест", "B", "C", "B и C"],
      [[t] + [G[k]["tests_failed_pct"][t] for k in ("B", "C", "B_and_C")] for t in tests])
shocks = list(G["B_and_C"]["below_sm_after_shock_pct"])
p("Какой шок опускает ниже ПМ (% людей уровня, оказавшихся ниже ПМ после шока):")
table(["Шок", "B", "C", "B и C", "A"],
      [[s] + [G[k]["below_sm_after_shock_pct"][s] for k in ("B", "C", "B_and_C", "A")] for s in shocks])
p("Доля уровней B и C внутри региона (% людей региона):")
table(["Регион", "B", "C", "B и C"],
      [[r["region"], r["B_pct"], r["C_pct"], r["B_and_C_pct"]] for r in R["levels_b_c_profile_2024"]["by_region"]])

# ---- 7. Меры при равном бюджете для B и C ----------------------------------------------------
h("7. Меры при равном бюджете для уровней B и C (2024)")
first = R["levels_b_c_equal_budget_2024"][0]
p(f"Группа — уровни B и C до шока ({num(first['group_persons_pct_of_sample'], 2)}% людей). Бюджет каждой меры одинаков: "
  f"{num(int(first['equal_cost_per_capita']))} тг на человека выборки в год (столько стоит доплата до 100% ПМ без шока). "
  "Показано, какая доля группы оказывается ниже ПМ после шока без меры и с каждой мерой.")
for block in R["levels_b_c_equal_budget_2024"]:
    p(f"**{block['shock']}.** Без меры ниже ПМ оказывается {num(block['group_below_sm_after_shock_no_policy_pct'])}% группы.")
    table(["Мера", "Группа ниже ПМ с мерой, %", "Удержано выше ПМ, п.п.", "Получают выплату, % группы",
           "Доля расходов меры, дошедшая до группы, %", "Все люди ниже ПМ с мерой, %"],
          [[r["policy"], r["group_below_sm_after_shock_and_policy_pct"], r["group_kept_above_sm_pct_points"],
            r["group_receives_payment_pct"], r["share_of_spending_to_group_pct"],
            r["all_below_sm_after_shock_and_policy_pct"]] for r in block["results"]])

# ---- 8. Регрессии (regression.py) ----------------------------------------------------------
FACTOR_RU = {"n_child": "Ещё один ребёнок", "n_elderly": "Ещё один пожилой", "n_working_age": "Ещё один взрослый трудоспособного возраста",
             "n_earners": "Ещё один работающий", "urban": "Город (против села)"}
if (out / "regression.json").exists():
    G = json.loads((out / "regression.json").read_text(encoding="utf-8"))
    h("8. Регрессии: что связано с доходом и уровнем (2024)")
    p("Уровень семьи, устойчивые стандартные ошибки. Это связи при прочих равных, а не причины. "
      "Во всех моделях учтён регион.")
    o = G["ols_income_per_person_2024"]
    p(f"**Доход на человека относительно регионального ПМ** (линейная модель, R² = {num(o['r2'], 3)}):")
    table(["Фактор", "Изменение дохода на человека, %", "95% ДИ, %"],
          [[FACTOR_RU[k], v["effect_pct"], f"{num(v['ci95_pct'][0])} … {num(v['ci95_pct'][1])}"] for k, v in o["effects"].items()])
    for key, title in [("logit_poor_2024", "Ниже регионального ПМ (уровни D и E)"),
                       ("logit_levels_b_c_among_nonpoor_2024", "Уровни B и C среди тех, кто выше ПМ")]:
        m = G[key]
        p(f"**{title}** (логистическая модель, псевдо-R² = {num(m['pseudo_r2'], 3)}):")
        table(["Фактор", "Отношение шансов", "95% ДИ", "Средний предельный эффект, п.п."],
              [[FACTOR_RU[k], v["odds_ratio"], f"{num(v['ci95'][0])}–{num(v['ci95'][1])}", v["avg_effect_points"]]
               for k, v in m["effects"].items()])
    cp = G["child_penalty_2024"]
    p("**Как ребёнок связан с доходом** (изменение на одного ребёнка, %):")
    table(["Модель", "Доход на человека", "Доход семьи"],
          [[{"children only": "только число детей",
             "holding adults, elderly, earners, region fixed": "при тех же взрослых, пожилых, работающих и регионе"}[k],
            v["per_person_income_pct_per_child"], v["household_income_pct_per_child"]]
           for k, v in cp.items() if isinstance(v, dict)])
    p(f"Чисто арифметический эффект — тот же доход семьи делится на одного человека больше: "
      f"{num(cp['arithmetic_effect_of_one_more_member_pct'])}%.")

# ---- 9. Быстрый скрининг (quick_screen.py) -------------------------------------------------
if (out / "quick_screen.json").exists():
    Q = json.loads((out / "quick_screen.json").read_text(encoding="utf-8"))
    h("9. Быстрый скрининг: можно ли найти семьи ниже ПМ, не зная дохода")
    p(f"Модель учится на {Q['train_years'][0]}–{Q['train_years'][-1]} годах и проверяется на семьях {Q['test_year']} года. "
      "Доход в признаки не входит. Это первый фильтр перед проверкой дохода: модель не решает, у кого доход ниже ПМ.")
    FS = {"composition_region": "состав семьи и регион", "plus_employment": "+ число работающих", "plus_utilities": "+ расходы на ЖКУ"}
    MN = {"logistic": "логистическая", "boosting": "бустинг"}
    table(["Признаки", "Модель", "AUC", "Найдено из тех, кто ниже ПМ, если отметить 20% людей, %",
           "Верно среди отмеченных, %"],
          [[FS[r["features"]], MN[r["model"]], num(r["auc"], 3), r["flag_top_20pct"]["found_pct"], r["flag_top_20pct"]["correct_pct"]]
           for r in Q["models"] if r["target"] == "poor"])
    RULE = {"3+ children": "3 и более детей", "4+ children": "4 и более детей", "no earner": "нет работающих",
            "one earner and 4+ members": "один работающий и 4+ человека"}
    p("Простые правила для сравнения:")
    table(["Правило", "Отмечено людей, %", "Найдено из тех, кто ниже ПМ, %", "Верно среди отмеченных, %"],
          [[RULE[k], v["flagged_pct_of_people"], v["found_pct"], v["correct_pct"]] for k, v in Q["rules"]["poor"].items()])
    c = Q["targeting_contest_2024"]
    p(f"Способы адресности при равном бюджете ({num(int(c['budget_per_capita_tenge_year']))} тг на человека выборки в год):")
    table(["Способ", "Получают, % людей", "Расходы, дошедшие до тех, кто ниже ПМ, %", "Закрыто дефицита до ПМ, %", "Ниже ПМ после, %"],
          [[r["method"], r["people_receiving_pct"], r["spending_reaching_the_poor_pct"], r["shortfall_closed_pct"],
            r["below_sm_after_pct"]] for r in c["results"]])

# ---- 10. Прогноз без данных о доходе (poverty_challenge.py) ---------------------------------
if (out / "poverty_challenge" / "summary.json").exists():
    C = json.loads((out / "poverty_challenge" / "summary.json").read_text(encoding="utf-8"))
    a = C["feature_sets"]["A"]
    d = a["complex_minus_simple"]
    h("10. Прогноз без данных о доходе: гипотеза H4 (обучение 2022–2023, проверка 2024)")
    p("Эксперимент по образцу Pover-T Tests (`poverty_challenge.py`). Модель видит только состав семьи и регион; "
      "признаков из дохода нет. Подробности и остальные модели — в `poverty_challenge/summary.md`.")
    table(["Модель", "AUC", "Log loss", "Найдено людей ниже ПМ среди 20% с наибольшим риском, %"],
          [[f"Простая ({a['best_simple']})", num(a["simple_metrics"]["auc"], 3), num(a["simple_metrics"]["log_loss"], 3), a["simple_metrics"]["recall_at_20_pct"]],
           [f"Сложная ({a['best_complex']})", num(a["complex_metrics"]["auc"], 3), num(a["complex_metrics"]["log_loss"], 3), a["complex_metrics"]["recall_at_20_pct"]]])
    p(f"Разница AUC (сложная минус простая): {num(d['auc_diff'], 4)}, 95% интервал {num(d['auc_diff_ci95'][0], 4)}–{num(d['auc_diff_ci95'][1], 4)}; "
      f"порог не-хуже — {num(C['thresholds']['h4b_margin_auc'], 2)}.")
    table(["Правило", "Отмечено людей, %", "Правило находит, %", "Модель находит при той же доле, %"],
          [[k.replace("children", "детей"), r["people_flagged_pct"], r["rule_recall_pct"], r["model_recall_pct"]]
           for k, r in a["model_vs_rules_same_share"].items()])
    RU_V = {"supported": "подтверждена", "not supported": "не подтверждена", "rejected": "отвергнута", "inconclusive": "вывод сделать нельзя"}
    p(f"**Вердикты.** H4a (бедность предсказуема без дохода): {RU_V[a['H4a']]}. H4b (простая модель не хуже сложной): "
      f"{RU_V[a['H4b']]}. Число работающих берётся из записей о доходах и в эти вердикты не входит; с ним AUC выше, "
      "но это отдельный прогон чувствительности.")

(out / "final_tables.md").write_text("\n".join(L).rstrip() + "\n", encoding="utf-8", newline="\n")

# ---- График трёх черт / the three-lines chart ------------------------------------------------
# RU: сгруппированные столбцы: год × три черты, значения подписаны. Цвета — фиксированный порядок.
# EN: grouped columns: year × three lines, values labelled. Colours in a fixed order.
rows = R["three_lines_by_year"]
series = [("below_tsa_line_pct", "Ниже черты АСП (70% регионального ПМ)", "#2a78d6"),
          ("below_budget_sm_pct", "Ниже бюджетного ПМ", "#eb6834"),
          ("below_regional_sm_pct", "Ниже регионального ПМ", "#1baf7a")]
W, H, left, right, top, bottom = 760, 420, 56, 20, 86, 44
ymax = 16
y = lambda v: top + (H - top - bottom) * (1 - v / ymax)
gw = (W - left - right) / len(rows)
bw = 24
S = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
     f'font-family="system-ui, Segoe UI, Arial, sans-serif">',
     f'<rect width="{W}" height="{H}" fill="#fcfcfb"/>',
     '<text x="20" y="28" font-size="17" font-weight="600" fill="#0b0b0b">Три черты: доля людей ниже каждой, %</text>',
     '<text x="20" y="48" font-size="12" fill="#52514e">Синтетические данные без весов, доли выборки. '
     'Разница между первым и третьим столбцом — непокрытая полоса.</text>']
lx = 20
for _, name, color in series:
    S.append(f'<rect x="{lx}" y="60" width="12" height="12" rx="2" fill="{color}"/>')
    S.append(f'<text x="{lx + 18}" y="70" font-size="12" fill="#52514e">{name}</text>')
    lx += 30 + 6.6 * len(name)
for v in range(0, ymax + 1, 4):
    S.append(f'<line x1="{left}" x2="{W - right}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#e1e0d9"/>')
    S.append(f'<text x="{left - 8}" y="{y(v) + 4:.1f}" font-size="11" text-anchor="end" fill="#898781">{v}</text>')
for i, r in enumerate(rows):
    cx = left + gw * (i + 0.5)
    for j, (key, _, color) in enumerate(series):
        x = cx + (j - 1) * (bw + 2) - bw / 2
        v = r[key]
        yy, hh = y(v), y(0) - y(v)
        S.append(f'<path d="M{x:.1f},{y(0):.1f}V{yy + 4:.1f}Q{x:.1f},{yy:.1f} {x + 4:.1f},{yy:.1f}H{x + bw - 4:.1f}'
                 f'Q{x + bw:.1f},{yy:.1f} {x + bw:.1f},{yy + 4:.1f}V{y(0):.1f}Z" fill="{color}"/>')
        S.append(f'<text x="{x + bw / 2:.1f}" y="{yy - 6:.1f}" font-size="11" text-anchor="middle" fill="#0b0b0b">{num(v)}</text>')
    S.append(f'<text x="{cx:.1f}" y="{H - bottom + 20}" font-size="12" text-anchor="middle" fill="#52514e">{r["year"]}</text>')
    S.append(f'<text x="{cx:.1f}" y="{H - bottom + 36}" font-size="11" text-anchor="middle" fill="#898781">'
             f'непокрытая полоса {num(r["uncovered_band_pct"])}%</text>')
S.append(f'<line x1="{left}" x2="{W - right}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="#c3c2b7"/>')
S.append("</svg>")
(out / "three_lines.svg").write_text("\n".join(S) + "\n", encoding="utf-8", newline="\n")
print("saved ->", out / "final_tables.md", "and", out / "three_lines.svg")
