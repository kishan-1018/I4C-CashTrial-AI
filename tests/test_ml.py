import json
from pathlib import Path
import pytest
from ml.predictor import HotspotPredictor

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

@pytest.fixture
def sample_incident():
    with open(DATA_DIR / "demo_scenarios.json", "r", encoding="utf-8") as f:
        return json.load(f)[0]

def test_response_priority_scoring(sample_incident):
    predictor = HotspotPredictor()
    
    # Fast reporting (<45 min)
    sample_incident["reporting_delay_minutes"] = 25
    priority_res = predictor.evaluate_response_priority(sample_incident)
    assert priority_res["priority_tier"] == "HIGH PRIORITY"
    assert priority_res["urgency_score"] >= 0.70

    # Old complaint (>200 min)
    sample_incident["reporting_delay_minutes"] = 300
    priority_res_old = predictor.evaluate_response_priority(sample_incident)
    assert priority_res_old["priority_tier"] in ["FORENSIC / FOLLOW-UP", "MEDIUM PRIORITY"]

def test_corridor_prediction_with_alternatives(sample_incident):
    predictor = HotspotPredictor()
    pred_res = predictor.predict_corridor(sample_incident)
    
    assert "primary_corridor" in pred_res
    assert "alternatives" in pred_res
    assert len(pred_res["alternatives"]) >= 1
    assert pred_res["primary_corridor"]["confidence"] > 0.0

def test_candidate_touchpoint_ranking(sample_incident):
    predictor = HotspotPredictor()
    ranked = predictor.rank_candidate_touchpoints("mewat_nuh_rural", sample_incident, top_k=3)
    
    assert len(ranked) == 3
    assert ranked[0]["ranking_score"] >= ranked[1]["ranking_score"]
    assert "contributing_factors" in ranked[0]
    assert len(ranked[0]["contributing_factors"]) > 0

def test_full_decision_support_taxonomy(sample_incident):
    predictor = HotspotPredictor()
    ds = predictor.generate_full_decision_support(sample_incident)
    
    tax = ds["taxonomy"]
    assert "observed" in tax
    assert "derived" in tax
    assert "predicted" in tax
    assert "recommended" in tax
    assert tax["recommended"]["human_review_required"] is True
