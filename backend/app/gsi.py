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
    def _phase_countdown(payload: dict[str, Any]) -> tuple[str, float]:
        countdown = payload.get("phase_countdowns") or {}
        phase = str(countdown.get("phase", "unknown") or "unknown")
        try:
            remaining = max(0.0, float(countdown.get("phase_ends_in", 0.0) or 0.0))
        except (TypeError, ValueError):
            remaining = 0.0
        return phase, remaining

    @staticmethod
    def _round_state_override(
        *,
        p_ct: float,
        source: str,
        phase: str,
        winner: str | None,
        full_team_data: bool,
        ct_alive: int,
        t_alive: int,
        bomb_state: str,
        time_remaining: float,
    ) -> tuple[float, str]:
        # Once GSI explicitly reports the round result, the probability is no
        # longer an estimate.
        if phase == "over" and winner == "CT":
            return 1.0, "round_result"
        if phase == "over" and winner == "T":
            return 0.0, "round_result"

        # Elimination rules only make sense when GSI is exposing the complete
        # player list. Do not use them for the local-player fallback.
        if not full_team_data:
            return p_ct, source

        if ct_alive == 0 and t_alive > 0:
            return 0.0, "terminal_elimination"

        if t_alive == 0 and ct_alive > 0:
            if bomb_state != "planted":
                return 1.0, "terminal_elimination"

            # With the bomb planted, dead Ts can still win if CT cannot defuse
            # in time. The model does not know defuse progress/kits yet, so use
            # a conservative bomb-clock floor instead of allowing impossible
            # low CT odds while plenty of time remains.
            if time_remaining >= 12.0:
                return max(p_ct, 0.94), "bomb_clock_override"
            if time_remaining >= 8.0:
                return max(p_ct, 0.78), "bomb_clock_override"
            if time_remaining >= 5.0:
                return max(p_ct, 0.45), "bomb_clock_override"
            if time_remaining > 0.0:
                return min(max(p_ct, 0.08), 0.35), "bomb_clock_override"
            return max(p_ct, 0.50), "bomb_clock_override"

        return p_ct, source

    def process(self, payload: dict[str, Any]) -> LiveState:
        allplayers = payload.get("allplayers") or {}
        full_team_data = bool(allplayers)

        players = self.features.parse_players(payload)
        ct = self.features.summarize_team(players, "CT")
        t = self.features.summarize_team(players, "T")

        map_data = payload.get("map") or {}
        round_data = payload.get("round") or {}
        bomb = payload.get("bomb") or {}
        map_name = str(map_data.get("name", "unknown"))
        phase = str(round_data.get("phase", "unknown") or "unknown")
        winner_raw = str(round_data.get("win_team", "") or "").upper()
        winner = winner_raw if winner_raw in {"CT", "T"} else None
        round_number = int(map_data.get("round", 0) or 0) + 1
        ct_score, t_score = self._scores(payload)
        bomb_state = str(bomb.get("state", round_data.get("bomb", "unknown")) or "unknown")
        timer_phase, round_time = self._phase_countdown(payload)

        bx, by, bz = self.features._parse_position(bomb.get("position"))
        bomb_position = None
        if bx is not None and by is not None:
            bomb_position = (bx, by, bz or 0.0)

        self.features.update_round_history(payload, round_number, phase)
        fv = self.features.build_features(
            ct=ct,
            t=t,
            bomb_state=bomb_state,
            round_time_remaining=round_time,
            ct_score=ct_score,
            t_score=t_score,
        )
        tactical = self.features.tactical_snapshot(
            map_name,
            players,
            bomb_position=bomb_position,
            bomb_state=bomb_state,
            round_time_remaining=round_time,
        )
        p_ct, source = self.predictor.predict(fv, tactical.positioning_adjustment)
        p_ct, source = self._round_state_override(
            p_ct=p_ct,
            source=source,
            phase=phase,
            winner=winner,
            full_team_data=full_team_data,
            ct_alive=ct.alive,
            t_alive=t.alive,
            bomb_state=bomb_state,
            time_remaining=round_time,
        )

        return LiveState(
            timestamp=float((payload.get("provider") or {}).get("timestamp", time.time()) or time.time()),
            map_name=map_name,
            round_number=round_number,
            round_phase=phase,
            timer_phase=timer_phase,
            winner=winner,
            full_team_data=full_team_data,
            bomb_state=bomb_state,
            bomb_x=bx,
            bomb_y=by,
            bomb_z=bz,
            round_time_remaining=round_time,
            ct_score=ct_score,
            t_score=t_score,
            ct=ct,
            t=t,
            players=sorted(players, key=lambda p: p.impact, reverse=True),
            features=fv,
            tactical=tactical,
            ct_win_probability=round(p_ct, 4),
            t_win_probability=round(1.0 - p_ct, 4),
            prediction_source=source,
            raw=payload,
        )
