"""Гейт качества: Haiku 4.5 проверяет ответ Sonnet против чек-листа
из docs/RULES.md. Не блокирует ответ — чек-лист показывается в интерфейсе
как ✓/✗-чипы под сообщением, чтобы механизм был виден, а не спрятан.
"""
from __future__ import annotations

import json

import anthropic

GATE_MODEL = "claude-haiku-4-5"

CHECKLIST_SCHEMA = {
    "type": "object",
    "properties": {
        "reported_n_and_missingness": {"type": "boolean"},
        "checked_schema_drift": {"type": "boolean"},
        "checked_correlation_reliability": {"type": "boolean"},
        "flagged_small_sample": {"type": "boolean"},
        "cross_checked_against_priors": {"type": "boolean"},
        "forecast_caveated": {"type": "boolean"},
        "applicable": {
            "type": "array",
            "items": {"type": "string"},
            "description": "какие из пяти пунктов вообще применимы к этому ответу",
        },
    },
    "required": [
        "reported_n_and_missingness",
        "checked_schema_drift",
        "checked_correlation_reliability",
        "flagged_small_sample",
        "cross_checked_against_priors",
        "forecast_caveated",
        "applicable",
    ],
    "additionalProperties": False,
}

GATE_PROMPT = """Ты проверяешь ответ ИИ-аналитика на соответствие правилам \
(docs/RULES.md проекта STAT.DATATHON-2026). Для каждого пункта чек-листа \
отметь true, если правило соблюдено ИЛИ неприменимо к этому конкретному \
ответу; false — если правило применимо, но нарушено. В "applicable" \
перечисли ключи пунктов, которые были реально применимы к этому ответу.

Пункты:
- reported_n_and_missingness: указаны n и/или заполненность при цифрах из данных
- checked_schema_drift: при сравнении лет учтён дрейф схемы (регионы 17->20 и т.п.)
- checked_correlation_reliability: при утверждении о связи двух переменных упомянута её надёжность
- flagged_small_sample: малые подвыборки (n<30) помечены как нестабильные
- cross_checked_against_priors: производные показатели сверены с реальными ориентирами
- forecast_caveated: прогноз дан с диапазоном и оговоркой, что это экстраполяция тренда по четырём годовым срезам

Блоки ```chart в ответе — спецификации графиков для интерфейса; числа в них считаются частью ответа.

Вопрос пользователя:
{question}

Ответ агента:
{answer}
"""


def check(client: anthropic.Anthropic, question: str, answer: str) -> dict:
    response = client.messages.create(
        model=GATE_MODEL,
        max_tokens=1024,
        output_config={"format": {"type": "json_schema", "schema": CHECKLIST_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": GATE_PROMPT.format(question=question, answer=answer),
            }
        ],
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)
