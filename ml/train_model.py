from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, log_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

FEATURES = [
    "ct_alive", "t_alive", "ct_health", "t_health", "ct_armor", "t_armor",
    "ct_money", "t_money", "ct_equipment", "t_equipment", "ct_utility", "t_utility",
    "bomb_planted", "round_time_remaining", "ct_score", "t_score", "recent_ct_win_rate"
]
TARGET = "ct_won"


def choose_model(kind: str):
    if kind == "xgboost":
        from xgboost import XGBClassifier
        return XGBClassifier(
            n_estimators=450,
            max_depth=6,
            learning_rate=0.045,
            subsample=0.85,
            colsample_bytree=0.85,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=42,
            n_jobs=4,
        )
    return Pipeline([
        ("scale", StandardScaler()),
        ("model", LogisticRegression(max_iter=2000, random_state=42)),
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/processed/training_states.csv")
    ap.add_argument("--out", default="models/round_win_model.joblib")
    ap.add_argument("--model", choices=["xgboost", "logreg"], default="xgboost")
    args = ap.parse_args()

    df = pd.read_csv(args.csv).dropna(subset=FEATURES + [TARGET])
    X = df[FEATURES]
    y = df[TARGET].astype(int)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = choose_model(args.model)
    model.fit(X_train, y_train)
    probs = model.predict_proba(X_test)[:, 1]
    preds = (probs >= 0.5).astype(int)
    print(f"samples={len(df):,}")
    print(f"accuracy={accuracy_score(y_test, preds):.4f}")
    print(f"f1={f1_score(y_test, preds):.4f}")
    print(f"roc_auc={roc_auc_score(y_test, probs):.4f}")
    print(f"log_loss={log_loss(y_test, probs):.4f}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out)
    print(f"saved={out}")


if __name__ == "__main__":
    main()
