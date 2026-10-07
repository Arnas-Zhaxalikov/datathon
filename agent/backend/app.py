"""FastAPI-бэкенд Qamqor AI. Локальный запуск:

    uvicorn app:app --reload --port 8000

Детерминированные эндпоинты (/api/regions, /api/summary, /api/classify,
/api/policy-simulate) работают без ключа — это чистый расчёт (engine.py) по
households_2021_2024.parquet.
/api/chat (аналитик, LLM поверх code_execution) требует ANTHROPIC_API_KEY в
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

import engine
import segmentation as seg

load_dotenv()

app = FastAPI(title="Qamqor AI — STAT.DATATHON-2026")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

sessions: dict = {}
_agent = None
_gate_client = None


def _require_llm():
    """Ленивая инициализация клиента Anthropic — только когда реально нужен
    чат-режим, чтобы детерминированные эндпоинты работали без ключа."""
    global _agent, _gate_client
    if _agent is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(
                status_code=503,
                detail="ANTHROPIC_API_KEY не задан — чат-режим недоступен. "
                "Калькулятор семьи и обзор по стране работают без ключа.",
            )
        import anthropic
        from claude_agent import ClaudeAgent

        _agent = ClaudeAgent()
        _gate_client = anthropic.Anthropic()
    return _agent, _gate_client


# ---------------------------------------------------------------------------
# Детерминированные эндпоинты — сегментация A/B/C/D, без ИИ, без ключа
# ---------------------------------------------------------------------------


def _calc(fn, **kwargs) -> dict:
    """Ошибка ввода уходит кодом (detail.code) — текст на нужном языке подставляет интерфейс."""
    try:
        return fn(**kwargs)
    except engine.InputError as e:
        raise HTTPException(status_code=400, detail={"code": e.code}) from e


@app.get("/api/regions")
def regions() -> list[dict]:
    return seg.regions()


@app.get("/api/summary")
def summary(year: int = engine.SM_YEAR) -> dict:
    return _calc(seg.national_summary, year=year)


class ClassifyRequest(BaseModel):
    hh_size: int
    n_child: int = 0
    n_employed: int = 0
    income_monthly: float
    region: int
    year: int = engine.SM_YEAR
    # необязательные: для пустых расчётный модуль берёт допущение и возвращает его
    earner_wage: Optional[float] = None
    transfers: Optional[float] = None
    housing_cost: Optional[float] = None
    # параметры трёх сценариев
    months_without_wage: int = engine.DEFAULT_MONTHS_WITHOUT_WAGE
    income_drop_pct: float = engine.DEFAULT_INCOME_DROP_PCT
    housing_rise_pct: float = engine.DEFAULT_HOUSING_RISE_PCT
    # «а что, если»
    whatif_extra_wage: float = 0
    whatif_child_allowance: float = 0


@app.post("/api/classify")
def classify(req: ClassifyRequest) -> dict:
    return _calc(seg.classify_household, **req.model_dump())


class PolicyRequest(BaseModel):
    year: int = engine.SM_YEAR
    new_asp_ratio: float = engine.ASP_RATIO
    topup_amount: float = 30000


@app.post("/api/policy-simulate")
def policy_simulate(req: PolicyRequest) -> dict:
    return _calc(
        seg.policy_simulate, year=req.year, new_asp_ratio=req.new_asp_ratio, topup_amount=req.topup_amount
    )


# ---------------------------------------------------------------------------
# Чат-режим — ИИ-аналитик (требует ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    lang: str = "en"


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    checklist: dict


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    agent, gate_client = _require_llm()
    import anthropic
    import gate
    from claude_agent import Session

    session_id = req.session_id or str(uuid.uuid4())
    session = sessions.setdefault(session_id, Session())

    try:
        reply = agent.ask(session, req.message, req.lang)
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    try:
        checklist = gate.check(gate_client, req.message, reply)
    except anthropic.APIError:
        checklist = {"applicable": []}

    return ChatResponse(session_id=session_id, reply=reply, checklist=checklist)


@app.post("/api/reset")
def reset(session_id: str) -> dict:
    sessions.pop(session_id, None)
    return {"ok": True}


WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
