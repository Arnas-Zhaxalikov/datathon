"""FastAPI-бэкенд Qamqor AI. Локальный запуск:

    uvicorn app:app --reload --port 8000

Все числа приходят из расчётного ядра qamqor/ (см. core.py). Эндпоинты /api/regions,
/api/summary и /api/classify работают без ключа. /api/chat — ассистент: Claude вызывает
четыре инструмента ядра и объясняет результат; ему нужен ANTHROPIC_API_KEY в
agent/backend/.env — без него отвечает понятной ошибкой, а не падает весь сервер.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import core

load_dotenv()

app = FastAPI(title="Qamqor AI — STAT.DATATHON-2026")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

sessions: dict = {}
_agent = None


def _require_llm():
    """Ленивая инициализация клиента Anthropic — только когда реально нужен
    чат-режим, чтобы остальные эндпоинты работали без ключа."""
    global _agent
    if _agent is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(
                status_code=503,
                detail="ANTHROPIC_API_KEY не задан — чат-режим недоступен. "
                "Калькулятор семьи и обзор по стране работают без ключа.",
            )
        from claude_agent import ClaudeAgent

        _agent = ClaudeAgent()
    return _agent


# ---------------------------------------------------------------------------
# Расчётные эндпоинты — только ядро, без ИИ и без ключа
# ---------------------------------------------------------------------------


@app.get("/api/regions")
def regions() -> list[dict]:
    return core.regions()


@app.get("/api/summary")
def summary() -> dict:
    return core.summary()


class ClassifyRequest(BaseModel):
    hh_size: int
    n_child: int = 0
    n_employed: int = 0
    income_monthly: float
    region: int
    # необязательные: для пустых берётся допущение, и оно возвращается в ответе
    earner_wage: Optional[float] = None
    earner_self_employed: bool = False
    transfers: Optional[float] = None
    housing_cost: Optional[float] = None
    # параметры четырёх стресс-тестов (по умолчанию — базовая версия ядра)
    months_without_wage: float = core.E.StressTests().main_earner_months_lost
    cost_of_living_pct: float = core.E.StressTests().cost_of_living_rise * 100
    housing_rise_pct: float = core.E.StressTests().utilities_rise * 100
    extra_dependants: float = core.E.StressTests().extra_dependants
    # «а что, если»
    whatif_extra_wage: float = 0
    whatif_child_allowance: float = 0


@app.post("/api/classify")
def classify(req: ClassifyRequest) -> dict:
    try:
        return core.classify_household(**req.model_dump())
    except core.InputError as e:
        # ошибка ввода уходит кодом — текст на нужном языке подставляет интерфейс
        raise HTTPException(status_code=400, detail={"code": e.code}) from e


# ---------------------------------------------------------------------------
# Чат — ассистент поверх четырёх инструментов ядра (требует ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    lang: str = "en"


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    # какие инструменты ядра вызваны для этого ответа — показывается под сообщением
    tools: list[dict]


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    agent = _require_llm()
    import anthropic
    from claude_agent import Session

    session_id = req.session_id or str(uuid.uuid4())
    session = sessions.setdefault(session_id, Session())
    try:
        reply, used = agent.ask(session, req.message, req.lang)
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return ChatResponse(session_id=session_id, reply=reply, tools=used)


@app.post("/api/reset")
def reset(session_id: str) -> dict:
    sessions.pop(session_id, None)
    return {"ok": True}


class FreshStaticFiles(StaticFiles):
    """Файлы интерфейса с заголовком no-cache: браузер каждый раз сверяет их с сервером.
    Без этого после обновления он показывает старые скрипты из кэша, а они не понимают
    ответы нового сервера."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/", FreshStaticFiles(directory=str(WEB_DIR), html=True), name="web")
