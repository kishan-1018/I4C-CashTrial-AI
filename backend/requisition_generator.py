"""
Requisition Package Generator.
Generates:
1. CFCFRMS / Sahyog-Compatible Account Freeze Requisition Package
2. Section 94 BNSS (erstwhile 91 CrPC) Statutory Notice for CCTV Footage & Transaction Log Preservation
3. I4C Samanvay Inter-State Tactical Coordination Notice
"""

import datetime
from typing import Dict, Any

class RequisitionGenerator:
    """Produces structured statutory notices and inter-state coordination packages."""

    @staticmethod
    def generate_cfcfrms_freeze_package(complaint: Dict[str, Any], decision_support: Dict[str, Any], officer_id: str) -> Dict[str, Any]:
        """Generates a CFCFRMS/Sahyog-compatible emergency fund-blocking requisition."""
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).isoformat()
        chain = complaint.get("transaction_chain", [])
        disputed_amt = complaint.get("disputed_amount_inr", 0)

        accounts_to_freeze = []
        for hop in chain:
            accounts_to_freeze.append({
                "hop_number": hop.get("hop_number"),
                "account_number": hop.get("receiver_account"),
                "vpa": hop.get("receiver_vpa"),
                "bank_name": hop.get("bank_name"),
                "ifsc": hop.get("ifsc"),
                "utr": hop.get("utr_number"),
                "amount": hop.get("amount_inr"),
                "status": "IMMEDIATE_DEBIT_FREEZE_REQUESTED"
            })

        return {
            "document_type": "CFCFRMS_EMERGENCY_FUND_FREEZE_REQUISITION",
            "requisition_id": f"REQ-CFCFRMS-{complaint.get('complaint_id', '0000')}",
            "generated_timestamp": now,
            "origin_investigating_unit": complaint.get("origin_jurisdiction", {}).get("police_station", "State Cyber Police"),
            "authorizing_officer_badge": officer_id,
            "statutory_basis": "Section 106 Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023 / Section 66D IT Act, 2000",
            "incident_reference": {
                "ncrp_acknowledgment_no": complaint.get("complaint_id"),
                "incident_timestamp": complaint.get("incident_timestamp"),
                "reporting_delay_minutes": complaint.get("reporting_delay_minutes"),
                "total_disputed_amount_inr": disputed_amt
            },
            "targeted_beneficiary_accounts": accounts_to_freeze,
            "disclaimer": "Demonstration draft structured to be compatible in intent with CFCFRMS/Sahyog workflows. Non-certified prototype."
        }

    @staticmethod
    def generate_sec94_bnss_cctv_notice(complaint: Dict[str, Any], top_touchpoint: Dict[str, Any], officer_id: str) -> Dict[str, Any]:
        """Generates Section 94 BNSS Notice for immediate CCTV preservation to bank branch / CSP operator."""
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).isoformat()
        tp_name = top_touchpoint.get("institution_name", "Target ATM/CSP")
        location = top_touchpoint.get("location_name", "Corridor Market")

        return {
            "document_type": "SECTION_94_BNSS_EVIDENCE_PRESERVATION_NOTICE",
            "notice_id": f"NOTICE-BNSS94-{complaint.get('complaint_id', '0000')}",
            "statutory_heading": "NOTICE UNDER SECTION 94 OF BHARATIYA NAGARIK SURAKSHA SANHITA, 2023 (ERSTWHILE SEC 91 CrPC)",
            "issued_by": top_touchpoint.get("police_jurisdiction", "Jurisdictional Cyber Police"),
            "served_to": f"The Branch Manager / Operator, {tp_name}, {location}",
            "issued_timestamp": now,
            "demanded_preservation_items": [
                "Continuous High-Definition CCTV Video Recordings from all internal and external cameras for the 3-hour window covering the incident",
                "Electronic Journal (EJ) logs and ATM/POS terminal transaction audit dumps",
                "Transaction slips, cash cassette dispensing audit records, and biometrics log (if CSP/AePS transaction)"
            ],
            "urgency_classification": "CRITICAL — MANDATORY PRESERVATION WITHIN 24 HOURS TO PREVENT OVERWRITE",
            "penal_warning": "Non-compliance or intentional destruction of digital evidence is punishable under Section 238 of Bharatiya Nyaya Sanhita (BNS), 2023."
        }

    @staticmethod
    def generate_samanvay_transfer_slip(complaint: Dict[str, Any], decision_support: Dict[str, Any]) -> Dict[str, Any]:
        """Generates I4C Samanvay Inter-State Police Coordination Packet."""
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).isoformat()
        origin = complaint.get("origin_jurisdiction", {})
        destination = decision_support.get("taxonomy", {}).get("predicted", {}).get("primary_corridor", {})

        return {
            "document_type": "I4C_SAMANVAY_INTER_STATE_TACTICAL_PACKET",
            "transmission_id": f"SAMANVAY-XFER-{complaint.get('complaint_id')}",
            "transmission_timestamp": now,
            "originating_state": origin.get("state"),
            "destination_state": destination.get("state"),
            "target_corridor": destination.get("name"),
            "priority_tier": decision_support.get("priority_assessment", {}).get("priority_tier"),
            "action_requested": "Tactical Field Verification / Beat Patrol Interception at candidate cash-out node",
            "assigned_destination_unit": decision_support.get("response_opportunity", {}).get("destination_field_unit")
        }
