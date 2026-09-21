from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from .schemas import LiveState


class StateStore:
    def __init__(self, database_url: str, history_limit: int = 300):
        self.history_limit = history_limit
        self._lock = threading.Lock()
        self._latest: LiveState | None = None
        self._memory_history: list[LiveState] = []
        self.db_path = self._parse_sqlite_path(database_url)
        self._init_db()

    @staticmethod
    def _parse_sqlite_path(url: str) -> Path:
        if url.startswith("sqlite:///./"):
            return Path(url[len("sqlite:///./"):])
        if url.startswith("sqlite:///"):
            return Path(url[len("sqlite:///"):])
        return Path("roundsense.db")

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS game_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    map_name TEXT,
                    round_number INTEGER,
                    round_phase TEXT,
                    ct_score INTEGER,
                    t_score INTEGER,
                    ct_win_probability REAL,
                    prediction_source TEXT,
                    payload_json TEXT NOT NULL
                )
            """)
            con.commit()

    def add(self, state: LiveState):
        with self._lock:
            self._latest = state
            self._memory_history.append(state)
            if len(self._memory_history) > self.history_limit:
                self._memory_history = self._memory_history[-self.history_limit:]
        with self._connect() as con:
            con.execute(
                "INSERT INTO game_states (ts,map_name,round_number,round_phase,ct_score,t_score,ct_win_probability,prediction_source,payload_json) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    state.timestamp, state.map_name, state.round_number, state.round_phase,
                    state.ct_score, state.t_score, state.ct_win_probability, state.prediction_source,
                    state.model_dump_json(exclude={"raw"}),
                ),
            )
            con.commit()

    def latest(self) -> LiveState | None:
        with self._lock:
            return self._latest

    def history(self, limit: int = 60) -> list[LiveState]:
        with self._lock:
            return self._memory_history[-max(1, min(limit, self.history_limit)):]
