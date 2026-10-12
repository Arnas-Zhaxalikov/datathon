# Qamqor AI — расчётное ядро / calculation engine (v0.3.4)

**RU.** Калькулятор социальной политики на синтетических микроданных STAT.DATATHON-2026.
Находит семьи, которые не считаются бедными, но не выдерживают обычного удара по доходу, и
показывает, что изменит та или иная мера поддержки.

**EN.** A social policy calculator on the STAT.DATATHON-2026 synthetic microdata. It finds
households that are not counted as poor yet cannot absorb an ordinary income shock, and shows
what a given support measure would change.

## Что нового в v0.3 / What is new in v0.3

| | RU | EN |
|---|---|---|
| 1 | Точные годовые ПМ по регионам за 2022–2024 (БНС) вместо приближения по июлю и августу 2024 | Exact annual regional SMs for 2022–2024 (BNS) instead of the July–August 2024 approximation |
| 2 | Региональная черта работает для всех трёх лет | The regional line works for all three years |
| 3 | `engine.three_lines`: три черты рядом и «непокрытая полоса» | `engine.three_lines`: three lines side by side and the "uncovered band" |
| 4 | `engine.equivalence_test`: проверка шкалой эквивалентности БНС | `engine.equivalence_test`: a test with the BNS equivalence scale |
| 5 | `gap_overview` возвращает `three_lines` и, по запросу, `equivalence_scale` | `gap_overview` returns `three_lines` and, on request, `equivalence_scale` |
| 6 | Три стресс-теста в трёх версиях: слабая, базовая, сильная (тест «ещё один иждивенец» убран в v0.3.4) | Three stress tests in three versions: weak, base, strong (the "one more dependant" test was removed in v0.3.4) |
| 7 | Карта доходов A–E вместо групп A–D; **буквы идут в обратную сторону** | The A–E income map replaces tiers A–D; **the letters run the other way** |
| 8 | `check_household` возвращает уровень и список непройденных тестов | `check_household` returns the level and the list of failed tests |
| 9 | `engine.at_risk_profile` и `engine.compare_for_group`: профиль уровней B и C и меры при равном бюджете для них | `engine.at_risk_profile` and `engine.compare_for_group`: the profile of levels B and C and measures at equal budget for them |
| 10 | Убран пересчёт стоимости «на страну»: данные без весов | Scaling of costs "to the country" is removed: the data has no weights |

**RU.** Из-за новых черт итог 2024 года сдвинулся с 9,0% до 9,07% ниже ПМ (95% ДИ 8,4–9,7);
Туркестанская область — с 12,5% до 14,2%. Что изменилось относительно v0.2 и какие старые цифры
больше нельзя использовать — в `CHANGES.md`. Все итоговые таблицы — в `results/final_tables.md`.

**EN.** With the new lines the 2024 headline moved from 9.0% to 9.07% below the SM (95% CI
8.4–9.7); Turkestan from 12.5% to 14.2%. What changed against v0.2 and which old figures must no
longer be used is in `CHANGES.md`. All final tables are in `results/final_tables.md`.

## Файлы / Files

| Файл / File | RU | EN |
|---|---|---|
| `build.py` | Собирает таблицу «семья-год» из D-008 и D-004 | Builds the household-year table from D-008 and D-004 |
| `engine.py` | Все расчёты: группы, меры, шоки, сравнение | All calculations: tiers, measures, shocks, comparison |
| `tools.py` | Шесть инструментов для языковой модели | Six tools for the language model |
| `risk_screen.py` | Оценка риска одной семьи без данных о доходе по сохранённой модели | Income-free risk screen for one household with the saved model |
| `build_graph.py` | Собирает граф правил и происхождения цифр из `results.json` и CSV | Builds the graph of rules and provenance from `results.json` and the CSV |
| `results/graph.json` | Граф: узлы, связи, источник каждой цифры | The graph: nodes, edges, the source of every figure |
| `verify_graph.py` | Проверка графа и инструмента `explain` | A check of the graph and the `explain` tool |
| `run_baseline.py` | Первый прогон всех модулей | First run of all modules |
| `results/results.json` | Результаты прогона | Results of the run |
| `verify.py` | Независимая проверка итогов без `engine.py` и сверка инструментов с `results.json` | An independent check of the results without `engine.py`, plus a tools-versus-`results.json` check |
| `make_tables.py` | Собирает итоговые таблицы и график из `results.json` | Builds the final tables and the chart from `results.json` |
| `results/final_tables.md` | Итоговые таблицы: единственный источник чисел для слайдов | The final tables: the single source of numbers for slides |
| `results/three_lines.svg` | График трёх черт | The three-lines chart |
| `CHANGES.md` | Что изменилось относительно v0.2 и какие цифры устарели | What changed against v0.2 and which figures are retired |
| `ref/regional_sm_annual_2022_2024.csv` | Годовые ПМ по регионам (БНС) | Annual regional SMs (BNS) |

## Запуск / Run

```
pip install pandas numpy scikit-learn statsmodels lightgbm matplotlib
python build.py  <папка с данными / data folder>  out
python run_baseline.py  out/households.csv  results
python regression.py  out/households.csv  results
python quick_screen.py  out/households.csv  results
python make_tables.py  results
python verify.py  out/households.csv  ref/regional_sm_annual_2022_2024.csv  results/results.json
python build_graph.py  results/results.json  ref/regional_sm_annual_2022_2024.csv  results/graph.json
python verify_graph.py  results/graph.json  results/results.json  ref/regional_sm_annual_2022_2024.csv
```

`<data folder>` — папка, где лежат `d004/`, `d008/` и т.д. / the folder holding `d004/`, `d008/` etc.

## Карта доходов A–E / The A–E income map

Доход на человека в месяц сравнивается с прожиточным минимумом (ПМ) своего региона / monthly
income per person is compared with the subsistence minimum (SM) of the household's region:

- **A** — выше ПМ и проходит все стресс-тесты / above the SM and passes every stress test
- **B** — выше ПМ, не проходит один стресс-тест / above the SM, fails one stress test
- **C** — выше ПМ, не проходит два и более / above the SM, fails two or more
- **D** — ниже ПМ, но не ниже черты АСП / below the SM but not below the TSA line
- **E** — ниже черты АСП (70% ПМ) / below the TSA line (70% of the SM)

**RU.** До v0.3 буквы шли наоборот: A — ниже черты АСП, D — устойчивые. Старые подписи с
буквами использовать нельзя.
**EN.** Before v0.3 the letters ran the other way: A — below the TSA line, D — resilient. Old
labels with letters must not be reused.

## Три стресс-теста / Three stress tests

`engine.StressTests`, версии / versions `engine.STRESS_VERSIONS`:

| Тест / Test | Слабая / Weak | Базовая / Base | Сильная / Strong |
|---|---|---|---|
| Главный кормилец без заработка; наёмный сохраняет 45%, самозанятый — ничего / main earner without earnings; an employee keeps 45%, a self-employed person nothing | 2 мес. / months | 3 | 6 |
| Стоимость жизни / cost of living | +5% | +10% | +15% |
| Жильё и коммунальные / housing and utilities | +15% | +30% | +50% |

**RU.** Тест не пройден, если после него доход на человека ниже ПМ. До v0.3.4 был четвёртый
тест, «ещё один иждивенец». Он убран: он был строже остальных почти для всех семей и один
определял уровень B.
**EN.** A test is failed if per-capita income after it is below the SM. Before v0.3.4 there was a
fourth test, "one more dependant". It was removed: it was stricter than the others for almost
every household and alone defined level B.

## Региональные черты / Regional lines

**RU.** Прожиточный минимум у каждого региона свой, и черта АСП считается от регионального ПМ.
Поэтому по умолчанию семья сравнивается с ПМ своего региона. В данных 20 регионов; Астана,
Алматы и Шымкент — отдельные регионы, остальные города выделить нельзя (есть только признак
город/село). Режим выбирается через `engine.set_line_mode(...)` или параметр `line_mode`:

**EN.** Each region has its own subsistence minimum, and the TSA line is based on the regional
SM. So by default a household is compared with its own region's SM. The data has 20 regions;
Astana, Almaty and Shymkent are separate regions, other cities cannot be singled out (there is
only an urban/rural flag). The mode is set with `engine.set_line_mode(...)` or the `line_mode`
parameter:

| Режим / Mode | RU | EN |
|---|---|---|
| `regional` | фактический ПМ своего региона (по умолчанию) | the actual SM of the household's region (default) |
| `actual` | фактический ПМ, единый по стране (43 567, 48 738 и 51 058 тг в 2022–2024) | one national actual SM (43,567, 48,738 and 51,058 tenge in 2022–2024) |
| `budget` | ПМ из закона о бюджете (37 046, 40 567 и 43 407 тг), как в v0.1 | the budget-law SM (37,046, 40,567 and 43,407 tenge), as in v0.1 |

## Три черты / Three lines

**RU.** `engine.three_lines(df, year)` считает на одной выборке долю людей ниже черты АСП
(70% регионального ПМ), ниже бюджетного ПМ и ниже регионального ПМ. Разница между первой и
третьей — люди ниже ПМ, которым помощь по доходу не положена.

**EN.** `engine.three_lines(df, year)` computes, on one sample, the share of people below the TSA
line (70% of the regional SM), below the budget-law SM and below the regional SM. The difference
between the first and the third is people below the SM who are not income-eligible.

## Шкала эквивалентности / Equivalence scale

**RU.** `engine.equivalence_test(df, year, group_by)` пересчитывает доход на эквивалентного члена
семьи по шкале БНС: первый член семьи — 1, каждый следующий — 0,8. Два чтения:
«та же черта» (бедных становится меньше по построению) и «та же доля бедных» (кто меняется
местами). Это проверка чувствительности: АСП по закону считается на человека, а БНС применяет
шкалу к доходам, использованным на потребление, а не к денежному доходу.

**EN.** `engine.equivalence_test(df, year, group_by)` recomputes income per equivalent member with
the BNS scale: the first member counts as 1, each further member as 0.8. Two readings: "same line"
(poverty falls by construction) and "same headcount" (who changes places). This is a sensitivity
test: TSA is per-capita by law, and BNS applies the scale to income used for consumption, not to
money income.

## Быстрый скрининг / Quick screen (v0.3.1)

**RU.** `quick_screen.py` отвечает на вопрос: можно ли, не зная дохода, предсказать, что семья
бедна или близка к бедности (доход ниже 125% ПМ)? Модель учится на 2022–2023 годах и проверяется
на семьях 2024 года. Три набора признаков: состав семьи и регион; плюс число работающих; плюс
расходы на ЖКУ. Доход в признаки не входит. Результаты — в `results/quick_screen.json`:
качество моделей, сравнение с простыми правилами, что важно для модели, состязание способов
адресности при равном бюджете, кого модель пропускает.

**EN.** `quick_screen.py` answers: without knowing income, can we predict that a household is poor
or close to poverty (income below 125% of the SM)? The model is trained on 2022–2023 and tested on
2024 households. Three feature sets: composition and region; plus the number of earners; plus
utility spending. Income is not a feature. Results are in `results/quick_screen.json`: model
quality, comparison with simple rules, what drives the model, a targeting contest at equal budget,
and whom the model misses.

**RU.** Оговорки: модель ранжирует семьи, но уровень риска завышает (обучена на более бедных
годах), поэтому порог задаётся долей отмеченных, а не вероятностью. Число работающих взято из
записей о доходах (доход от труда больше нуля). Модель не решает, кто беден: это первый фильтр
перед проверкой дохода.

**EN.** Caveats: the model ranks households but overstates the level of risk (it is trained on
poorer years), so the cut-off is set as a share flagged, not as a probability. The number of
earners is taken from the income records (labour income above zero). The model does not decide who
is poor: it is a first filter before an income check.

## Регрессии / Regressions (v0.3.2)

**RU.** `regression.py` оценивает, что связано с бедностью при прочих равных: линейная модель
дохода на человека относительно регионального ПМ, логистические модели «ниже ПМ» и «скрытые
уязвимые среди небедных», разложение «детского штрафа» и проверка по годам. Результаты — в
`results/regression.json`. Это связи, а не причины.

**EN.** `regression.py` estimates what is associated with poverty, other things equal: a linear
model of income per person relative to the regional SM, logistic models for "below the SM" and
"levels B and C among the non-poor", a decomposition of the "child penalty" and a check by year.
Results are in `results/regression.json`. These are associations, not causes.

## Четыре модуля / Four modules

| Модуль / Module | Функция / Function |
|---|---|
| Gap Detector | `engine.classify`, `engine.summary`, `tools.call("gap_overview")` |
| Policy Simulator | `engine.scenario(policy=...)` |
| Shock Simulator | `engine.scenario(shock=...)` |
| Policy Comparison | `engine.compare(..., equal_cost_per_capita=...)` |

Сторона гражданина / citizen side: `engine.check_household`.

## Подключение языковой модели / Connecting a language model

**RU.** Передайте `tools.TOOLS` модели как список инструментов. Когда модель просит вызвать
инструмент, выполните `tools.call(name, args)` и верните ей результат. Модель не решает, кто
беден: она только выбирает расчёт и объясняет цифры.

**EN.** Pass `tools.TOOLS` to the model as its tool list. When the model asks for a tool call,
run `tools.call(name, args)` and return the result. The model does not decide who is poor:
it only picks the calculation and explains the numbers.

## Прогноз бедности без дохода / Poverty prediction challenge (H4)

**RU.** `poverty_challenge.py` — эксперимент по образцу конкурса Всемирного банка Pover-T Tests.
Проверяет гипотезу H4: бедность семьи можно предсказать без данных о доходе (H4a), и простая
объяснимая модель делает это не хуже сложной (H4b). Признаки — только состав семьи и регион; число
работающих (`n_earners`) берётся из записей о доходах, поэтому входит только в отдельный прогон
чувствительности. Обучение на 2022–2023, проверка на 2024; дополнительно каждый регион 2024 года
по очереди исключается из обучения. Пороги вердиктов заданы до расчёта и печатаются первыми.

**EN.** `poverty_challenge.py` is an experiment modelled on the World Bank's Pover-T Tests. It tests
H4: household poverty can be predicted without income data (H4a), and a simple, explainable model
does this as well as a complex one (H4b). Features are household composition and region only; the
number of earners (`n_earners`) comes from the income records, so it enters only a separately
labelled sensitivity run. Train on 2022–2023, test on 2024; in addition each 2024 region is held
out once. The verdict thresholds are fixed before the run and printed first.

```
python poverty_challenge.py out/households.csv results/poverty_challenge
python poverty_challenge.py out/households.csv results/poverty_challenge --persons out/persons.csv --raw <data folder>
```

The second form adds feature set B (member aggregates and the household head, from
`out/persons.csv`) and set C (D-006 housing items). Results: `results/poverty_challenge/`
(`summary.md`, `summary.json`, `leaderboard.csv`, `scores_2024.csv`, four charts). The run takes
about two minutes.

## Оценка без данных о доходе / The income-free risk screen

**RU.** `poverty_challenge.py` сохраняет логистическую регрессию в
`results/poverty_challenge/model_logit.joblib` вместе со списком признаков, версией и датой
обучения. Признаки: размер семьи, дети, дети до 7 лет, пожилые, взрослые трудоспособного возраста,
город или село, регион. Дохода, числа работающих и ничего, посчитанного из дохода, среди них нет.
`scores_2024.csv` хранит риск каждой семьи 2024 года: по нему вероятность переводится в место в
рейтинге («риск выше, чем у X% людей выборки»). `risk_screen.py` применяет модель к одной семье.
Это фильтр, а не решение: на 2024 году модель находит около 60% людей ниже минимума среди 20% с
наибольшим риском и остальных пропускает.

**EN.** `poverty_challenge.py` saves a logistic regression to
`results/poverty_challenge/model_logit.joblib` with its feature list, version and training date.
Features: household size, children, children under 7, elderly, working-age adults, urban or rural,
region. No income, no number of earners, nothing derived from income. `scores_2024.csv` holds the
risk of every 2024 household and turns a probability into a place in the ranking. `risk_screen.py`
applies the model to one household. It is a filter, not a decision: on 2024 it finds about 60% of
people below the minimum among the 20% with the highest risk and misses the rest.

```python
tools.call("risk_screen", {"size": 6, "n_child": 4, "region": "Shymkent city"})
```

## Инструменты / Tools

| Инструмент / Tool | RU | EN |
|---|---|---|
| `gap_overview` | Доли людей по уровням A–E, три черты, разбивки | Shares of people on levels A–E, the three lines, breakdowns |
| `simulate` | «Что, если»: шок и/или мера | What-if: a shock and/or a measure |
| `compare_policies` | Несколько мер рядом, при равном бюджете | Several measures side by side, at an equal budget |
| `check_household` | Одна семья по описанию | One household from a description |
| `explain` | Откуда цифра и по какому правилу она получена | Where a figure comes from and which rule produced it |
| `risk_screen` | Оценка риска одной семьи без данных о доходе: место в рейтинге, уровень, факторы | Income-free risk screen for one household: rank, level, factors |

**RU.** `explain` ничего не считает. Он читает `results/graph.json` — граф, который
`build_graph.py` собирает из `results.json`, `quick_screen.json` и CSV прожиточных минимумов без
участия языковой модели. В графе нет ни одной цифры, которой нет в этих файлах; `verify_graph.py`
проверяет это с допуском 0. Узлы: регионы, прожиточные минимумы и черты, уровни A–E, стресс-тесты,
меры, метрики, формы данных, оговорки. Связи: `has_sm`, `defines`, `decides`, `moves`,
`has_metric`, `computed_from`, `limited_by`, `changes`, `refers_to`. В граф входят только АСП и
детские пособия из ядра: правила других программ нужно сверять с законом. У узлов, где это важно,
в `note` стоит `legal check needed`.

**EN.** `explain` computes nothing. It reads `results/graph.json`, the graph that `build_graph.py`
builds from `results.json`, `quick_screen.json` and the subsistence minimum CSV with no language
model involved. The graph holds no figure that is absent from those files; `verify_graph.py` checks
this with zero tolerance. Only TSA and the engine's child allowances are in the graph: the rules of
other programmes need a legal check.

```python
tools.call("explain", {"node": "threshold:tsa_line_70pct"})         # черта АСП / the TSA line
tools.call("explain", {"node": "sm:2024:Astana city"})              # ПМ региона / a regional minimum
tools.call("explain", {"node": "metric:poverty_rate_sm_2024"})      # откуда цифра / where a figure comes from
tools.call("explain", {"node": "Turkestan", "year": 2023, "depth": 2})  # часть названия / part of a name
```

Ответ / the answer: `node`, `neighbors` (`relation`, `direction`, `node`), `path_to_sources`,
`sources` (форма данных, ключ в `results.json`, проверка `verify.py` / data form, `results.json`
key, `verify.py` check), `caveats`. Если узел не найден, возвращаются до пяти похожих id / if the
node is not found, up to five close ids are returned.

## Допущения / Assumptions

1. **RU.** Смысл колонок доходов (`kv_vopr11`, `GR1…GR23`) восстановлен по данным, без бланка
   формы. Уверенно: GR1 зарплата, GR2 самозанятость, GR4 пенсия, GR5 стипендия. Общий доход —
   сумма всех 23 колонок, поэтому итог от расшифровки не зависит.
   **EN.** The meaning of the income columns is inferred from the data, without the form blank.
   Confident: GR1 wages, GR2 self-employment, GR4 pension, GR5 scholarship. Total income is the
   sum of all 23 columns, so the total does not depend on the decoding.
2. **RU.** Региональные ПМ — годовые значения БНС. За 2023 и 2024 годы они взяты из выпусков
   за IV квартал. За 2022 год годового значения по регионам в выпусках нет: оно восстановлено
   методом БНС, (9 × среднее за 9 месяцев + октябрь + ноябрь + декабрь) / 12; тот же расчёт
   по стране совпал с опубликованными итогами с точностью до 2 тенге.
   **EN.** Regional SMs are BNS annual values. For 2023 and 2024 they come from the fourth-quarter
   editions. For 2022 the editions carry no annual regional value: it is rebuilt with the BNS
   method, (9 × nine-month average + October + November + December) / 12; the same calculation
   for the country matched the published totals to within 2 tenge.
3. **RU.** K=1 — город, K=2 — село. **EN.** K=1 urban, K=2 rural.
5. **RU.** Тип занятости главного кормильца в таблице «семья-год» неизвестен. В тесте «кормилец без
   заработка» 45% применяется к доле зарплаты в трудовом доходе всей семьи (`inc_wage / inc_labor`).
   В `check_household` тип задаётся явно (`self_employed`).
   **EN.** The main earner's employment type is not in the household-year table. In the "main earner
   without earnings" test the 45% applies to the wage share of the whole household's labour income
   (`inc_wage / inc_labor`). In `check_household` the type is given explicitly (`self_employed`).
4. **RU.** Кварталы без интервью (`REZ=2`) пересчитаны на полный год.
   **EN.** Quarters with no interview (`REZ=2`) are scaled to a full year.

## Ограничения / Limitations

- **RU.** Данные синтетические: цифры иллюстративные. **EN.** Synthetic data: figures are illustrative.
- **RU.** Весов нет: доли — это доли выборки. Допустимы только относительные и методологические
  выводы; оценок численности или сумм по стране ядро не выдаёт.
  **EN.** No weights: shares are sample shares. Only relative and methodological statements are
  valid; the engine gives no national counts or sums.
- **RU.** Бедность считается по доходу; официальная статистика — по потреблению.
  **EN.** Poverty is income-based; official statistics use consumption.
- **RU.** В данных нет расходов на еду (форма D-003), поэтому нет шока цен на продукты.
  **EN.** The data has no food spending (form D-003), so there is no food price shock.
- **RU.** Какая колонка — АСП, неизвестно, поэтому «положено, но не получает» пока не считается.
  **EN.** Which column is TSA is unknown, so "eligible but not receiving" is not computed yet.
- **RU.** Модель статическая: поведение не меняется, охват полный, если не задан `takeup`.
  **EN.** The model is static: no behavioural change, full take-up unless `takeup` is set.
- **RU.** Кварталы в синтетике слабо связаны между собой, поэтому число работающих в семье
  завышено, а зависимость от одного кормильца занижена.
  **EN.** Quarters are weakly linked in the synthetic data, so the number of earners per household
  is overstated and single-earner dependence is understated.
- **RU.** Сравнение лет: семьи в разные годы разные (панели нет), а по отдельным регионам доля
  ниже ПМ скачет от года к году (например, область Абай: 10,9% → 19,2% → 5,6%). Динамику по
  регионам использовать нельзя; по стране — только как иллюстрацию.
  **EN.** Comparing years: households differ between years (no panel), and for single regions the
  share below the SM jumps from year to year (for example Abai: 10.9% → 19.2% → 5.6%). Regional
  trends should not be used; the national trend is illustrative only.
- **RU.** Доверительные интервалы занижены (README организаторов, п. 6).
  **EN.** Confidence intervals are too narrow (organizers' README, item 6).
