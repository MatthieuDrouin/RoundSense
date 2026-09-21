from backend.app.feature_engine import FeatureEngine
from backend.app.predictor import RoundPredictor
from backend.app.map_data import world_to_radar
from backend.app.gsi import GSIProcessor


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


def inverse_mirage(rx, ry):
    return -3230 + rx * 5.0 * 1024, 1713 - ry * 5.0 * 1024


def positioned_player(name, team, rx, ry):
    x, y = inverse_mirage(rx, ry)
    return {
        "name": name,
        "team": team,
        "position": f"{x},{y},0",
        "state": {"health":100, "armor":100, "money":3000},
        "weapons": {"0":{"name":"weapon_ak47" if team=="T" else "weapon_m4a1"}},
        "match_stats": {"kills":10,"deaths":8,"assists":2,"mvps":1,"score":20},
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


def test_world_to_radar_mirage_site_a():
    x, y = inverse_mirage(.54, .76)
    point = world_to_radar("de_mirage", x, y)
    assert point is not None
    assert abs(point[0] - .54) < 1e-6
    assert abs(point[1] - .76) < 1e-6


def test_empty_site_execute_favors_t():
    e = FeatureEngine()
    payload = {
        "allplayers": {
            **{f"t{i}": positioned_player(f"T{i}", "T", .54 + i*.005, .76 + i*.004) for i in range(5)},
            **{f"ct{i}": positioned_player(f"CT{i}", "CT", .23 + i*.006, .28 + i*.004) for i in range(5)},
        }
    }
    players = e.parse_players(payload)
    tactical = e.tactical_snapshot(
        "de_mirage",
        players,
        bomb_state="carried",
        round_time_remaining=30,
    )
    assert tactical.target_site == "A"
    assert tactical.t_site_pressure >= 3
    assert tactical.ct_site_coverage == 0
    assert tactical.positioning_adjustment < 0


def test_positioning_adjustment_changes_probability(tmp_path):
    e = FeatureEngine()
    ps = e.parse_players(sample_payload())
    f = e.build_features(
        ct=e.summarize_team(ps,"CT"),
        t=e.summarize_team(ps,"T"),
        bomb_state="carried",
        round_time_remaining=40,
        ct_score=5,
        t_score=5,
    )
    predictor = RoundPredictor(str(tmp_path/'missing.joblib'))
    neutral,_ = predictor.predict(f, 0)
    t_edge,_ = predictor.predict(f, -0.8)
    assert t_edge < neutral


def test_all_t_dead_preplant_is_100_percent_ct(tmp_path):
    payload = sample_payload()
    payload["allplayers"]["2"]["state"]["health"] = 0
    payload["bomb"]["state"] = "carried"
    payload["phase_countdowns"] = {"phase": "live", "phase_ends_in": "40"}
    processor = GSIProcessor(RoundPredictor(str(tmp_path / "missing.joblib")))
    state = processor.process(payload)
    assert state.full_team_data is True
    assert state.t.alive == 0
    assert state.ct_win_probability == 1.0
    assert state.t_win_probability == 0.0
    assert state.prediction_source == "terminal_elimination"


def test_round_result_overrides_model(tmp_path):
    payload = sample_payload()
    payload["round"] = {"phase": "over", "win_team": "T"}
    payload["phase_countdowns"] = {"phase": "over", "phase_ends_in": "0"}
    processor = GSIProcessor(RoundPredictor(str(tmp_path / "missing.joblib")))
    state = processor.process(payload)
    assert state.ct_win_probability == 0.0
    assert state.t_win_probability == 1.0
    assert state.prediction_source == "round_result"


def test_planted_bomb_with_dead_t_uses_bomb_clock(tmp_path):
    payload = sample_payload()
    payload["allplayers"]["2"]["state"]["health"] = 0
    payload["bomb"]["state"] = "planted"
    payload["phase_countdowns"] = {"phase": "bomb", "phase_ends_in": "18"}
    processor = GSIProcessor(RoundPredictor(str(tmp_path / "missing.joblib")))
    state = processor.process(payload)
    assert state.t.alive == 0
    assert state.ct_win_probability >= 0.94
    assert state.prediction_source == "bomb_clock_override"
