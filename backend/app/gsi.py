from __future__ import annotations

import time
from typing import Any

from .feature_engine import FeatureEngine
from .predictor import RoundPredictor
from .schemas import LiveState


class GSIProcessor:
    def __init__(self, predictor: RoundPredictor):
        self.features = FeatureEngine()
        self.predictor = predictor

    @staticmethod
    def _scores(payload: dict[str, Any]) -> tuple[int, int]:
        map_data = payload.get("map") or {}
        ct = map_data.get("team_ct") or {}
        t = map_data.get("team_t") or {}
        return int(ct.get("score", 0) or 0), int(t.get("score", 0) or 0)

    @staticmethod
    def _round_time(payload: dict[str, Any]) -> float:
        phase = payload.get("phase_countdowns") or {}
        return float(phase.get("phase_ends_in", 0.0) or 0.0)

    def process(self, payload: dict[str, Any]) -> LiveState:
        players = self.features.parse_players(payload)
        ct = self.features.summarize_team(players, "CT")
        t = self.features.summarize_team(players, "T")

        map_data = payload.get("map") or {}
        round_data = payload.get("round") or {}
        bomb = payload.get("bomb") or {}
        phase = str(round_data.get("phase", "unknown"))
        round_number = int(map_data.get("round", 0) or 0) + 1
        ct_score, t_score = self._scores(payload)
        bomb_state = str(bomb.get("state", round_data.get("bomb", "unknown")) or "unknown")
        round_time = self._round_time(payload)

        self.features.update_round_history(payload, round_number, phase)
        fv = self.features.build_features(
            ct=ct, t=t, bomb_state=bomb_state, round_time_remaining=round_time,
            ct_score=ct_score, t_score=t_score,
        )
        p_ct, source = self.predictor.predict(fv)

        return LiveState(
            timestamp=float((payload.get("provider") or {}).get("timestamp", time.time()) or time.time()),
            map_name=str(map_data.get("name", "unknown")),
            round_number=round_number,
            round_phase=phase,
            bomb_state=bomb_state,
            round_time_remaining=round_time,
            ct_score=ct_score,
            t_score=t_score,
            ct=ct,
            t=t,
            players=sorted(players, key=lambda p: p.impact, reverse=True),
            features=fv,
            ct_win_probability=round(p_ct, 4),
            t_win_probability=round(1.0 - p_ct, 4),
            prediction_source=source,
            raw=payload,
        )
