import json
from pathlib import Path
import pytest
from ml.graph_analyzer import TransactionGraphAnalyzer

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def test_graph_construction_and_centrality():
    with open(DATA_DIR / "demo_scenarios.json", "r", encoding="utf-8") as f:
        incident = json.load(f)[0]

    analyzer = TransactionGraphAnalyzer()
    graph_res = analyzer.build_ego_graph(incident)

    assert graph_res["total_nodes"] >= 4
    assert graph_res["total_edges"] >= 3
    assert graph_res["hop_depth"] >= 2
    
    # Check that victim node exists
    victim_nodes = [n for n in graph_res["nodes"] if n["node_type"] == "VICTIM"]
    assert len(victim_nodes) == 1
    
    # Check that each node has a centrality index
    for n in graph_res["nodes"]:
        assert "centrality" in n
        assert isinstance(n["centrality"], (int, float))
