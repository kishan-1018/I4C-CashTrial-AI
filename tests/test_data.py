import json
from pathlib import Path
import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def test_touchpoints_registry_exists_and_valid():
    tp_file = DATA_DIR / "cashout_touchpoints_registry.json"
    assert tp_file.exists(), "Touchpoints registry file must exist"
    
    with open(tp_file, "r", encoding="utf-8") as f:
        tps = json.load(f)

    assert len(tps) >= 50, f"Expected at least 50 touchpoints, got {len(tps)}"
    valid_types = {"BANK_ATM", "WHITE_LABEL_ATM", "CSP_BANK_MITRA", "MICRO_ATM_MERCHANT"}
    
    for tp in tps:
        assert "touchpoint_id" in tp
        assert tp["touchpoint_type"] in valid_types
        assert len(tp["coordinates"]) == 2
        assert isinstance(tp["coordinates"][0], (int, float))
        assert isinstance(tp["coordinates"][1], (int, float))
        assert "police_jurisdiction" in tp

def test_demo_scenarios_structure():
    scenarios_file = DATA_DIR / "demo_scenarios.json"
    assert scenarios_file.exists()
    
    with open(scenarios_file, "r", encoding="utf-8") as f:
        scenarios = json.load(f)

    assert len(scenarios) >= 4, "Expected at least 4 curated demo scenarios"
    
    for sc in scenarios:
        assert "complaint_id" in sc
        assert "scam_category" in sc
        assert sc["disputed_amount_inr"] > 0
        assert "transaction_chain" in sc
        assert len(sc["transaction_chain"]) >= 2
        assert "ground_truth" in sc
        assert "origin_jurisdiction" in sc
