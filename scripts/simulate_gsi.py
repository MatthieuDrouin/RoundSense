from __future__ import annotations

import argparse
import random
import time
import requests

WEAPONS_CT = ["weapon_m4a1_silencer", "weapon_m4a1", "weapon_awp", "weapon_famas", "weapon_mp9"]
WEAPONS_T = ["weapon_ak47", "weapon_ak47", "weapon_awp", "weapon_galilar", "weapon_mac10"]


def player(i, team, alive=True):
    health = random.randint(25, 100) if alive else 0
    weapon = random.choice(WEAPONS_CT if team == "CT" else WEAPONS_T)
    return {
        "name": f"{team}_Player_{i+1}",
        "team": team,
        "position": f"{random.uniform(-1800,1800):.1f}, {random.uniform(-1800,1800):.1f}, {random.uniform(-100,250):.1f}",
        "state": {"health": health, "armor": random.randint(0,100) if alive else 0, "money": random.randint(0,7000)},
        "weapons": {
            "weapon_0": {"name": weapon},
            "weapon_1": {"name": "weapon_flashbang"} if random.random() > .45 else {"name": "weapon_knife"},
        },
        "match_stats": {
            "kills": random.randint(4, 24), "assists": random.randint(0, 8), "deaths": random.randint(4, 20),
            "mvps": random.randint(0, 4), "score": random.randint(8, 45),
        },
    }


def payload(round_num, ct_score, t_score, tick):
    ct_alive = random.randint(1,5)
    t_alive = random.randint(1,5)
    planted = random.random() < .25
    players = {}
    for i in range(5):
        players[str(1000+i)] = player(i, "CT", i < ct_alive)
        players[str(2000+i)] = player(i, "T", i < t_alive)
    return {
        "provider": {"name": "RoundSense Simulator", "timestamp": int(time.time())},
        "map": {"name": "de_mirage", "round": round_num-1, "team_ct": {"score": ct_score}, "team_t": {"score": t_score}},
        "round": {"phase": "live"},
        "bomb": {"state": "planted" if planted else "carried"},
        "phase_countdowns": {"phase": "live", "phase_ends_in": max(3, 100 - tick*4)},
        "allplayers": players,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000/gsi")
    ap.add_argument("--interval", type=float, default=1.0)
    args = ap.parse_args()
    ct_score, t_score, round_num = 7, 6, 14
    print(f"Sending demo states to {args.url}. Ctrl+C to stop.")
    tick = 0
    while True:
        r = requests.post(args.url, json=payload(round_num, ct_score, t_score, tick), timeout=3)
        print(r.status_code, f"round={round_num} state={tick}")
        tick += 1
        if tick >= 20:
            tick = 0
            if random.random() < .5: ct_score += 1
            else: t_score += 1
            round_num += 1
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
