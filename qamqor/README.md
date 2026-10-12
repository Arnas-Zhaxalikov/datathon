# Qamqor AI — расчётное ядро / calculation engine (v0.3)

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

**RU.** Группы A–D, стресс-тесты, меры и шоки не менялись. Из-за новых черт итог 2024 года
сдвинулся с 9,0% до 9,1% ниже ПМ; Туркестанская область — с 12,5% до 14,2%.

**EN.** Tiers A–D, stress tests, measures and shocks are unchanged. With the new lines the 2024
headline moved from 9.0% to 9.1% below the SM; Turkestan from 12.5% to 14.2%.

## Файлы / Files

| Файл / File | RU | EN |
|---|---|---|
| `build.py` | Собирает таблицу «семья-год» из D-008 и D-004 | Builds the household-year table from D-008 and D-004 |
| `engine.py` | Все расчёты: группы, меры, шоки, сравнение | All calculations: tiers, measures, shocks, comparison |
| `tools.py` | Четыре инструмента для языковой модели | Four tools for the language model |
| `run_baseline.py` | Первый прогон всех модулей | First run of all modules |
| `results/results.json` | Результаты прогона | Results of the run |
| `verify.py` | Независимая проверка итогов без `engine.py` | An independent check of the results without `engine.py` |
| `ref/regional_sm_annual_2022_2024.csv` | Годовые ПМ по регионам (БНС) | Annual regional SMs (BNS) |

## Запуск / Run

```
pip install pandas numpy
python build.py  <папка с данными / data folder>  out
python run_baseline.py  out/households.csv  results
python verify.py  out/households.csv  ref/regional_sm_annual_2022_2024.csv  results/results.json
```

`<data folder>` — папка, где лежат `d004/`, `d008/` и т.д. / the folder holding `d004/`, `d008/` etc.

## Четыре группы / Four tiers

Доход на человека в месяц сравнивается с прожиточным минимумом (ПМ) / monthly income per
person is compared with the subsistence minimum (SM):

- **A** — ниже черты АСП (70% ПМ) / below the TSA line (70% of SM)
- **B** — ниже ПМ, но выше черты АСП: бедные, которым помощь не положена / below SM but above
  the TSA line: poor yet not eligible
- **C** — выше ПМ, но падают ниже ПМ хотя бы в одном стресс-тесте: «скрытые уязвимые» /
  above SM but falling below it in at least one stress test: the "hidden vulnerable"
- **D** — устойчивые / resilient

Стресс-тесты по умолчанию / default stress tests (`engine.StressTests`):
главный кормилец 3 месяца без заработка; доход −15%; жильё и коммунальные +30% /
main earner loses 3 months of earnings; income −15%; housing and utilities +30%.

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
4. **RU.** Кварталы без интервью (`REZ=2`) пересчитаны на полный год.
   **EN.** Quarters with no interview (`REZ=2`) are scaled to a full year.

## Ограничения / Limitations

- **RU.** Данные синтетические: цифры иллюстративные. **EN.** Synthetic data: figures are illustrative.
- **RU.** Весов нет: доли — это доли выборки. **EN.** No weights: shares are sample shares.
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
