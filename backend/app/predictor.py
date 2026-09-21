from __future__ import annotations

import math
from pathlib import Path

from .schemas import FeatureVector

FEATURE_ORDER = [
    "ct_alive", "t_alive", "ct_health", "t_health", "ct_armor", "t_armor",
    "ct_money", "t_money", "ct_equipment", "t_equipment", "ct_utility", "t_utility",
    "bomb_planted", "round_time_remaining", "ct_score", "t_score", "recent_ct_win_rate"
]


class RoundPredictor:
    def __init__(self, model_path: str):
        self.model_path = Path(model_path)
        self.model = None
        self.source = "heuristic"
        self._load()

    def _load(self):
        if not self.model_path.exists():
            return
        try:
            import joblib
            self.model = joblib.load(self.model_path)
            self.source = "trained_model"
        except Exception:
            self.model = None
            self.source = "heuristic"

    @staticmethod
    def _sigmoid(x: float) -> float:
        return 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, x))))

    @staticmethod
    def _logit(p: float) -> float:
        p = max(0.001, min(0.999, p))
        return math.log(p / (1.0 - p))

    def heuristic(self, f: FeatureVector) -> float:
        alive = (f.ct_alive - f.t_alive) * 0.85
        health = (f.ct_health - f.t_health) / 260.0
        armor = (f.ct_armor - f.t_armor) / 500.0
        equip = (f.ct_equipment - f.t_equipment) / 8500.0
        utility = (f.ct_utility - f.t_utility) * 0.08
        score = (f.ct_score - f.t_score) * 0.025
        momentum = (f.recent_ct_win_rate - 0.5) * 0.5
        bomb = -0.55 if f.bomb_planted else 0.0
        time_adjust = 0.0
        if f.bomb_planted and f.round_time_remaining < 20:
            time_adjust = -0.25
        z = alive + health + armor + equip + utility + score + momentum + bomb + time_adjust
        p = self._sigmoid(z)
        return max(0.01, min(0.99, p))

    def _base_prediction(self, f: FeatureVector) -> tuple[float, str]:
        if self.model is None:
            return self.heuristic(f), "heuristic"
        try:
            import pandas as pd
            row = pd.DataFrame([[getattr(f, name) for name in FEATURE_ORDER]], columns=FEATURE_ORDER)
            if hasattr(self.model, "predict_proba"):
                p = float(self.model.predict_proba(row)[0][1])
            else:
                p = float(self.model.predict(row)[0])
            return max(0.01, min(0.99, p)), "trained_model"
        except Exception:
            return self.heuristic(f), "heuristic_fallback"

    def predict(self, f: FeatureVector, positioning_adjustment: float = 0.0) -> tuple[float, str]:
        p, source = self._base_prediction(f)

        # Positioning is blended in log-odds space so it can move an ML
        # probability without replacing the trained model. A negative tactical
        # adjustment favors T; a positive adjustment favors CT.
        if abs(positioning_adjustment) >= 0.01:
            p = self._sigmoid(self._logit(p) + positioning_adjustment)
            source = f"{source}+positioning"

        return max(0.01, min(0.99, p)), source
