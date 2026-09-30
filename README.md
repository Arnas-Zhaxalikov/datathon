# STAT.DATATHON-2026 — «Котлы чудес»

Дескриптивная аналитика синтетических микроданных БНС АСПР РК за 2021–2024 годы.
Descriptive analytics of the synthetic microdata published by the Bureau of National Statistics of Kazakhstan, 2021–2024.

**Команда / Team:** Котлы чудес
**Авторы / Authors:** Арнас Жаксаликов (Arnas Zhaksalikov), Аружан Болат (Aruzhan Bolat)
**Трек / Track:** аналитика данных + ИИ-компонент / data analysis + AI component

---

## Что здесь / What is here

Конвейер из четырёх шагов, который превращает 4,68 ГБ разнородных CSV в одну аналитическую таблицу и набор проверяемых агрегатов.

A four-step pipeline that turns 4.68 GB of heterogeneous CSV files into a single analytical table and a set of reproducible aggregates.

| Шаг / Step | Скрипт / Script | Что делает / What it does |
|---|---|---|
| 1 | `src/01_to_parquet.py` | Распаковывает архив по одному файлу и пишет parquet+zstd: 4,68 ГБ → 300 МБ / Unpacks one file at a time, writes parquet+zstd: 4.68 GB → 300 MB |
| 2 | `src/02_analyze_labour.py` | Индикаторы рынка труда по T-001, качество данных, дрейф схемы / Labour indicators from T-001, data quality, schema drift |
| 3 | `src/03_build_merged.py` | Объединяет D-002/004/006/008 в таблицу домохозяйств / Merges D-002/004/006/008 into a household table |
| 4 | `src/04_analyze_merged.py` | Анализ на мерджах: сегменты, депривация, корреляции, регрессия / Join-based analysis: segments, deprivation, correlations, regression |

`notebooks/01_descriptive_analysis.ipynb` — тот же путь с пояснениями, 45 ячеек, каждая проверена запуском.
The same path with commentary, 45 cells, every one verified by execution.

---

## Как запустить / How to run

```bash
pip install -r requirements.txt

# Архив организатора положить в data/ или указать путь
# Place the organiser's archive in data/ or point to it
export DATATHON_ZIP=/path/to/synthetic_microdata_2021-2024_20260921.zip

python src/01_to_parquet.py            # ~5 минут / ~5 minutes
python src/02_analyze_labour.py
python src/03_build_merged.py
python src/04_analyze_merged.py
```

Шаг 1 идемпотентен: готовые файлы пропускаются, так что повторный запуск бесплатен.
Step 1 is idempotent: existing files are skipped, so re-running costs nothing.

Требования: Python 3.10+, 4 ГБ оперативной памяти. Тяжёлые таблицы никогда не грузятся в память целиком — всё считает DuckDB потоково.
Requirements: Python 3.10+, 4 GB RAM. Large tables are never loaded whole — DuckDB streams everything.

---

## Данные / The data

236 таблиц, 72,6 млн строк, 8 форм. / 236 tables, 72.6 million rows, 8 forms.

| Форма / Form | Единица наблюдения / Unit | Строк / Rows |
|---|---|---|
| `1t_god` | предприятие × показатель / enterprise × indicator | 30 025 899 |
| `1t_kv` | предприятие × показатель, квартал / enterprise × indicator, quarterly | 24 480 242 |
| `2t` | предприятие × показатель, оплата труда / enterprise × indicator, pay | 7 328 814 |
| `d004` | покупка / доход / purchase / income | 8 612 484 |
| `t001` | респондент обследования занятости / employment survey respondent | 1 885 110 |
| `d008` | член домохозяйства / household member | 169 059 |
| `d002` | домохозяйство, субъективные оценки / household, subjective ratings | 95 542 |
| `d006` | домохозяйство, жильё / household, housing | 46 743 |

D-серия связывается по ключу `NOMER` без потерь: из 12 000 домохозяйств реестра 11 704 нашлись в жилищной форме, 11 931 в субъективной, 11 958 в расходах, «сирот» нет.

The D-series joins on `NOMER` with no losses: of 12,000 households in the roster, 11,704 appear in housing, 11,931 in subjective ratings, 11,958 in expenditure, with no orphans.

---

## Результат / Result

`outputs/households_2021_2024.csv` — 48 000 строк (12 000 домохозяйств × 4 года), 37 колонок: состав, жильё, благоустройство, доходы, расходы, субъективные оценки и производные индексы.

48,000 rows (12,000 households × 4 years), 37 columns: composition, housing, amenities, income, spending, subjective ratings and derived indices.

Агрегаты для слайдов и дашборда — в `outputs/aggregates/`. Полные текстовые выводы — в `outputs/*_analysis_output.txt`. Интерактивный дашборд — `outputs/dashboard.html`.

Aggregates for slides and the dashboard live in `outputs/aggregates/`. Full textual output is in `outputs/*_analysis_output.txt`. The interactive dashboard is `outputs/dashboard.html`.

---

## Предварительные наблюдения / Preliminary observations

Подробно — в [`docs/data_notes.md`](docs/data_notes.md). Кратко:
In detail in [`docs/data_notes.md`](docs/data_notes.md). In brief:

1. **Восстановлен неподписанный разрез город–село.** Поле `K` не описано в документации, но три независимые формы дают согласованную картину: земельный участок у 85,3% против 20,2%, площадь 82,4 против 65,1 м², неформальная занятость 7,2% против 2,8%.
   **An undocumented urban/rural dimension was recovered.** The `K` field is undocumented, yet three independent forms agree: land ownership 85.3% versus 20.2%, area 82.4 versus 65.1 m², informal employment 7.2% versus 2.8%.

2. **Найдено ограничение достоверности, отсутствующее в README.** Норма сбережений выходит 66,1%, и даже при самой щедрой оценке продовольствия — 56,9%, против реальных 10–15% по Казахстану. Блоки доходов и расходов откалиброваны независимо.
   **A fidelity limitation absent from the README was found.** The savings rate comes to 66.1%, and 56.9% even under the most generous food estimate, against a real 10–15% for Kazakhstan. The income and expenditure blocks were calibrated independently.

3. **Межформенные связи обнулены, а не ослаблены вдвое.** README обещает ослабление примерно в два раза; фактически благоустройство ~ доход даёт r = 0,015, образование ~ доход 0,014, благоустройство ~ удовлетворённость 0,002.
   **Cross-form relationships are gone, not halved.** The README promises roughly halved associations; in practice amenities-income gives r = 0.015, education-income 0.014, amenities-satisfaction 0.002.

4. **Занятость снижается монотонно** с 67,6% до 65,9% за четыре года при устойчивом гендерном разрыве около 7 п.п. Расхождение по регионам гораздо сильнее среднего: Астана +6,3 п.п., ВКО −5,1 п.п.
   **Employment declines monotonically** from 67.6% to 65.9% over four years, with a stable gender gap near 7pp. Regional divergence far exceeds the average: Astana +6.3pp, East Kazakhstan −5.1pp.

5. **Бедность определяется числом иждивенцев, а не заработком.** Нижний квинтиль по доходу на душу — 4,99 человека в домохозяйстве, верхний — 2,04. Каждый ребёнок снижает доход на душу примерно на 16%.
   **Poverty is driven by dependants, not earnings.** The bottom income-per-capita quintile averages 4.99 people per household, the top 2.04. Each child reduces income per capita by roughly 16%.

---

## Ограничения данных / Data limitations

Учтены в анализе и проговорены явно / Accounted for in the analysis and stated openly:

- **Панели между годами нет.** Номера домохозяйств перевыдаются: совпадение региона по одному номеру между 2023 и 2024 составляет 5,4% при случайном уровне 5%. Только повторные срезы.
  **No panel across years.** Household IDs are reissued: region agreement for a given ID between 2023 and 2024 is 5.4% against a 5% random baseline. Repeated cross-sections only.
- **Аномалия генератора.** Алматинская область: доля работающих без договора 4,8% → 40,7% за год при стабильной базе ответов. Без этого региона ряд ровный на 3,0%.
  **A generator anomaly.** Almaty region: the no-contract share jumps 4.8% → 40.7% in one year with a stable response base. Excluding it, the series is flat at 3.0%.
- **Нет справочника `KCP`** для форм 1-Т и 2-Т, поэтому абсолютные величины по ним не интерпретируются. Расчёт средней зарплаты даёт нестабильные 47–774 тг/мес по годам.
  **No `KCP` codebook** for forms 1-T and 2-T, so their absolute values are uninterpretable. A wage calculation yields an unstable 47–774 KZT/month across years.
- **Дрейф схемы.** `GR1` → `VAL_NUM`, `KATO` → `KATO1`, ОКЭД с 2 знаков до 5, регионов 17 → 20 после реформы 2022 года, предприятий 83 754 → 52 289.
  **Schema drift.** `GR1` → `VAL_NUM`, `KATO` → `KATO1`, OKED from 2 to 5 digits, regions 17 → 20 after the 2022 reform, enterprises 83,754 → 52,289.
- **Продовольствие не в денежном виде.** Дневник питания (D-001) в архив не включён, вопросы 9–10 записаны в натуральных единицах, поэтому коэффициент Энгеля напрямую не считается.
  **Food is not monetary.** The food diary (D-001) is absent and questions 9–10 are in physical units, so the Engel coefficient cannot be computed directly.
- **Битая строка.** T-001, 2022, строка 26332: запятая внутри кавычек ломает автоопределение парсера. Решается явным `quote='"'`.
  **A malformed row.** T-001, 2022, line 26332: a comma inside quotes breaks parser auto-detection. Fixed with an explicit `quote='"'`.
- **Стандартные ошибки занижены** (указано в README организатора): одна синтетическая таблица без репликаций, поэтому тесты либеральны. Значимость трактуется осторожно.
  **Standard errors are understated** (noted in the organiser's README): one synthetic table with no replicates, so tests are liberal. Significance is treated cautiously.

---

## Структура / Structure

```
├── src/                 конвейер из четырёх шагов / the four-step pipeline
├── notebooks/           воспроизводимый разбор с пояснениями / reproducible walkthrough
├── outputs/
│   ├── aggregates/      агрегаты для слайдов / aggregates for slides
│   ├── households_2021_2024.csv    объединённая таблица / the merged table
│   └── dashboard.html   интерактивный дашборд / interactive dashboard
├── docs/data_notes.md   находки и ограничения / findings and limitations
└── data/                архив и parquet (не в git) / archive and parquet (git-ignored)
```

## Источник данных / Data source

Синтетические микроданные организатора конкурса (`synthetic_microdata_2021-2024_20260921`). Все записи синтетические, реальных респондентов в наборе нет.

Synthetic microdata provided by the competition organiser (`synthetic_microdata_2021-2024_20260921`). Every record is synthetic; no real respondent appears in the dataset.
