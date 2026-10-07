"""Слой 2 ИИ-аналитика: Claude Sonnet 5.5 с code_execution поверх
агрегатов и детерминированного аудита (outputs/aggregates/data_quality_flags.json).

Системный промпт собирается из docs/RULES.md — агент обязан свериться с
дрейфом схемы / надёжностью корреляций / заполненностью перед тем, как
делать содержательное утверждение.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = ROOT / "docs" / "RULES.md"
AGG_DIR = ROOT / "outputs" / "aggregates"
HOUSEHOLDS_CSV = ROOT / "outputs" / "households_2021_2024.csv"

MODEL = "claude-sonnet-5-5"

# язык интерфейса (agent/web/i18n.js) → инструкция о языке ответа
DEFAULT_LANG = "en"
REPLY_LANGUAGE = {
    # на самом целевом языке и с оговоркой про историю: иначе после смены
    # языка посреди диалога модель продолжает отвечать на прежнем
    "en": (
        "[Interface language: English. Write this entire reply in English — headings, "
        "tables and all chart text included — even if the earlier conversation or the "
        "question itself is in another language.]"
    ),
    "kk": (
        "[Интерфейс тілі: қазақ тілі. Осы жауапты толығымен қазақ тілінде жаз — "
        "тақырыптар, кестелер және графиктердегі мәтін де — алдыңғы әңгіме немесе "
        "сұрақтың өзі басқа тілде болса да.]"
    ),
    "ru": (
        "[Язык интерфейса: русский. Весь этот ответ пиши на русском языке — включая "
        "заголовки, таблицы и текст графиков, — даже если предыдущий разговор или сам "
        "вопрос на другом языке.]"
    ),
}

AGG_FILES = sorted(AGG_DIR.glob("*.csv"))
DATA_FILES = [HOUSEHOLDS_CSV, AGG_DIR / "data_quality_flags.json"] + AGG_FILES

# API принимает не больше 16 файлов на контейнер за раз, а агрегатов уже 17 —
# поэтому они уходят в песочницу одним архивом
AGG_ZIP_NAME = "aggregates.zip"


def _zip_aggregates() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in AGG_FILES:
            zf.write(path, arcname=path.name)
    return buf.getvalue()


# Графики, прогноз и поиск связей. Формат блока ```chart разбирает
# agent/web/charts.js — менять их нужно вместе.
ANALYSIS_GUIDE = """## Графики

Интерфейс сам рисует графики по спецификации. Не строй картинки в matplotlib
и не сохраняй файлы — вместо этого вставляй в ответ блок:

```chart
{"type": "line", "title": "...", "subtitle": "...", "x_label": "Год", "y_label": "%", ...}
```

Внутри блока — один валидный JSON-объект (двойные кавычки, числа без пробелов
и знака %, пропуск — null). Числа бери только из результата выполненного кода.
Три типа:

- line — динамика во времени. Поля: "x" — подписи точек (годы), "series" —
  до 4 рядов {"name", "values"}; массив "values" той же длины, что "x".
  Все ряды одного графика — в одних единицах; показатели разного масштаба
  разноси по разным графикам.
- bar — сравнение категорий (регионы, типы домохозяйств, квинтили). Поля:
  "x" — названия категорий, "series" — ровно один ряд {"name", "values"}.
  Отсортируй по значению. Вместо кодов регионов пиши названия.
- scatter — связь двух показателей. Поля: "points" — массив
  {"x", "y", "label"}, не больше 60 точек (агрегируй: регионы, группы,
  бины — не выводи отдельные домохозяйства), "x_label", "y_label",
  по желанию "fit": {"slope", "intercept"} — линия МНК.

"title" — вывод одной фразой, "subtitle" — что измерено, n, источник
(а для scatter — ещё r и тег надёжности). Текст графика — на языке ответа.

К каждому содержательному ответу с числами прикладывай 1–3 графика: динамику —
line, сравнение — bar, связь — scatter. Не дублируй один и тот же ряд дважды
и не рисуй график ради одного числа. Таблицу оставляй, только если в ней есть
то, чего нет на графике.

## Прогноз

Когда вопрос касается динамики показателя и по нему есть сопоставимые годовые
значения за 2021–2024, добавляй ориентировочный прогноз на 2025 и 2026 годы:

- метод — линейный тренд МНК по годовым значениям, посчитанный кодом
  (numpy/scipy/statsmodels), не на глаз;
- диапазон — 80%-ный интервал предсказания этой регрессии. По четырём точкам
  он широкий — так и должно быть, не сужай его;
- на графике line добавь будущие годы в "x", у ряда — массивы "forecast",
  "low", "high" той же длины, что "x": null для фактических лет, числа для
  прогнозных; в "values" для прогнозных лет — null;
- в тексте назови прогнозное значение вместе с диапазоном и прямо скажи: это
  экстраполяция тренда по четырём годовым срезам синтетических данных, а не
  предсказание. Если диапазон допускает и рост, и снижение — так и напиши:
  направление не определено.

Прогноз не строится, и ты объясняешь почему: если ряд несопоставим между
годами (дрейф схемы, смена справочника или охвата), если в ряду известная
аномалия из реестра (например, неформальная занятость в Алматинской области),
если подвыборка меньше 30 наблюдений в каком-либо году, а также для отдельного
домохозяйства — панели нет.

## Связи

Отвечая на вопрос о показателе, проверь кодом, с чем он связан: 2–4
содержательно уместных признака (состав семьи, занятость, тип поселения,
регион, жильё, доход). Для каждой проверенной связи укажи коэффициент (r
Пирсона или Спирмена, либо разницу средних между группами), n и тег
надёжности: при |r| < 0.1 — «связь не воспроизводится в этих данных», а не
«слабая связь». Сообщай и о ненайденных связях — это тоже результат.
Корреляцию не выдавай за причинность. Самую сильную связь покажи графиком
scatter или bar."""


def _build_system_prompt() -> str:
    missing = [str(p) for p in DATA_FILES if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Не найдены файлы данных — сначала прогоните src/04_analyze_merged.py "
            f"и src/08_data_quality_profile.py. Отсутствуют: {missing}"
        )
    filenames = (
        f"- {HOUSEHOLDS_CSV.name}\n- data_quality_flags.json\n"
        f"- {AGG_ZIP_NAME} — архив с агрегатами, сначала распакуй его (zipfile). Внутри:\n"
        + "\n".join(f"  - {f.name}" for f in AGG_FILES)
    )
    rules = RULES_PATH.read_text(encoding="utf-8")
    return (
        "Ты — Qamqor AI, ИИ-аналитик социальной политики поверх официальной "
        "статистики БНС АСПР РК (STAT.DATATHON-2026, трек AI for Official "
        "Statistics). Помогаешь аналитику находить домохозяйства, которых не "
        "видит официальная статистика бедности, и оценивать последствия мер "
        "поддержки и шоков (потеря дохода, рост тарифов). "
        "В твоей песочнице code_execution доступны следующие файлы:\n"
        f"{filenames}\n\n"
        "households_2021_2024.csv — объединённая таблица домохозяйств "
        "(48000 строк, 2021-2024, 37 колонок). data_quality_flags.json — "
        "детерминированный аудит данных: дрейф схемы между годами, тег "
        "надёжности для каждой измеренной корреляции (near_zero при |r|<0.1, "
        "иначе structural), таблицы с заполненностью ниже 50%, реестр "
        "известных аномалий синтетики. Остальные CSV — агрегаты по "
        "занятости, доходам, сегментам домохозяйств, корреляциям.\n\n"
        "Перед любым содержательным утверждением выполни код, который "
        "читает data_quality_flags.json, и свериcь с ним. Отвечай "
        "кратко и по существу, с конкретными числами из данных. Строго "
        "следуй правилам ниже.\n\n"
        "Язык ответа: в конце каждого сообщения пользователя стоит пометка "
        "в квадратных скобках с языком интерфейса (English, қазақ тілі или "
        "русский). Весь ответ — текст, заголовки, таблицы, подписи графиков — "
        "пиши на этом языке. Пометка важнее языка самого вопроса, языка этих "
        "инструкций и языка предыдущих ответов: если она изменилась посреди "
        "диалога, переходи на новый язык сразу.\n\n"
        + ANALYSIS_GUIDE
        + "\n\n"
        + rules
    )


class Session:
    """Состояние одного чата: история сообщений + id контейнера песочницы."""

    def __init__(self) -> None:
        self.container_id: str | None = None
        self.history: list[dict] = []


class ClaudeAgent:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic()
        self.system_prompt = _build_system_prompt()
        self._uploaded_file_ids: list[str] | None = None

    def _ensure_files_uploaded(self) -> list[str]:
        if self._uploaded_file_ids is None:
            ids = []
            for path in (HOUSEHOLDS_CSV, AGG_DIR / "data_quality_flags.json"):
                with open(path, "rb") as f:
                    uploaded = self.client.files.upload(file=f)
                ids.append(uploaded.id)
            uploaded = self.client.files.upload(
                file=(AGG_ZIP_NAME, _zip_aggregates(), "application/zip")
            )
            ids.append(uploaded.id)
            self._uploaded_file_ids = ids
        return self._uploaded_file_ids

    def ask(self, session: Session, user_message: str, lang: str = DEFAULT_LANG) -> str:
        # язык ответа идёт в сообщении, а не в system: блоки размышлений в истории
        # привязаны к системному промпту, и если он изменится посреди диалога
        # (пользователь переключил язык), API отклонит всю историю с ошибкой 400
        content: list[dict] = [
            {"type": "text", "text": user_message},
            {"type": "text", "text": REPLY_LANGUAGE.get(lang, REPLY_LANGUAGE[DEFAULT_LANG])},
        ]

        kwargs: dict = dict(
            model=MODEL,
            max_tokens=8000,
            system=[
                {
                    "type": "text",
                    "text": self.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=[{"type": "code_execution_20260120", "name": "code_execution"}],
            output_config={"effort": "medium"},
        )

        if session.container_id is None:
            # первое сообщение сессии — прикрепляем файлы к новому контейнеру
            for file_id in self._ensure_files_uploaded():
                content.append({"type": "container_upload", "file_id": file_id})
        else:
            kwargs["container"] = session.container_id

        session.history.append({"role": "user", "content": content})
        kwargs["messages"] = session.history

        try:
            response = self.client.messages.create(**kwargs)
        except anthropic.APIError:
            # иначе неотвеченное сообщение (и его вложения) останется в истории
            # и уйдёт повторно со следующим вопросом
            session.history.pop()
            raise

        if response.container is not None:
            session.container_id = response.container.id
        session.history.append({"role": "assistant", "content": response.content})

        return "\n".join(b.text for b in response.content if b.type == "text")
