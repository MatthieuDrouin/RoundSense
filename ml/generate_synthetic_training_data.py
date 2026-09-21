from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=30000)
    ap.add_argument("--out", default="data/processed/training_states.csv")
    args = ap.parse_args()

    rng = np.random.default_rng(42)
    n = args.rows
    ct_alive = rng.integers(0, 6, n)
    t_alive = rng.integers(0, 6, n)
    invalid = (ct_alive == 0) & (t_alive == 0)
    ct_alive[invalid] = 1
    ct_health = np.array([rng.integers(max(1, a*35), max(2, a*100+1)) if a else 0 for a in ct_alive])
    t_health = np.array([rng.integers(max(1, a*35), max(2, a*100+1)) if a else 0 for a in t_alive])
    ct_armor = np.array([rng.integers(0, a*101) if a else 0 for a in ct_alive])
    t_armor = np.array([rng.integers(0, a*101) if a else 0 for a in t_alive])
    ct_equipment = rng.integers(0, 26001, n)
    t_equipment = rng.integers(0, 26001, n)
    ct_money = rng.integers(0, 30001, n)
    t_money = rng.integers(0, 30001, n)
    ct_utility = rng.integers(0, 16, n)
    t_utility = rng.integers(0, 16, n)
    bomb_planted = rng.binomial(1, 0.24, n)
    round_time_remaining = rng.uniform(0, 115, n)
    ct_score = rng.integers(0, 13, n)
    t_score = rng.integers(0, 13, n)
    recent = rng.beta(3, 3, n)

    latent = (
        0.9*(ct_alive-t_alive)
        + (ct_health-t_health)/260
        + (ct_armor-t_armor)/600
        + (ct_equipment-t_equipment)/9000
        + 0.07*(ct_utility-t_utility)
        + 0.025*(ct_score-t_score)
        + 0.6*(recent-0.5)
        - 0.65*bomb_planted
        + rng.normal(0, 0.55, n)
    )
    p = sigmoid(latent)
    y = rng.binomial(1, p)
    df = pd.DataFrame({
        "ct_alive": ct_alive, "t_alive": t_alive,
        "ct_health": ct_health, "t_health": t_health,
        "ct_armor": ct_armor, "t_armor": t_armor,
        "ct_money": ct_money, "t_money": t_money,
        "ct_equipment": ct_equipment, "t_equipment": t_equipment,
        "ct_utility": ct_utility, "t_utility": t_utility,
        "bomb_planted": bomb_planted,
        "round_time_remaining": round_time_remaining.round(2),
        "ct_score": ct_score, "t_score": t_score,
        "recent_ct_win_rate": recent.round(4),
        "ct_won": y,
    })
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"wrote {len(df):,} synthetic rows to {out}")
    print("NOTE: synthetic data is for pipeline testing only; do not report its metrics as real CS2 model performance.")


if __name__ == "__main__":
    main()
