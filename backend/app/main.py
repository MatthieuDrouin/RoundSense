from __future__ import annotations

import asyncio
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .gsi import GSIProcessor
from .predictor import RoundPredictor
from .store import StateStore

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

predictor = RoundPredictor(settings.model_path)
processor = GSIProcessor(predictor)
store = StateStore(settings.database_url, settings.history_limit)
websocket_clients: set[WebSocket] = set()


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "model": predictor.source}


@app.get("/api/state")
def get_state():
    state = store.latest()
    if state is None:
        raise HTTPException(404, "No GSI state has been received yet. Start CS2 or run scripts/simulate_gsi.py.")
    return state


@app.get("/api/history")
def get_history(limit: int = 60):
    return store.history(limit)


@app.get("/api/players")
def get_players():
    state = store.latest()
    return [] if state is None else state.players


async def broadcast(state):
    stale = []
    data = state.model_dump_json(exclude={"raw"})
    for ws in list(websocket_clients):
        try:
            await ws.send_text(data)
        except Exception:
            stale.append(ws)
    for ws in stale:
        websocket_clients.discard(ws)


@app.post("/gsi")
async def receive_gsi(request: Request):
    payload = await request.json()
    state = processor.process(payload)
    store.add(state)
    await broadcast(state)
    return {"ok": True}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    websocket_clients.add(ws)
    latest = store.latest()
    if latest is not None:
        await ws.send_text(latest.model_dump_json(exclude={"raw"}))
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        websocket_clients.discard(ws)
