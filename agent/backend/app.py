"""FastAPI-бэкенд Qamqor AI. Локальный запуск:

    uvicorn app:app --reload --port 8000

Детерминированные эндпоинты (/api/summary, /api/classify, /api/policy-simulate)
работают без ключа — это чистый расчёт по households_2021_2024.parquet.
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


@app.get("/api/summary")
def summary(year: int = 2024) -> dict:
    return seg.national_summary(year)


class ClassifyRequest(BaseModel):
    hh_size: int
    n_child: int = 0
    n_employed: int = 0
    income_monthly: float
    settlement: str = "город"
    year: int = 2024


@app.post("/api/classify")
def classify(req: ClassifyRequest) -> dict:
    if req.hh_size < 1:
        raise HTTPException(status_code=400, detail="Размер семьи должен быть не меньше 1")
    if req.income_monthly < 0:
        raise HTTPException(status_code=400, detail="Доход не может быть отрицательным")
    return seg.classify_household(
        hh_size=req.hh_size,
        n_child=req.n_child,
        n_employed=req.n_employed,
        income_monthly=req.income_monthly,
        settlement=req.settlement,
        year=req.year,
    )


class PolicyRequest(BaseModel):
    year: int = 2024
    new_asp_ratio: float = 0.7
    topup_amount: float = 30000


@app.post("/api/policy-simulate")
def policy_simulate(req: PolicyRequest) -> dict:
    return seg.policy_simulate(
        year=req.year, new_asp_ratio=req.new_asp_ratio, topup_amount=req.topup_amount
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
