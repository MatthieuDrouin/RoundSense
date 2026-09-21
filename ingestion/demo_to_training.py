from __future__ import annotations

"""Starter extractor for historical CS2 demos.

Awpy exposes parsed rounds, events and tick-level data. Exact column names may change
between releases, so this script prints discovered columns and includes a conservative
snapshot builder you can adapt after parsing your first real demo.
"""

import argparse
from pathlib import Path

import pandas as pd


def parse_demo(path: str):
    from awpy import Demo
    demo = Demo(path)
    demo.parse()
    print("round columns:", demo.rounds.columns)
    print("tick columns:", demo.ticks.columns)
    return demo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("demo")
    ap.add_argument("--out", default="data/processed/awpy_ticks.csv")
    ap.add_argument("--sample-every", type=int, default=64, help="Keep one of every N parsed tick rows")
    args = ap.parse_args()

    demo = parse_demo(args.demo)
    ticks = demo.ticks.to_pandas()
    sampled = ticks.iloc[::max(1, args.sample_every)].copy()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sampled.to_csv(out, index=False)
    print(f"saved {len(sampled):,} sampled tick rows to {out}")
    print("Next: map your installed Awpy tick columns into RoundSense's 17 model features and attach each round winner as ct_won.")


if __name__ == "__main__":
    main()
