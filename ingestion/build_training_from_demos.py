from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

import pandas as pd

UTILITY_NAMES = ("flash", "smoke", "hegrenade", "molotov", "incgrenade", "incendiary")


def first_col(df, *names):
    for n in names:
        if n in df.columns:
            return n
    return None


def norm_side(v):
    s = str(v).strip().lower()
    if s in {"ct", "counter-terrorist", "counterterrorist", "3"}:
        return "ct"
    if s in {"t", "terrorist", "2"}:
        return "t"
    return s


def inv_utility(v):
    if not isinstance(v, (list, tuple)):
        return 0
    return sum(any(k in str(item).lower().replace(" ", "") for k in UTILITY_NAMES) for item in v)


def parse_one(path: Path, sample_seconds: float):
    from awpy import Demo

    props = [
        "team_name", "X", "Y", "Z", "health", "armor_value", "inventory",
        "current_equip_value", "has_defuser", "has_helmet"
    ]
    demo = Demo(str(path))
    try:
        demo.parse(player_props=props)
    except TypeError:
        demo.parse()

    ticks = demo.ticks.to_pandas()
    rounds = demo.rounds.to_pandas()
    if ticks.empty or rounds.empty:
        return pd.DataFrame()

    round_col = first_col(ticks, "round_num", "round")
    tick_col = first_col(ticks, "tick")
    side_col = first_col(ticks, "side", "team_name", "team")
    health_col = first_col(ticks, "health")
    armor_col = first_col(ticks, "armor", "armor_value")
    equip_col = first_col(ticks, "current_equip_value", "equipment_value")
    inventory_col = first_col(ticks, "inventory")
    if not all([round_col, tick_col, side_col, health_col]):
        raise RuntimeError(f"Required columns missing. Tick columns: {list(ticks.columns)}")

    rr_col = first_col(rounds, "round_num", "round")
    winner_col = first_col(rounds, "winner_side", "winner")
    freeze_col = first_col(rounds, "freeze_end_tick", "freeze_end")
    end_col = first_col(rounds, "end_tick", "end")
    plant_col = first_col(rounds, "bomb_plant_tick", "bomb_plant")
    if not all([rr_col, winner_col, freeze_col, end_col]):
        raise RuntimeError(f"Required round columns missing. Round columns: {list(rounds.columns)}")

    try:
        tickrate = float(demo.tickrate)
    except Exception:
        tickrate = 64.0
    step_ticks = max(1, int(tickrate * sample_seconds))

    winners = {}
    round_meta = {}
    for _, r in rounds.iterrows():
        rn = int(r[rr_col])
        winners[rn] = str(r[winner_col]).upper()
        round_meta[rn] = {
            "freeze": int(r[freeze_col]) if pd.notna(r[freeze_col]) else None,
            "end": int(r[end_col]) if pd.notna(r[end_col]) else None,
            "plant": int(r[plant_col]) if plant_col and pd.notna(r.get(plant_col)) else None,
        }

    ct_score = 0
    t_score = 0
    recent = deque(maxlen=5)
    output = []

    for rn in sorted(round_meta):
        meta = round_meta[rn]
        freeze, end, plant = meta["freeze"], meta["end"], meta["plant"]
        if freeze is None or end is None or end <= freeze:
            continue
        rdf = ticks[ticks[round_col] == rn].copy()
        if rdf.empty:
            continue
        rdf["_side"] = rdf[side_col].map(norm_side)
        unique_ticks = sorted(int(x) for x in rdf[tick_col].dropna().unique() if freeze <= int(x) <= end)
        if not unique_ticks:
            continue
        targets = list(range(freeze, end + 1, step_ticks))
        cursor = 0
        selected = []
        for target in targets:
            while cursor < len(unique_ticks) and unique_ticks[cursor] < target:
                cursor += 1
            if cursor < len(unique_ticks):
                selected.append(unique_ticks[cursor])
        selected = sorted(set(selected))

        recent_ct = (sum(x == "CT" for x in recent) / len(recent)) if recent else 0.5
        for tick in selected:
            frame = rdf[rdf[tick_col] == tick]
            ct = frame[frame["_side"] == "ct"]
            tt = frame[frame["_side"] == "t"]
            if ct.empty or tt.empty:
                continue

            def team_stats(team):
                health = pd.to_numeric(team[health_col], errors="coerce").fillna(0)
                alive = int((health > 0).sum())
                armor = int(pd.to_numeric(team[armor_col], errors="coerce").fillna(0).sum()) if armor_col else 0
                equip = int(pd.to_numeric(team[equip_col], errors="coerce").fillna(0).sum()) if equip_col else 0
                utility = int(team[inventory_col].map(inv_utility).sum()) if inventory_col else 0
                return alive, int(health.sum()), armor, equip, utility

            ca, ch, carmor, ceq, cu = team_stats(ct)
            ta, th, tarmor, teq, tu = team_stats(tt)
            elapsed = max(0.0, (tick - freeze) / tickrate)
            remaining = max(0.0, 115.0 - elapsed)
            planted = int(plant is not None and tick >= plant)
            output.append({
                "source_demo": path.name,
                "round_num": rn,
                "tick": tick,
                "ct_alive": ca, "t_alive": ta,
                "ct_health": ch, "t_health": th,
                "ct_armor": carmor, "t_armor": tarmor,
                "ct_money": 0, "t_money": 0,
                "ct_equipment": ceq, "t_equipment": teq,
                "ct_utility": cu, "t_utility": tu,
                "bomb_planted": planted,
                "round_time_remaining": round(remaining, 2),
                "ct_score": ct_score, "t_score": t_score,
                "recent_ct_win_rate": round(recent_ct, 4),
                "ct_won": int(winners.get(rn, "").upper() == "CT"),
            })

        winner = winners.get(rn, "").upper()
        if winner == "CT":
            ct_score += 1
            recent.append("CT")
        elif winner == "T":
            t_score += 1
            recent.append("T")

    return pd.DataFrame(output)


def main():
    ap = argparse.ArgumentParser(description="Build RoundSense ML training rows from CS2 .dem files using Awpy.")
    ap.add_argument("inputs", nargs="+", help="Demo files or directories containing .dem files")
    ap.add_argument("--out", default="data/processed/training_states.csv")
    ap.add_argument("--sample-seconds", type=float, default=2.0)
    ap.add_argument("--append", action="store_true")
    args = ap.parse_args()

    demos = []
    for x in args.inputs:
        p = Path(x)
        if p.is_dir():
            demos.extend(sorted(p.rglob("*.dem")))
        elif p.suffix.lower() == ".dem":
            demos.append(p)
    if not demos:
        raise SystemExit("No .dem files found.")

    frames = []
    for i, demo in enumerate(demos, 1):
        print(f"[{i}/{len(demos)}] parsing {demo}")
        try:
            df = parse_one(demo, args.sample_seconds)
            print(f"  -> {len(df):,} training rows")
            if not df.empty:
                frames.append(df)
        except Exception as exc:
            print(f"  !! skipped: {exc}")

    if not frames:
        raise SystemExit("No training rows were produced.")
    result = pd.concat(frames, ignore_index=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.append and out.exists():
        old = pd.read_csv(out)
        result = pd.concat([old, result], ignore_index=True)
    result.to_csv(out, index=False)
    print(f"saved {len(result):,} total rows to {out}")
    print("ct_won distribution:")
    print(result["ct_won"].value_counts(normalize=True).sort_index())


if __name__ == "__main__":
    main()
