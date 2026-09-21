from __future__ import annotations

from collections import deque
from math import hypot
from typing import Any

from .schemas import FeatureVector, PlayerSnapshot, TeamSnapshot


WEAPON_VALUES = {
    "weapon_awp": 4750,
    "weapon_ak47": 2700,
    "weapon_m4a1": 2900,
    "weapon_m4a1_silencer": 2900,
    "weapon_aug": 3300,
    "weapon_sg556": 3000,
    "weapon_famas": 2050,
    "weapon_galilar": 1800,
    "weapon_mp9": 1250,
    "weapon_mac10": 1050,
    "weapon_mp7": 1500,
    "weapon_mp5sd": 1500,
    "weapon_ump45": 1200,
    "weapon_p90": 2350,
    "weapon_nova": 1050,
    "weapon_xm1014": 2000,
    "weapon_mag7": 1300,
    "weapon_sawedoff": 1100,
    "weapon_deagle": 700,
    "weapon_elite": 300,
    "weapon_fiveseven": 500,
    "weapon_tec9": 500,
    "weapon_cz75a": 500,
    "weapon_revolver": 600,
    "weapon_hkp2000": 200,
    "weapon_usp_silencer": 200,
    "weapon_glock": 200,
    "weapon_p250": 300,
}

UTILITY_PREFIXES = ("weapon_flashbang", "weapon_smokegrenade", "weapon_hegrenade", "weapon_molotov", "weapon_incgrenade")


class FeatureEngine:
    def __init__(self, recent_rounds: int = 5):
        self.recent_results: deque[str] = deque(maxlen=recent_rounds)
        self._last_round: int | None = None
        self._last_phase: str | None = None

    @staticmethod
    def _team_name(player: dict[str, Any]) -> str:
        team = str(player.get("team", "UNKNOWN")).upper()
        if team in {"CT", "T"}:
            return team
        return "UNKNOWN"

    @staticmethod
    def _weapon_list(player: dict[str, Any]) -> list[str]:
        weapons = player.get("weapons") or {}
        if isinstance(weapons, dict):
            result = []
            for item in weapons.values():
                if isinstance(item, dict) and item.get("name"):
                    result.append(str(item["name"]))
            return result
        if isinstance(weapons, list):
            return [str(w.get("name", w)) if isinstance(w, dict) else str(w) for w in weapons]
        return []

    @staticmethod
    def _equipment_value(weapons: list[str]) -> int:
        return sum(WEAPON_VALUES.get(w, 0) for w in weapons)

    @staticmethod
    def _utility_count(weapons: list[str]) -> int:
        return sum(1 for w in weapons if w.startswith(UTILITY_PREFIXES))

    @staticmethod
    def _parse_position(position: str | None):
        if not position:
            return None, None, None
        try:
            x, y, z = [float(x.strip()) for x in position.split(",")[:3]]
            return x, y, z
        except Exception:
            return None, None, None

    @staticmethod
    def _impact(player: dict[str, Any]) -> float:
        match_stats = player.get("match_stats") or {}
        kills = float(match_stats.get("kills", 0))
        assists = float(match_stats.get("assists", 0))
        deaths = float(match_stats.get("deaths", 0))
        mvps = float(match_stats.get("mvps", 0))
        score = float(match_stats.get("score", 0))
        kd = kills / max(1.0, deaths)
        raw = 0.38 * kd + 0.16 * (kills / 10.0) + 0.12 * (assists / 8.0) + 0.12 * (mvps / 4.0) + 0.22 * (score / 30.0)
        return round(max(0.0, min(raw, 2.5)), 2)

    def _snapshot(self, steam_id: str, p: dict[str, Any]) -> PlayerSnapshot:
        state = p.get("state") or {}
        stats = p.get("match_stats") or {}
        weapons = self._weapon_list(p)
        x, y, z = self._parse_position(p.get("position"))
        team = self._team_name(p)
        health = int(state.get("health", 0) or 0)
        return PlayerSnapshot(
            steam_id=str(steam_id),
            name=str(p.get("name", "Unknown")),
            team=team,
            alive=health > 0,
            health=health,
            armor=int(state.get("armor", 0) or 0),
            money=int(state.get("money", 0) or 0),
            equipment_value=self._equipment_value(weapons),
            kills=int(stats.get("kills", 0) or 0),
            assists=int(stats.get("assists", 0) or 0),
            deaths=int(stats.get("deaths", 0) or 0),
            mvps=int(stats.get("mvps", 0) or 0),
            score=int(stats.get("score", 0) or 0),
            weapons=weapons,
            x=x, y=y, z=z,
            impact=self._impact(p),
        )

    def parse_players(self, payload: dict[str, Any]) -> list[PlayerSnapshot]:
        allplayers = payload.get("allplayers") or {}
        if allplayers:
            return [self._snapshot(str(steam_id), p) for steam_id, p in allplayers.items()]

        # Normal player GSI often does not expose allplayers. Fall back to the
        # local/observed player so the dashboard still shows useful live data.
        p = payload.get("player") or {}
        if not p:
            return []
        provider = payload.get("provider") or {}
        steam_id = str(p.get("steamid") or provider.get("steamid") or "local-player")
        return [self._snapshot(steam_id, p)]

    @staticmethod
    def summarize_team(players: list[PlayerSnapshot], team: str) -> TeamSnapshot:
        ps = [p for p in players if p.team == team]
        return TeamSnapshot(
            alive=sum(p.alive for p in ps),
            health=sum(p.health for p in ps),
            armor=sum(p.armor for p in ps),
            money=sum(p.money for p in ps),
            equipment_value=sum(p.equipment_value for p in ps),
            utility=sum(sum(1 for w in p.weapons if w.startswith(UTILITY_PREFIXES)) for p in ps),
        )

    def recent_ct_win_rate(self) -> float:
        if not self.recent_results:
            return 0.5
        return sum(r == "CT" for r in self.recent_results) / len(self.recent_results)

    def update_round_history(self, payload: dict[str, Any], round_number: int, phase: str):
        round_data = payload.get("round") or {}
        win_team = str(round_data.get("win_team", "")).upper()
        if self._last_phase != "over" and phase == "over" and win_team in {"CT", "T"}:
            self.recent_results.append(win_team)
        self._last_phase = phase
        self._last_round = round_number

    def build_features(
        self,
        *,
        ct: TeamSnapshot,
        t: TeamSnapshot,
        bomb_state: str,
        round_time_remaining: float,
        ct_score: int,
        t_score: int,
    ) -> FeatureVector:
        return FeatureVector(
            ct_alive=ct.alive,
            t_alive=t.alive,
            ct_health=ct.health,
            t_health=t.health,
            ct_armor=ct.armor,
            t_armor=t.armor,
            ct_money=ct.money,
            t_money=t.money,
            ct_equipment=ct.equipment_value,
            t_equipment=t.equipment_value,
            ct_utility=ct.utility,
            t_utility=t.utility,
            bomb_planted=1 if bomb_state == "planted" else 0,
            round_time_remaining=round_time_remaining,
            ct_score=ct_score,
            t_score=t_score,
            recent_ct_win_rate=self.recent_ct_win_rate(),
        )

    @staticmethod
    def nearest_enemy_distance(player: PlayerSnapshot, players: list[PlayerSnapshot]) -> float | None:
        if player.x is None or player.y is None:
            return None
        enemies = [p for p in players if p.team != player.team and p.team in {"CT", "T"} and p.alive and p.x is not None and p.y is not None]
        if not enemies:
            return None
        return min(hypot(player.x - p.x, player.y - p.y) for p in enemies)
