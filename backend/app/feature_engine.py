from __future__ import annotations

from collections import deque
from math import hypot
from statistics import mean
from typing import Any

from .map_data import MAPS, radar_distance, world_to_radar
from .schemas import FeatureVector, PlayerSnapshot, TacticalSnapshot, TeamSnapshot


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

UTILITY_PREFIXES = (
    "weapon_flashbang",
    "weapon_smokegrenade",
    "weapon_hegrenade",
    "weapon_molotov",
    "weapon_incgrenade",
)


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
        raw = (
            0.38 * kd
            + 0.16 * (kills / 10.0)
            + 0.12 * (assists / 8.0)
            + 0.12 * (mvps / 4.0)
            + 0.22 * (score / 30.0)
        )
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
            x=x,
            y=y,
            z=z,
            impact=self._impact(p),
        )

    def parse_players(self, payload: dict[str, Any]) -> list[PlayerSnapshot]:
        allplayers = payload.get("allplayers") or {}
        if allplayers:
            return [self._snapshot(str(steam_id), p) for steam_id, p in allplayers.items()]

        # Normal player GSI commonly exposes only the local/observed player.
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

    @staticmethod
    def _positioned(players: list[PlayerSnapshot], team: str) -> list[PlayerSnapshot]:
        return [
            p
            for p in players
            if p.team == team and p.alive and p.x is not None and p.y is not None
        ]

    @staticmethod
    def _centroid(players: list[PlayerSnapshot]) -> tuple[float, float] | None:
        if not players:
            return None
        return mean(float(p.x) for p in players), mean(float(p.y) for p in players)

    @staticmethod
    def _spread(players: list[PlayerSnapshot], centroid: tuple[float, float] | None) -> float | None:
        if not players or centroid is None:
            return None
        cx, cy = centroid
        return mean(hypot(float(p.x) - cx, float(p.y) - cy) for p in players)

    @staticmethod
    def _avg_nearest(source: list[PlayerSnapshot], enemies: list[PlayerSnapshot]) -> float | None:
        if not source or not enemies:
            return None
        values = []
        for p in source:
            values.append(min(hypot(float(p.x) - float(e.x), float(p.y) - float(e.y)) for e in enemies))
        return mean(values) if values else None

    @staticmethod
    def _radar_points(map_name: str, players: list[PlayerSnapshot]) -> list[tuple[PlayerSnapshot, tuple[float, float]]]:
        out = []
        for p in players:
            if p.x is None or p.y is None:
                continue
            point = world_to_radar(map_name, float(p.x), float(p.y))
            if point is not None:
                out.append((p, point))
        return out

    @staticmethod
    def _site_count(points: list[tuple[PlayerSnapshot, tuple[float, float]]], site: tuple[float, float], radius: float = 0.18) -> int:
        return sum(radar_distance(point, site) <= radius for _, point in points)

    @staticmethod
    def _avg_site_distance(points: list[tuple[PlayerSnapshot, tuple[float, float]]], site: tuple[float, float]) -> float | None:
        if not points:
            return None
        return mean(radar_distance(point, site) for _, point in points)

    def tactical_snapshot(
        self,
        map_name: str,
        players: list[PlayerSnapshot],
        *,
        bomb_position: tuple[float, float, float] | None = None,
        bomb_state: str = "unknown",
        round_time_remaining: float = 0.0,
    ) -> TacticalSnapshot:
        ct = self._positioned(players, "CT")
        tt = self._positioned(players, "T")
        ct_centroid = self._centroid(ct)
        t_centroid = self._centroid(tt)
        ct_spread = self._spread(ct, ct_centroid)
        t_spread = self._spread(tt, t_centroid)
        centroid_distance = None
        if ct_centroid is not None and t_centroid is not None:
            centroid_distance = hypot(ct_centroid[0] - t_centroid[0], ct_centroid[1] - t_centroid[1])

        snapshot = TacticalSnapshot(
            players_with_position=len(ct) + len(tt),
            ct_spread=round(ct_spread, 1) if ct_spread is not None else None,
            t_spread=round(t_spread, 1) if t_spread is not None else None,
            centroid_distance=round(centroid_distance, 1) if centroid_distance is not None else None,
            ct_avg_nearest_enemy=round(self._avg_nearest(ct, tt), 1) if ct and tt else None,
            t_avg_nearest_enemy=round(self._avg_nearest(tt, ct), 1) if ct and tt else None,
        )

        overview = MAPS.get(map_name)
        if overview is None or overview.bomb_a is None or overview.bomb_b is None:
            snapshot.note = "Player positions are available, but this map has no site metadata in RoundSense yet."
            return snapshot

        ct_points = self._radar_points(map_name, ct)
        t_points = self._radar_points(map_name, tt)
        if not t_points:
            snapshot.note = "Waiting for full T-side position data."
            return snapshot

        # If GSI exposes a bomb position, use the site nearest to the bomb.
        # Otherwise infer the attack focus from the T-side centroid.
        focus_point = None
        if bomb_position is not None:
            focus_point = world_to_radar(map_name, bomb_position[0], bomb_position[1])
        if focus_point is None:
            focus_point = (
                mean(p[1][0] for p in t_points),
                mean(p[1][1] for p in t_points),
            )

        sites = {"A": overview.bomb_a, "B": overview.bomb_b}
        target_site = min(sites, key=lambda name: radar_distance(focus_point, sites[name]))
        target = sites[target_site]

        ct_coverage = self._site_count(ct_points, target)
        t_pressure = self._site_count(t_points, target)
        ct_dist = self._avg_site_distance(ct_points, target)
        t_dist = self._avg_site_distance(t_points, target)

        snapshot.target_site = target_site
        snapshot.ct_site_coverage = ct_coverage
        snapshot.t_site_pressure = t_pressure
        snapshot.ct_avg_distance_to_target = round(ct_dist, 3) if ct_dist is not None else None
        snapshot.t_avg_distance_to_target = round(t_dist, 3) if t_dist is not None else None

        # Convert tactical positioning into a bounded log-odds adjustment.
        # Negative values favor T; positive values favor CT.
        adjustment = 0.0
        adjustment += max(-0.65, min(0.65, (ct_coverage - t_pressure) * 0.14))
        if ct_dist is not None and t_dist is not None:
            adjustment += max(-0.45, min(0.45, (t_dist - ct_dist) * 1.15))

        # A compact T group attacking a lightly covered site should receive an
        # additional advantage, especially later in the round.
        if t_pressure >= 3 and ct_coverage == 0:
            adjustment -= 0.28
        elif t_pressure >= 3 and ct_coverage == 1:
            adjustment -= 0.12
        if ct_coverage >= 3 and t_pressure <= 1:
            adjustment += 0.20

        # Early-round locations are less informative than late-round site pressure.
        if round_time_remaining > 80:
            adjustment *= 0.45
        elif round_time_remaining > 45:
            adjustment *= 0.72

        if bomb_state == "planted":
            adjustment *= 1.25

        adjustment = max(-1.10, min(1.10, adjustment))
        snapshot.positioning_adjustment = round(adjustment, 4)

        if t_pressure >= 3 and ct_coverage == 0:
            snapshot.note = f"T has heavy pressure toward {target_site} with no nearby CT coverage."
        elif ct_coverage >= 3 and t_pressure <= 1:
            snapshot.note = f"CT has strong coverage around {target_site} while T pressure is low."
        elif t_pressure > ct_coverage:
            snapshot.note = f"T has a positional edge around {target_site} ({t_pressure} attackers vs {ct_coverage} defenders nearby)."
        elif ct_coverage > t_pressure:
            snapshot.note = f"CT has a positional edge around {target_site} ({ct_coverage} defenders vs {t_pressure} attackers nearby)."
        else:
            snapshot.note = f"Positioning around {target_site} is currently balanced."

        return snapshot

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
        enemies = [
            p
            for p in players
            if p.team != player.team
            and p.team in {"CT", "T"}
            and p.alive
            and p.x is not None
            and p.y is not None
        ]
        if not enemies:
            return None
        return min(hypot(float(player.x) - float(p.x), float(player.y) - float(p.y)) for p in enemies)
