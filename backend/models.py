"""
Pydantic Data Models for Incident Ingestion, AI Decision Support,
Requisitions, Alerts, Audit Logging, and Complaint Workflow Tracking.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class IncidentIntakeRequest(BaseModel):
    complaint_id: Optional[str] = None
    scam_category: str = Field(..., description="Scam typology e.g. DIGITAL_ARREST, SEXTORTION")
    disputed_amount_inr: float = Field(..., gt=0, description="Amount lost in INR")
    origin_state: str = Field(default="Maharashtra")
    origin_district: str = Field(default="Mumbai Suburban")
    reporting_delay_minutes: int = Field(default=30, ge=0)
    transaction_mode: str = Field(default="UPI")
    primary_utr: Optional[str] = None
    target_corridor_hint: Optional[str] = None
    num_mule_hops: Optional[int] = Field(default=None, ge=1, le=10, description="Number of mule chain hops (1-10); None = auto")
    # Dynamic destination & victim-friendly fields
    destination_state: Optional[str] = Field(default=None, description="Optional target destination state")
    destination_district: Optional[str] = Field(default=None, description="Optional target destination district/city")
    preferred_touchpoint_modality: Optional[str] = Field(default="ALL", description="ALL | BANK_ATM | WHITE_LABEL_ATM | CSP_BANK_MITRA | MICRO_ATM_MERCHANT")
    suspect_bank_hint: Optional[str] = Field(default=None, description="Suspect bank / UPI app hint")
    victim_name: Optional[str] = Field(default="Complainant (Confidential)", description="Victim/citizen name")
    victim_phone: Optional[str] = Field(default=None, description="Victim phone number")

class HumanReviewAction(BaseModel):
    complaint_id: str
    reviewer_id: str = Field(default="OFFICER_KA_8841")
    reviewer_role: str = Field(default="AUTHORIZED_OFFICER")
    decision: str = Field(..., description="ACCEPT | REJECT | REQUEST_MORE_INFO | SELECT_ALTERNATIVE")
    selected_alternative_corridor: Optional[str] = None
    override_reason: Optional[str] = None
    timestamp: Optional[str] = None

class AlertNotificationRequest(BaseModel):
    incident_id: str
    priority_tier: str
    target_jurisdiction: str
    target_corridor: str
    channels: List[str] = Field(default=["DASHBOARD", "WEBHOOK", "SMS_SIMULATED", "EMAIL_SIMULATED"])
    alert_message: str

class AuditLogEntry(BaseModel):
    event_id: str
    timestamp: str
    complaint_id: str
    action_type: str
    actor: str
    payload_hash_sha256: str
    previous_hash: str
    details: Dict[str, Any]

# ── New Workflow Models ──────────────────────────────────────────────────────

class ReviewDecisionRequest(BaseModel):
    """
    Investigator human review decision.
    decision: APPROVE → triggers LEA/Bank/CFCFRMS alerts automatically.
    decision: REJECT  → triggers re-validation loop (up to MAX_RETRIES=3 cycles).
    """
    complaint_id: str
    reviewer_id: str = Field(default="OFFICER_KA_8841")
    reviewer_role: str = Field(default="AUTHORIZED_OFFICER")
    decision: str = Field(..., description="APPROVE | REJECT")
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Required when decision=REJECT. Stored in tamper-evident audit trail."
    )

class WorkflowStage(str, Enum):
    """Enumeration of complaint lifecycle stages."""
    VALIDATING           = "VALIDATING"
    VALIDATION_FAILED    = "VALIDATION_FAILED"
    PENDING_REVIEW       = "PENDING_REVIEW"
    UNDER_REVIEW         = "UNDER_REVIEW"
    APPROVED             = "APPROVED"
    ALERTS_DISPATCHED    = "ALERTS_DISPATCHED"
    REJECTED             = "REJECTED"
    RE_VALIDATING        = "RE_VALIDATING"
    REVISION_REQUESTED   = "REVISION_REQUESTED"
    PERMANENTLY_REJECTED = "PERMANENTLY_REJECTED"
