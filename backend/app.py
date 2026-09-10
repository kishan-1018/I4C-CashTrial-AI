"""
FastAPI Server for I4C Cybercrime Predictive Cash-Out Decision Support System.
Implements complete REST API, authenticated WebSocket live stream,
audit trail logging, and requisition/PDF dossier endpoints.
"""

import os
import json
import datetime
import asyncio
import copy
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.requests import Request
from fastapi.middleware.cors import CORSMiddleware

from ml.predictor import HotspotPredictor
from ml.graph_analyzer import TransactionGraphAnalyzer
from backend.models import IncidentIntakeRequest, HumanReviewAction, AlertNotificationRequest, ReviewDecisionRequest, WorkflowStage
from backend.validator import validate_complaint, MAX_RETRIES
from backend.auth import get_current_user_role, require_role
from backend.audit import audit_ledger
from backend.requisition_generator import RequisitionGenerator
from backend.pdf_generator import ForensicPDFGenerator
from data.generator import generate_single_complaint

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "frontend" / "static"
TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"
DATA_DIR = BASE_DIR / "data"

app = FastAPI(
    title="I4C Predictive Cash-Out Hotspot Decision-Support System",
    description="Law Enforcement Decision Support for Smart India Hackathon PS ID 26184",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files & Templates
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Initialize ML & Graph Engines
predictor = HotspotPredictor()
graph_analyzer = TransactionGraphAnalyzer()

# In-Memory Active Incident Store & Alert Delivery Logs
ACTIVE_INCIDENTS: Dict[str, Dict[str, Any]] = {}
ALERT_LOGS: List[Dict[str, Any]] = []

# Workflow metadata store: complaint_id -> {stage, priority_score, validation, retry_count, timeline_events, ...}
WORKFLOW_META: Dict[str, Dict[str, Any]] = {}

def init_active_incidents():
    """Seeds active incidents from curated demo scenarios and pan-India live test dataset."""
    scenarios_file = DATA_DIR / "demo_scenarios.json"
    if scenarios_file.exists():
        with open(scenarios_file, "r", encoding="utf-8") as f:
            demo_items = json.load(f)
            for item in demo_items:
                ACTIVE_INCIDENTS[item["complaint_id"]] = item

    # Seed 12 diverse pan-India incidents from test set
    test_file = DATA_DIR / "complaints_test.json"
    if test_file.exists():
        with open(test_file, "r", encoding="utf-8") as f:
            test_items = json.load(f)
            for i, item in enumerate(test_items[:12]):
                cid = f"NCRP-2026-LIVE{i+1:03d}"
                item_copy = dict(item)
                item_copy["complaint_id"] = cid
                ACTIVE_INCIDENTS[cid] = item_copy

init_active_incidents()

# --- WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

ws_manager = ConnectionManager()

# --- 1. Frontend Route ---
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

# --- 2. Touchpoint & Incident Endpoints ---
@app.get("/api/touchpoints")
@app.get("/api/atms")
async def get_touchpoints(corridor_id: Optional[str] = None, touchpoint_type: Optional[str] = None):
    tps = predictor.touchpoints_registry
    if corridor_id:
        tps = [t for t in tps if t.get("corridor_id") == corridor_id]
    if touchpoint_type and touchpoint_type != "ALL":
        tps = [t for t in tps if t.get("touchpoint_type") == touchpoint_type]
    return {"total": len(tps), "touchpoints": tps}

@app.get("/api/recent-incidents")
async def get_recent_incidents():
    return {"total": len(ACTIVE_INCIDENTS), "incidents": list(ACTIVE_INCIDENTS.values())}

@app.get("/api/demo-scenarios")
async def get_demo_scenarios():
    scenarios_file = DATA_DIR / "demo_scenarios.json"
    if scenarios_file.exists():
        with open(scenarios_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return list(ACTIVE_INCIDENTS.values())[:4]

# --- 3. Heatmap Data with Filtering ---
@app.get("/api/heatmap")
async def get_heatmap_data(
    state: Optional[str] = None,
    typology: Optional[str] = None,
    touchpoint_type: Optional[str] = None,
    time_window: Optional[str] = "24h"
):
    """
    Returns multi-layer GIS heatmap:
    - Historical Density Points
    - Real-Time Active Corridors
    - Predicted High-Risk Zones
    """
    tps = predictor.touchpoints_registry
    if state and state != "ALL":
        tps = [t for t in tps if t.get("state", "").lower() == state.lower()]
    if touchpoint_type and touchpoint_type != "ALL":
        tps = [t for t in tps if t.get("touchpoint_type") == touchpoint_type]

    # Historical heat points (lat, lon, weight)
    historical_points = []
    for tp in tps:
        count = tp.get("historical_cashout_count", 0)
        if count > 0:
            lat, lon = tp.get("coordinates", [0, 0])
            historical_points.append({
                "lat": lat,
                "lon": lon,
                "intensity": min(1.0, count / 35.0),
                "touchpoint_name": tp.get("institution_name"),
                "touchpoint_type": tp.get("touchpoint_type"),
                "layer": "HISTORICAL"
            })

    # Real-time incident pins
    realtime_points = []
    for inc in ACTIVE_INCIDENTS.values():
        if typology and typology != "ALL" and inc.get("scam_category") != typology:
            continue
        gt = inc.get("ground_truth", {})
        tp_id = gt.get("target_touchpoint_id")
        matching_tp = next((t for t in tps if t.get("touchpoint_id") == tp_id), None)
        if matching_tp:
            lat, lon = matching_tp.get("coordinates", [0, 0])
            realtime_points.append({
                "complaint_id": inc.get("complaint_id"),
                "lat": lat,
                "lon": lon,
                "scam_category": inc.get("scam_category"),
                "disputed_amount": inc.get("disputed_amount_inr"),
                "reporting_delay_mins": inc.get("reporting_delay_minutes"),
                "touchpoint_name": matching_tp.get("institution_name"),
                "touchpoint_type": matching_tp.get("touchpoint_type"),
                "layer": "REAL_TIME"
            })

    # Corridor polygon centroids & risk shading
    corridor_layers = []
    from data.generator import CORRIDORS
    for cid, cinfo in CORRIDORS.items():
        if state and state != "ALL" and cinfo["state"].lower() != state.lower():
            continue
        corridor_layers.append({
            "corridor_id": cid,
            "name": cinfo["name"],
            "state": cinfo["state"],
            "district": cinfo["district"],
            "center": cinfo["center"],
            "radius_km": cinfo["radius_km"],
            "risk_level": "HIGH" if cid in ["mewat_nuh_rural", "jamtara_cyber_hub"] else "MEDIUM",
            "layer": "PREDICTED_CORRIDOR"
        })

    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "filters_applied": {"state": state, "typology": typology, "touchpoint_type": touchpoint_type, "window": time_window},
        "historical_layer": historical_points,
        "realtime_layer": realtime_points,
        "predicted_corridors": corridor_layers
    }

# --- 4. Simulation & Ingestion Endpoint ---
@app.get("/api/geo/states-and-districts")
async def get_states_and_districts():
    from data.generator import STATE_DEFAULT_DISTRICTS, CITY_COORDINATES, STATE_DEFAULT_COORDINATES
    return {
        "states": sorted(list(STATE_DEFAULT_COORDINATES.keys())),
        "default_districts": STATE_DEFAULT_DISTRICTS,
        "cities": sorted(list(CITY_COORDINATES.keys()))
    }

@app.post("/api/simulate-incident")
async def simulate_incident(req: IncidentIntakeRequest):
    cid = req.complaint_id or f"NCRP-LIVE-{int(datetime.datetime.now().timestamp()) % 100000:05d}"
    
    from data.generator import resolve_or_create_corridor_and_touchpoints, CORRIDORS, STATE_DEFAULT_DISTRICTS

    dest_state = req.destination_state
    dest_district = req.destination_district

    corridor_id = req.target_corridor_hint
    if corridor_id and corridor_id in CORRIDORS and corridor_id != "AUTO":
        c_meta = CORRIDORS[corridor_id]
        dest_state = c_meta["state"]
        dest_district = c_meta["district"]

    # If destination state not explicitly provided, predict it dynamically
    if not dest_state or dest_state == "AUTO" or dest_state == "ALL":
        if req.scam_category in ["SEXTORTION_VIDEO_BLACKMAIL", "UPI_QR_OLX_FRAUD"]:
            dest_state = "Rajasthan" if req.origin_state == "Haryana" else "Haryana"
            dest_district = "Nuh"
        elif req.scam_category in ["ELECTRICITY_KYC_APK_FRAUD", "SIM_SWAP_FRAUD"]:
            dest_state = "Jharkhand"
            dest_district = "Jamtara"
        elif req.scam_category == "INVESTMENT_STOCK_SCAM":
            dest_state = "Karnataka" if req.origin_state != "Karnataka" else "Maharashtra"
            dest_district = "Bengaluru Urban" if dest_state == "Karnataka" else "Mumbai Suburban"
        elif req.scam_category == "LOAN_APP_EXTORTION":
            dest_state = "Gujarat"
            dest_district = "Surat"
        elif req.scam_category == "DIGITAL_ARREST":
            dest_state = "Delhi"
            dest_district = "North West Delhi"
        else:
            dest_state = "Bihar" if req.origin_state != "Bihar" else "Uttar Pradesh"
            dest_district = "Patna" if dest_state == "Bihar" else "Lucknow"

    if not dest_district:
        dest_district = STATE_DEFAULT_DISTRICTS.get(dest_state, f"{dest_state} Central")

    # Dynamically resolve or synthesize corridor and touchpoints for this destination
    c_info, new_touchpoints = resolve_or_create_corridor_and_touchpoints(
        state=dest_state,
        district=dest_district,
        scam_type=req.scam_category,
        preferred_modality=req.preferred_touchpoint_modality or "ALL"
    )
    corridor_id = c_info["corridor_id"]

    # Register any new touchpoints into predictor
    existing_tp_ids = {t.get("touchpoint_id") for t in predictor.touchpoints_registry}
    for tp in new_touchpoints:
        if tp.get("touchpoint_id") not in existing_tp_ids:
            predictor.touchpoints_registry.append(tp)

    incident = generate_single_complaint(
        cid,
        predictor.touchpoints_registry,
        forced_scenario={
            "scam_type": req.scam_category,
            "corridor_id": corridor_id,
            "origin_state": req.origin_state,
            "origin_district": req.origin_district,
            "destination_state": dest_state,
            "destination_district": dest_district,
            "amount": req.disputed_amount_inr,
            "delay_mins": req.reporting_delay_minutes,
            "num_hops": req.num_mule_hops,
            "preferred_modality": req.preferred_touchpoint_modality,
            "suspect_bank": req.suspect_bank_hint,
            "victim_name": req.victim_name,
            "victim_phone": req.victim_phone
        }
    )
    if req.primary_utr:
        incident["primary_utr"] = req.primary_utr
        if incident.get("transaction_chain"):
            incident["transaction_chain"][0]["utr_number"] = req.primary_utr

    incident["target_corridor_hint"] = corridor_id

    # ── Step A: AI Validation (Stage 1: Transaction + Stage 2: Fraud Check) ──
    validation = validate_complaint(
        {
            "disputed_amount_inr": req.disputed_amount_inr,
            "primary_utr": req.primary_utr,
            "scam_category": req.scam_category,
            "reporting_delay_minutes": req.reporting_delay_minutes,
            "origin_state": req.origin_state,
            "transaction_chain": incident.get("transaction_chain", []),
        },
        retry_count=0,
    )
    incident["_validation"] = validation

    # If validation hard-fails (score < 30), reject before adding to queue
    if not validation["is_valid"] and validation["validation_score"] < 30:
        audit_ledger.log_event(
            cid, "VALIDATION_HARD_FAILED", "AI_VALIDATOR",
            {"flags": validation["flags"], "score": validation["validation_score"]}
        )
        await ws_manager.broadcast({
            "type": "VALIDATION_FAILED",
            "complaint_id": cid,
            "flags": validation["flags"],
            "hints": validation["revision_hints"]
        })
        return {
            "status": "VALIDATION_FAILED",
            "complaint_id": cid,
            "validation": validation,
            "incident": incident,
            "decision_support": None
        }

    ACTIVE_INCIDENTS[cid] = incident

    # ── Step B: Run AI Decision Support (Corridor Prediction + ATM Ranking) ──
    ds = predictor.generate_full_decision_support(incident)

    # ── Step C: Compute Priority Score ────────────────────────────────────────
    priority_score = predictor.compute_priority_score(
        incident, validation_score=validation["validation_score"]
    )
    ds["priority_score"] = priority_score

    # ── Step D: Store Workflow Metadata ───────────────────────────────────────
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    primary_corridor = ds["taxonomy"]["predicted"]["primary_corridor"]
    top_atms = ds.get("candidate_touchpoints", [])
    WORKFLOW_META[cid] = {
        "complaint_id": cid,
        "stage": WorkflowStage.PENDING_REVIEW if validation["is_valid"] else WorkflowStage.VALIDATION_FAILED,
        "priority_score": priority_score,
        "validation": validation,
        "decision_support": ds,
        "revalidation_count": 0,
        "created_at": now_iso,
        "last_updated": now_iso,
        "reviewer_decision": None,
        "rejection_reason": None,
        "alerts_sent": [],
        "timeline_events": [
            {
                "event": "COMPLAINT_SUBMITTED",
                "stage": "Complaint Filed via NCRP 1930",
                "desc": f"Complaint {cid} registered. Amount: ₹{int(req.disputed_amount_inr):,}. Category: {req.scam_category.replace('_', ' ')}.",
                "time": now_iso,
                "icon": "📋",
                "status": "completed"
            },
            {
                "event": "AI_VALIDATION",
                "stage": "AI Validation Check",
                "desc": validation["validation_summary"],
                "time": now_iso,
                "icon": "🔍" if validation["is_valid"] else "⚠️",
                "status": "completed" if validation["is_valid"] else "warning",
                "score": validation["validation_score"],
                "flags": validation["flags"]
            },
            {
                "event": "CORRIDOR_PREDICTION",
                "stage": "AI Analysis & Corridor Prediction",
                "desc": f"ML model identified primary cash-out corridor: {primary_corridor['name']} (confidence {primary_corridor['confidence']*100:.1f}%). Top {len(top_atms)} ATM/CSP points ranked.",
                "time": now_iso,
                "icon": "🧠",
                "status": "completed"
            },
            {
                "event": "PENDING_REVIEW",
                "stage": "Under Investigator Review",
                "desc": "Complaint forwarded to authorized investigator for human review and approval before alerts are dispatched.",
                "time": now_iso,
                "icon": "👮",
                "status": "active"
            },
        ]
    }

    # ── Step E: Log to Audit Ledger ───────────────────────────────────────────
    audit_ledger.log_event(
        cid, "INCIDENT_INGESTED", "NCRP_GATEWAY",
        {
            "scam": req.scam_category,
            "amount": req.disputed_amount_inr,
            "origin": f"{req.origin_district}, {req.origin_state}",
            "destination": f"{dest_district}, {dest_state}",
            "validation_score": validation["validation_score"],
            "priority_score": priority_score,
        }
    )

    # ── Step F: Broadcast to WebSocket ────────────────────────────────────────
    await ws_manager.broadcast({
        "type": "NEW_INCIDENT",
        "complaint_id": cid,
        "priority": ds["priority_assessment"]["priority_tier"],
        "priority_score": priority_score,
        "validation_score": validation["validation_score"],
        "is_valid": validation["is_valid"],
        "scam_category": req.scam_category,
        "disputed_amount": req.disputed_amount_inr,
        "primary_corridor": primary_corridor["name"],
        "origin": f"{req.origin_district}, {req.origin_state}",
        "destination": f"{dest_district}, {dest_state}",
        "timestamp": incident["report_timestamp"]
    })

    return {
        "status": "INGESTED_SUCCESSFULLY" if validation["is_valid"] else "INGESTED_WITH_WARNINGS",
        "incident": incident,
        "decision_support": ds,
        "validation": validation,
        "priority_score": priority_score,
        "workflow_stage": WORKFLOW_META[cid]["stage"]
    }

# --- Dynamic Real-Time Stream, Batch & Sensitivity Endpoints ---
@app.get("/api/stream/next-incident")
async def stream_next_incident():
    """Generates a dynamic pan-India cybercrime incident on the fly and broadcasts it."""
    import random
    cid = f"NCRP-2026-LIVE{random.randint(1000, 9999)}"
    states_cities = [
        ("Maharashtra", "Mumbai"), ("Karnataka", "Bengaluru"), ("Delhi", "New Delhi"),
        ("Telangana", "Hyderabad"), ("Tamil Nadu", "Chennai"), ("Gujarat", "Ahmedabad"),
        ("West Bengal", "Kolkata"), ("Rajasthan", "Jaipur"), ("Uttar Pradesh", "Lucknow"),
        ("Kerala", "Kochi"), ("Madhya Pradesh", "Bhopal"), ("Punjab", "Chandigarh")
    ]
    state, city = random.choice(states_cities)
    typologies = [
        "DIGITAL_ARREST", "INVESTMENT_STOCK_SCAM", "SEXTORTION_VIDEO_BLACKMAIL",
        "ELECTRICITY_KYC_APK_FRAUD", "LOAN_APP_EXTORTION", "UPI_QR_OLX_FRAUD"
    ]
    typology = random.choice(typologies)
    amounts = [85000, 145000, 290000, 480000, 750000, 1250000, 2400000, 4800000]
    amount = random.choice(amounts)
    delay = random.randint(8, 95)

    inc = generate_single_complaint(
        cid,
        predictor.touchpoints_registry,
        forced_scenario={
            "scam_type": typology,
            "origin_state": state,
            "origin_district": city,
            "amount": amount,
            "delay_mins": delay
        }
    )
    ACTIVE_INCIDENTS[cid] = inc
    ds = predictor.generate_full_decision_support(inc)

    audit_ledger.log_event(
        cid, "LIVE_FEED_STREAMED", "NCRP_1930_API",
        {"scam": typology, "amount": amount, "origin": state}
    )

    await ws_manager.broadcast({
        "type": "NEW_INCIDENT",
        "complaint_id": cid,
        "priority": ds["priority_assessment"]["priority_tier"],
        "scam_category": typology,
        "disputed_amount": amount,
        "primary_corridor": ds["taxonomy"]["predicted"]["primary_corridor"]["name"],
        "origin_state": state,
        "timestamp": inc["report_timestamp"]
    })

    return {"incident": inc, "decision_support": ds}

@app.post("/api/batch-generate")
async def batch_generate_incidents(count: int = 10):
    """Dynamically generates N pan-India incidents and ingests them into the live store."""
    import random
    created = []
    for _ in range(min(count, 20)):
        cid = f"NCRP-2026-LIVE{random.randint(1000, 9999)}"
        states_cities = [
            ("Maharashtra", "Pune"), ("Karnataka", "Mysuru"), ("Delhi", "North Delhi"),
            ("Telangana", "Warangal"), ("Tamil Nadu", "Coimbatore"), ("Gujarat", "Surat"),
            ("West Bengal", "Siliguri"), ("Rajasthan", "Jodhpur"), ("Uttar Pradesh", "Kanpur")
        ]
        state, city = random.choice(states_cities)
        typologies = ["DIGITAL_ARREST", "INVESTMENT_STOCK_SCAM", "SEXTORTION_VIDEO_BLACKMAIL", "ELECTRICITY_KYC_APK_FRAUD", "LOAN_APP_EXTORTION"]
        typology = random.choice(typologies)
        amount = random.choice([95000, 180000, 350000, 820000, 1600000, 3200000])
        delay = random.randint(10, 80)
        
        inc = generate_single_complaint(
            cid, predictor.touchpoints_registry,
            forced_scenario={"scam_type": typology, "origin_state": state, "origin_district": city, "amount": amount, "delay_mins": delay}
        )
        ACTIVE_INCIDENTS[cid] = inc
        created.append(inc)

    return {"status": "BATCH_GENERATED", "count": len(created), "incidents": created}

@app.post("/api/calculate-sensitivity")
async def calculate_sensitivity(payload: Dict[str, Any]):
    """Live interactive What-If sensitivity recalculator based on modified delay/loss."""
    cid = payload.get("complaint_id")
    inc = ACTIVE_INCIDENTS.get(cid)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    delay = int(payload.get("reporting_delay_minutes", inc.get("reporting_delay_minutes", 30)))
    amt = float(payload.get("disputed_amount_inr", inc.get("disputed_amount_inr", 350000)))

    sim_inc = copy.deepcopy(inc)
    sim_inc["reporting_delay_minutes"] = delay
    sim_inc["disputed_amount_inr"] = amt

    ds = predictor.generate_full_decision_support(sim_inc)
    return {
        "complaint_id": cid,
        "simulated_delay": delay,
        "simulated_amount": amt,
        "priority_assessment": ds["priority_assessment"],
        "response_opportunity": ds["response_opportunity"],
        "candidate_touchpoints": ds["candidate_touchpoints"],
        "taxonomy": ds["taxonomy"],
        "algorithm_telemetry": ds["algorithm_telemetry"]
    }

# --- 5. Prediction & Decision Support Endpoints ---
@app.post("/api/predict-hotspot")
async def predict_hotspot(complaint: Dict[str, Any]):
    return predictor.generate_full_decision_support(complaint)

# --- 5b. Complaint Workflow Status (Victim-Safe) ---
@app.get("/api/complaint-status/{complaint_id}")
async def get_complaint_status(complaint_id: str):
    """
    Victim-facing endpoint: returns current workflow stage and timeline events.
    Deliberately excludes sensitive investigator notes and ATM coordinates.
    """
    meta = WORKFLOW_META.get(complaint_id)
    if not meta:
        # Check if it's a legacy/demo incident with no workflow metadata
        inc = ACTIVE_INCIDENTS.get(complaint_id)
        if not inc:
            raise HTTPException(status_code=404, detail="Complaint not found")
        return {
            "complaint_id": complaint_id,
            "stage": WorkflowStage.PENDING_REVIEW,
            "priority_score": 50,
            "validation_score": 80,
            "is_valid": True,
            "timeline_events": [],
            "reviewer_decision": None,
            "alerts_sent_count": 0
        }
    return {
        "complaint_id": complaint_id,
        "stage": meta["stage"],
        "priority_score": meta["priority_score"],
        "validation_score": meta["validation"]["validation_score"],
        "is_valid": meta["validation"]["is_valid"],
        "validation_flags": meta["validation"]["flags"],
        "revision_hints": meta["validation"]["revision_hints"] if meta["stage"] in [
            WorkflowStage.VALIDATION_FAILED, WorkflowStage.REVISION_REQUESTED
        ] else [],
        "timeline_events": meta["timeline_events"],
        "reviewer_decision": meta["reviewer_decision"],
        "rejection_reason": meta["rejection_reason"] if meta["stage"] in [
            WorkflowStage.REJECTED, WorkflowStage.REVISION_REQUESTED
        ] else None,
        "alerts_sent_count": len(meta["alerts_sent"]),
        "revalidation_count": meta["revalidation_count"],
        "last_updated": meta["last_updated"]
    }

# --- 5c. Investigator Review Queue (sorted by priority score) ---
@app.get("/api/review-queue")
async def get_review_queue():
    """
    Returns complaints currently in PENDING_REVIEW stage,
    sorted descending by priority score.
    """
    queue = []
    for cid, meta in WORKFLOW_META.items():
        if meta["stage"] in [WorkflowStage.PENDING_REVIEW, WorkflowStage.UNDER_REVIEW, WorkflowStage.RE_VALIDATING]:
            inc = ACTIVE_INCIDENTS.get(cid, {})
            queue.append({
                "complaint_id": cid,
                "stage": meta["stage"],
                "priority_score": meta["priority_score"],
                "validation_score": meta["validation"]["validation_score"],
                "is_valid": meta["validation"]["is_valid"],
                "scam_category": inc.get("scam_category"),
                "disputed_amount_inr": inc.get("disputed_amount_inr"),
                "origin_state": inc.get("origin_jurisdiction", {}).get("state"),
                "report_timestamp": inc.get("report_timestamp"),
                "revalidation_count": meta["revalidation_count"]
            })
    queue.sort(key=lambda x: x["priority_score"], reverse=True)
    return {"total": len(queue), "queue": queue}

# --- 5d. Human Review Decision: APPROVE (→ Alerts) or REJECT (→ Re-validate) ---
@app.post("/api/review-complaint")
async def review_complaint(req: ReviewDecisionRequest):
    """
    Investigator human review decision endpoint.
    APPROVE: Automatically sends alerts to LEAs, Banks, and CFCFRMS.
    REJECT:  Triggers re-validation loop (up to MAX_RETRIES times).
    """
    meta = WORKFLOW_META.get(req.complaint_id)
    inc = ACTIVE_INCIDENTS.get(req.complaint_id)
    if not inc or not meta:
        raise HTTPException(status_code=404, detail="Complaint not found in review queue")

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if req.decision == "APPROVE":
        # ── APPROVE: Send alerts to LEAs, Banks, CFCFRMS ──────────────────────
        ds = meta["decision_support"]
        primary_corridor = ds["taxonomy"]["predicted"]["primary_corridor"]
        top_tp = ds["taxonomy"]["predicted"]["top_candidate_touchpoint"] or {}

        alert_targets = [
            {
                "channel": "BANK_CFCFRMS",
                "target": "CFCFRMS Fund Freeze Gateway",
                "message": f"FUND FREEZE ALERT: Beneficiary accounts in incident {req.complaint_id} flagged for immediate hold. Corridor: {primary_corridor['name']}.",
                "status": "DELIVERED_SIMULATED"
            },
            {
                "channel": "LEA_SAMANVAY",
                "target": f"{primary_corridor['state']} Cyber Crime Cell (I4C Samanvay)",
                "message": f"TACTICAL ALERT: High-probability cash-out route predicted for {req.complaint_id}. Primary corridor: {primary_corridor['name']} ({primary_corridor['confidence']*100:.1f}% confidence). Deploy field unit immediately.",
                "status": "DELIVERED_SIMULATED"
            },
            {
                "channel": "SMS_SIMULATED",
                "target": "Destination Jurisdictional Police",
                "message": f"I4C ALERT #{req.complaint_id}: Cash-out expected at {top_tp.get('institution_name', 'Target ATM')} ({top_tp.get('location_name', 'Target Location')}). Patrol ETA requested.",
                "status": "DELIVERED_SIMULATED"
            },
            {
                "channel": "EMAIL_SIMULATED",
                "target": "Nodal Bank Officer & RBI Cybercrime Cell",
                "message": f"Cybercrime Alert — Fraud incident {req.complaint_id} approved for action. Amount: ₹{int(inc.get('disputed_amount_inr', 0)):,}. Freeze coordination initiated.",
                "status": "DELIVERED_SIMULATED"
            }
        ]

        meta["stage"] = WorkflowStage.ALERTS_DISPATCHED
        meta["reviewer_decision"] = "APPROVED"
        meta["alerts_sent"] = alert_targets
        meta["last_updated"] = now_iso
        meta["timeline_events"].append({
            "event": "INVESTIGATOR_APPROVED",
            "stage": "Investigator Approved",
            "desc": f"Authorized officer {req.reviewer_id} reviewed and approved the complaint. Alerts dispatched to LEAs, Banks, and CFCFRMS.",
            "time": now_iso,
            "icon": "✅",
            "status": "completed"
        })
        meta["timeline_events"].append({
            "event": "BANK_FREEZE_ALERT",
            "stage": "Bank Freeze Alert Dispatched",
            "desc": "CFCFRMS fund freeze alert sent to beneficiary banks. Target accounts flagged for immediate hold under Golden Hour protocol.",
            "time": now_iso,
            "icon": "🏦",
            "status": "completed"
        })
        meta["timeline_events"].append({
            "event": "LEA_TACTICAL_ALERT",
            "stage": "LEA Tactical Alert Dispatched",
            "desc": f"Inter-state coordination alert dispatched via I4C Samanvay to {primary_corridor['state']} Cyber Crime Cell. Field unit deployment requested.",
            "time": now_iso,
            "icon": "🚔",
            "status": "completed"
        })

        # Log to audit trail
        audit_ledger.log_event(
            req.complaint_id, "REVIEW_APPROVED", req.reviewer_id,
            {"role": req.reviewer_role, "alerts_count": len(alert_targets), "corridor": primary_corridor["name"]}
        )

        # Broadcast WebSocket
        await ws_manager.broadcast({
            "type": "COMPLAINT_APPROVED",
            "complaint_id": req.complaint_id,
            "reviewer_id": req.reviewer_id,
            "alerts_sent": len(alert_targets),
            "corridor": primary_corridor["name"]
        })

        return {
            "status": "APPROVED_AND_ALERTS_DISPATCHED",
            "complaint_id": req.complaint_id,
            "alerts": alert_targets,
            "workflow_stage": meta["stage"]
        }

    elif req.decision == "REJECT":
        # ── REJECT: Run re-validation loop (max MAX_RETRIES=3 times) ─────────
        retry_count = meta["revalidation_count"] + 1

        if retry_count > MAX_RETRIES:
            # Permanently rejected — exhausted all retries
            meta["stage"] = WorkflowStage.PERMANENTLY_REJECTED
            meta["reviewer_decision"] = "PERMANENTLY_REJECTED"
            meta["rejection_reason"] = req.rejection_reason
            meta["last_updated"] = now_iso
            meta["timeline_events"].append({
                "event": "PERMANENTLY_REJECTED",
                "stage": "Complaint Permanently Rejected",
                "desc": f"Complaint rejected after {MAX_RETRIES} re-validation cycles. Reason: {req.rejection_reason or 'Not specified'}. Please file a new complaint with complete details.",
                "time": now_iso,
                "icon": "❌",
                "status": "failed"
            })
            audit_ledger.log_event(
                req.complaint_id, "PERMANENTLY_REJECTED", req.reviewer_id,
                {"reason": req.rejection_reason, "retry_count": retry_count}
            )
            await ws_manager.broadcast({
                "type": "COMPLAINT_PERMANENTLY_REJECTED",
                "complaint_id": req.complaint_id
            })
            return {
                "status": "PERMANENTLY_REJECTED",
                "complaint_id": req.complaint_id,
                "message": f"Complaint permanently rejected after {MAX_RETRIES} attempts.",
                "workflow_stage": meta["stage"]
            }

        # Run re-validation with incremented retry count
        meta["stage"] = WorkflowStage.RE_VALIDATING
        meta["rejection_reason"] = req.rejection_reason
        meta["revalidation_count"] = retry_count
        meta["last_updated"] = now_iso
        meta["timeline_events"].append({
            "event": "INVESTIGATOR_REJECTED",
            "stage": "Investigator Requested Revision",
            "desc": f"Officer {req.reviewer_id} flagged the complaint for revision (attempt {retry_count}/{MAX_RETRIES}). Reason: {req.rejection_reason or 'Not specified'}.",
            "time": now_iso,
            "icon": "🔄",
            "status": "warning"
        })

        # Re-run validation with incremented retry_count
        re_validation = validate_complaint(
            {
                "disputed_amount_inr": inc.get("disputed_amount_inr"),
                "primary_utr": inc.get("primary_utr"),
                "scam_category": inc.get("scam_category"),
                "reporting_delay_minutes": inc.get("reporting_delay_minutes"),
                "origin_state": inc.get("origin_jurisdiction", {}).get("state"),
                "transaction_chain": inc.get("transaction_chain", []),
            },
            retry_count=retry_count,
        )
        meta["validation"] = re_validation
        inc["_validation"] = re_validation

        if re_validation["is_valid"]:
            # Re-validation passed — re-queue for review
            meta["stage"] = WorkflowStage.PENDING_REVIEW
            new_priority = predictor.compute_priority_score(inc, validation_score=re_validation["validation_score"])
            meta["priority_score"] = new_priority
            meta["timeline_events"].append({
                "event": "RE_VALIDATION_PASSED",
                "stage": "Re-validation Passed — Back in Queue",
                "desc": f"AI re-validation (attempt {retry_count}) confirmed the transaction and fraud pattern. Complaint re-queued for investigator review. New priority score: {new_priority}.",
                "time": now_iso,
                "icon": "✅",
                "status": "completed"
            })
            meta["timeline_events"].append({
                "event": "PENDING_REVIEW",
                "stage": "Under Investigator Review",
                "desc": "Complaint re-queued and awaiting investigator approval.",
                "time": now_iso,
                "icon": "👮",
                "status": "active"
            })
        else:
            # Re-validation also failed — request victim revision
            meta["stage"] = WorkflowStage.REVISION_REQUESTED
            meta["timeline_events"].append({
                "event": "RE_VALIDATION_FAILED",
                "stage": "Revision Requested",
                "desc": f"Re-validation could not confirm all details. {re_validation['validation_summary']} Please review the hints and contact your cyber cell.",
                "time": now_iso,
                "icon": "⚠️",
                "status": "warning"
            })

        audit_ledger.log_event(
            req.complaint_id, f"REVIEW_REJECTED_RETRY_{retry_count}", req.reviewer_id,
            {"reason": req.rejection_reason, "re_validation_score": re_validation["validation_score"],
             "re_validation_passed": re_validation["is_valid"]}
        )
        await ws_manager.broadcast({
            "type": "COMPLAINT_REVALIDATED",
            "complaint_id": req.complaint_id,
            "retry_count": retry_count,
            "re_validation_passed": re_validation["is_valid"],
            "new_stage": meta["stage"]
        })
        return {
            "status": "REJECTED_AND_REVALIDATED",
            "complaint_id": req.complaint_id,
            "retry_count": retry_count,
            "re_validation": re_validation,
            "new_stage": meta["stage"],
            "workflow_stage": meta["stage"]
        }

    else:
        raise HTTPException(status_code=400, detail="decision must be APPROVE or REJECT")

@app.get("/api/incident-analysis/{complaint_id}")
async def get_incident_analysis(complaint_id: str):
    inc = ACTIVE_INCIDENTS.get(complaint_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    ds = predictor.generate_full_decision_support(inc)
    graph = graph_analyzer.build_ego_graph(inc)
    audit_events = audit_ledger.get_events_for_complaint(complaint_id)

    return {
        "incident": inc,
        "decision_support": ds,
        "network_graph": graph,
        "audit_trail": audit_events
    }

# --- 6. Requisitions & Statutory Notices ---
@app.post("/api/prepare-requisition")
async def prepare_requisitions(payload: Dict[str, Any], role: str = Depends(get_current_user_role)):
    cid = payload.get("complaint_id")
    inc = ACTIVE_INCIDENTS.get(cid)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    officer_id = payload.get("officer_id", "OFFICER_KA_8841")
    ds = predictor.generate_full_decision_support(inc)
    top_tp = ds["taxonomy"]["predicted"]["top_candidate_touchpoint"] or {}

    cfcfrms_pkg = RequisitionGenerator.generate_cfcfrms_freeze_package(inc, ds, officer_id)
    bnss_notice = RequisitionGenerator.generate_sec94_bnss_cctv_notice(inc, top_tp, officer_id)
    samanvay_xfer = RequisitionGenerator.generate_samanvay_transfer_slip(inc, ds)

    # Log Requisition Creation
    audit_ledger.log_event(
        cid,
        "REQUISITIONS_GENERATED",
        officer_id,
        {"cfcfrms_req_id": cfcfrms_pkg["requisition_id"], "bnss_notice_id": bnss_notice["notice_id"]}
    )

    return {
        "complaint_id": cid,
        "cfcfrms_freeze_package": cfcfrms_pkg,
        "section_94_bnss_notice": bnss_notice,
        "samanvay_transfer_slip": samanvay_xfer
    }

# --- 7. Human Review & Override ---
@app.post("/api/review-action")
async def record_human_review_action(action: HumanReviewAction, role: str = Depends(get_current_user_role)):
    inc = ACTIVE_INCIDENTS.get(action.complaint_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    event = audit_ledger.log_event(
        action.complaint_id,
        f"DECISION_{action.decision}",
        action.reviewer_id,
        {
            "role": action.reviewer_role,
            "decision": action.decision,
            "selected_alternative": action.selected_alternative_corridor,
            "override_reason": action.override_reason
        }
    )

    return {
        "status": "DECISION_RECORDED_IMMUTABLY",
        "complaint_id": action.complaint_id,
        "decision": action.decision,
        "audit_event": event
    }

# --- 8. Alerting & Webhooks ---
@app.post("/api/alerts/send")
async def trigger_alerts(req: AlertNotificationRequest):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record = {
        "alert_id": f"ALT-{int(datetime.datetime.now().timestamp())}",
        "incident_id": req.incident_id,
        "timestamp": now,
        "priority_tier": req.priority_tier,
        "target_jurisdiction": req.target_jurisdiction,
        "target_corridor": req.target_corridor,
        "channels": req.channels,
        "alert_message": req.alert_message,
        "delivery_status": {c: "DELIVERED_SIMULATED" if c != "WEBHOOK" else "POSTED_200" for c in req.channels}
    }
    ALERT_LOGS.append(record)

    audit_ledger.log_event(
        req.incident_id,
        "ALERT_DISPATCHED",
        "SYSTEM_ALERT_DISPATCHER",
        {"alert_id": record["alert_id"], "target": req.target_jurisdiction, "priority": req.priority_tier}
    )

    await ws_manager.broadcast({
        "type": "ALERT_TRIGGERED",
        "alert": record
    })

    return {"status": "ALERTS_SENT", "alert_record": record}

@app.get("/api/alerts/log")
async def get_alert_logs():
    return {"total": len(ALERT_LOGS), "alerts": ALERT_LOGS}

@app.post("/api/webhooks/alert")
async def webhook_receiver(payload: Dict[str, Any]):
    return {"status": "WEBHOOK_PAYLOAD_RECEIVED", "received_at": datetime.datetime.now().isoformat()}

# --- 9. Forensic PDF Dossier Download ---
@app.get("/api/dossier/{complaint_id}")
async def download_forensic_dossier(complaint_id: str):
    inc = ACTIVE_INCIDENTS.get(complaint_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    ds = predictor.generate_full_decision_support(inc)
    audit_events = audit_ledger.get_events_for_complaint(complaint_id)
    pdf_bytes = ForensicPDFGenerator.generate_dossier_pdf(inc, ds, audit_events)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Forensic_Integrity_Report_{complaint_id}.pdf"}
    )

@app.get("/api/audit/{complaint_id}")
async def get_audit_trail(complaint_id: str):
    return {
        "complaint_id": complaint_id,
        "events": audit_ledger.get_events_for_complaint(complaint_id)
    }

# --- 10. WebSocket Live Feed ---
@app.websocket("/ws/live-stream")
async def websocket_live_stream(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Initial greeting and live status
        await websocket.send_json({
            "type": "CONNECTION_ESTABLISHED",
            "status": "LIVE",
            "message": "Connected to I4C Cybercrime Predictive Decision Support Live Stream",
            "timestamp": datetime.datetime.now().isoformat()
        })
        while True:
            # Heartbeat / receive incoming commands from client
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=False)
