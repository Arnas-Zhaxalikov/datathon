# Заметки по данным / Data notes

Всё ниже измерено на полном архиве (236 таблиц, 72,6 млн строк), а не взято из документации.
Everything below is measured on the full archive (236 tables, 72.6 million rows), not taken from documentation.

---

## 1. Восстановление неподписанных переменных / Recovering undocumented variables

### Поле `K` — это признак город/село / The `K` field is an urban/rural flag

В документации поле не описано и принимает два значения. Его нельзя принимать за номер домохозяйства: домохозяйство внутри года определяется полем `NOMER`.

The field is undocumented and takes two values. It must not be mistaken for a household number: within a year the household is identified by `NOMER`.

Три независимые формы дают согласованную и содержательно ожидаемую картину (2024):
Three independent forms agree, and in the expected direction (2024):

| Показатель / Indicator | K = 1 | K = 2 | Источник / Source |
|---|---|---|---|
| Земельный участок, % / Land ownership, % | 20,2 | **85,3** | d006 |
| Площадь жилья, м² / Dwelling area, m² | 65,1 | 82,4 | d006 |
| Удобств из 42 / Amenities of 42 | 12,7 | 11,9 | d006 |
| Предметов ДП из 46 / Durables of 46 | 15,4 | 16,8 | d006 |
| Размер домохозяйства / Household size | 3,26 | 3,77 | d008 |
| Без трудового договора, % / No labour contract, % | 2,8 | **7,2** | t001 |

Решающий признак — земельный участок: 85,3% против 20,2%. Меньше площади, больше коммуникаций, меньше семья и втрое ниже неформальность — это город (K = 1). Обратная картина — село (K = 2). Направление кодировки стоит подтвердить у организаторов.

The decisive marker is land ownership at 85.3% versus 20.2%. Less space, more utilities, smaller families and a third the informality — that is urban (K = 1). The reverse is rural (K = 2). The coding direction is worth confirming with the organisers.

### Коды `KCP` в формах 1-Т и 2-Т / The `KCP` codes in forms 1-T and 2-T

Официального справочника нет, но группы различимы по профилю значений (2024, годовая 1-Т):
There is no official codebook, yet the groups separate by value profile (2024, annual 1-T):

| Группа / Group | Медиана / Median | Максимум / Max | Гипотеза / Hypothesis |
|---|---|---|---|
| `2514xx` | 4–7 | 4 821 | численность работников / headcount |
| `2521xx`, `2522xx` | 17 542 – 216 035 | 20 286 817 | фонд оплаты труда, тенге / payroll, KZT |

Медиана по `KCP = 252101` растёт со 141 335 в 2021 году до 216 035 в 2024, что похоже на реальную динамику фонда оплаты труда.

The median for `KCP = 252101` rises from 141,335 in 2021 to 216,035 in 2024, consistent with plausible payroll growth.

**Но абсолютные величины считать нельзя.** Попытка вывести среднюю зарплату как отношение фонда к численности даёт 47, 570, 269 и 774 тенге в месяц по годам — бессмысленный и нестабильный результат. Причины: коды иерархичны (шести- и восьмизначные, суммирование по группе даёт двойной счёт), на одно предприятие приходится до 18 строк с одним кодом, и охват выборки меняется.

**Absolute values cannot be computed.** Deriving an average wage as payroll over headcount yields 47, 570, 269 and 774 KZT per month by year — meaningless and unstable. The reasons: the codes are hierarchical (six- and eight-digit, so group sums double-count), a single enterprise carries up to 18 rows under one code, and sample coverage shifts.

До получения справочника формы 1-Т и 2-Т используются только структурно: сколько предприятий, в каких ОКЭД, какого размера.

Until a codebook is available, forms 1-T and 2-T are used structurally only: how many enterprises, in which OKED classes, at what size.

---

## 2. Ограничения достоверности, которых нет в README / Fidelity limitations absent from the README

### Блоки доходов и расходов откалиброваны независимо / Income and expenditure blocks are independently calibrated

| Показатель, 2024 / Indicator, 2024 | Значение / Value |
|---|---|
| Доход на домохозяйство, тг/мес / Household income, KZT/month | 364 525 |
| Расходы, вопросы 1–7, тг/мес / Spending, q1–q7, KZT/month | 124 591 |
| Продовольствие, верхняя граница / Food, upper bound | 40 441 |
| Норма сбережений / Savings rate | **66,1%** |
| Норма сбережений с продовольствием / Savings rate including food | **56,9%** |

Расходы по вопросам 1–7 не включают продовольствие: оно записано в вопросах 9–10 в натуральных и смешанных единицах и в денежное поле `STOIMK` не попадает. Мы посчитали самую щедрую оценку, засчитав все числовые поля вопросов 9–10 как тенге. Норма сбережений падает лишь до 56,9%.

Spending in questions 1–7 excludes food: food sits in questions 9–10 in physical and mixed units and never reaches the monetary field `STOIMK`. We computed the most generous estimate, counting every numeric field of q9–q10 as tenge. The savings rate falls only to 56.9%.

Реальный показатель для Казахстана — порядка 10–15%. Вывод: разрыв не поведенческий, совместное распределение доходов и расходов в синтетике не воспроизведено. В README перечислены ослабленные корреляции и заниженные стандартные ошибки, но не это.

The real figure for Kazakhstan is around 10–15%. Conclusion: the gap is not behavioural — the joint distribution of income and spending was not reproduced. The README lists attenuated correlations and understated standard errors, but not this.

### Межформенные связи обнулены, а не ослаблены вдвое / Cross-form relationships are gone, not halved

README обещает ослабление примерно в два раза. Измерено на 2024 году:
The README promises roughly halved associations. Measured on 2024:

| Связь / Relationship | r | Наблюдений / n |
|---|---|---|
| Доля занятых ~ доход на душу / Employment ratio ~ income pc | 0,336 | 11 948 |
| Площадь жилья ~ размер домохозяйства / Area ~ household size | 0,268 | 11 704 |
| Доход ~ расход / Income ~ spending | 0,241 | 11 948 |
| Площадь ~ число детей / Area ~ children | 0,206 | 11 704 |
| Предметы ДП ~ доход / Durables ~ income | 0,098 | 11 661 |
| Доход на душу ~ удовлетворённость / Income pc ~ satisfaction | **−0,075** | 11 885 |
| Благоустройство ~ доход / Amenities ~ income | **0,015** | 11 661 |
| Образование главы ~ доход / Head education ~ income | **0,014** | 11 947 |
| Благоустройство ~ удовлетворённость / Amenities ~ satisfaction | **0,002** | 11 674 |

Закономерность: связи внутри одной формы сохранились, между формами — практически исчезли.

The pattern: within-form relationships survived, cross-form ones essentially vanished.

**Следствие для выбора темы.** Любая гипотеза вида «более обеспеченные живут в лучших условиях» на этих данных не проверяется. Работают темы, опирающиеся на структуру домохозяйства и разрез город–село.

**Consequence for topic selection.** Any hypothesis of the form "better-off households live in better conditions" is untestable here. What works rests on household structure and the urban/rural split.

---

## 3. Что показывает регрессия / What the regression shows

Зависимая переменная — логарифм дохода на душу, 2024 год, n = 11 543, R² = 0,375.
Dependent variable: log income per capita, 2024, n = 11,543, R² = 0.375.

| Переменная / Variable | Коэффициент / Coefficient | t |
|---|---|---|
| Число детей / Children | **−0,1612** | −27,6 |
| Доля занятых / Employment ratio | **0,2838** | 22,7 |
| Размер домохозяйства / Household size | −0,0448 | −12,2 |
| Село / Rural | 0,0602 | 7,4 |
| Образование главы / Head education | 0,0098 | 1,4 |
| Благоустройство / Amenities | 0,0033 | 1,5 |
| Предметы ДП / Durables | 0,0012 | 1,2 |

Работают только структурные переменные. Образование и благоустройство дают коэффициенты на уровне шума — согласуется с обнулением межформенных связей выше.

Only structural variables work. Education and amenities produce noise-level coefficients, consistent with the collapse of cross-form relationships above.

Стандартные ошибки на синтетике занижены (README организатора), поэтому значимость трактуется осторожно.
Standard errors are understated on synthetic data (organiser's README), so significance is treated cautiously.

---

## 4. Сегменты домохозяйств / Household segments

2024 год, 11 948 домохозяйств с известными доходами и расходами.
2024, 11,948 households with known income and spending.

| Тип / Type | Домохозяйств / Households | Доход на душу, тг/мес / Income pc, KZT/month | Удовлетворённость / Satisfaction |
|---|---|---|---|
| Одиночки / Single | 1 700 | 166 565 | 7,29 |
| Взрослые без детей / Adults, no children | 2 640 | 151 133 | 7,49 |
| Пожилые без детей / Elderly, no children | 1 583 | 145 294 | 7,41 |
| С детьми / With children | 4 455 | 97 173 | 7,58 |
| Многодетные, 3+ / Three or more children | 1 570 | **68 866** | **7,71** |

Доход на душу у многодетных в 2,4 раза ниже, чем у одиночек, а удовлетворённость при этом самая высокая. По квинтилям: нижний — 4,99 человека в домохозяйстве, верхний — 2,04.

Large families have 2.4 times lower income per capita than single-person households, yet report the highest satisfaction. By quintile: the bottom averages 4.99 people per household, the top 2.04.

---

## 5. Дрейф схемы между годами / Schema drift across years

| Что меняется / What changes | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|
| Колонка со значением / Value column | `GR1` | `GR1` | `GR1` | `VAL_NUM` |
| Колонка региона / Region column | `KATO` | `KATO` | `KATO` | `KATO1` |
| Колонок в 1-Т годовой / Columns in annual 1-T | 16 | 18 | 19 | 30 |
| Кодов ОКЭД / OKED codes | 83 (2 знака / digits) | — | — | 539 (4–5 знаков / digits) |
| Регионов / Regions | 17 | 20 | 20 | 20 |
| Предприятий / Enterprises | 70 874 | 77 994 | 83 754 | **52 289** |

Рост числа регионов с 17 до 20 — административная реформа 2022 года: выделены Абай (`10`), Жетісу (`33`), Ұлытау (`62`). Любой региональный ряд за 2021–2024 разрывается в этом месте.

The region count rising from 17 to 20 reflects the 2022 administrative reform, which created Abai (`10`), Jetisu (`33`) and Ulytau (`62`). Any regional series spanning 2021–2024 breaks here.

Падение числа предприятий в 2024 году — смена охвата выгрузки, не экономика.
The 2024 drop in enterprise count is a change in extraction coverage, not economics.

---

## 6. Отсутствие панели / Absence of a panel

`NOMER` содержит год, поэтому годы напрямую не сопоставимы. Косвенная проверка: если порядковые номера сохраняются, домохозяйство под номером N в 2023 и 2024 году должно быть из одного региона.

`NOMER` embeds the year, so years are not directly comparable. An indirect test: if sequence numbers persisted, household N in 2023 and 2024 would come from the same region.

Совпадение региона: **5,4%** при случайном уровне 5% (1 из 20 регионов). Номера перевыдаются каждый год, панели нет, анализ возможен только повторными срезами.

Region agreement: **5.4%** against a 5% random baseline (1 of 20 regions). IDs are reissued annually, there is no panel, and only repeated cross-sections are possible.

---

## 7. Заполненность / Completeness

Низкая заполненность у анкет с ветвлениями — норма, а не ошибка: респондент не отвечает на неприменимые вопросы.

Low completeness in branching questionnaires is normal, not an error: respondents skip inapplicable questions.

| Таблица / Table | Непустых ячеек, % / Non-null cells, % |
|---|---|
| `d006` (жильё, 247 колонок / housing, 247 columns) | 33 |
| `1t_god` 2021 | 42 |
| `d002` оценки / ratings | 45 |
| `d008` реестр / roster | 57–60 |
| мелкие таблицы `d004` / small `d004` tables | 100 |

Проблема возникает там, где заполненность одной переменной меняется между годами: тогда динамика показателя может отражать смену методики сбора. Пример — `ORB_TRDDOG` в T-001: база ответов в Алматинской области падает с 22 733 в 2021 году до 13 204 в 2024.

The problem arises where a single variable's completeness shifts between years: then the indicator's trend may reflect a change in collection method. Example — `ORB_TRDDOG` in T-001: the response base in Almaty region falls from 22,733 in 2021 to 13,204 in 2024.

---

## 8. Технические ловушки / Technical pitfalls

- **T-001, 2022, строка 26332.** Запятая внутри кавычек ломает автоопределение парсера DuckDB и pandas. Решение: явный `quote='"'`.
  **T-001, 2022, line 26332.** A comma inside quotes breaks auto-detection in both DuckDB and pandas. Fix: an explicit `quote='"'`.
- **`sample_size=-1`** при чтении CSV: иначе редкие нечисловые значения обрезаются при определении типов.
  **`sample_size=-1`** when reading CSV: otherwise rare non-numeric values are truncated during type inference.
- **Поле `K` — не ключ.** Ключ домохозяйства внутри года — `NOMER`; внутри домохозяйства человек определяется полем `NOMP`.
  **`K` is not a key.** The household key within a year is `NOMER`; a person inside the household is identified by `NOMP`.
- **Глава домохозяйства** — строка с `RODSTVO = 1`, ровно одна на домохозяйство (12 000 из 12 000).
  **The household head** is the row with `RODSTVO = 1`, exactly one per household (12,000 of 12,000).
