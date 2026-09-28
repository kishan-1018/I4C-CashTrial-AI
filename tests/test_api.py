import pytest
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

def test_root_serves_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "CYBERCRIME PREDICTIVE" in response.text
    assert "Run Live Scam Case Simulation" in response.text

def test_api_touchpoints():
    response = client.get("/api/touchpoints")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    assert len(data["touchpoints"]) > 0

def test_api_recent_incidents():
    response = client.get("/api/recent-incidents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0

def test_api_heatmap_layers():
    response = client.get("/api/heatmap")
    assert response.status_code == 200
    data = response.json()
    assert "historical_layer" in data
    assert "realtime_layer" in data
    assert "predicted_corridors" in data

def test_api_simulate_and_predict():
    payload = {
        "scam_category": "DIGITAL_ARREST",
        "disputed_amount_inr": 350000.0,
        "origin_state": "Karnataka",
        "origin_district": "Bengaluru Urban",
        "reporting_delay_minutes": 25
    }
    response = client.post("/api/simulate-incident", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "INGESTED_SUCCESSFULLY"
    assert "incident" in data
    assert "decision_support" in data

def test_api_prepare_requisitions():
    inc_res = client.get("/api/recent-incidents").json()
    cid = inc_res["incidents"][0]["complaint_id"]
    
    response = client.post("/api/prepare-requisition", json={"complaint_id": cid, "officer_id": "OFFICER_TEST"})
    assert response.status_code == 200
    data = response.json()
    assert "cfcfrms_freeze_package" in data
    assert "section_94_bnss_notice" in data
    assert "samanvay_transfer_slip" in data

def test_api_dossier_pdf_download():
    inc_res = client.get("/api/recent-incidents").json()
    cid = inc_res["incidents"][0]["complaint_id"]
    
    response = client.get(f"/api/dossier/{cid}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 1000

def test_api_audit_trail():
    inc_res = client.get("/api/recent-incidents").json()
    cid = inc_res["incidents"][0]["complaint_id"]
    
    response = client.get(f"/api/audit/{cid}")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data

def test_api_geo_states_and_districts():
    response = client.get("/api/geo/states-and-districts")
    assert response.status_code == 200
    data = response.json()
    assert "states" in data
    assert "default_districts" in data
    assert len(data["states"]) >= 36
    assert "Kerala" in data["states"]
    assert "Bihar" in data["states"]
    assert "Maharashtra" in data["states"]

def test_dynamic_pan_india_simulation_with_custom_destination():
    payload = {
        "scam_category": "INVESTMENT_STOCK_SCAM",
        "disputed_amount_inr": 450000.0,
        "origin_state": "Kerala",
        "origin_district": "Ernakulam",
        "destination_state": "Bihar",
        "destination_district": "Patna",
        "preferred_touchpoint_modality": "CSP_BANK_MITRA",
        "suspect_bank_hint": "PUNJAB NATIONAL BANK",
        "reporting_delay_minutes": 20,
        "primary_utr": "428987654321",
        "num_mule_hops": 3
    }
    response = client.post("/api/simulate-incident", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "INGESTED_SUCCESSFULLY"
    
    incident = data["incident"]
    assert incident["origin_jurisdiction"]["state"] == "Kerala"
    assert incident["origin_jurisdiction"]["district"] == "Ernakulam"
    assert "bihar" in incident["ground_truth"]["corridor_id"]
    assert incident["ground_truth"]["destination_jurisdiction"]["state"] == "Bihar"
    
    ds = data["decision_support"]
    assert "trajectory" in ds
    traj = ds["trajectory"]
    assert traj["origin"]["state"] == "Kerala"
    assert traj["origin"]["district"] == "Ernakulam"
    assert len(traj["origin"]["coordinates"]) == 2
    
    assert traj["destination_hotspot"]["state"] == "Bihar"
    assert len(traj["transit_hops"]) > 0
    assert len(traj["candidate_touchpoints"]) > 0
    
    # Touchpoints must be synthesized in Bihar
    for tp in traj["candidate_touchpoints"]:
        assert tp["state"] == "Bihar"
        assert len(tp["coordinates"]) == 2

def test_root_serves_victim_page_by_default():
    response = client.get("/")
    assert response.status_code == 200
    # Victim view must be active
    assert 'id="view-victim" class="role-view active-view"' in response.text
    # Investigator view must be hidden by default
    assert 'id="view-investigator" class="main-layout role-view" style="display: none;"' in response.text
    # Auth login trigger button must be present
    assert 'id="btn-auth-login-trigger"' in response.text
    assert 'id="modal-auth-backdrop"' in response.text

def test_auth_login_investigator_success():
    payload = {
        "username": "investigator",
        "password": "investigator123",
        "requested_role": "INVESTIGATOR"
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "token" in data
    assert data["user"]["role"] == "INVESTIGATOR"
    assert data["user"]["username"] == "investigator"
    assert "Rajesh Sharma" in data["user"]["display_name"]

def test_auth_login_admin_success():
    payload = {
        "username": "admin",
        "password": "admin123",
        "requested_role": "ADMIN"
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "token" in data
    assert data["user"]["role"] == "ADMIN"
    assert data["user"]["username"] == "admin"

def test_auth_login_invalid_password():
    payload = {
        "username": "investigator",
        "password": "wrong_password_123"
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]

def test_auth_login_invalid_user():
    payload = {
        "username": "unknown_hacker",
        "password": "anypassword"
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]

def test_auth_profile_and_logout():
    # Login as investigator
    login_res = client.post("/api/auth/login", json={
        "username": "investigator",
        "password": "investigator123"
    }).json()
    token = login_res["token"]

    # Verify /api/auth/me with Bearer token
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["authenticated"] is True
    assert me_data["user"]["role"] == "INVESTIGATOR"

    # Logout
    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200
    assert logout_res.json()["success"] is True

    # Subsequent check shows unauthenticated
    after_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert after_res.status_code == 200
    assert after_res.json()["authenticated"] is False
    assert after_res.json()["role"] == "VICTIM"

def test_api_admin_corridors():
    response = client.get("/api/admin/corridors")
    assert response.status_code == 200
    data = response.json()
    assert "corridors" in data
    assert data["total"] == len(data["corridors"])
    assert data["total"] > 0
    # Verify corridor structure
    first = data["corridors"][0]
    assert "corridor_id" in first
    assert "name" in first
    assert "risk_level" in first

def test_api_audit_ledger():
    response = client.get("/api/audit-ledger")
    assert response.status_code == 200
    data = response.json()
    assert data["chain_integrity"] == "CRYPTOGRAPHICALLY_VERIFIED"
    assert data["total_records"] > 0
    assert len(data["events"]) > 0
    assert "payload_hash_sha256" in data["events"][0]
