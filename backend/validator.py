"""
AI Complaint Validation Engine — I4C Cybercrime Decision Support System.

Two-stage validation pipeline:
  Stage 1: Transaction Verification
    → Verifies the reported transaction actually occurred / is plausible.
    → Checks: UTR format, amount bounds, reporting timing, origin state.

  Stage 2: Fraud Pattern Verification
    → Verifies the complaint matches a genuine cybercrime fraud pattern.
    → Checks: scam-type vs amount consistency, speed-vs-size anomalies.

Returns a ValidationResult dict with:
  - is_valid (bool)
  - validation_score (0–100)
  - stage1_transaction_verified (bool)
  - stage2_fraud_verified (bool)
  - flags (list of flag codes)
  - revision_hints (list of human-readable hints for re-submission)
  - retry_count (int — how many re-validation cycles have been run)
  - validation_summary (str — short human-readable summary)

Re-validation policy: runs up to MAX_RETRIES=3 times.
After the 1st retry, system applies benefit-of-the-doubt for borderline scores (≥40).
"""

import re
from typing import Dict, Any, List

MAX_RETRIES = 3

# Minimum plausible transaction amounts per scam type (INR)
SCAM_MIN_AMOUNTS: Dict[str, int] = {
    "DIGITAL_ARREST":             10_000,
    "INVESTMENT_STOCK_SCAM":      20_000,
    "SEXTORTION_VIDEO_BLACKMAIL":  5_000,
    "ELECTRICITY_KYC_APK_FRAUD":   1_000,
    "LOAN_APP_EXTORTION":          2_000,
    "UPI_QR_OLX_FRAUD":              500,
    "SIM_SWAP_FRAUD":              5_000,
}

# Maximum plausible amounts per scam type (INR) — above is suspicious / data-entry error
SCAM_MAX_AMOUNTS: Dict[str, int] = {
    "DIGITAL_ARREST":              5_000_000,   # ₹50 L
    "INVESTMENT_STOCK_SCAM":      50_000_000,   # ₹5 Cr
    "SEXTORTION_VIDEO_BLACKMAIL":  2_000_000,   # ₹20 L
    "ELECTRICITY_KYC_APK_FRAUD":     500_000,   # ₹5 L
    "LOAN_APP_EXTORTION":          1_000_000,   # ₹10 L
    "UPI_QR_OLX_FRAUD":            1_000_000,   # ₹10 L
    "SIM_SWAP_FRAUD":             10_000_000,   # ₹1 Cr
}

VALID_SCAM_TYPES = {
    "DIGITAL_ARREST", "INVESTMENT_STOCK_SCAM", "SEXTORTION_VIDEO_BLACKMAIL",
    "ELECTRICITY_KYC_APK_FRAUD", "LOAN_APP_EXTORTION", "UPI_QR_OLX_FRAUD",
    "SIM_SWAP_FRAUD",
}

# Standard Indian UTR / UPI reference — 10 to 22 digits
UTR_PATTERN = re.compile(r"^\d{10,22}$")


def validate_complaint(complaint: Dict[str, Any], retry_count: int = 0) -> Dict[str, Any]:
    """
    Run two-stage validation on a victim complaint dict.

    Args:
        complaint: Raw complaint data (same shape as IncidentIntakeRequest or simulate-incident body).
        retry_count: Number of prior re-validation cycles (0 = first time).

    Returns:
        Full ValidationResult dict.
    """
    flags: List[str] = []
    hints: List[str] = []
    score = 100  # Start full; deduct for each issue found

    # ── Extract fields ────────────────────────────────────────────────────────
    amount = float(complaint.get("disputed_amount_inr", 0) or 0)
    utr = (complaint.get("primary_utr", "") or "").strip()
    scam_type = (complaint.get("scam_category", "") or "").strip()
    delay_mins = int(complaint.get("reporting_delay_minutes", 30) or 30)

    # Support both flat origin fields and nested origin_jurisdiction
    origin_state = (
        complaint.get("origin_state", "")
        or (complaint.get("origin_jurisdiction") or {}).get("state", "")
        or ""
    ).strip()

    transaction_chain = complaint.get("transaction_chain", []) or []

    # ═══════════════════════════════════════════════════════════════════════════
    # STAGE 1 — Transaction Verification
    # ═══════════════════════════════════════════════════════════════════════════
    stage1_passed = True

    # 1a — Amount must be positive and within an absolute maximum (₹10 Cr)
    if amount <= 0:
        stage1_passed = False
        flags.append("INVALID_AMOUNT_ZERO")
        hints.append(
            "Amount lost must be greater than ₹0. "
            "Please enter the exact INR amount shown in your bank statement."
        )
        score -= 40

    elif amount < 100:
        stage1_passed = False
        flags.append("AMOUNT_BELOW_MINIMUM")
        hints.append(
            f"Amount ₹{int(amount)} is too low to be a cybercrime transaction. "
            "Minimum reportable amount is ₹100."
        )
        score -= 30

    elif amount > 100_000_000:          # > ₹10 Crore
        flags.append("AMOUNT_UNUSUALLY_HIGH")
        hints.append(
            "Amount exceeds ₹10 Crore. Please double-check the amount — "
            "a data-entry error may have occurred."
        )
        score -= 15

    # 1b — UTR / UPI reference format verification
    #      A valid UTR proves the transaction reference exists in the banking rail.
    if not utr:
        flags.append("MISSING_UTR")
        hints.append(
            "Transaction reference number (UTR / UPI Ref) is missing. "
            "Providing it greatly speeds up fund-freeze coordination."
        )
        score -= 10
    elif not UTR_PATTERN.match(utr):
        flags.append("INVALID_UTR_FORMAT")
        hints.append(
            f"Reference '{utr}' does not match the standard UTR/UPI format "
            "(10–22 digits). Please copy it exactly from your bank statement or payment app."
        )
        score -= 15

    # 1c — Reporting delay must be non-negative and not absurdly long
    if delay_mins < 0:
        stage1_passed = False
        flags.append("INVALID_REPORTING_TIME")
        hints.append("Reporting time cannot be negative. Please indicate when the fraud occurred.")
        score -= 20

    elif delay_mins > 43200:            # > 30 days
        flags.append("EXTREMELY_LATE_REPORTING")
        hints.append(
            "Fraud reported more than 30 days after occurrence. "
            "Early reporting is required for fund freeze eligibility under RBI guidelines."
        )
        score -= 5

    # 1d — Origin state is required for jurisdiction routing
    if not origin_state:
        stage1_passed = False
        flags.append("MISSING_ORIGIN_STATE")
        hints.append(
            "Your state of residence is required to route the complaint "
            "to the correct jurisdictional cyber cell."
        )
        score -= 20

    # 1e — Transaction chain consistency (if already generated by the generator)
    if transaction_chain and amount > 0:
        first_hop_amount = float(
            (transaction_chain[0].get("amount_inr") or transaction_chain[0].get("amount", 0))
        )
        if first_hop_amount > 0:
            deviation = abs(first_hop_amount - amount) / amount
            if deviation > 0.15:        # > 15% mismatch
                flags.append("CHAIN_AMOUNT_MISMATCH")
                score -= 8

    stage1_verified = stage1_passed and score >= 40

    # ═══════════════════════════════════════════════════════════════════════════
    # STAGE 2 — Fraud Pattern Verification
    # ═══════════════════════════════════════════════════════════════════════════
    stage2_passed = True

    # 2a — Scam type must be one of the registered typologies
    if scam_type not in VALID_SCAM_TYPES:
        stage2_passed = False
        flags.append("INVALID_SCAM_CATEGORY")
        hints.append(
            "Please select the type of fraud that matches your experience "
            "from the provided options (e.g., 'Fake Police/CBI Call', 'Stock Investment Scam', etc.)."
        )
        score -= 25

    elif amount > 0:
        # 2b — Amount vs scam-type plausibility
        min_amt = SCAM_MIN_AMOUNTS.get(scam_type, 500)
        max_amt = SCAM_MAX_AMOUNTS.get(scam_type, 50_000_000)

        if amount < min_amt:
            flags.append("AMOUNT_TOO_LOW_FOR_SCAM_TYPE")
            hints.append(
                f"₹{int(amount):,} is unusually low for "
                f"{scam_type.replace('_', ' ').title()} fraud "
                f"(typical minimum: ₹{min_amt:,}). "
                "Please verify the fraud type and the amount."
            )
            score -= 12

        elif amount > max_amt:
            flags.append("AMOUNT_EXCEEDS_SCAM_TYPE_RANGE")
            hints.append(
                f"₹{int(amount):,} is unusually high for "
                f"{scam_type.replace('_', ' ').title()} fraud "
                f"(typical maximum: ₹{max_amt:,}). "
                "If the amount is correct, please provide additional evidence."
            )
            score -= 8

    # 2c — Extremely rapid report on a very large amount → automated/test submission signal
    if amount > 10_000_000 and delay_mins < 5:
        flags.append("RAPID_REPORT_VERY_HIGH_AMOUNT")
        hints.append(
            "Extremely fast reporting on a very high amount may indicate "
            "a test or automated submission. Your complaint will be reviewed manually."
        )
        score -= 10

    stage2_verified = stage2_passed and not any(
        f in flags for f in [
            "AMOUNT_TOO_LOW_FOR_SCAM_TYPE",
            "INVALID_SCAM_CATEGORY",
            "RAPID_REPORT_VERY_HIGH_AMOUNT"
        ]
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # Final Decision
    # ═══════════════════════════════════════════════════════════════════════════
    score = max(0, min(100, score))

    # Base validity: score ≥ 50, Stage 1 passed, scam type known
    is_valid = (score >= 50) and stage1_verified and (scam_type in VALID_SCAM_TYPES)

    # Benefit of the doubt from retry 1 onward: accept borderline scores ≥ 40
    if not is_valid and retry_count >= 1 and score >= 40 and stage1_verified and (scam_type in VALID_SCAM_TYPES):
        is_valid = True
        flags.append("BENEFIT_OF_DOUBT_RETRY")

    return {
        "is_valid": is_valid,
        "validation_score": score,
        "stage1_transaction_verified": stage1_verified,
        "stage2_fraud_verified": stage2_verified,
        "flags": flags,
        "revision_hints": hints,
        "retry_count": retry_count,
        "can_retry": retry_count < MAX_RETRIES,
        "validation_summary": _build_summary(is_valid, stage1_verified, stage2_verified, flags),
    }


def _build_summary(is_valid: bool, stage1: bool, stage2: bool, flags: List[str]) -> str:
    if is_valid:
        return (
            "✅ Complaint validated — transaction reference verified "
            "and fraud pattern confirmed. Forwarded to Investigator Queue."
        )
    elif not stage1:
        return (
            "⚠️ Transaction could not be verified. "
            "Please check the amount, UTR / UPI reference, and your state of residence."
        )
    elif not stage2:
        return (
            "⚠️ Fraud pattern inconsistency detected. "
            "Please verify the selected fraud type matches your experience and re-check the amount."
        )
    else:
        issue_count = len(flags)
        return (
            f"⚠️ {issue_count} issue(s) flagged during validation. "
            "Review the hints above and re-submit."
        )
