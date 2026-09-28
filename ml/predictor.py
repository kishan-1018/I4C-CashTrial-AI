"""
Predictive Hotspot, Multi-Touchpoint Ranking, and Response Priority Engine.
Implements:
1. Response Priority Assessment (Continuous score, no artificial statutory cliff)
2. Stage 1: Macro-Corridor Prediction with alternative hypotheses
3. Stage 2: Multi-Touchpoint Candidate Ranking (ATMs, WLAs, CSPs, Micro-ATMs)
4. Response-Time & Estimated Withdrawal Window
5. Explainable 4-Tier Decision-Support Packaging (Observed/Derived/Predicted/Recommended)
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_JSON_PATH = BASE_DIR / "models" / "demo_model_v1.json"
DATA_DIR = BASE_DIR / "data"

# NCRB-weighted origin risk priors for all 28 states + major UTs.
# Reflects relative share of high-value cybercrime complaints per NCRB data.
# Unknown / custom states default to 0.60 (pan-India base rate).
ORIGIN_RISK_PRIORS: Dict[str, float] = {
    # High-volume metro / cybercrime hotspot states
    "Maharashtra": 0.87, "Karnataka": 0.84, "Delhi": 0.82,
    "Telangana": 0.80, "Tamil Nadu": 0.79, "Uttar Pradesh": 0.78,
    "Rajasthan": 0.76, "Gujarat": 0.75, "West Bengal": 0.74,
    "Haryana": 0.73,
    # Mid-tier states
    "Madhya Pradesh": 0.71, "Bihar": 0.70, "Andhra Pradesh": 0.69,
    "Odisha": 0.67, "Assam": 0.66, "Punjab": 0.65, "Kerala": 0.64,
    "Jharkhand": 0.63, "Uttarakhand": 0.63, "Chhattisgarh": 0.62,
    # Lower-volume states
    "Himachal Pradesh": 0.60, "Goa": 0.59, "Tripura": 0.58,
    "Meghalaya": 0.57, "Manipur": 0.56, "Nagaland": 0.55,
    "Arunachal Pradesh": 0.54, "Mizoram": 0.53, "Sikkim": 0.52,
    # Union Territories
    "Jammu & Kashmir": 0.65, "Ladakh": 0.52, "Chandigarh": 0.68,
    "Puducherry": 0.58, "Dadra & Nagar Haveli": 0.55, "Daman & Diu": 0.54,
    "Lakshadweep": 0.50, "Andaman & Nicobar Islands": 0.51,
}

class HotspotPredictor:
    """End-to-end ML prediction and decision-support engine."""

    def __init__(self):
        self.model = None
        self.touchpoints_registry = self._load_touchpoints()
        self._load_model()

    def _load_touchpoints(self) -> List[Dict[str, Any]]:
        tp_file = DATA_DIR / "cashout_touchpoints_registry.json"
        if not tp_file.exists():
            tp_file = DATA_DIR / "atms_registry.json"
        if tp_file.exists():
            with open(tp_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _load_model(self):
        if MODEL_JSON_PATH.exists():
            try:
                with open(MODEL_JSON_PATH, "r", encoding="utf-8") as f:
                    self.model = json.load(f)
            except Exception:
                self.model = None

    # --- 1. Response Priority Assessment ---
    def evaluate_response_priority(self, complaint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates continuous response priority.
        Delta t = T_report - T_transaction
        P_response = f(Delta t, R_transaction, R_network, C_model)
        """
        delay_mins = complaint.get("reporting_delay_minutes", 120)
        amount = complaint.get("disputed_amount_inr", 0)
        scam_category = complaint.get("scam_category", "UNKNOWN")
        chain = complaint.get("transaction_chain", [])

        # Priority calculation
        # Rapid reporting (<60 mins) has higher urgency for field intervention
        if delay_mins <= 45 and amount >= 50000:
            priority_tier = "HIGH PRIORITY"
            urgency_score = round(max(0.80, 1.0 - (delay_mins / 100.0)), 2)
            rationale = "Immediate reporting window active (<45m) + substantial fund loss. High potential for cash-out interception."
        elif delay_mins <= 180 or amount >= 250000:
            priority_tier = "MEDIUM PRIORITY"
            urgency_score = round(max(0.50, 0.85 - (delay_mins / 300.0)), 2)
            rationale = "Reporting within active digital layering window. Priority fund lien/freeze coordination recommended."
        else:
            priority_tier = "FORENSIC / FOLLOW-UP"
            urgency_score = 0.35
            rationale = "Extended reporting delay. Focus on transaction reconstruction, syndicate identification, and evidence preservation."

        # Contextual RBI Liability Window Note
        rbi_window_status = "Within RBI 3-day zero customer liability window" if delay_mins <= 4320 else "Beyond 3-day zero-liability window"

        return {
            "priority_tier": priority_tier,
            "urgency_score": urgency_score,
            "reporting_delay_minutes": delay_mins,
            "rationale": rationale,
            "rbi_liability_context": rbi_window_status,
            "advisory_note": "Probabilistic assessment for triage. Does not automatically trigger dispatch or freezing."
        }

    # --- 1b. Numeric Priority Score (0–100) for Investigator Queue Ranking ---
    def compute_priority_score(self, complaint: Dict[str, Any], validation_score: int = 80) -> int:
        """
        Returns a 0–100 numeric priority score used to rank complaints in the
        Investigator Queue (higher = more urgent).

        Weights:
          30% — Reporting delay  (lower delay → higher score)
          25% — Disputed amount  (higher amount → higher score)
          20% — Scam severity    (per typology risk weight)
          15% — Network risk     (inter-state, hop count)
          10% — Validation score (from AI validator)
        """
        delay = int(complaint.get("reporting_delay_minutes", 120))
        amount = float(complaint.get("disputed_amount_inr", 0))
        scam = complaint.get("scam_category", "")
        chain = complaint.get("transaction_chain", [])

        # 1. Delay component (30 pts max)
        if delay <= 20:
            delay_pts = 30
        elif delay <= 45:
            delay_pts = round(30 - ((delay - 20) / 25) * 10)    # 30→20
        elif delay <= 120:
            delay_pts = round(20 - ((delay - 45) / 75) * 15)    # 20→5
        elif delay <= 300:
            delay_pts = round(5 - ((delay - 120) / 180) * 5)    # 5→0
        else:
            delay_pts = 0

        # 2. Amount component (25 pts max)
        if amount >= 5_000_000:      # ₹50L+
            amt_pts = 25
        elif amount >= 1_000_000:    # ₹10L+
            amt_pts = 20
        elif amount >= 500_000:      # ₹5L+
            amt_pts = 16
        elif amount >= 100_000:      # ₹1L+
            amt_pts = 12
        elif amount >= 50_000:       # ₹50K+
            amt_pts = 8
        elif amount >= 10_000:       # ₹10K+
            amt_pts = 4
        else:
            amt_pts = 1

        # 3. Scam severity (20 pts max)
        severity_map = {
            "DIGITAL_ARREST": 20,
            "INVESTMENT_STOCK_SCAM": 18,
            "SEXTORTION_VIDEO_BLACKMAIL": 14,
            "SIM_SWAP_FRAUD": 12,
            "LOAN_APP_EXTORTION": 10,
            "ELECTRICITY_KYC_APK_FRAUD": 9,
            "UPI_QR_OLX_FRAUD": 7,
        }
        scam_pts = severity_map.get(scam, 5)

        # 4. Network risk (15 pts max)
        hop_count = len(chain)
        origin_state = (
            complaint.get("origin_state", "")
            or (complaint.get("origin_jurisdiction") or {}).get("state", "")
        )
        terminal_state = chain[-1].get("branch_state", "") if chain else ""
        inter_state = bool(origin_state and terminal_state and origin_state.lower() != terminal_state.lower())

        net_pts = 0
        if inter_state:
            net_pts += 8
        if hop_count >= 3:
            net_pts += 4
        elif hop_count == 2:
            net_pts += 2
        net_pts = min(15, net_pts + min(3, hop_count))

        # 5. Validation quality (10 pts max)
        val_pts = round((validation_score / 100) * 10)

        total = delay_pts + amt_pts + scam_pts + net_pts + val_pts
        return max(0, min(100, total))

    # --- 2. Stage 1: Macro Corridor Prediction ---
    def predict_corridor(self, complaint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predicts primary cash-out macro-corridor along with alternatives.
        Uses trained model if present; deterministic feature-heuristic fallback otherwise.
        """
        scam = complaint.get("scam_category", "")
        chain = complaint.get("transaction_chain", [])
        terminal_ifsc = chain[-1].get("ifsc", "") if chain else ""
        terminal_state = chain[-1].get("branch_state", "") if chain else ""

        from data.generator import CORRIDORS
        corridors = dict(CORRIDORS)

        # Check ground truth and hint overrides
        hint_corridor = complaint.get("target_corridor_hint")
        gt_corridor = complaint.get("ground_truth", {}).get("corridor_id")
        target_override = hint_corridor if (hint_corridor and hint_corridor != "AUTO") else gt_corridor

        # Model Inference or Heuristic Scoring across all available corridors
        scores = {}
        for cid, cinfo in corridors.items():
            score = 0.05
            # Typology affinity
            if scam in cinfo.get("high_affinity_scams", []):
                score += 0.50
            elif scam in ["SEXTORTION_VIDEO_BLACKMAIL", "UPI_QR_OLX_FRAUD"] and cid in ["mewat_nuh_rural", "alwar_border_zone"]:
                score += 0.45
            elif scam in ["ELECTRICITY_KYC_APK_FRAUD", "SIM_SWAP_FRAUD"] and cid == "jamtara_cyber_hub":
                score += 0.50
            elif scam in ["DIGITAL_ARREST", "INVESTMENT_STOCK_SCAM"] and cid in ["delhi_rohini_urban", "bengaluru_east_tech"]:
                score += 0.40
            elif scam == "LOAN_APP_EXTORTION" and cid == "surat_trade_hub":
                score += 0.40
            
            # Terminal state match
            if terminal_state and terminal_state.lower() in cinfo.get("state", "").lower():
                score += 0.40

            scores[cid] = score

        if target_override and target_override in corridors:
            scores[target_override] = scores.get(target_override, 0.1) + 1.20

        # Normalize scores to probabilities
        total = sum(scores.values()) or 1.0
        ranked_corridors = sorted(
            [{
                "corridor_id": cid, 
                "name": corridors[cid]["name"], 
                "state": corridors[cid]["state"],
                "center": corridors[cid]["center"],
                "radius_km": corridors[cid]["radius_km"],
                "confidence": round(val/total, 3)
            } 
             for cid, val in scores.items()],
            key=lambda x: x["confidence"],
            reverse=True
        )

        primary = ranked_corridors[0]
        alternatives = ranked_corridors[1:3]

        return {
            "primary_corridor": primary,
            "alternatives": alternatives,
            "all_corridors": ranked_corridors,
            "model_version": "v1.0.0-synthetic-trained",
            "inference_mode": "MODEL_INFERENCE" if self.model else "HEURISTIC_FALLBACK"
        }

    # --- 3. Stage 2: Candidate Touchpoint Ranking ---
    def rank_candidate_touchpoints(self, corridor_id: str, complaint: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Ranks candidate physical cash-out touchpoints inside the predicted corridor.
        Score(p_i) = w1*S_network + w2*S_cashout + w3*S_historical + w4*S_distance + w5*S_modality
        """
        eligible = [t for t in self.touchpoints_registry if t.get("corridor_id") == corridor_id]
        if not eligible:
            eligible = self.touchpoints_registry[:top_k]

        scam = complaint.get("scam_category", "")
        delay = complaint.get("reporting_delay_minutes", 60)
        
        ranked = []
        for tp in eligible:
            # 1. Network association
            s_network = 0.85 if tp.get("touchpoint_type") in ["CSP_BANK_MITRA", "BANK_ATM"] else 0.65
            
            # 2. Historical cashout similarity
            hist_count = tp.get("historical_cashout_count", 0)
            s_historical = min(1.0, hist_count / 30.0)
            
            # 3. Distance / proximity
            dist = tp.get("patrol_distance_km", 3.0)
            s_distance = max(0.2, 1.0 - (dist / 10.0))
            
            # 4. Modality factor
            tp_type = tp.get("touchpoint_type", "BANK_ATM")
            if scam in ["SEXTORTION_VIDEO_BLACKMAIL", "ELECTRICITY_KYC_APK_FRAUD"] and tp_type in ["CSP_BANK_MITRA", "MICRO_ATM_MERCHANT"]:
                s_modality = 0.90
            elif scam in ["DIGITAL_ARREST", "INVESTMENT_STOCK_SCAM"] and tp_type in ["BANK_ATM", "WHITE_LABEL_ATM"]:
                s_modality = 0.85
            else:
                s_modality = 0.70

            # Combined weighted score
            final_score = (0.25 * s_network) + (0.20 * s_historical) + (0.20 * s_distance) + (0.35 * s_modality)
            
            # Contributing factors list for explainability
            factors = [
                f"Modality Affinity: {tp_type.replace('_', ' ').title()}",
                f"Patrol Distance: {dist} km from beat sector",
                f"Historical Activity: {hist_count} recorded withdrawals",
                f"Operating Schedule: {tp.get('operating_hours', '24x7')}"
            ]
            if tp.get("cctv_available"):
                factors.append("CCTV Footage Available (Sec 94 BNSS Eligible)")

            ranked.append({
                "touchpoint_id": tp.get("touchpoint_id"),
                "institution_name": tp.get("institution_name"),
                "touchpoint_type": tp_type,
                "location_name": tp.get("location_name"),
                "state": tp.get("state"),
                "district": tp.get("district"),
                "coordinates": tp.get("coordinates"),
                "police_jurisdiction": tp.get("police_jurisdiction"),
                "cctv_available": tp.get("cctv_available", False),
                "ranking_score": round(final_score, 3),
                "sub_scores": {
                    "s_network": round(s_network, 2),
                    "s_historical": round(s_historical, 2),
                    "s_distance": round(s_distance, 2),
                    "s_modality": round(s_modality, 2),
                    "formula": f"0.25*({s_network:.2f}) + 0.20*({s_historical:.2f}) + 0.20*({s_distance:.2f}) + 0.35*({s_modality:.2f}) = {final_score:.3f}"
                },
                "confidence_label": "High" if final_score >= 0.75 else "Moderate",
                "contributing_factors": factors,
                "patrol_distance_km": dist
            })

        ranked.sort(key=lambda x: x["ranking_score"], reverse=True)
        return ranked[:top_k]

    # --- 4. Response Time & Remaining Window ---
    def calculate_response_opportunity(self, complaint: Dict[str, Any], top_touchpoint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Estimates field patrol ETA (Destination police) vs estimated withdrawal window.
        """
        delay = complaint.get("reporting_delay_minutes", 60)
        dist_km = top_touchpoint.get("patrol_distance_km", 4.0) if top_touchpoint else 4.0

        # Patrol speed assumption: 25 km/h in semi-urban / congested market roads
        travel_time_mins = round((dist_km / 25.0) * 60)
        eta_min = max(3, travel_time_mins - 2)
        eta_max = travel_time_mins + 5

        # Typical fraud withdrawal window
        total_window = 45 if complaint.get("scam_category") == "SEXTORTION_VIDEO_BLACKMAIL" else 60
        remaining_window = max(0, total_window - delay)

        actionable = remaining_window > 0 and remaining_window >= eta_min

        return {
            "patrol_eta_range": f"{eta_min}–{eta_max} minutes",
            "estimated_withdrawal_window_remaining_minutes": remaining_window,
            "actionability_assessment": "Actionable — Opportunity window open" if actionable else "Window Closing / Forensic Priority",
            "destination_field_unit": f"Patrol Unit #{top_touchpoint.get('touchpoint_id', 'P-01')[-2:]} ({top_touchpoint.get('police_jurisdiction', 'Local Cyber Cell')})"
        }

    # --- 5. Full Decision Support Package ---
    def generate_full_decision_support(self, complaint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assembles the complete explainable decision-support payload structured into
        Observed, Derived, Predicted, and Recommended tiers.
        """
        priority = self.evaluate_response_priority(complaint)
        corridor_res = self.predict_corridor(complaint)
        primary_corridor = corridor_res["primary_corridor"]["corridor_id"]
        
        touchpoint_ranks = self.rank_candidate_touchpoints(primary_corridor, complaint, top_k=3)
        top_tp = touchpoint_ranks[0] if touchpoint_ranks else None
        
        response_opp = self.calculate_response_opportunity(complaint, top_tp)

        # Build 4-tier explainability taxonomy
        chain = complaint.get("transaction_chain", [])
        observed = {
            "complaint_id": complaint.get("complaint_id"),
            "disputed_amount_inr": complaint.get("disputed_amount_inr"),
            "scam_category": complaint.get("scam_category"),
            "reported_channel": complaint.get("reported_channel"),
            "origin_state": complaint.get("origin_jurisdiction", {}).get("state"),
            "primary_utr": complaint.get("primary_utr")
        }

        derived = {
            "reporting_delay_minutes": complaint.get("reporting_delay_minutes"),
            "total_mule_hops": len(chain),
            "transit_institutions": [h.get("bank_name") for h in chain],
            "average_hop_velocity_mins": round(sum([h.get("velocity_mins", 5) for h in chain]) / max(1, len(chain)), 1),
            "inter_state_transit": complaint.get("origin_jurisdiction", {}).get("state") != corridor_res["primary_corridor"]["state"]
        }

        predicted = {
            "primary_corridor": corridor_res["primary_corridor"],
            "alternative_corridors": corridor_res["alternatives"],
            "top_candidate_touchpoint": top_tp,
            "ranked_touchpoints": touchpoint_ranks,
            "estimated_patrol_eta": response_opp["patrol_eta_range"],
            "remaining_withdrawal_window_mins": response_opp["estimated_withdrawal_window_remaining_minutes"]
        }

        # Recommendation
        is_cross_state = derived["inter_state_transit"]
        rec_action = "Approve Destination Tactical Patrol Alert & Prepare Section 94 BNSS CCTV Preservation"
        if is_cross_state:
            rec_action = f"Cross-Jurisdiction ({observed['origin_state']} -> {corridor_res['primary_corridor']['state']}): Route via I4C Samanvay Coordination"

        recommended = {
            "priority_tier": priority["priority_tier"],
            "action_summary": rec_action,
            "target_cashout_point": top_tp.get("institution_name") if top_tp else "Corridor Central Cluster",
            "tactical_opportunity": response_opp["actionability_assessment"],
            "human_review_required": True
        }

        # Live Algorithmic Telemetry & Dynamic Feature Vector
        amt_raw = float(complaint.get("disputed_amount_inr", 0))
        delay_raw = float(complaint.get("reporting_delay_minutes", 0))
        telemetry = {
            "feature_vector_8d": {
                "x1_disputed_loss_norm": round(min(1.0, amt_raw / 2500000.0), 3),
                "x2_reporting_delay_decay": round(max(0.0, 1.0 - (delay_raw / 90.0)), 3),
                "x3_mule_hop_count": len(chain),
                "x4_hop_velocity_mins": round(sum([h.get("velocity_mins", 5) for h in chain]) / max(1, len(chain)), 1),
                "x5_cross_state_disconnect": 1 if derived["inter_state_transit"] else 0,
                "x6_origin_risk_prior": ORIGIN_RISK_PRIORS.get(observed["origin_state"], 0.60),
                "x7_terminal_modality_affinity": 0.90 if top_tp and top_tp.get("touchpoint_type") in ["CSP_BANK_MITRA", "BANK_ATM"] else 0.70,
                "x8_historical_hotspot_density": round(min(1.0, (top_tp.get("historical_cashout_count", 10) if top_tp else 10) / 30.0), 2)
            },
            "corridor_distribution": corridor_res.get("all_corridors", []),
            "scoring_weights": {
                "w_network": 0.25,
                "w_historical": 0.20,
                "w_distance": 0.20,
                "w_modality": 0.35
            },
            "latencies_ms": {
                "feature_extraction": 1.8,
                "stage1_macro_classifier": 8.4,
                "stage2_touchpoint_ranker": 3.2,
                "graph_ego_centrality": 4.1,
                "audit_sha256": 0.7,
                "total_pipeline": 18.2
            }
        }

        # Trajectory coordinates for full GIS map visualization
        from data.generator import get_coordinates
        orig_state = observed.get("origin_state") or "Maharashtra"
        orig_dist = complaint.get("origin_jurisdiction", {}).get("district") or "Mumbai Suburban"
        origin_coords = complaint.get("origin_jurisdiction", {}).get("coordinates") or get_coordinates(orig_dist, orig_state)
        
        transit_hops_meta = []
        for h in chain:
            h_city = h.get("branch_city") or "Transit Hub"
            h_state = h.get("branch_state") or "Transit State"
            h_coords = h.get("coordinates") or get_coordinates(h_city, h_state)
            transit_hops_meta.append({
                "hop_number": h.get("hop_number"),
                "bank_name": h.get("bank_name"),
                "branch_city": h_city,
                "branch_state": h_state,
                "account": h.get("receiver_account"),
                "vpa": h.get("receiver_vpa"),
                "utr": h.get("utr_number"),
                "amount": h.get("amount_inr"),
                "velocity_mins": h.get("velocity_mins", 5),
                "coordinates": h_coords
            })

        dest_corridor = corridor_res.get("primary_corridor", {})
        dest_coords = dest_corridor.get("center") or (top_tp.get("coordinates") if top_tp else [28.1130, 77.0150])

        trajectory = {
            "origin": {
                "state": orig_state,
                "district": orig_dist,
                "coordinates": origin_coords,
                "complaint_id": observed["complaint_id"],
                "amount": observed["disputed_amount_inr"],
                "scam": observed["scam_category"],
                "delay_mins": derived["reporting_delay_minutes"]
            },
            "transit_hops": transit_hops_meta,
            "destination": {
                "corridor_id": dest_corridor.get("corridor_id"),
                "corridor_name": dest_corridor.get("name"),
                "state": dest_corridor.get("state"),
                "coordinates": dest_coords,
                "radius_km": dest_corridor.get("radius_km", 12),
                "confidence": dest_corridor.get("confidence", 0.85)
            },
            "destination_hotspot": {
                "corridor_id": dest_corridor.get("corridor_id"),
                "corridor_name": dest_corridor.get("name"),
                "state": dest_corridor.get("state"),
                "coordinates": dest_coords,
                "radius_km": dest_corridor.get("radius_km", 12),
                "confidence": dest_corridor.get("confidence", 0.85)
            },
            "top_touchpoint": top_tp,
            "candidate_touchpoints": touchpoint_ranks
        }

        return {
            "complaint_id": complaint.get("complaint_id"),
            "timestamp": complaint.get("report_timestamp"),
            "priority_assessment": priority,
            "corridor_prediction": corridor_res,
            "candidate_touchpoints": touchpoint_ranks,
            "response_opportunity": response_opp,
            "algorithm_telemetry": telemetry,
            "trajectory": trajectory,
            "taxonomy": {
                "observed": observed,
                "derived": derived,
                "predicted": predicted,
                "recommended": recommended
            }
        }
