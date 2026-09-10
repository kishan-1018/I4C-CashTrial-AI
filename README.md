# 🚔 I4C Cybercrime Predictive Cash-Out Decision Support System

<div align="center">

![PS ID](https://img.shields.io/badge/PS%20ID-26184-blue?style=for-the-badge)
![Smart India Hackathon](https://img.shields.io/badge/Smart%20India%20Hackathon-2024-orange?style=for-the-badge)
![Ministry of Home Affairs](https://img.shields.io/badge/Ministry%20of%20Home%20Affairs-I4C-red?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)

**A real-time AI-powered decision support system for intercepting cybercrime cash-out operations.**  
Built for the Indian Cybercrime Coordination Centre (I4C) under the Ministry of Home Affairs.

</div>

---

## 📌 Problem Statement

> **PS ID 26184** — *"Predictive Hotspot Identification for Cybercrime Cash-Out Interception"*

Cybercrime victims in India lose money through layered mule-account chains that rapidly move funds across states before cash-out at ATMs, CSPs, or Micro-ATM merchants. Law enforcement faces a critical **Golden Hour** window — often under 60 minutes — to intercept funds before they are withdrawn.

### The Core Challenge
- Funds travel across **3–7 mule hops** in under an hour
- Investigators lack real-time tools to **predict which ATM corridor** the money is moving toward
- No automated pipeline exists from **victim complaint → validation → corridor prediction → field alert**
- Victim has no visibility into investigation progress

---

## 💡 Our Solution

A full-stack AI decision support dashboard that implements a **complete intelligence pipeline**:

```
Victim Files Complaint
        │
        ▼
 AI Validation Engine ──── Fake/Invalid? ──► Reject with Hints (up to 3 retries)
        │ Valid
        ▼
 Priority Scoring (0–100)
        │
        ▼
 Investigator Queue (sorted by urgency)
        │
        ▼
 ML Corridor Prediction + ATM Ranking
        │
        ▼
 Human Review Report (auto-generated for Investigator)
        │
   ┌────┴─────┐
APPROVE      REJECT
   │            │
   ▼            ▼
Alerts      Re-Validation Loop
Dispatched  (max 3 cycles)
   │
   ├── 🏦 CFCFRMS Fund Freeze Alert
   ├── 🚔 LEA Samanvay Tactical Alert
   ├── 📱 SMS to Destination Police
   └── 📧 Email to Nodal Bank Officer
        │
        ▼
Victim Timeline Updated in Real-Time (5s polling)
```

---

## 🖥️ Dashboard Preview

The system has **3 role-based views**:

| Role | View |
|---|---|
| 🔍 **Investigator** | Priority-ranked complaint queue, AI Review Report, corridor map, ATM rankings, Approve/Reject |
| 👤 **Victim** | Live 8-step investigation timeline, complaint status, validation feedback |
| 🛡️ **Admin** | System metrics, audit trail, heatmap analytics |

---

## ✨ Key Features

### 🤖 AI Validation Engine (Two-Stage)
When a victim submits a complaint, the system immediately runs:

| Stage | Checks |
|---|---|
| **Stage 1 — Transaction Verification** | UTR/UPI reference format (10–22 digits), amount plausibility, reporting delay, origin state |
| **Stage 2 — Fraud Pattern Verification** | Scam-type vs. amount consistency, cross-checks against known fraud typologies |

Returns a **0–100 validation score** with human-readable revision hints if issues are found.

### 📊 Priority Scoring (0–100)
Every complaint is automatically ranked for the Investigator queue:

| Factor | Weight | Description |
|---|---|---|
| Reporting delay | 30% | Faster report → higher urgency |
| Disputed amount | 25% | Higher loss → higher priority |
| Scam severity | 20% | Digital Arrest > Investment Scam > others |
| Network risk | 15% | Inter-state routes, hop count |
| Validation quality | 10% | Cleaner complaint → higher confidence |

### 🗺️ ML Corridor Prediction (Stage 1 + Stage 2)
- **Stage 1 Macro-Classifier**: Predicts the primary cash-out corridor from 6 known syndicate zones (Mewat-Nuh, Jamtara, Delhi-Rohini, Bengaluru East, Surat Trade Hub, Alwar Border Zone) with confidence scores
- **Stage 2 Touchpoint Ranker**: Ranks individual ATMs, White-Label ATMs, CSPs, and Micro-ATM merchants within the predicted corridor using a 4-factor scoring formula:
  ```
  Score(p_i) = 0.25·S_network + 0.20·S_historical + 0.20·S_distance + 0.35·S_modality
  ```

### 📋 Investigator Review Report (Auto-Generated)
When an investigator selects a complaint, the system instantly generates:
- Validation status (Stage 1 TX verified + Stage 2 Fraud confirmed)
- Predicted corridor with confidence % and alternatives
- **Top 5 ranked ATMs** with animated score bars
- Recommended action summary

### 🔄 Approve → Alert / Reject → Re-validate Loop
- **APPROVE**: Dispatches 4 simultaneous alerts — CFCFRMS (fund freeze), I4C Samanvay (LEA tactical), SMS, and Email
- **REJECT**: Triggers automatic re-validation with the officer's reason logged to tamper-evident audit trail (max 3 cycles → permanent rejection)

### ⏱️ Live Victim Timeline (8 Steps, 5-second polling)
Victims see real-time investigation status via `/api/complaint-status/{id}`:
1. 📋 Complaint Filed
2. 🔍 AI Validation Check (score + stage results)
3. 🧠 Corridor Prediction
4. 👮 Under Investigator Review
5. ✅ Investigator Decision
6. 🏦 Bank Freeze Alert Dispatched
7. 🚔 LEA Tactical Alert Dispatched
8. ✅ Case Resolved

### 📄 Tamper-Evident Audit Trail
All actions (ingestion, validation, review decisions, alert dispatch) are SHA-256 hashed and chained for forensic integrity under **Section 94 BNSS**.

### 🗺️ Interactive GIS Map
Full trajectory visualization from victim origin → mule hops → predicted corridor, with animated patrol car dispatch to top-ranked ATM.

---

## 🏛️ Statutory & Regulatory Alignment

| Framework | Integration |
|---|---|
| **CFCFRMS** | Fund freeze requisition auto-generated on approval |
| **Section 94 BNSS** | CCTV preservation notice auto-drafted |
| **I4C Samanvay** | Inter-state coordination alert dispatch |
| **RBI Zero-Liability Window** | Complaint delay classified against 3-day window |
| **NCRB Typologies** | 7 scam categories aligned with NCRB Crime in India report |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Browser Client                    │
│  Role-Based Views: Investigator / Victim / Admin    │
│  (Vanilla JS + CSS, Jinja2 Templates, WebSocket)    │
└────────────────────┬────────────────────────────────┘
                     │ HTTP + WebSocket
┌────────────────────▼────────────────────────────────┐
│              FastAPI Backend (Python)               │
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │  Validator  │  │  Predictor   │  │  Auditor  │  │
│  │  (2-stage)  │  │  (ML Engine) │  │ (SHA-256) │  │
│  └─────────────┘  └──────────────┘  └───────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │            Workflow State Machine            │   │
│  │  VALIDATING → PENDING_REVIEW → APPROVED      │   │
│  │          ↘ RE_VALIDATING (×3 max)            │   │
│  └──────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│            Data & ML Layer                          │
│                                                     │
│  data/cashout_touchpoints_registry.json             │
│  data/demo_scenarios.json                           │
│  models/demo_model_v1.json                          │
│  ml/predictor.py  (HotspotPredictor)                │
│  ml/graph_analyzer.py  (NetworkX transaction graph) │
└─────────────────────────────────────────────────────┘
```

### Directory Structure

```
i4c_hotspot_predictor/
├── backend/
│   ├── app.py              # FastAPI app — all API & WebSocket endpoints
│   ├── validator.py        # 🆕 AI two-stage complaint validation engine
│   ├── models.py           # Pydantic models + WorkflowStage constants
│   ├── audit.py            # SHA-256 tamper-evident audit ledger
│   ├── auth.py             # Role-based access control
│   ├── pdf_generator.py    # Forensic Integrity Dossier PDF
│   └── requisition_generator.py  # CFCFRMS / BNSS 94 auto-documents
├── ml/
│   ├── predictor.py        # HotspotPredictor — corridor + ATM ranking + priority score
│   ├── graph_analyzer.py   # Transaction graph analysis (NetworkX)
│   └── evaluator.py        # Model evaluation utilities
├── data/
│   ├── generator.py        # Synthetic complaint & corridor data generator
│   ├── cashout_touchpoints_registry.json  # ATM / CSP / WLA registry
│   ├── demo_scenarios.json # Curated hackathon demo cases
│   └── README_DATA.md      # Data provenance & privacy statement
├── models/
│   └── demo_model_v1.json  # Trained model weights (heuristic + ML hybrid)
├── frontend/
│   ├── templates/index.html  # Jinja2 main dashboard (all 3 role views)
│   └── static/
│       ├── css/dashboard.css
│       ├── js/app.js         # Reactive dashboard controller
│       └── js/gis_map.js     # Leaflet GIS map renderer
├── tests/
│   ├── test_api.py
│   ├── test_ml.py
│   ├── test_graph.py
│   └── test_data.py
├── requirements.txt
├── START_SERVER.bat          # One-click Windows launcher
└── .gitignore
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or higher
- Internet connection (for first-time `pip install`)

### Option A — One-Click Launch (Windows)
```bat
START_SERVER.bat
```
This installs dependencies, starts the server, and opens `http://127.0.0.1:8000` in your browser automatically.

### Option B — Manual Setup

```bash
# 1. Clone the repository
git clone https://github.com/<your-org>/i4c_hotspot_predictor.git
cd i4c_hotspot_predictor

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the server
uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload

# 5. Open in browser
#    http://127.0.0.1:8000
```

### Run Tests
```bash
pytest tests/ -v
```

---

## 🎮 Demo Walkthrough

### Investigator Flow
1. Open `http://127.0.0.1:8000` → select **Investigator** role
2. Browse the complaint queue — sorted by **Priority Score** (highest urgency first)
3. Click any complaint → **Review Report auto-generates**: corridor prediction + ranked ATMs + validation status
4. Click **✅ Approve & Send Alerts** → 4 simultaneous alerts dispatched (CFCFRMS, LEA Samanvay, SMS, Email)
5. Or click **❌ Reject & Re-validate** → enter reason → re-validation runs automatically (up to 3 times)

### Victim Flow
1. Switch to **Victim** role → fill in the complaint form
2. Click **Submit** → see inline validation result (score, Stage 1 & 2 status, hints)
3. Watch the **8-step live timeline** update every 5 seconds as the investigator acts

### Quick Scenario Presets
Use the **Load Preset** buttons in the intake modal for instant demo scenarios:
- 🔴 **CBI Digital Arrest** — ₹12.5L, Mumbai → Mewat-Nuh corridor
- 🟠 **Jamtara Electricity** — ₹95K, Kolkata → Jamtara Cyber Hub
- 🟡 **Investment Stock Scam** — ₹28L, Bengaluru → Delhi Rohini
- 🔵 **Loan App Extortion** — ₹3.2L, Pune → Surat Trade Hub

---

## 📡 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/simulate-incident` | `POST` | Submit complaint (runs validation + priority scoring + corridor prediction) |
| `/api/complaint-status/{id}` | `GET` | Victim-safe timeline status (polled every 5s) |
| `/api/review-queue` | `GET` | Investigator queue sorted by priority score |
| `/api/review-complaint` | `POST` | `APPROVE` (→ alerts) or `REJECT` (→ re-validate loop) |
| `/api/incident-analysis/{id}` | `GET` | Full ML decision support payload |
| `/api/dossier/{id}` | `GET` | Download Forensic Integrity Dossier (PDF) |
| `/api/alerts/send` | `POST` | Manual alert dispatch |
| `/api/prepare-requisition` | `POST` | Generate CFCFRMS + BNSS 94 documents |
| `/api/audit-log` | `GET` | Tamper-evident audit trail |
| `/ws/live-stream` | `WebSocket` | Real-time new complaint broadcasts |
| `/docs` | `GET` | Interactive Swagger API documentation |

---

## 🧠 ML & Algorithmic Details

### Complaint Validation Score (0–100)
```
score = 100
  − 40  if amount ≤ 0               (hard fail)
  − 15  if UTR format invalid
  − 10  if UTR missing
  − 20  if origin state missing
  − 12  if amount < scam-type minimum
  −  8  if amount > scam-type maximum
  − 10  if rapid report on very high amount
  ...
is_valid = score ≥ 50 AND stage1_ok AND scam_type in valid_set
# Benefit-of-doubt: retry ≥ 1 → accept score ≥ 40
```

### Priority Score (0–100)
```
P = delay_pts(30) + amount_pts(25) + scam_pts(20) + network_pts(15) + val_pts(10)
```

### Corridor Classifier
```
score(corridor) = typology_affinity(0.5) + terminal_state_match(0.4) + base(0.05)
# Target override (ground truth / hint): +1.20 boost
confidence = score / Σ(all corridor scores)
```

### ATM Touchpoint Ranker
```
Score(p_i) = 0.25·S_network + 0.20·S_historical + 0.20·S_distance + 0.35·S_modality
```

---

## 📊 Data Sources

| Data | Source | Nature |
|---|---|---|
| ATM / CSP locations | OpenStreetMap + RBI CSP Directory | Real geospatial anchors |
| Administrative boundaries | GADM India | Real |
| Cybercrime frequency priors | NCRB "Crime in India" reports | Real statistical weights |
| Individual complaints, accounts, phone numbers | 100% synthetically generated | **No real PII** |

> All victim names, account numbers, UTRs, and phone numbers are **synthetically generated**.  
> No operational NCRP, bank customer, or classified law enforcement data is included.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, FastAPI, Uvicorn, WebSockets |
| ML / Analytics | scikit-learn, NumPy, pandas, SciPy, NetworkX |
| Frontend | Vanilla JS, CSS3 (glassmorphism dark theme), Leaflet.js (GIS) |
| Templating | Jinja2 |
| PDF Generation | ReportLab |
| Data Validation | Pydantic v2 |
| Testing | pytest |

---

## 👥 Team

**Smart India Hackathon 2024 — PS ID 26184**  
Organization: Indian Cybercrime Coordination Centre (I4C), Ministry of Home Affairs

---

## ⚖️ Disclaimer

This is a **prototype / proof-of-concept** developed for the Smart India Hackathon. All alert dispatches, fund freeze actions, and law enforcement notifications are **simulated** and do not trigger real-world consequences. The system is intended to demonstrate the feasibility of the proposed decision-support pipeline.
