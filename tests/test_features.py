from backend.app.feature_engine import FeatureEngine
from backend.app.predictor import RoundPredictor


def sample_payload():
    return {
        "provider": {"timestamp": 1},
        "map": {"name": "de_mirage", "round": 3, "team_ct": {"score": 2}, "team_t": {"score": 1}},
        "round": {"phase": "live"},
        "bomb": {"state": "carried"},
        "phase_countdowns": {"phase_ends_in": "91.2"},
        "allplayers": {
            "1": {"name":"A","team":"CT","position":"1,2,3","state":{"health":100,"armor":90,"money":1200},"weapons":{"0":{"name":"weapon_m4a1"}},"match_stats":{"kills":8,"deaths":4,"assists":2,"mvps":1,"score":18}},
            "2": {"name":"B","team":"T","position":"4,5,6","state":{"health":70,"armor":50,"money":800},"weapons":{"0":{"name":"weapon_ak47"}},"match_stats":{"kills":4,"deaths":6,"assists":1,"mvps":0,"score":9}},
        },
    }


def test_player_parsing_and_team_totals():
    e=FeatureEngine()
    ps=e.parse_players(sample_payload())
    assert len(ps)==2
    ct=e.summarize_team(ps,"CT")
    t=e.summarize_team(ps,"T")
    assert ct.alive==1 and t.alive==1
    assert ct.equipment_value==2900
    assert t.equipment_value==2700


def test_heuristic_probability_range(tmp_path):
    e=FeatureEngine()
    ps=e.parse_players(sample_payload())
    f=e.build_features(ct=e.summarize_team(ps,"CT"),t=e.summarize_team(ps,"T"),bomb_state="carried",round_time_remaining=91.2,ct_score=2,t_score=1)
    p,_=RoundPredictor(str(tmp_path/'missing.joblib')).predict(f)
    assert 0.0 < p < 1.0
