from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class TeamSnapshot(BaseModel):
    alive: int = 0
    health: int = 0
    armor: int = 0
    money: int = 0
    equipment_value: int = 0
    utility: int = 0


class PlayerSnapshot(BaseModel):
    steam_id: str
    name: str = "Unknown"
    team: str = "UNKNOWN"
    alive: bool = False
    health: int = 0
    armor: int = 0
    money: int = 0
    equipment_value: int = 0
    kills: int = 0
    assists: int = 0
    deaths: int = 0
    mvps: int = 0
    score: int = 0
    weapons: list[str] = Field(default_factory=list)
    x: float | None = None
    y: float | None = None
    z: float | None = None
    impact: float = 0.0


class FeatureVector(BaseModel):
    ct_alive: int = 0
    t_alive: int = 0
    ct_health: int = 0
    t_health: int = 0
    ct_armor: int = 0
    t_armor: int = 0
    ct_money: int = 0
    t_money: int = 0
    ct_equipment: int = 0
    t_equipment: int = 0
    ct_utility: int = 0
    t_utility: int = 0
    bomb_planted: int = 0
    round_time_remaining: float = 0.0
    ct_score: int = 0
    t_score: int = 0
    recent_ct_win_rate: float = 0.5


class TacticalSnapshot(BaseModel):
    players_with_position: int = 0
    ct_spread: float | None = None
    t_spread: float | None = None
    centroid_distance: float | None = None
    ct_avg_nearest_enemy: float | None = None
    t_avg_nearest_enemy: float | None = None
    target_site: str | None = None
    ct_site_coverage: int = 0
    t_site_pressure: int = 0
    ct_avg_distance_to_target: float | None = None
    t_avg_distance_to_target: float | None = None
    positioning_adjustment: float = 0.0
    note: str = "Not enough full-team position data yet."


class LiveState(BaseModel):
    timestamp: float
    map_name: str = "unknown"
    round_number: int = 0
    round_phase: str = "unknown"
    timer_phase: str = "unknown"
    winner: str | None = None
    full_team_data: bool = False
    bomb_state: str = "unknown"
    bomb_x: float | None = None
    bomb_y: float | None = None
    bomb_z: float | None = None
    round_time_remaining: float = 0.0
    ct_score: int = 0
    t_score: int = 0
    ct: TeamSnapshot = Field(default_factory=TeamSnapshot)
    t: TeamSnapshot = Field(default_factory=TeamSnapshot)
    players: list[PlayerSnapshot] = Field(default_factory=list)
    features: FeatureVector = Field(default_factory=FeatureVector)
    tactical: TacticalSnapshot = Field(default_factory=TacticalSnapshot)
    ct_win_probability: float = 0.5
    t_win_probability: float = 0.5
    prediction_source: str = "heuristic"
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)
