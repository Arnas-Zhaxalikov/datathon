# STAT.DATATHON-2026 — «Котлы чудес»

Дескриптивная аналитика синтетических микроданных БНС АСПР РК за 2021–2024 годы.

**Команда:** Котлы чудес
**Авторы:** Арнас Жаксаликов, Аружан Болат
**Трек:** AI for Official Statistics — ИИ-аналитик поверх микроданных, методология в [`docs/RULES.md`](docs/RULES.md), гипотезы Результата 2 — в [`docs/hypotheses.md`](docs/hypotheses.md)

---

## Qamqor AI: что умеет система

Qamqor AI показывает, кого не видит официальное определение бедности и что изменит та или иная мера поддержки. Система состоит из расчётного ядра ([`qamqor/`](qamqor/)) и веб-приложения ([`agent/`](agent/)).

**Главный принцип.** Каждое число считает Python-ядро. ИИ-ассистент ничего не считает и не решает, кто беден: он вызывает инструменты ядра и объясняет их ответ.

### Карта доходов A–E

Доход семьи на человека в месяц сравнивается с прожиточным минимумом (ПМ) её региона. ПМ — годовые значения БНС по 20 регионам за 2022–2024 годы.

| Уровень | Условие |
|---|---|
| A | выше ПМ, семья проходит все три стресс-теста |
| B | выше ПМ, не проходит один тест |
| C | выше ПМ, не проходит два и более |
| D | ниже ПМ, но не ниже черты АСП (70% ПМ) |
| E | ниже черты АСП |

Стресс-тесты: главный кормилец 3 месяца без заработка (наёмный сохраняет 45%, самозанятый ничего), стоимость жизни +10%, жильё и коммунальные +30%. Есть слабая, базовая и сильная версии.

### Веб-приложение

Три раздела, три языка (английский, казахский, русский), светлая и тёмная тема.

- **Моя семья.** Калькулятор для гражданина, работает без ключа API. Вводятся состав семьи, доход и регион; по желанию — заработок и тип занятости главного кормильца, пенсии и пособия, расходы на жильё. Экран показывает:
  - уровень A–E и положение дохода относительно черты АСП и ПМ региона;
  - три стресс-теста с ползунками: силу каждого можно менять и сразу видеть доход на человека после теста;
  - блок «А что, если»: прибавка к заработку или детское пособие;
  - сравнение с семьями выборки с тем же числом детей в том же регионе (при 30 и более семьях);
  - допущения, принятые для незаполненных полей.
- **Обзор по стране.** Доли людей по уровням A–E и таблица 20 регионов. Без ключа API.
- **Для анализа (ИИ).** Чат с ассистентом (Claude Sonnet 5.5, нужен ключ API). Отвечает на вопросы о бедности, регионах, мерах и шоках, строит графики (линии, столбцы, точки) и показывает под ответом, какие расчёты ядра были вызваны.

### Пять инструментов ассистента

| Инструмент | Что делает |
|---|---|
| `gap_overview` | Доли людей по уровням A–E; три черты (АСП, бюджетный ПМ, региональный ПМ) и «непокрытая полоса» между ними; разбивка по типу семьи, региону, город/село, числу детей; шкала эквивалентности БНС; профиль уровней B и C |
| `simulate` | «Что, если»: шок (заработки, потеря кормильца, коммунальные, цены) и/или мера поддержки (АСП с другой чертой, правило 2025 года, детское пособие, неполный охват); сравнение с базой по бедности, неравенству, стоимости и получателям |
| `compare_policies` | Несколько мер рядом при равном бюджете, в том числе после шока и отдельно для уровней B и C |
| `check_household` | Одна семья по описанию: уровень, доплата АСП, запас над ПМ, какие тесты она не проходит |
| `explain` | Откуда взята цифра и каким правилом получена: источник (форма данных, ключ в `results.json`, проверка), связанные правила и оговорки. Читает граф из 128 узлов и 336 связей, ничего не считает |

### Аналитика ядра

- Доли по годам, регионам, типам семей и город/село; доверительные интервалы.
- Чувствительность к силе стресс-тестов и к выбору черты.
- Три регрессии и разложение связи «ребёнок — доход» (`regression.py`).
- Скрининг без данных о доходе: насколько состав семьи и регион предсказывают доход ниже ПМ (`quick_screen.py`).
- Итоговые таблицы и график трёх черт (`results/final_tables.md`, `results/three_lines.svg`).

### Проверка

- `verify.py` пересчитывает главные цифры независимо от ядра и сверяет, что инструменты ассистента возвращают те же числа: 72 проверки.
- `verify_graph.py` проверяет, что каждая цифра графа равна значению в результатах: 22 проверки.
- `agent/backend/test_core.py` проверяет связь приложения с ядром: 9 тестов.

### Ограничения

- Данные синтетические и без весов: доли — это доли выборки. Допустимы только относительные и методологические выводы, без оценок численности или сумм по стране.
- Бедность считается по денежному доходу; официальная статистика — по потреблению.
- Модель статическая: это эффект «на следующий день», а не прогноз.
- Панели нет: семьи в разные годы разные.
- У АСП есть неденежные условия, которые модель не учитывает; правило АСП изменилось в 2025 году и требует сверки с законом.
- Приложение запускается локально; публикации в сети пока нет.

Запуск приложения — в [`agent/README.md`](agent/README.md), запуск ядра и методика — в [`qamqor/README.md`](qamqor/README.md).

---

## Qamqor AI: what the system does

Qamqor AI shows who is missed by the official poverty definition and what a given support measure would change. It consists of a calculation engine ([`qamqor/`](qamqor/)) and a web application ([`agent/`](agent/)).

**Core principle.** Every number is computed by the Python engine. The AI assistant computes nothing and does not decide who is poor: it calls the engine's tools and explains their output.

### The A–E income map

A household's monthly income per person is compared with the subsistence minimum (SM) of its region. The SMs are Bureau of National Statistics annual values for 20 regions, 2022–2024.

| Level | Condition |
|---|---|
| A | above the SM, passes all three stress tests |
| B | above the SM, fails one test |
| C | above the SM, fails two or more |
| D | below the SM but not below the TSA line (70% of the SM) |
| E | below the TSA line |

TSA is targeted social assistance. Stress tests: the main earner goes 3 months without earnings (an employee keeps 45%, a self-employed person nothing), cost of living +10%, housing and utilities +30%. Weak, base and strong versions exist.

### Web application

Three sections, three languages (English, Kazakh, Russian), light and dark themes.

- **My family.** A calculator for citizens; works without an API key. Inputs are household composition, income and region; optionally the main earner's earnings and employment type, pensions and benefits, and housing costs. The screen shows:
  - the A–E level and where income stands against the TSA line and the regional SM;
  - three stress tests with sliders: change the strength of each and see income per person after the test;
  - a "what if" block: extra earnings or a child allowance;
  - a comparison with sample households with the same number of children in the same region (30 or more households);
  - the assumptions used for fields left empty.
- **Country overview.** Shares of people on levels A–E and a table of 20 regions. No API key needed.
- **For analysis (AI).** A chat with the assistant (Claude Sonnet 5.5, API key required). It answers questions on poverty, regions, measures and shocks, draws charts (line, bar, scatter) and lists under each answer which engine calculations were called.

### The assistant's five tools

| Tool | What it does |
|---|---|
| `gap_overview` | Shares of people on levels A–E; three lines (TSA, budget-law SM, regional SM) and the uncovered band between them; breakdown by household type, region, urban/rural, number of children; the Bureau's equivalence scale; the profile of levels B and C |
| `simulate` | What-if: a shock (wages, loss of the main earner, utilities, prices) and/or a support measure (TSA with another line, the 2025 rule, a child allowance, partial take-up); comparison with the baseline on poverty, inequality, cost and beneficiaries |
| `compare_policies` | Several measures side by side at an equal budget, also after a shock and separately for levels B and C |
| `check_household` | One household from a description: level, TSA top-up, margin above the SM, which tests it fails |
| `explain` | Where a figure comes from and which rule produced it: the source (data form, `results.json` key, check), related rules and caveats. Reads a graph of 128 nodes and 336 edges; computes nothing |

### Engine analytics

- Shares by year, region, household type and urban/rural; confidence intervals.
- Sensitivity to the strength of the stress tests and to the choice of line.
- Three regressions and a decomposition of the child–income link (`regression.py`).
- A screen without income data: how well household composition and region predict income below the SM (`quick_screen.py`).
- Final tables and the three-lines chart (`results/final_tables.md`, `results/three_lines.svg`).

### Verification

- `verify.py` recomputes the headline figures independently of the engine and checks that the assistant's tools return the same numbers: 72 checks.
- `verify_graph.py` checks that every figure in the graph equals the value in the results: 22 checks.
- `agent/backend/test_core.py` checks the bridge between the application and the engine: 9 tests.

### Limitations

- The data is synthetic and has no survey weights: shares are shares of the sample. Only relative and methodological statements are valid, with no national counts or sums.
- Poverty is measured by money income; official statistics use consumption.
- The model is static: a next-day effect, not a forecast.
- There is no panel: households differ between years.
- TSA also has non-income conditions that the model does not cover; the TSA rule changed in 2025 and needs a legal check.
- The application runs locally; it is not published online yet.

How to run the application: [`agent/README.md`](agent/README.md). How to run the engine, and the method: [`qamqor/README.md`](qamqor/README.md).

---

## Конвейер

Семь шагов превращают 4,68 ГБ разнородных CSV в одну аналитическую таблицу, набор агрегатов, готовые графики и слайды.

| Шаг | Скрипт | Что делает |
|---|---|---|
| 1 | `src/01_to_parquet.py` | Распаковывает архив по одному файлу и пишет parquet + zstd: 4,68 ГБ → 300 МБ |
| 2 | `src/02_analyze_labour.py` | Индикаторы рынка труда по T-001, заполненность, дрейф схемы |
| 3 | `src/03_build_merged.py` | Объединяет d002, d004, d006 и d008 в таблицу домохозяйств |
| 4 | `src/04_analyze_merged.py` | Сегменты, депривация, корреляции, регрессия |
| 5 | `src/05_make_charts.py` | Одиннадцать графиков презентации в `outputs/figures/` |
| 6 | `src/06_make_isometrics.py` | Изометрическая графика в `outputs/isometric/` (в текущей вёрстке не используется) |
| 7 | `src/07_build_slides.py` | Сборка HTML-слайдов презентации из графиков и изометрии |
| 8 | `src/08_data_quality_profile.py` | Детерминированный аудит для ИИ-аналитика: дрейф схемы, надёжность корреляций, заполненность, реестр аномалий → `outputs/aggregates/data_quality_flags.json` |

`notebooks/01_descriptive_analysis.ipynb` — тот же путь с пояснениями, 45 ячеек. Сохранён вместе с выводом — таблицы и графики видны прямо на GitHub без запуска. Читает те же `data/pq`, что и скрипты, свои агрегаты пишет в `data/agg`.

---

## Как запустить

```bash
pip install -r requirements.txt

# Архив организатора положить в data/ или указать путь
export DATATHON_ZIP=/path/to/synthetic_microdata_2021-2024_20260921.zip

python src/01_to_parquet.py            # около 5 минут
python src/02_analyze_labour.py
python src/03_build_merged.py
python src/04_analyze_merged.py
python src/05_make_charts.py
python src/06_make_isometrics.py
python src/07_build_slides.py
```

Тема графиков задаётся переменной `CHART_THEME`: `light` по умолчанию, под белые слайды, или `dark` — тогда файлы пишутся в `outputs/figures_dark/`. Изометрия переключается переменной `ISO_THEME` теми же значениями.

Шаг 1 идемпотентен: готовые файлы пропускаются, повторный запуск бесплатен.

Требования: Python 3.10+, 4 ГБ оперативной памяти. Тяжёлые таблицы никогда не грузятся в память целиком — всё считает DuckDB потоково.

---

## Данные

236 таблиц, 72,6 млн строк, 8 форм.

| Форма | Единица наблюдения | Строк |
|---|---|---|
| `1t_god` | предприятие × показатель, год | 30 025 899 |
| `1t_kv` | то же, поквартально | 24 480 242 |
| `d004` | покупка или доход домохозяйства | 8 612 484 |
| `2t` | предприятие × показатель, оплата труда | 7 328 814 |
| `t001` | респондент обследования занятости | 1 885 110 |
| `d008` | член домохозяйства | 169 059 |
| `d002` | домохозяйство, субъективные оценки | 95 542 |
| `d006` | домохозяйство, жильё и благоустройство | 46 743 |

D-серия связывается по ключу `NOMER` без потерь: из 12 000 домохозяйств реестра 11 704 нашлись в жилищной форме, 11 931 в субъективной, 11 958 в расходах. «Сирот» нет.

---

## Результат

`outputs/households_2021_2024.csv` — 48 000 строк (12 000 домохозяйств × 4 года), 37 колонок: состав, жильё, благоустройство, доходы, расходы, субъективные оценки и производные индексы.

- `outputs/aggregates/` — восемнадцать CSV с агрегатами для слайдов
- `outputs/figures/` — одиннадцать графиков презентации, светлая тема
- `outputs/figures_dark/` — те же графики на тёмном фоне
- `outputs/isometric/` — изометрические SVG: сетка фона, стопка слоёв, конвейер, схема слияния
- `outputs/slides/` — HTML-исходники десяти слайдов презентации и индекс `deck.json`. Картинки подключаются из `outputs/figures/`; для хостинга слайдов карту ключ → URL можно передать в `SLIDES_BLOBS` (пример — `blobs.json`)
- `outputs/dashboard.html` — интерактивный дашборд
- `outputs/*_analysis_output.txt` — полный текстовый вывод анализа

---

## Предварительные наблюдения

Подробно — в [`docs/data_notes.md`](docs/data_notes.md).

1. **Восстановлен неподписанный разрез город–село.** Поле `K` не описано в документации, но три независимые формы дают согласованную картину: земельный участок у 85,3% против 20,2%, площадь жилья 82,4 против 65,1 м², неформальная занятость 7,2% против 2,8%.

2. **Найдено ограничение достоверности, отсутствующее в README организатора.** Норма сбережений выходит 66,1%, и даже при самой щедрой оценке продовольствия — 56,9%, против реальных 10–15% по Казахстану. Блоки доходов и расходов откалиброваны независимо друг от друга.

3. **Связи между признаками уровня жизни обнулены, а не ослаблены вдвое.** Благоустройство ~ доход даёт r = 0,015, образование главы ~ доход 0,014, благоустройство ~ удовлетворённость 0,002. Работают только структурные признаки: доля занятых ~ доход на душу 0,336.

4. **Занятость снижается монотонно** с 67,6% до 65,9% за четыре года при устойчивом гендерном разрыве около 7 п.п. Расхождение по регионам гораздо сильнее среднего: Астана +6,3 п.п., ВКО −5,1 п.п.

5. **Бедность определяется числом иждивенцев, а не заработком.** Нижний квинтиль по доходу на душу — 4,99 человека в домохозяйстве, верхний — 2,04. Каждый ребёнок снижает доход на душу примерно на 16%.

---

## Ограничения данных

Учтены в анализе и проговорены явно:

- **Панели между годами нет.** Номера домохозяйств перевыдаются: совпадение региона по одному номеру между 2023 и 2024 составляет 5,4% при случайном уровне 5%. Возможны только повторные срезы.
- **Аномалия генератора.** Алматинская область: доля работающих без договора 4,8% → 40,7% за год при стабильной базе ответов. Без этого региона ряд ровный на 3,0%.
- **Нет справочника `KCP`** для форм 1-Т и 2-Т, поэтому абсолютные величины по ним не интерпретируются. Расчёт средней зарплаты даёт нестабильные 47–774 тг/мес по годам.
- **Дрейф схемы.** `GR1` → `VAL_NUM`, `KATO` → `KATO1`, ОКЭД с 2 знаков до 5, регионов 17 → 20 после реформы 2022 года, предприятий 83 754 → 52 289.
- **Продовольствие не в денежном виде.** Дневник питания (D-001) в архив не включён, вопросы 9–10 записаны в натуральных единицах, поэтому коэффициент Энгеля напрямую не считается.
- **Битая строка.** T-001, 2022, строка 26332: запятая внутри кавычек ломает автоопределение парсера. Решается явным `quote='"'`.
- **Стандартные ошибки занижены** (указано в README организатора): одна синтетическая таблица без репликаций, поэтому тесты либеральны. Значимость трактуется осторожно.

---

## Структура

```
├── src/                 конвейер из семи шагов
├── notebooks/           воспроизводимый разбор с пояснениями
├── outputs/
│   ├── aggregates/      агрегаты для слайдов
│   ├── slides/          HTML-исходники слайдов
│   ├── figures/         графики презентации
│   ├── isometric/       изометрическая графика слайдов
│   ├── households_2021_2024.csv    объединённая таблица
│   └── dashboard.html   интерактивный дашборд
├── docs/data_notes.md   находки и ограничения
└── data/                архив и parquet (не в git)
```

## Источник данных

Синтетические микроданные организатора конкурса (`synthetic_microdata_2021-2024_20260921`). Все записи синтетические, реальных респондентов в наборе нет.
