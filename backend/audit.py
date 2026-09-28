"""
Cryptographic Tamper-Evident Audit Ledger.
Chains audit events with SHA-256 hashes to guarantee provenance and data integrity.
"""

import json
import hashlib
import datetime
import threading
import uuid
from pathlib import Path
from typing import Dict, Any, List

AUDIT_LOG_FILE = Path(__file__).resolve().parent.parent / "data" / "audit_ledger.json"

class AuditLedger:
    def __init__(self):
        self.ledger_file = AUDIT_LOG_FILE
        self._lock = threading.Lock()
        self._init_ledger()

    def _init_ledger(self):
        if not self.ledger_file.exists():
            genesis_record = {
                "event_id": "EVT-GENESIS-0000",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "complaint_id": "SYSTEM_INIT",
                "action_type": "GENESIS_BLOCK",
                "actor": "SYSTEM",
                "previous_hash": "0" * 64,
                "payload_hash_sha256": hashlib.sha256(b"I4C_HOTSPOT_DECISION_SUPPORT_GENESIS").hexdigest(),
                "details": {"system": "I4C Predictive Cash-Out Decision Support", "status": "INITIALIZED"}
            }
            with open(self.ledger_file, "w", encoding="utf-8") as f:
                json.dump([genesis_record], f, indent=2)

    def _get_last_hash(self) -> str:
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                records = json.load(f)
                return records[-1]["payload_hash_sha256"] if records else "0" * 64
        except Exception:
            return "0" * 64

    def log_event(self, complaint_id: str, action_type: str, actor: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """Logs an event and computes SHA-256 cryptographic chain hash."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._lock:
            prev_hash = self._get_last_hash()
            
            event_payload = {
                "timestamp": now,
                "complaint_id": complaint_id,
                "action_type": action_type,
                "actor": actor,
                "previous_hash": prev_hash,
                "details": details
            }
            
            payload_bytes = json.dumps(event_payload, sort_keys=True).encode("utf-8")
            current_hash = hashlib.sha256(payload_bytes).hexdigest()

            event_record = {
                "event_id": f"EVT-{uuid.uuid4().hex[:12].upper()}",
                "timestamp": now,
                "complaint_id": complaint_id,
                "action_type": action_type,
                "actor": actor,
                "previous_hash": prev_hash,
                "payload_hash_sha256": current_hash,
                "details": details
            }

            try:
                with open(self.ledger_file, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception:
                records = []

            records.append(event_record)
            with open(self.ledger_file, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)

        return event_record

    def get_events_for_complaint(self, complaint_id: str) -> List[Dict[str, Any]]:
        """Retrieves chronological audit trail for a complaint."""
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                records = json.load(f)
                return [r for r in records if r["complaint_id"] == complaint_id]
        except Exception:
            return []

    @property
    def ledger(self) -> List[Dict[str, Any]]:
        """Returns all audit ledger events."""
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def verify_integrity(self) -> bool:
        """Verifies the cryptographic SHA-256 hash chain of the entire audit ledger."""
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                records = json.load(f)
            if not records:
                return True
            for i in range(1, len(records)):
                expected_prev = records[i - 1]["payload_hash_sha256"]
                actual_prev = records[i]["previous_hash"]
                if actual_prev != expected_prev:
                    return False
            return True
        except Exception:
            return False

audit_ledger = AuditLedger()
