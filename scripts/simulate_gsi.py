from __future__ import annotations

import argparse
import random
import time

import requests

MAP = {"name": "de_mirage", "pos_x": -3230, "pos_y": 1713, "scale": 5.0}
SITES = {"A": (0.54, 0.76), "B": (0.23, 0.28)}
SPAWNS = {"T": (0.87, 0.36), "CT": (0.28, 0.70)}
WEAPONS_CT = ["weapon_m4a1_silencer", "weapon_m4a1", "weapon_awp", "weapon_famas", "weapon_mp9"]
WEAPONS_T = ["weapon_ak47", "weapon_ak47", "weapon_awp", "weapon_galilar", "weapon_mac10"]


def radar_to_world(point):
    rx, ry = point
    x = MAP["pos_x"] + rx * MAP["scale"] * 1024
    y = MAP["pos_y"] - ry * MAP["scale"] * 1024
    return x, y


def lerp(a, b, t):
    return a + (b - a) * t


def player(i, team, radar_point, alive=True):
    health = random.randint(25, 100) if alive else 0
    weapon = random.choice(WEAPONS_CT if team == "CT" else WEAPONS_T)
    x, y = radar_to_world(radar_point)
    x += random.uniform(-100, 100)
    y += random.uniform(-100, 100)
    return {
        "name": f"{team}_Player_{i+1}",
        "team": team,
        "position": f"{x:.1f}, {y:.1f}, {random.uniform(-80,180):.1f}",
        "state": {
            "health": health,
            "armor": random.randint(0, 100) if alive else 0,
            "money": random.randint(0, 7000),
        },
        "weapons": {
            "weapon_0": {"name": weapon},
            "weapon_1": {"name": "weapon_flashbang"} if random.random() > .45 else {"name": "weapon_knife"},
        },
        "match_stats": {
            "kills": random.randint(4, 24),
            "assists": random.randint(0, 8),
            "deaths": random.randint(4, 20),
            "mvps": random.randint(0, 4),
            "score": random.randint(8, 45),
        },
    }


def payload(round_num, ct_score, t_score, tick, attack_site, ct_read):
    ct_alive = random.randint(3, 5)
    t_alive = random.randint(3, 5)
    target = SITES[attack_site]
    other = SITES["B" if attack_site == "A" else "A"]
    progress = min(1.0, tick / 12.0)

    players = {}
    for i in range(5):
        # T players move together from spawn toward the selected bombsite.
        tx = lerp(SPAWNS["T"][0], target[0], progress) + random.uniform(-0.025, 0.025)
        ty = lerp(SPAWNS["T"][1], target[1], progress) + random.uniform(-0.025, 0.025)
        players[str(2000 + i)] = player(i, "T", (tx, ty), i < t_alive)

        # If CT guessed the execute, defenders rotate toward the target.
        # Otherwise most CTs remain around the opposite site.
        ct_target = target if ct_read else other
        cx = lerp(SPAWNS["CT"][0], ct_target[0], min(1.0, tick / 15.0)) + random.uniform(-0.035, 0.035)
        cy = lerp(SPAWNS["CT"][1], ct_target[1], min(1.0, tick / 15.0)) + random.uniform(-0.035, 0.035)
        players[str(1000 + i)] = player(i, "CT", (cx, cy), i < ct_alive)

    bomb_x, bomb_y = radar_to_world((
        lerp(SPAWNS["T"][0], target[0], progress),
        lerp(SPAWNS["T"][1], target[1], progress),
    ))
    planted = tick >= 15

    return {
        "provider": {"name": "RoundSense Simulator", "timestamp": int(time.time())},
        "map": {
            "name": MAP["name"],
            "round": round_num - 1,
            "team_ct": {"score": ct_score},
            "team_t": {"score": t_score},
        },
        "round": {"phase": "live"},
        "bomb": {
            "state": "planted" if planted else "carried",
            "position": f"{bomb_x:.1f}, {bomb_y:.1f}, 0",
        },
        "phase_countdowns": {
            "phase": "live",
            "phase_ends_in": max(3, 100 - tick * 5),
        },
        "allplayers": players,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000/gsi")
    ap.add_argument("--interval", type=float, default=1.0)
    args = ap.parse_args()

    ct_score, t_score, round_num = 7, 6, 14
    tick = 0
    attack_site = random.choice(["A", "B"])
    ct_read = random.random() < 0.45

    print(f"Sending tactical demo states to {args.url}. Ctrl+C to stop.")
    print(f"Round {round_num}: T attacking {attack_site}; CT read={ct_read}")

    while True:
        state = payload(round_num, ct_score, t_score, tick, attack_site, ct_read)
        r = requests.post(args.url, json=state, timeout=3)
        print(r.status_code, f"round={round_num} tick={tick} target={attack_site} ct_read={ct_read}")
        tick += 1

        if tick >= 20:
            tick = 0
            if random.random() < .5:
                ct_score += 1
            else:
                t_score += 1
            round_num += 1
            attack_site = random.choice(["A", "B"])
            ct_read = random.random() < 0.45
            print(f"Round {round_num}: T attacking {attack_site}; CT read={ct_read}")

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
