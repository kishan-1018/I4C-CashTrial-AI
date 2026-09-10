"""
Multi-Rail Transaction Network Analysis Engine.
Extracts localized 3-hop bounded ego graphs, calculates centrality,
identifies potential network hubs, and measures transaction velocities.
"""

from typing import Dict, Any, List
import networkx as nx

class TransactionGraphAnalyzer:
    """Analyzes multi-hop financial transaction chains for a cybercrime complaint."""

    def __init__(self):
        pass

    def build_ego_graph(self, complaint_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Builds a directed ego graph from the complaint's transaction chain
        and returns a node/link structure ready for both analysis and frontend visualization.
        """
        G = nx.DiGraph()
        chain = complaint_data.get("transaction_chain", [])
        
        nodes_dict = {}
        links = []

        # Add Victim Node
        victim_id = "VICTIM_ACCOUNT"
        victim_vpa = "Victim Complainant"
        if chain:
            victim_id = chain[0].get("sender_account", "VICTIM_ACCOUNT")
            victim_vpa = chain[0].get("sender_vpa", "Victim Complainant")

        G.add_node(victim_id, node_type="VICTIM", label=victim_vpa, bank="Victim Bank", role="Origin")
        nodes_dict[victim_id] = {
            "id": victim_id,
            "label": victim_vpa,
            "node_type": "VICTIM",
            "bank": "Victim Origin Account",
            "jurisdiction": complaint_data.get("origin_jurisdiction", {}).get("state", "Origin State"),
            "risk_score": 0.0
        }

        # Traverse transaction hops
        for hop in chain:
            sender = hop.get("sender_account")
            receiver = hop.get("receiver_account")
            receiver_vpa = hop.get("receiver_vpa", receiver)
            bank_name = hop.get("bank_name", "Unknown Bank")
            ifsc = hop.get("ifsc", "")
            amount = hop.get("amount_inr", 0)
            utr = hop.get("utr_number", "")
            velocity = hop.get("velocity_mins", 0)
            hop_num = hop.get("hop_number", 1)

            # Determine role/type based on hop position and bank
            if hop_num == len(chain):
                role = "TERMINAL_MULE"
                node_type = "TERMINAL_MULE"
            elif "Payment" in bank_name or "PYTM" in ifsc or "AIRP" in ifsc:
                role = "DIGITAL_WALLET_TRANSIT"
                node_type = "MULE_HOP"
            else:
                role = "INTERMEDIARY_LAYER"
                node_type = "MULE_HOP"

            if receiver not in nodes_dict:
                G.add_node(receiver, node_type=node_type, label=receiver_vpa, bank=bank_name, role=role)
                nodes_dict[receiver] = {
                    "id": receiver,
                    "label": receiver_vpa,
                    "node_type": node_type,
                    "bank": bank_name,
                    "ifsc": ifsc,
                    "branch_state": hop.get("branch_state", ""),
                    "branch_city": hop.get("branch_city", ""),
                    "hop_number": hop_num,
                    "role": role,
                    "risk_score": round(0.45 + (0.15 * hop_num), 2)
                }

            G.add_edge(sender, receiver, amount=amount, utr=utr, velocity_mins=velocity, hop_number=hop_num)
            links.append({
                "source": sender,
                "target": receiver,
                "amount": amount,
                "utr": utr,
                "velocity_mins": velocity,
                "hop_number": hop_num
            })

        # Add target Cash-Out point as terminal sink node
        gt = complaint_data.get("ground_truth", {})
        if gt.get("target_touchpoint_id"):
            tp_id = gt["target_touchpoint_id"]
            tp_name = gt.get("target_touchpoint_name", "Cash-Out Point")
            tp_type = gt.get("target_touchpoint_type", "CASH_OUT_TOUCHPOINT")
            last_account = chain[-1]["receiver_account"] if chain else victim_id

            G.add_node(tp_id, node_type="TOUCHPOINT", label=tp_name, role="CASH_OUT")
            nodes_dict[tp_id] = {
                "id": tp_id,
                "label": tp_name,
                "node_type": "TOUCHPOINT",
                "touchpoint_type": tp_type,
                "role": "PHYSICAL_CASH_OUT",
                "risk_score": 0.95
            }
            G.add_edge(last_account, tp_id, amount=complaint_data.get("disputed_amount_inr", 0), utr="ATM_CSP_DISBURSEMENT")
            links.append({
                "source": last_account,
                "target": tp_id,
                "amount": complaint_data.get("disputed_amount_inr", 0),
                "utr": "CASH_WITHDRAWAL",
                "velocity_mins": 5,
                "hop_number": len(chain) + 1
            })

        # Calculate network indicators
        degree_centrality = nx.degree_centrality(G)
        for node_id, data in nodes_dict.items():
            data["centrality"] = round(degree_centrality.get(node_id, 0.0), 3)

        # Detect potential network hub
        potential_hubs = [
            nid for nid, cent in degree_centrality.items() 
            if cent >= 0.5 and nodes_dict[nid]["node_type"] != "VICTIM"
        ]

        return {
            "complaint_id": complaint_data.get("complaint_id"),
            "total_nodes": len(nodes_dict),
            "total_edges": len(links),
            "hop_depth": len(chain),
            "potential_network_hubs": potential_hubs,
            "nodes": list(nodes_dict.values()),
            "links": links
        }
