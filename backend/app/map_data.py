from __future__ import annotations

from dataclasses import dataclass
from math import hypot


RADAR_SIZE = 1024.0


@dataclass(frozen=True)
class MapOverview:
    pos_x: float
    pos_y: float
    scale: float
    bomb_a: tuple[float, float] | None = None
    bomb_b: tuple[float, float] | None = None


# Overview metadata comes from Counter-Strike overview files. Site coordinates
# are normalized radar coordinates (0..1). The project can still operate on
# maps not listed here, but site-control features will be unavailable.
MAPS: dict[str, MapOverview] = {
    "de_cache": MapOverview(-2000, 3250, 5.5, (0.325, 0.26), (0.345, 0.79)),
    "de_mirage": MapOverview(-3230, 1713, 5.0, (0.54, 0.76), (0.23, 0.28)),
    "de_dust2": MapOverview(-2476, 3239, 4.4, (0.80, 0.16), (0.21, 0.12)),
    "de_inferno": MapOverview(-2087, 3870, 4.9, (0.81, 0.69), (0.49, 0.22)),
    "de_nuke": MapOverview(-3453, 2887, 7.0, (0.58, 0.48), (0.58, 0.58)),
    "de_ancient": MapOverview(-2953, 2164, 5.0, (0.31, 0.25), (0.80, 0.40)),
    "de_overpass": MapOverview(-4831, 1781, 5.2, (0.55, 0.23), (0.70, 0.31)),
    "de_train": MapOverview(-2308, 2078, 4.082077, (0.63, 0.49), (0.52, 0.76)),
    "de_vertigo": MapOverview(-3168, 1762, 4.0, (0.705, 0.585), (0.222, 0.223)),
}


def world_to_radar(map_name: str, x: float, y: float) -> tuple[float, float] | None:
    overview = MAPS.get(map_name)
    if overview is None:
        return None
    # Valve overview coordinates use the upper-left world origin. The world Y
    # axis is inverted relative to image Y.
    rx = (x - overview.pos_x) / (overview.scale * RADAR_SIZE)
    ry = (overview.pos_y - y) / (overview.scale * RADAR_SIZE)
    return rx, ry


def radar_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])
