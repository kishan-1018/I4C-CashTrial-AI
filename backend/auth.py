"""
Authentication & Role-Based Access Control (RBAC) Module for I4C System.
Roles:
- VICTIM: Public citizen access (unauthenticated / default).
- INVESTIGATOR / AUTHORIZED_OFFICER: Law enforcement officers handling live tactical feeds, requisitions, and freeze packages.
- ADMIN: System administrators managing ML model performance, audit trails, and security settings.
"""

import secrets
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import HTTPException, Header, Depends, status

# Credential Store for Law Enforcement & System Admin
USERS_DB: Dict[str, Dict[str, Any]] = {
    "investigator": {
        "username": "investigator",
        "password": "investigator123",
        "role": "INVESTIGATOR",
        "aliases": ["AUTHORIZED_OFFICER"],
        "display_name": "Inspector Rajesh Sharma",
        "badge_id": "I4C-INV-26184",
        "jurisdiction": "National Cyber Crime Threat Analytics Unit (I4C)"
    },
    "officer": {
        "username": "officer",
        "password": "investigator123",
        "role": "INVESTIGATOR",
        "aliases": ["AUTHORIZED_OFFICER"],
        "display_name": "ACP Priya Deshmukh",
        "badge_id": "I4C-LE-4422",
        "jurisdiction": "Maharashtra Cyber Crime Cell"
    },
    "admin": {
        "username": "admin",
        "password": "admin123",
        "role": "ADMIN",
        "aliases": [],
        "display_name": "System Administrator",
        "badge_id": "I4C-ADM-001",
        "jurisdiction": "MHA Cyber & Information Security Division"
    },
    "sysadmin": {
        "username": "sysadmin",
        "password": "admin123",
        "role": "ADMIN",
        "aliases": [],
        "display_name": "Senior Ops Engineer",
        "badge_id": "I4C-ADM-002",
        "jurisdiction": "Central Operations Command"
    }
}

# In-memory session store: token -> user dict
ACTIVE_TOKENS: Dict[str, Dict[str, Any]] = {}

ROLES = ["VICTIM", "VIEWER", "ANALYST", "INVESTIGATOR", "AUTHORIZED_OFFICER", "ADMIN"]

class LoginRequest(BaseModel):
    username: str
    password: str
    requested_role: Optional[str] = None

def authenticate_user(username: str, password: str, requested_role: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Authenticates credentials against the user database."""
    user = USERS_DB.get(username.strip().lower())
    if not user:
        return None
    if user["password"] != password.strip():
        return None
    if requested_role:
        req = requested_role.strip().upper()
        allowed = [user["role"]] + user.get("aliases", [])
        if req != "VICTIM" and req not in allowed:
            return None
    return user

def create_session_token(user: Dict[str, Any]) -> str:
    """Generates and registers a new secure session token."""
    token = f"i4c_sec_{secrets.token_hex(16)}"
    ACTIVE_TOKENS[token] = user
    return token

def get_current_user_role(
    authorization: Optional[str] = Header(default=None),
    x_role: Optional[str] = Header(default="AUTHORIZED_OFFICER"),
    x_auth_token: Optional[str] = Header(default=None)
) -> str:
    """
    Extracts role from bearer token, x-auth-token, or legacy x-role header.
    Normalizes INVESTIGATOR to AUTHORIZED_OFFICER for downstream RBAC handlers.
    """
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
    elif x_auth_token:
        token = x_auth_token.strip()

    if token and token in ACTIVE_TOKENS:
        role = ACTIVE_TOKENS[token]["role"]
        return "AUTHORIZED_OFFICER" if role == "INVESTIGATOR" else role

    role = x_role.upper() if x_role else "AUTHORIZED_OFFICER"
    if role in ["INVESTIGATOR", "AUTHORIZED_OFFICER"]:
        return "AUTHORIZED_OFFICER"
    if role not in ROLES:
        raise HTTPException(status_code=403, detail=f"Invalid or unauthorized role: {role}")
    return role

def require_role(allowed_roles: List[str]):
    """Enforces role-based authorization check."""
    def role_checker(current_role: str = Depends(get_current_user_role)):
        normalized_current = "AUTHORIZED_OFFICER" if current_role == "INVESTIGATOR" else current_role
        normalized_allowed = ["AUTHORIZED_OFFICER" if r == "INVESTIGATOR" else r for r in allowed_roles]
        if normalized_current not in normalized_allowed and current_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail=f"Access forbidden for role {current_role}. Required one of: {allowed_roles}"
            )
        return current_role
    return role_checker
