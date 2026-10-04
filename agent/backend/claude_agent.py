"""Слой 2 ИИ-аналитика: Claude Sonnet 5.5 с code_execution поверх
агрегатов и детерминированного аудита (outputs/aggregates/data_quality_flags.json).

Системный промпт собирается из docs/RULES.md — агент обязан свериться с
дрейфом схемы / надёжностью корреляций / заполненностью перед тем, как
делать содержательное утверждение.
"""
from __future__ import annotations

from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = ROOT / "docs" / "RULES.md"
AGG_DIR = ROOT / "outputs" / "aggregates"
HOUSEHOLDS_CSV = ROOT / "outputs" / "households_2021_2024.csv"

MODEL = "claude-sonnet-5-5"

DATA_FILES = [HOUSEHOLDS_CSV, AGG_DIR / "data_quality_flags.json"] + sorted(
    AGG_DIR.glob("*.csv")
)


def _build_system_prompt() -> str:
    missing = [str(p) for p in DATA_FILES if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Не найдены файлы данных — сначала прогоните src/04_analyze_merged.py "
            f"и src/08_data_quality_profile.py. Отсутствуют: {missing}"
        )
    filenames = "\n".join(f"- {f.name}" for f in DATA_FILES)
    rules = RULES_PATH.read_text(encoding="utf-8")
    return (
        "Ты — ИИ-аналитик официальной статистики БНС АСПР РК "
        "(STAT.DATATHON-2026, трек AI for Official Statistics). "
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
        "читает data_quality_flags.json, и свериcь с ним. Отвечай на русском, "
        "кратко и по существу, с конкретными числами из данных. Строго "
        "следуй правилам ниже.\n\n"
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
            for path in DATA_FILES:
                with open(path, "rb") as f:
                    uploaded = self.client.files.upload(file=f)
                ids.append(uploaded.id)
            self._uploaded_file_ids = ids
        return self._uploaded_file_ids

    def ask(self, session: Session, user_message: str) -> str:
        content: list[dict] = [{"type": "text", "text": user_message}]

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

        response = self.client.messages.create(**kwargs)

        if response.container is not None:
            session.container_id = response.container.id
        session.history.append({"role": "assistant", "content": response.content})

        return "\n".join(b.text for b in response.content if b.type == "text")
