"""FastAPI-бэкенд ИИ-аналитика. Локальный запуск:

    uvicorn app:app --reload --port 8000

Требует ANTHROPIC_API_KEY в agent/backend/.env (см. .env.example).
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import gate
from claude_agent import ClaudeAgent, Session

load_dotenv()

if not os.environ.get("ANTHROPIC_API_KEY"):
    raise RuntimeError(
        "ANTHROPIC_API_KEY не задан. Скопируйте agent/backend/.env.example в "
        ".env и впишите ключ."
    )

app = FastAPI(title="ИИ-аналитик STAT.DATATHON-2026")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

agent = ClaudeAgent()
gate_client = anthropic.Anthropic()
sessions: dict[str, Session] = {}


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    checklist: dict


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    session_id = req.session_id or str(uuid.uuid4())
    session = sessions.setdefault(session_id, Session())

    try:
        reply = agent.ask(session, req.message)
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
